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
    cursor.execute("SELECT id, role, hub_id FROM users WHERE username=? AND password=?", (username, password))
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

# ===== USER MANAGEMENT HELPERS =====
def fetch_all_users():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, username, email, role, hub_id, active FROM users ORDER BY id")
    users = c.fetchall()
    conn.close()
    return users

def add_user(username, email, password, role, hub_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO users (username, email, password, role, hub_id, active) VALUES (?, ?, ?, ?, ?, 1)",
              (username, email, password, role, hub_id if hub_id else None))
    conn.commit()
    conn.close()

def update_user(user_id, username, email, password, role, hub_id, active):
    conn = get_connection()
    c = conn.cursor()
    if password:
        c.execute("UPDATE users SET username=?, email=?, password=?, role=?, hub_id=?, active=? WHERE id=?",
                  (username, email, password, role, hub_id if hub_id else None, active, user_id))
    else:
        c.execute("UPDATE users SET username=?, email=?, role=?, hub_id=?, active=? WHERE id=?",
                  (username, email, role, hub_id if hub_id else None, active, user_id))
    conn.commit()
    conn.close()

def remove_user(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

# ====== ADMIN USER MANAGEMENT TAB ======
def render_user_management_panel():
    st.subheader("👥 User Management")
    with st.expander("➕ Add New User"):
        with st.form("add_user_form"):
            new_username = st.text_input("Username", key="new_username")
            new_email = st.text_input("Email", key="new_email")
            new_password = st.text_input("Password", type="password", key="new_password")
            new_role = st.selectbox("Role", ["admin", "hub_manager", "supplier", "user"], key="new_role")
            new_hub_id = st.number_input("Hub ID (0 for admin/supplier)", min_value=0, step=1, key="new_hub_id")
            add_submit = st.form_submit_button("Add User")
            if add_submit and new_username and new_email and new_password:
                add_user(new_username, new_email, new_password, new_role, int(new_hub_id) if new_hub_id else None)
                st.success("User added.")
                st.experimental_rerun()

    st.markdown("### 📝 Edit/Remove Existing Users")
    users = fetch_all_users()
    for u in users:
        with st.expander(f"User #{u[0]}: {u[1]} ({u[3]}) [{ 'Active' if u[5] else 'Inactive' }]"):
            with st.form(f"edit_user_{u[0]}"):
                username = st.text_input("Username", value=u[1], key=f"username_{u[0]}")
                email = st.text_input("Email", value=u[2], key=f"email_{u[0]}")
                password = st.text_input("Password (leave blank to keep current)", type="password", key=f"pw_{u[0]}")
                role = st.selectbox("Role", ["admin", "hub_manager", "supplier", "user"], index=["admin", "hub_manager", "supplier", "user"].index(u[3]), key=f"role_{u[0]}")
                hub_id = st.number_input("Hub ID", min_value=0, value=u[4] if u[4] else 0, key=f"hubid_{u[0]}")
                active = st.checkbox("Active", value=bool(u[5]), key=f"active_{u[0]}")
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.form_submit_button("Update"):
                        update_user(u[0], username, email, password, role, int(hub_id), 1 if active else 0)
                        st.success("User updated.")
                        st.experimental_rerun()
                with col2:
                    if st.form_submit_button("Remove"):
                        remove_user(u[0])
                        st.warning("User removed.")
                        st.experimental_rerun()

# --- DASHBOARD HELPERS ---
def render_hub_dashboard(hub_id):
    st.subheader("📊 Hub Dashboard")

    st.markdown("### ➕ Add Inventory Transactions")
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

    inventory_df = pd.DataFrame(fetch_inventory_for_hub(hub_id), columns=["Product", "SKU", "Barcode", "Inventory"])
    st.dataframe(inventory_df)

    low_stock = inventory_df[inventory_df["Inventory"] < 10]
    if not low_stock.empty:
        st.warning("⚠️ The following items are below 10 in stock. Contact HQ for restock:")
        st.dataframe(low_stock)

    history_df = fetch_inventory_history(hub_id)
    if not history_df.empty:
        chart = alt.Chart(history_df).mark_line().encode(
            x='date:T',
            y='total_out:Q',
            color='sku:N'
        ).properties(title="Inventory OUT Trends")
        st.altair_chart(chart, use_container_width=True)

    today_orders = fetch_today_orders(hub_id)
    st.success(f"✅ Orders Processed Today: {today_orders}")

def render_admin_dashboard():
    admin_tabs = st.tabs([
        "All Inventory", "All Orders/OUT+IN", "All Supply Notes/Requests", "All Shipments", "Assign/Remove SKUs", "User Management"
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
        st.dataframe(reqs)
    # Tab 4: Shipments
    with admin_tabs[3]:
        st.subheader("🚚 All Shipments")
        # (Your shipments tab code here)
        st.info("Shipments feature coming soon.")
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
    st.sidebar.success(f"Logged in as: {st.session_state.user['username']}")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    user = st.session_state.user
    if user["role"] == "admin":
        render_admin_dashboard()
    else:
        render_hub_dashboard(user["hub_id"])
