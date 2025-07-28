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

# --- TABS ---
def render_hub_dashboard(hub_id, username):
    tabs = st.tabs([
        "Inventory", "Inventory Out Trends", "Supply Notes", "Shipments", "Add Inventory Transaction"
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
                st.experimental_rerun()
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
            st.experimental_rerun()

def render_admin_dashboard(username):
    admin_tabs = st.tabs([
        "All Inventory", "All Orders/OUT+IN", "All Supply Notes/Requests", "All Shipments", "Assign/Remove SKUs"
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
                            st.experimental_rerun()
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

def render_supplier_dashboard(username):
    st.subheader("🚚 Supplier Dashboard")
    with st.form("shipment_form"):
        tracking = st.text_input("Tracking Number")
        carrier = st.selectbox("Carrier", ["USPS", "UPS", "FedEx", "DHL"])
        conn = get_connection()
        hubs_df = pd.read_sql_query("SELECT id, name FROM hubs", conn)
        conn.close()
        hub_map = dict(zip(hubs_df['name'], hubs_df['id']))
        selected_hub = st.selectbox("Select Hub to Ship To", list(hub_map.keys()))
        product = st.text_input("Product Name (must match SKU product name)")
        amount = st.number_input("Amount", min_value=1, step=1)
        submit_shipment = st.form_submit_button("Add Shipment")
        if submit_shipment:
            insert_shipment(username, tracking, hub_map[selected_hub], product, amount, carrier)
            st.success("Shipment logged and sent to HQ and hub.")
            st.experimental_rerun()
    # Show all shipments logged by this supplier
    ships = fetch_all_shipments()
    ships = ships[ships['supplier'] == username] if not ships.empty else pd.DataFrame()
    st.subheader("My Shipments")
    st.dataframe(ships if not ships.empty else pd.DataFrame(columns=["date", "tracking", "hub_id", "product", "amount", "carrier"]))

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
                st.experimental_rerun()
            else:
                st.error("❌ Invalid username or password")
else:
    st.sidebar.success(f"Logged in as: {st.session_state.user['username']} ({st.session_state.user['role']})")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.experimental_rerun()
    user = st.session_state.user
    if user["role"] == "admin":
        render_admin_dashboard(user["username"])
    elif user["role"] == "supplier":
        render_supplier_dashboard(user["username"])
    else:
        render_hub_dashboard(user["hub_id"], user["username"])
