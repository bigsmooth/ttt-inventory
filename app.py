import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import altair as alt

DB_FILE = "barcodes.db"
st.set_page_config(page_title="TTT Inventory System", page_icon="🧦", layout="wide")
st.image("https://i.imgur.com/Y7SgqZR.jpeg", width=150)

# --- DATABASE HELPERS ---
def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def login(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, role, hub_id FROM users WHERE username=? AND password=? AND active=1", (username, password))
    result = cursor.fetchone()
    conn.close()
    return result

def fetch_hub_name(hub_id):
    if hub_id is None:
        return "HQ Admin"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM hubs WHERE id = ?", (hub_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "Unknown"

def fetch_all_hubs():
    conn = get_connection()
    hubs = pd.read_sql_query("SELECT id, name FROM hubs", conn)
    conn.close()
    return hubs

def log_inventory(user_id, sku, action, quantity, hub_id, comment):
    conn = get_connection()
    cursor = conn.cursor()
    timestamp = datetime.now()
    cursor.execute("""
        INSERT INTO inventory_log (timestamp, sku, action, quantity, hub, user_id, comment)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (timestamp, sku, action, quantity, hub_id, user_id, comment))
    conn.commit()
    conn.close()

def fetch_skus_for_hub(hub_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.name, p.sku, p.barcode
        FROM hub_skus hs
        JOIN products p ON hs.sku = p.sku
        WHERE hs.hub_id = ?
        ORDER BY p.name
    """, (hub_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def fetch_inventory_for_hub(hub_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.name, p.sku, p.barcode,
        COALESCE(SUM(CASE WHEN il.action = 'IN' THEN il.quantity ELSE 0 END), 0) -
        COALESCE(SUM(CASE WHEN il.action = 'OUT' THEN il.quantity ELSE 0 END), 0) AS net_quantity
        FROM hub_skus hs
        JOIN products p ON hs.sku = p.sku
        LEFT JOIN inventory_log il ON hs.sku = il.sku AND il.hub = ?
        WHERE hs.hub_id = ?
        GROUP BY p.name, p.sku, p.barcode
        ORDER BY p.name
    """, (hub_id, hub_id))
    results = cursor.fetchall()
    conn.close()
    return results

def fetch_inventory_history(hub_id):
    conn = get_connection()
    query = """
        SELECT sku, date(timestamp) as date, SUM(CASE WHEN action = 'OUT' THEN quantity ELSE 0 END) as total_out
        FROM inventory_log
        WHERE hub = ?
        GROUP BY sku, date
        ORDER BY date
    """
    df = pd.read_sql_query(query, conn, params=(hub_id,))
    conn.close()
    return df

def fetch_full_inventory_log(hub_id):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT timestamp, sku, action, quantity, user_id, comment
        FROM inventory_log
        WHERE hub = ?
        ORDER BY timestamp DESC
    """, conn, params=(hub_id,))
    conn.close()
    return df

def insert_supply_request(hub_id, username, notes):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO supply_requests (hub_id, username, notes, timestamp)
        VALUES (?, ?, ?, ?)
    """, (hub_id, username, notes, datetime.now()))
    conn.commit()
    conn.close()

def fetch_today_orders(hub_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(quantity)
        FROM inventory_log
        WHERE hub = ? AND action = 'OUT' AND date(timestamp) = date('now')
    """, (hub_id,))
    result = cursor.fetchone()[0]
    conn.close()
    return result or 0

def fetch_all_inventory():
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT h.name AS Hub, p.name AS Product, p.sku, p.barcode,
        COALESCE(SUM(CASE WHEN il.action = 'IN' THEN il.quantity ELSE 0 END), 0) -
        COALESCE(SUM(CASE WHEN il.action = 'OUT' THEN il.quantity ELSE 0 END), 0) AS Inventory
        FROM inventory_log il
        JOIN products p ON il.sku = p.sku
        JOIN hubs h ON il.hub = h.id
        GROUP BY h.name, p.name, p.sku, p.barcode
        ORDER BY h.name, p.name
    """, conn)
    conn.close()
    return df

def fetch_all_supply_requests():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM supply_requests ORDER BY timestamp DESC", conn)
    conn.close()
    return df

def assign_sku_to_hub(sku, hub_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO hub_skus (sku, hub_id) VALUES (?, ?)", (sku, hub_id))
    conn.commit()
    conn.close()

def remove_sku_from_hub(sku, hub_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM hub_skus WHERE sku = ? AND hub_id = ?", (sku, hub_id))
    conn.commit()
    conn.close()

def insert_shipment(supplier, tracking, hub_id, product, amount, carrier):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO shipments (date, supplier, tracking, hub_id, product, amount, carrier)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now(), supplier, tracking, hub_id, product, amount, carrier))
    conn.commit()
    conn.close()

def fetch_shipments_for_hub(hub_id):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT * FROM shipments
        WHERE hub_id = ?
        ORDER BY date DESC
    """, conn, params=(hub_id,))
    conn.close()
    return df

def fetch_all_shipments():
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT * FROM shipments
        ORDER BY date DESC
    """, conn)
    conn.close()
    return df

def reply_to_supply_request(request_id, reply_text, admin_username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE supply_requests SET response = ?, admin = ? WHERE id = ?
    """, (reply_text, admin_username, request_id))
    conn.commit()
    conn.close()

