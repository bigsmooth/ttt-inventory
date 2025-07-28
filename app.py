import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import altair as alt

DB_FILE = "barcodes.db"
st.set_page_config(page_title="TTT Inventory System", page_icon="🧦", layout="wide")

# --- AUTO CREATE TABLES ---
def create_tables():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT, email TEXT, role TEXT, hub_id INTEGER, active INTEGER DEFAULT 1
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS hubs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS products (
        sku TEXT PRIMARY KEY, name TEXT, barcode TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS inventory_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME, sku TEXT, action TEXT, quantity INTEGER, hub INTEGER, user_id INTEGER, comment TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS hub_skus (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, hub_id INTEGER, UNIQUE (sku, hub_id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS supply_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT, hub_id INTEGER, username TEXT, notes TEXT, timestamp DATETIME, response TEXT, admin TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS shipments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, date DATETIME, supplier TEXT, tracking TEXT, hub_id INTEGER, product TEXT, amount INTEGER, carrier TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, created DATETIME, user_role TEXT, user_id INTEGER, message TEXT
    )""")
    conn.commit()
    conn.close()

create_tables()

try:
    st.image("https://i.imgur.com/Y7SgqZR.jpeg", width=150)
except Exception:
    st.info("Logo image not found.")

# ---- DB HELPERS ----
def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def login(username, password):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, role, hub_id FROM users WHERE username=? AND password=? AND active=1", (username, password))
    result = c.fetchone()
    conn.close()
    return result

def fetch_all_hubs():
    conn = get_connection()
    df = pd.read_sql_query("SELECT id, name FROM hubs", conn)
    conn.close()
    return df

def log_inventory(user_id, sku, action, quantity, hub_id, comment):
    conn = get_connection()
    c = conn.cursor()
    timestamp = datetime.now()
    c.execute("""
        INSERT INTO inventory_log (timestamp, sku, action, quantity, hub, user_id, comment)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (timestamp, sku, action, quantity, hub_id, user_id, comment))
    conn.commit()
    conn.close()

def fetch_skus_for_hub(hub_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT p.name, p.sku, p.barcode FROM hub_skus hs
        JOIN products p ON hs.sku = p.sku
        WHERE hs.hub_id = ?
        ORDER BY p.name""", (hub_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def fetch_inventory_for_hub(hub_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT p.name, p.sku, p.barcode,
        COALESCE(SUM(CASE WHEN il.action='IN' THEN il.quantity ELSE 0 END),0) -
        COALESCE(SUM(CASE WHEN il.action='OUT' THEN il.quantity ELSE 0 END),0) AS net_quantity
        FROM hub_skus hs
        JOIN products p ON hs.sku = p.sku
        LEFT JOIN inventory_log il ON hs.sku = il.sku AND il.hub = ?
        WHERE hs.hub_id = ?
        GROUP BY p.name, p.sku, p.barcode
        ORDER BY p.name""", (hub_id, hub_id))
    data = c.fetchall()
    conn.close()
    return data

def fetch_inventory_history(hub_id):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT sku, date(timestamp) as date, SUM(CASE WHEN action = 'OUT' THEN quantity ELSE 0 END) as total_out
        FROM inventory_log WHERE hub = ?
        GROUP BY sku, date ORDER BY date
    """, conn, params=(hub_id,))
    conn.close()
    return df

def fetch_my_supply_requests(hub_id):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT * FROM supply_requests WHERE hub_id = ? ORDER BY timestamp DESC
    """, conn, params=(hub_id,))
    conn.close()
    return df

def insert_supply_request(hub_id, username, notes):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO supply_requests (hub_id, username, notes, timestamp)
        VALUES (?, ?, ?, ?)
    """, (hub_id, username, notes, datetime.now()))
    conn.commit()
    conn.close()

def reply_to_supply_request(request_id, reply_text, admin_username):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE supply_requests SET response=?, admin=? WHERE id=?
    """, (reply_text, admin_username, request_id))
    conn.commit()
    conn.close()

def fetch_today_orders(hub_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT SUM(quantity)
        FROM inventory_log
        WHERE hub = ? AND action = 'OUT' AND date(timestamp) = date('now')
    """, (hub_id,))
    result = c.fetchone()[0]
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

# Notifications
def insert_notification(user_role, user_id, message):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO notifications (created, user_role, user_id, message)
        VALUES (?, ?, ?, ?)""", (datetime.now(), user_role, user_id, message))
    conn.commit()
    conn.close()

