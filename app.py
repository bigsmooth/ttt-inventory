import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import altair as alt
import os
import shutil

from pathlib import Path

# ====== LOGO / BRANDING SETUP ======
LOCAL_LOGO_PATH = "ttt_logo.png"
FALLBACK_REMOTE_LOGO = "https://i.ibb.co/6RpPD8q/ttt-logo-2024-b.png"  # upload your real logo if desired

def show_logo():
    logo_shown = False
    if Path(LOCAL_LOGO_PATH).exists():
        st.image(LOCAL_LOGO_PATH, width=170)
        logo_shown = True
    else:
        try:
            st.image(FALLBACK_REMOTE_LOGO, width=170)
            logo_shown = True
        except Exception:
            pass
    if not logo_shown:
        st.markdown("## 🧦 Thick Thigh Tribe Inventory")
show_logo()

st.markdown("<h1 style='font-size:2.1em;color:#ee4d8c'>TTT Inventory Management</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:gray'>Welcome to your real-time stock and shipment portal.</p>", unsafe_allow_html=True)

DB_FILE = "barcodes.db"
BACKUP_FILE = f"backup_{datetime.now().strftime('%Y_%m_%d')}.db"
BACKUP_FREQ_DAYS = 7

st.set_page_config(page_title="TTT Inventory System", page_icon="🧦", layout="wide")

# ========== WEEKLY BACKUP ==========
def backup_db():
    try:
        last_backup = Path("last_backup.txt")
        do_backup = True
        if last_backup.exists():
            with open("last_backup.txt", "r") as f:
                last = f.read().strip()
                if last:
                    dt = datetime.strptime(last, "%Y-%m-%d")
                    if (datetime.now() - dt).days < BACKUP_FREQ_DAYS:
                        do_backup = False
        if do_backup and Path(DB_FILE).exists():
            shutil.copy(DB_FILE, BACKUP_FILE)
            with open("last_backup.txt", "w") as f:
                f.write(datetime.now().strftime("%Y-%m-%d"))
    except Exception as e:
        st.warning(f"Backup failed: {e}")
backup_db()

# --- AUTO CREATE TABLES ---
def create_tables():
    try:
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
            id INTEGER PRIMARY KEY AUTOINCREMENT, date DATETIME, hub_id INTEGER, tracking TEXT, carrier TEXT, notes TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created DATETIME, user_role TEXT, user_id INTEGER, message TEXT
        )""")
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Table creation error: {e}")
create_tables()

# ========= GOOGLE AUTH (streamlit-authenticator) ========
import streamlit_authenticator as stauth
import yaml

def do_google_auth():
    try:
        with open('config.yaml') as file:
            config = yaml.safe_load(file)
        authenticator = stauth.Authenticate(
            config['credentials'],
            config['cookie']['name'],
            config['cookie']['key'],
            config['cookie']['expiry_days'],
            config['preauthorized']
        )
        name, auth_status, username = authenticator.login("Login with Google", "main")
        if auth_status:
            return {"id": None, "role": "admin", "hub_id": None, "username": name}
        elif auth_status is False:
            st.error("Google Auth failed. Try again.")
            return None
    except Exception:
        return None

# =========== ERROR HANDLING (WRAPPER) ============
def safe_db_call(f):
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            st.error(f"Database error: {e}")
            return pd.DataFrame() if 'fetch' in f.__name__ else None
    return wrapper

# ========= DB FUNCTIONS (all wrapped) ==========
@safe_db_call
def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

@safe_db_call
def login(username, password):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, role, hub_id FROM users WHERE username=? AND password=? AND active=1", (username, password))
    result = c.fetchone()
    conn.close()
    return result

@safe_db_call
def fetch_all_hubs():
    conn = get_connection()
    df = pd.read_sql_query("SELECT id, name FROM hubs", conn)
    conn.close()
    return df

@safe_db_call
def fetch_shipments_for_hub(hub_id):
    conn = get_connection()
    df = pd.read_sql_query("SELECT date, tracking, carrier, notes FROM shipments WHERE hub_id=? ORDER BY date DESC", conn, params=(hub_id,))
    conn.close()
    return df

@safe_db_call
def fetch_all_shipments():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM shipments ORDER BY date DESC", conn)
    conn.close()
    return df

@safe_db_call
def fetch_my_supply_requests(hub_id):
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM supply_requests WHERE hub_id=? ORDER BY timestamp DESC", conn, params=(hub_id,))
    conn.close()
    return df

@safe_db_call
def fetch_all_supply_requests():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM supply_requests ORDER BY timestamp DESC", conn)
    conn.close()
    return df

@safe_db_call
def fetch_inventory_for_hub(hub_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT p.name, p.sku, p.barcode,
        COALESCE(SUM(CASE WHEN il.action='IN' THEN il.quantity ELSE 0 END),0) -
        COALESCE(SUM(CASE WHEN il.action='OUT' THEN il.quantity ELSE 0 END),0) AS Inventory
        FROM hub_skus hs
        JOIN products p ON hs.sku = p.sku
        LEFT JOIN inventory_log il ON hs.sku = il.sku AND il.hub = ?
        WHERE hs.hub_id = ?
        GROUP BY p.name, p.sku, p.barcode
        ORDER BY p.name""", (hub_id, hub_id))
    data = c.fetchall()
    conn.close()
    return data