def fetch_my_supply_requests(hub_id):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT * FROM supply_requests
        WHERE hub_id = ?
        ORDER BY timestamp DESC
    """, conn, params=(hub_id,))
    conn.close()
    return df

# --- NOTIFICATIONS HELPERS ---
def insert_notification(user_role, user_id, message):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO notifications (created, user_role, user_id, message) VALUES (?, ?, ?, ?)",
        (datetime.now(), user_role, user_id, message),
    )
    conn.commit()
    conn.close()

def fetch_admin_id():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE role='admin' AND active=1 LIMIT 1")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def fetch_hub_manager_id(hub_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM users WHERE hub_id=? AND role IN ('manager', 'user') AND active=1 LIMIT 1",
        (hub_id,),
    )
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def fetch_notifications_for_user(user_role, user_id):
    if user_id is None:
        return pd.DataFrame(columns=["created", "message"])
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT created, message FROM notifications WHERE user_role = ? AND user_id = ? ORDER BY created DESC",
        conn,
        params=(user_role, user_id),
    )
    conn.close()
    return df

### USER MANAGEMENT ###
def fetch_all_users():
    conn = get_connection()
    users = pd.read_sql_query(
        "SELECT id, username, email, role, hub_id, active FROM users ORDER BY id", conn
    )
    conn.close()
    return users

def add_user(username, password, email, role, hub_id, active=1):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (username, password, email, role, hub_id, active)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (username, password, email, role, hub_id, active))
    conn.commit()
    conn.close()

def update_user(user_id, username, email, role, hub_id, active):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users SET username=?, email=?, role=?, hub_id=?, active=?
        WHERE id=?
    """, (username, email, role, hub_id, active, user_id))
    conn.commit()
    conn.close()

def deactivate_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET active=0 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

def activate_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET active=1 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