def fetch_notifications_for_user(user_role, user_id):
    if not user_id:
        return pd.DataFrame(columns=["created", "message"])
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT created, message FROM notifications WHERE user_role=? AND user_id=? ORDER BY created DESC
    """, conn, params=(user_role, user_id))
    conn.close()
    return df

### USER MANAGEMENT ###
def fetch_all_users():
    conn = get_connection()
    users = pd.read_sql_query(
        "SELECT id, username, email, role, hub_id, active FROM users ORDER BY id", conn)
    conn.close()
    return users

def add_user(username, password, email, role, hub_id, active=1):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (username, password, email, role, hub_id, active)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (username, password, email, role, hub_id, active))
    conn.commit()
    conn.close()

def update_user(user_id, username, email, role, hub_id, active):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE users SET username=?, email=?, role=?, hub_id=?, active=?
        WHERE id=?
    """, (username, email, role, hub_id, active, user_id))
    conn.commit()
    conn.close()

def deactivate_user(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET active=0 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

def activate_user(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET active=1 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

# ---- UI: User Management ----
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

# ---- UI: Hub Dashboard ----
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
        if today_orders >= 10:
            st.success(f"✅ Orders Processed Today: {today_orders}  \n🎉 <span style='color:gold;font-size:1.4em'><b>WOOHOO!</b></span>", unsafe_allow_html=True)
        else:
            st.success(f"✅ Orders Processed Today: {today_orders}")
    with tabs[1]:
        st.subheader("📈 Inventory OUT Trends")
        history_df = fetch_inventory_history(hub_id)
        if not history_df.empty:
            chart = alt.Chart(history_df).mark_line().encode(
                x='date:T', y='total_out:Q', color='sku:N'
            ).properties(title="Inventory OUT Trends")
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No OUT transactions yet.")
    with tabs[2]:
        st.subheader("📝 Supply Notes / Messages to HQ")
        with st.form("supply_request_form"):
            note = st.text_area("Message or Supply Request to HQ")
            submit_note = st.form_submit_button("Send to HQ")
            if submit_note and note.strip():
                insert_supply_request(hub_id, username, note.strip())
                st.success("Sent to HQ.")
                st.rerun()
        reqs = fetch_my_supply_requests(hub_id)
        if not reqs.empty:
            for i, row in reqs.iterrows():
                msg = f"**{row['timestamp']}**: {row['notes']}"
                st.markdown(f":blue[Message]: {msg}")
                if row['response']:
                    st.markdown(f":green[HQ Reply]: {row['response']} _(by {row['admin']})_")
        else:
            st.info("No messages to HQ yet.")
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
        if not sku_data:
            st.info("No SKUs assigned yet.")
            return
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
    with tabs[5]:
        st.subheader("🔔 Notifications")
        notif_df = fetch_notifications_for_user('hub', st.session_state.user["id"])
        if not notif_df.empty:
            st.dataframe(notif_df)
        else:
            st.info("No notifications yet.")

# ---- UI: Admin Dashboard ----
def render_admin_dashboard(username):
    admin_tabs = st.tabs([
        "All Inventory", "All Orders/OUT+IN", "All Supply Notes/Requests", "All Shipments", "Assign/Remove SKUs", "User Management", "Notifications"
    ])
    with admin_tabs[0]:
        st.subheader("📊 All Inventory Across Hubs")
        inv = fetch_all_inventory()
        st.dataframe(inv)
        if st.button("Export All Inventory as CSV"):
            st.download_button("Download CSV", inv.to_csv(index=False), file_name="all_inventory.csv", mime="text/csv")
    with admin_tabs[1]:
        st.subheader("🧾 All Orders/IN+OUT Logs")
        conn = get_connection()
        logs_df = pd.read_sql_query("SELECT * FROM inventory_log ORDER BY timestamp DESC", conn)
        st.dataframe(logs_df)
        conn.close()
    with admin_tabs[2]:
        st.subheader("📬 All Hub Messages/Supply Requests")
        reqs = fetch_all_supply_requests()
        if not reqs.empty:
            for idx, row in reqs.iterrows():
                st.markdown(f"---\n:blue[From {row['username']} (hub_id: {row['hub_id']})] **{row['timestamp']}**\n> {row['notes']}")
                if row['response']:
                    st.markdown(f":green[You replied]: {row['response']} _(by {row['admin']})_")
                else:
                    with st.form(f"reply_form_{row['id']}"):
                        reply_text = st.text_area("Reply", key=f"reply_{row['id']}")
                        if st.form_submit_button("Send Reply"):
                            reply_to_supply_request(row['id'], reply_text, username)
                            st.success("Reply sent.")
                            st.rerun()
        else:
            st.info("No supply notes/requests found.")
    with admin_tabs[3]:
        st.subheader("🚚 All Shipments")
        ships = fetch_all_shipments()
        st.dataframe(ships)
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
    with admin_tabs[5]:
        render_user_management_panel()
    with admin_tabs[6]:
        st.subheader("🔔 Notifications")
        notif_df = fetch_notifications_for_user(st.session_state.user['role'], st.session_state.user['id'])
        if not notif_df.empty:
            st.dataframe(notif_df)
        else:
            st.info("No notifications yet.")

# ---- LOGIN FLOW ----
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
    else:
        render_hub_dashboard(user["hub_id"], user["username"])