@safe_db_call
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

@safe_db_call
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

@safe_db_call
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

@safe_db_call
def fetch_inventory_history(hub_id):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT sku, date(timestamp) as date, SUM(CASE WHEN action = 'OUT' THEN quantity ELSE 0 END) as total_out
        FROM inventory_log WHERE hub = ?
        GROUP BY sku, date ORDER BY date
    """, conn, params=(hub_id,))
    conn.close()
    return df

@safe_db_call
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

@safe_db_call
def insert_supply_request(hub_id, username, notes):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO supply_requests (hub_id, username, notes, timestamp) VALUES (?, ?, ?, ?)", (hub_id, username, notes, datetime.now()))
    conn.commit()
    conn.close()

@safe_db_call
def reply_to_supply_request(request_id, reply_text, admin_username):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE supply_requests SET response=?, admin=? WHERE id=?", (reply_text, admin_username, request_id))
    conn.commit()
    conn.close()

@safe_db_call
def insert_notification(user_role, user_id, message):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO notifications (created, user_role, user_id, message)
        VALUES (?, ?, ?, ?)""", (datetime.now(), user_role, user_id, message))
    conn.commit()
    conn.close()

@safe_db_call
def fetch_notifications_for_user(user_role, user_id):
    if not user_id:
        return pd.DataFrame(columns=["created", "message"])
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT created, message FROM notifications WHERE user_role=? AND user_id=? ORDER BY created DESC
    """, conn, params=(user_role, user_id))
    conn.close()
    return df

@safe_db_call
def fetch_all_users():
    conn = get_connection()
    users = pd.read_sql_query(
        "SELECT id, username, email, role, hub_id, active FROM users ORDER BY id", conn)
    conn.close()
    return users

@safe_db_call
def add_user(username, password, email, role, hub_id, active=1):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (username, password, email, role, hub_id, active)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (username, password, email, role, hub_id, active))
    conn.commit()
    conn.close()

@safe_db_call
def update_user(user_id, username, email, role, hub_id, active):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE users SET username=?, email=?, role=?, hub_id=?, active=?
        WHERE id=?
    """, (username, email, role, hub_id, active, user_id))
    conn.commit()
    conn.close()