# --- TABS ---
def render_user_management_panel():
    st.subheader("👤 User Management")
    users = fetch_all_users()
    hubs = fetch_all_hubs()
    hub_choices = dict(zip(hubs['name'], hubs['id']))

    st.markdown("#### Add New User")
    with st.form("add_user_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            username = st.text_input("Username")
            password = st.text_input("Password")
        with col2:
            email = st.text_input("Email")
            role = st.selectbox("Role", ["user", "manager", "admin", "supplier"])
        with col3:
            hub_name = st.selectbox("Assign to Hub", ["None"] + list(hub_choices.keys()))
            active = st.checkbox("Active", value=True)
        submitted = st.form_submit_button("Add User")
        if submitted:
            hub_id = hub_choices.get(hub_name) if hub_name != "None" else None
            add_user(username, password, email, role, hub_id, int(active))
            st.success("User added!")
            st.rerun()

    st.markdown("#### All Users")
    for idx, row in users.iterrows():
        with st.expander(f"{row['username']} (Role: {row['role']}, Active: {row['active']})"):
            col1, col2 = st.columns([3,1])
            with col1:
                new_username = st.text_input(f"Username_{row['id']}", value=row['username'], key=f"username_{row['id']}")
                new_email = st.text_input(f"Email_{row['id']}", value=row['email'] or "", key=f"email_{row['id']}")
                new_role = st.selectbox(f"Role_{row['id']}", ["user", "manager", "admin", "supplier"], index=["user", "manager", "admin", "supplier"].index(row['role']), key=f"role_{row['id']}")
                new_hub = st.selectbox(f"Hub_{row['id']}", ["None"] + list(hub_choices.keys()), index=(list(hub_choices.values()).index(row['hub_id'])+1 if row['hub_id'] in hub_choices.values() else 0), key=f"hub_{row['id']}")
                new_active = st.checkbox(f"Active_{row['id']}", value=bool(row['active']), key=f"active_{row['id']}")
            with col2:
                if st.button("Update", key=f"update_{row['id']}"):
                    hub_id = hub_choices.get(new_hub) if new_hub != "None" else None
                    update_user(row['id'], new_username, new_email, new_role, hub_id, int(new_active))
                    st.success("User updated.")
                    st.rerun()
                if row['active']:
                    if st.button("Deactivate", key=f"deactivate_{row['id']}"):
                        deactivate_user(row['id'])
                        st.warning("User deactivated.")
                        st.rerun()
                else:
                    if st.button("Activate", key=f"activate_{row['id']}"):
                        activate_user(row['id'])
                        st.success("User activated.")
                        st.rerun()

def render_hub_dashboard(hub_id, username):
    tabs = st.tabs([
        "Inventory", "Inventory Out Trends", "Supply Notes", "Shipments", "Add Inventory Transaction", "Notifications"
    ])
    with tabs[0]:
        inventory_df = pd.DataFrame(fetch_inventory_for_hub(hub_id), columns=["Product", "SKU", "Barcode", "Inventory"])
        st.subheader("📦 My Inventory")
        st.dataframe(inventory_df)
        low_stock = inventory_df[inventory_df["Inventory"] < 10]
        if not low_stock.empty:
            st.warning("⚠️ The following items are below 10 in stock. Contact HQ for restock:")
            st.dataframe(low_stock)
        today_orders = fetch_today_orders(hub_id)
        st.success(f"✅ Orders Processed Today: {today_orders}")
    with tabs[1]:
        st.subheader("📈 Inventory OUT Trends")
        history_df = fetch_inventory_history(hub_id)
        if not history_df.empty:
            chart = alt.Chart(history_df).mark_line().encode(
                x='date:T',
                y='total_out:Q',
                color='sku:N'
            ).properties(title="Inventory OUT Trends")
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No OUT transactions yet.")
    with tabs[2]:
        st.subheader("📝 Supply Notes / Messages to HQ")
        # Submit new note
        with st.form("supply_request_form"):
            note = st.text_area("Message or Supply Request to HQ")
            submit_note = st.form_submit_button("Send to HQ")
            if submit_note and note.strip():
                insert_supply_request(hub_id, username, note.strip())
                st.success("Sent to HQ.")
                st.rerun()
        # Show requests and any admin replies
        reqs = fetch_my_supply_requests(hub_id)
        if not reqs.empty:
            st.dataframe(reqs[["timestamp", "notes", "response", "admin"]])
    with tabs[3]:
        st.subheader("🚚 Shipments to My Hub")
        ship_df = fetch_shipments_for_hub(hub_id)
        if not ship_df.empty:
            st.dataframe(ship_df)
        else:
            st.info("No shipments yet.")
    with tabs[4]:
        st.subheader("➕ Add Inventory Transaction")
        sku_data = fetch_skus_for_hub(hub_id)
        sku_options = {f"{name} ({sku})": sku for name, sku, _ in sku_data}
        selected_label = st.selectbox("Select SKU", list(sku_options.keys()))
        selected_sku = sku_options[selected_label]
        action = st.radio("Action", ["IN", "OUT"], horizontal=True)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        comment = st.text_input("Optional Comment")
        if st.button("Submit Inventory Update"):
            log_inventory(st.session_state.user["id"], selected_sku, action, quantity, hub_id, comment)
            st.success(f"{action} of {quantity} for {selected_label} recorded.")
            st.rerun()
    # --- NOTIFICATIONS TAB FOR HUB USERS ---
    with tabs[5]:
        st.subheader("🔔 Notifications")
        notif_df = fetch_notifications_for_user('hub', st.session_state.user["id"])
        if not notif_df.empty:
            st.dataframe(notif_df)
        else:
            st.info("No notifications yet.")

def render_admin_dashboard(username):
    admin_tabs = st.tabs([
        "All Inventory", "All Orders/OUT+IN", "All Supply Notes/Requests", "All Shipments", "Assign/Remove SKUs", "User Management", "Notifications"
    ])
    # Tab 1: All Inventory
    with admin_tabs[0]:
        st.subheader("📊 All Inventory Across Hubs")
        inv = fetch_all_inventory()
        st.dataframe(inv)
        if st.button("Export All Inventory as CSV"):
            st.download_button("Download CSV", inv.to_csv(index=False), file_name="all_inventory.csv", mime="text/csv")
    # Tab 2: All Logs
    with admin_tabs[1]:
        st.subheader("🧾 All Orders/IN+OUT Logs")
        conn = get_connection()
        logs_df = pd.read_sql_query("SELECT * FROM inventory_log ORDER BY timestamp DESC", conn)
        st.dataframe(logs_df)
        conn.close()
    # Tab 3: All Supply Notes
    with admin_tabs[2]:
        st.subheader("📬 All Hub Messages/Supply Requests")
        reqs = fetch_all_supply_requests()
        if not reqs.empty:
            st.dataframe(reqs[["id", "hub_id", "username", "notes", "timestamp", "response", "admin"]])
            for idx, row in reqs.iterrows():
                if not row.get('response'):
                    with st.form(f"reply_form_{row['id']}"):
                        reply_text = st.text_area("Reply", key=f"reply_{row['id']}")
                        if st.form_submit_button("Send Reply"):
                            reply_to_supply_request(row['id'], reply_text, username)
                            st.success("Reply sent.")
                            st.rerun()
        else:
            st.info("No supply notes/requests found.")
    # Tab 4: Shipments
    with admin_tabs[3]:
        st.subheader("🚚 All Shipments")
        ships = fetch_all_shipments()
        st.dataframe(ships)
    # Tab 5: SKU Assignment
    with admin_tabs[4]:
        st.subheader("🧩 Assign or Remove SKUs to/from Hubs")
        all_hubs = pd.read_sql_query("SELECT id, name FROM hubs", get_connection())
        all_products = pd.read_sql_query("SELECT sku, name FROM products ORDER BY name", get_connection())
        hub_map = dict(zip(all_hubs['name'], all_hubs['id']))
        product_map = dict(zip(all_products['name'], all_products['sku']))
        selected_hub = st.selectbox("Select Hub", list(hub_map.keys()))
        selected_product = st.selectbox("Select Product", list(product_map.keys()))
        selected_sku = product_map[selected_product]
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Assign SKU"):
                assign_sku_to_hub(selected_sku, hub_map[selected_hub])
                st.success(f"{selected_product} assigned to {selected_hub}")
        with col2:
            if st.button("❌ Remove SKU"):
                remove_sku_from_hub(selected_sku, hub_map[selected_hub])
                st.warning(f"{selected_product} removed from {selected_hub}")
        if selected_hub:
            st.markdown(f"### Current SKUs at {selected_hub}")
            hub_id = hub_map[selected_hub]
            current = fetch_skus_for_hub(hub_id)
            st.dataframe(pd.DataFrame(current, columns=["Product", "SKU", "Barcode"]))
    # Tab 6: User Management
    with admin_tabs[5]:
        render_user_management_panel()
    # --- NOTIFICATIONS TAB FOR ADMIN ---
    with admin_tabs[6]:
        st.subheader("🔔 Notifications")
        admin_id = fetch_admin_id()
        notif_df = fetch_notifications_for_user('admin', admin_id) if admin_id else pd.DataFrame()
        if not notif_df.empty:
            st.dataframe(notif_df)
        else:
            st.info("No notifications yet.")

def render_supplier_dashboard(username):
    st.subheader("🚚 Supplier Dashboard")

    # --- Multi-row input for products in this shipment ---
    if "shipment_products" not in st.session_state:
        st.session_state.shipment_products = [{
            "product": "",
            "sku": "",
            "barcode": "",
            "amount": 1,
            "other_product": "",
            "other_sku": "",
        }]

    # Load product list for dropdown
    conn = get_connection()
    products_df = pd.read_sql_query("SELECT name, sku, barcode FROM products ORDER BY name", conn)
    hubs_df = pd.read_sql_query("SELECT id, name FROM hubs", conn)
    conn.close()
    product_choices = list(products_df["name"]) + ["Other"]
    hub_map = dict(zip(hubs_df['name'], hubs_df['id']))

    # --- Main Form ---
    with st.form("shipment_form"):
        tracking = st.text_input("Tracking Number")
        carrier = st.selectbox("Carrier", ["USPS", "UPS", "FedEx", "DHL"])
        selected_hub = st.selectbox("Select Hub to Ship To", list(hub_map.keys()))
        shipment_products = st.session_state.shipment_products

        # Dynamic product rows
        st.markdown("#### Products in Shipment")
        to_remove = []
        for i, prod in enumerate(shipment_products):
            cols = st.columns([3,2,2,2,2])
            with cols[0]:
                product_name = st.selectbox(
                    f"Product {i+1}", product_choices, 
                    index=(product_choices.index(prod["product"]) if prod["product"] in product_choices else 0), key=f"product_{i}"
                )
                prod["product"] = product_name
            with cols[1]:
                if product_name == "Other":
                    prod["other_product"] = st.text_input(f"Other Product Name {i+1}", value=prod["other_product"], key=f"otherprod_{i}")
                else:
                    prod["other_product"] = ""
            with cols[2]:
                if product_name == "Other":
                    prod["other_sku"] = st.text_input(f"Other SKU {i+1}", value=prod["other_sku"], key=f"othersku_{i}")
                    prod["sku"] = prod["other_sku"]
                else:
                    this_row = products_df[products_df["name"] == product_name]
                    prod["sku"] = this_row["sku"].iloc[0] if not this_row.empty else ""
            with cols[3]:
                if product_name != "Other":
                    prod["barcode"] = this_row["barcode"].iloc[0] if not this_row.empty else ""
                    st.text(f"{prod['barcode']}")
                else:
                    prod["barcode"] = ""
                    st.text("-")
            with cols[4]:
                prod["amount"] = st.number_input(f"Qty {i+1}", min_value=1, step=1, value=prod["amount"], key=f"qty_{i}")
                if i > 0:
                    if st.button(f"Remove", key=f"remove_{i}"):
                        to_remove.append(i)
        
        # Remove any rows requested
        if to_remove:
            for idx in sorted(to_remove, reverse=True):
                shipment_products.pop(idx)
            st.session_state.shipment_products = shipment_products
            st.experimental_rerun()

        if st.button("Add Another Product"):
            shipment_products.append({
                "product": "",
                "sku": "",
                "barcode": "",
                "amount": 1,
                "other_product": "",
                "other_sku": "",
            })
            st.session_state.shipment_products = shipment_products
            st.experimental_rerun()

        # CSV Upload
        st.markdown("#### Bulk Add Products (CSV Upload)")
        csv_file = st.file_uploader("CSV file (columns: product, sku, barcode, amount)", type=["csv"])
        if csv_file:
            csv_df = pd.read_csv(csv_file)
            for _, row in csv_df.iterrows():
                shipment_products.append({
                    "product": row.get("product", ""),
                    "sku": row.get("sku", ""),
                    "barcode": row.get("barcode", ""),
                    "amount": int(row.get("amount", 1)),
                    "other_product": "" if row.get("product", "") in product_choices else row.get("product", ""),
                    "other_sku": "" if row.get("sku", "") else "",
                })
            st.session_state.shipment_products = shipment_products
            st.success("CSV products added to this shipment! Review below before submitting.")
            st.experimental_rerun()

        # Submit Shipment
        submitted = st.form_submit_button("Add Shipment")
        if submitted:
            errors = []
            for prod in shipment_products:
                name = prod["product"] if prod["product"] != "Other" else prod["other_product"]
                sku = prod["sku"] or prod["other_sku"]
                amt = prod["amount"]
                if not name or not sku or amt <= 0:
                    errors.append(f"Product row missing required fields.")
            if not tracking:
                errors.append("Tracking number required.")
            if errors:
                st.error("\n".join(errors))
            else:
                hub_id = hub_map[selected_hub]
                for prod in shipment_products:
                    name = prod["product"] if prod["product"] != "Other" else prod["other_product"]
                    sku = prod["sku"] or prod["other_sku"]
                    amt = prod["amount"]
                    insert_shipment(username, tracking, hub_id, name, amt, carrier)
                # --- NOTIFY HQ ADMIN & HUB MANAGER/USER ---
                admin_id = fetch_admin_id()
                msg = f"New shipment from {username} (Tracking: {tracking}) for hub '{selected_hub}'."
                if admin_id:
                    insert_notification('admin', admin_id, msg)
                hub_manager_id = fetch_hub_manager_id(hub_id)
                if hub_manager_id:
                    insert_notification('hub', hub_manager_id, f"Shipment from {username} is on the way. Tracking: {tracking}")
                st.success("Shipment logged and notifications sent to HQ and hub!")
                st.session_state.shipment_products = [{
                    "product": "",
                    "sku": "",
                    "barcode": "",
                    "amount": 1,
                    "other_product": "",
                    "other_sku": "",
                }]
                st.experimental_rerun()

    # Historical Shipments (with export)
    st.subheader("My Shipments")
    ships = fetch_all_shipments()
    ships = ships[ships['supplier'] == username] if not ships.empty else pd.DataFrame()
    if not ships.empty:
        st.dataframe(ships)
        st.download_button("Download My Shipments (CSV)", ships.to_csv(index=False), file_name="my_shipments.csv", mime="text/csv")
    else:
        st.info("No shipments found.")

    st.markdown("---")
    st.info("Need to ship to multiple hubs at once? Use the above form, then repeat for each hub.")

# --- LOGIN FLOW ---
if 'user' not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("🧦 TTT Inventory Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            result = login(username, password)
            if result:
                st.session_state.user = {
                    "id": result[0],
                    "role": result[1],
                    "hub_id": result[2],
                    "username": username
                }
                st.rerun()
            else:
                st.error("❌ Invalid username or password")
else:
    st.sidebar.success(f"Logged in as: {st.session_state.user['username']} ({st.session_state.user['role']})")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()
    user = st.session_state.user
    if user["role"] == "admin":
        render_admin_dashboard(user["username"])
    elif user["role"] == "supplier":
        render_supplier_dashboard(user["username"])
    else:
        render_hub_dashboard(user["hub_id"], user["username"])