@safe_db_call
def deactivate_user(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET active=0 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

@safe_db_call
def activate_user(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET active=1 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

# =========== FILTER COMPONENTS ===========
def filter_dataframe(df):
    if df.empty:
        return df
    cols = st.multiselect("Filter columns", df.columns.tolist(), default=df.columns.tolist())
    query = st.text_input("🔎 Global or column-specific filter (eg. Nike or Product:Nike)", "")
    if query:
        if ':' in query:
            col, val = query.split(':', 1)
            col = col.strip()
            val = val.strip().lower()
            if col in df.columns:
                df = df[df[col].astype(str).str.lower().str.contains(val)]
        else:
            mask = df[cols].apply(lambda row: query.lower() in str(row).lower(), axis=1)
            df = df[mask]
    return df[cols]

# ========== UI PANELS WITH INSTRUCTIONS =============
def render_user_management_panel():
    st.subheader("👤 User Management")
    st.info("**Purpose:** Manage system users, assign roles, activate/deactivate accounts, and reset passwords. Only HQ Admins can add, edit, or remove users. Use search and filter tools to quickly find a user by any info.")
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
    users = filter_dataframe(users)
    st.dataframe(users)
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
        st.info("**Purpose:** See your current stock for all SKUs. Filter or search to find a specific product or barcode. Low stock is highlighted. Contact HQ for restock.")
        inventory_df = pd.DataFrame(fetch_inventory_for_hub(hub_id), columns=["Product", "SKU", "Barcode", "Inventory"])
        inventory_df = filter_dataframe(inventory_df)
        st.dataframe(inventory_df)
        low_stock = inventory_df[inventory_df["Inventory"] < 10]
        if not low_stock.empty:
            st.warning("⚠️ The following items are below 10 in stock. Contact HQ for restock:")
            st.dataframe(low_stock)
        today_orders = fetch_today_orders(hub_id)
        st.success(f"✅ Orders Processed Today: {today_orders}")
    with tabs[1]:
        st.info("**Purpose:** Visualize your daily/weekly OUT transactions by SKU. Use filters to analyze patterns and spot trends for re-ordering.")
        st.subheader("📈 Inventory OUT Trends")
        history_df = fetch_inventory_history(hub_id)
        if not history_df.empty:
            chart = alt.Chart(history_df).mark_line().encode(
                x='date:T', y='total_out:Q', color='sku:N'
            ).properties(title="Inventory OUT Trends")
            st.altair_chart(chart, use_container_width=True)
            st.dataframe(history_df)
        else:
            st.info("No OUT transactions yet.")
    with tabs[2]:
        st.info("**Purpose:** Communicate supply requests or questions to HQ. Check for responses. All correspondence is logged and visible to HQ admins.")
        st.subheader("📝 Supply Notes / Messages to HQ")
        with st.form("supply_request_form"):
            note = st.text_area("Message or Restock Note to HQ")
            submit_note = st.form_submit_button("Send to HQ")
            if submit_note and note.strip():
                insert_supply_request(hub_id, username, note.strip())
                st.success("Sent to HQ.")
                st.rerun()
        reqs = fetch_my_supply_requests(hub_id)
        reqs = filter_dataframe(reqs)
        if not reqs.empty:
            for i, row in reqs.iterrows():
                msg = f"**{row['timestamp']}**: {row['notes']}"
                st.markdown(f":blue[Message]: {msg}")
                if row['response']:
                    st.markdown(f":green[HQ Reply]: {row['response']} _(by {row['admin']})_")
        else:
            st.info("No messages to HQ yet.")
    with tabs[3]:
        st.info("**Purpose:** View all shipments that have been sent to your hub. Use search/filter to find by tracking, carrier, or date.")
        st.subheader("🚚 Shipments to My Hub")
        ship_df = fetch_shipments_for_hub(hub_id)
        ship_df = filter_dataframe(ship_df)
        if not ship_df.empty:
            st.dataframe(ship_df)
        else:
            st.info("No shipments yet.")
    with tabs[4]:
        st.info("**Purpose:** Log new inventory activity (IN or OUT) for your hub. Select SKU, choose IN/OUT, enter quantity, and comment if needed.")
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
        st.info("**Purpose:** See notifications sent by HQ Admin. All inventory, compliance, or urgent messages show here.")
        st.subheader("🔔 Notifications")
        notif_df = fetch_notifications_for_user('hub', st.session_state.user["id"])
        notif_df = filter_dataframe(notif_df)
        if not notif_df.empty:
            st.dataframe(notif_df)
        else:
            st.info("No notifications yet.")

def render_admin_dashboard(username):
    admin_tabs = st.tabs([
        "All Inventory", "Inventory Charts", "All Supply Requests", "All Shipments", "User Management", "Notifications"
    ])
    with admin_tabs[0]:
        st.info("**Purpose:** See all hub inventories at a glance. Export as CSV. Use filter/search for any hub, product, or barcode.")
        inv = fetch_all_inventory()
        inv = filter_dataframe(inv)
        st.dataframe(inv)
        if st.button("Export All Inventory as CSV"):
            st.download_button("Download CSV", inv.to_csv(index=False), file_name="all_inventory.csv", mime="text/csv")
    with admin_tabs[1]:
        st.info("**Purpose:** Visualize, compare, and analyze inventory levels by hub/product using interactive bar charts. Use filters for deep dives.")
        st.subheader("📈 Graphical Inventory Overview")
        df = fetch_all_inventory()
        if not df.empty:
            hub = st.selectbox("Select Hub", ["All"] + sorted(df["Hub"].unique()))
            prod = st.selectbox("Select Product", ["All"] + sorted(df["Product"].unique()))
            filtered = df.copy()
            if hub != "All":
                filtered = filtered[filtered["Hub"] == hub]
            if prod != "All":
                filtered = filtered[filtered["Product"] == prod]
            if filtered.empty:
                st.info("No data for this filter.")
            else:
                chart = alt.Chart(filtered).mark_bar().encode(
                    x=alt.X('Product:N', sort='-y'),
                    y='Inventory:Q',
                    color='Hub:N',
                    tooltip=['Hub', 'Product', 'Inventory']
                ).properties(width=700, height=400)
                st.altair_chart(chart, use_container_width=True)
                st.dataframe(filtered)
        else:
            st.info("No inventory data yet.")
    with admin_tabs[2]:
        st.info("**Purpose:** Manage and reply to all hub requests. Filter/search requests for priority or status.")
        st.subheader("📬 All Hub Messages/Supply Requests")
        reqs = fetch_all_supply_requests()
        reqs = filter_dataframe(reqs)
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
        st.info("**Purpose:** View, filter, and search all shipments to any hub. Use for tracking and reconciliation.")
        st.subheader("🚚 All Shipments")
        ships = fetch_all_shipments()
        ships = filter_dataframe(ships)
        st.dataframe(ships)
    with admin_tabs[4]:
        render_user_management_panel()
    with admin_tabs[5]:
        st.info("**Purpose:** See all notifications sent by HQ to managers and hubs. Use to communicate updates, recalls, and alerts.")
        st.subheader("🔔 Notifications")
        notif_df = fetch_notifications_for_user('admin', None)
        notif_df = filter_dataframe(notif_df)
        if not notif_df.empty:
            st.dataframe(notif_df)
        else:
            st.info("No notifications yet.")

# ============ AUTH FLOW (Google or fallback) ===========
if 'user' not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    user = do_google_auth()
    if user is None:
        st.title("🧦 TTT Inventory Login")
        st.markdown("**TIP:** Login with your username/password if Google SSO is not configured.")
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
        st.session_state.user = user
        st.rerun()
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
