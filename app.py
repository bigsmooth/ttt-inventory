import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import altair as alt
import os

# Try to import Google Auth, fallback if not available
try:
    from streamlit_oauth import st_oauth
    GOOGLE_AUTH = True
except ImportError:
    GOOGLE_AUTH = False

try:
    import streamlit_authenticator as stauth
    ST_AUTH = True
except ImportError:
    ST_AUTH = False

DB_FILE = "barcodes.db"
BACKUP_FILE = f"backup_{datetime.now().strftime('%Y%m%d')}.db"

# -- Logo Setup (upload your PNG to /streamlit/ folder or use a URL)
LOGO_URL = "https://i.imgur.com/k7fTkqf.png"  # update to your own logo if needed

st.set_page_config(page_title="TTT Inventory System", page_icon="🧦", layout="wide")

# -- Auto create tables --
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
    c.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, created DATETIME, user_role TEXT, user_id INTEGER, message TEXT
    )""")
    conn.commit()
    conn.close()

create_tables()

# -- Weekly DB Backup (Monday) --
def backup_database():
    if datetime.now().weekday() == 0:  # Monday
        if not os.path.exists(BACKUP_FILE):
            import shutil
            shutil.copy(DB_FILE, BACKUP_FILE)

backup_database()

def get_connection():
    try:
        return sqlite3.connect(DB_FILE, check_same_thread=False)
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return None

# -- Auth: Google & fallback to username/password
def google_login():
    # This function uses streamlit-oauth (set up in GCP)
    try:
        token = st_oauth(
            client_id="YOUR_GOOGLE_CLIENT_ID",
            client_secret="YOUR_GOOGLE_CLIENT_SECRET",
            redirect_uri=None,
            provider="google"
        )
        if token:
            user_email = token.get('userinfo', {}).get('email', None)
            return user_email
    except Exception as e:
        st.warning("Google login failed or not set up.")
    return None

def fallback_login():
    # Uses streamlit-authenticator for local password auth
    users = fetch_all_users()
    usernames = list(users['username'].values)
    passwords = list(users['password'].values)
    names = list(users['username'].values)
    creds = {"usernames": {u: {"email": users.iloc[i]['email'], "name": names[i], "password": passwords[i]} for i, u in enumerate(usernames)}}
    authenticator = stauth.Authenticate(creds, "ttt_inventory_auth", "abcdef", cookie_expiry_days=1)
    name, auth_status, username = authenticator.login("Login", "main")
    if auth_status:
        return username
    elif auth_status == False:
        st.error("Username/password is incorrect.")
    return None

def login_flow():
    if GOOGLE_AUTH:
        st.markdown("## Sign in with Google")
        user_email = google_login()
        if user_email:
            user = find_user_by_email(user_email)
            if user is not None:
                return user
            st.error("No user found for this email.")
    if ST_AUTH:
        st.markdown("## Or use local account")
        user = fallback_login()
        if user:
            user_data = get_user_by_username(user)
            if user_data:
                return user_data
    st.stop()

def get_user_by_username(username):
    try:
        conn = get_connection()
        if conn is None:
            return None
        c = conn.cursor()
        c.execute("SELECT id, role, hub_id, username FROM users WHERE username=? AND active=1", (username,))
        result = c.fetchone()
        conn.close()
        if result:
            return {"id": result[0], "role": result[1], "hub_id": result[2], "username": result[3]}
    except Exception as e:
        st.error(f"User lookup failed: {e}")
    return None

def find_user_by_email(email):
    try:
        conn = get_connection()
        if conn is None:
            return None
        c = conn.cursor()
        c.execute("SELECT id, role, hub_id, username FROM users WHERE email=? AND active=1", (email,))
        result = c.fetchone()
        conn.close()
        if result:
            return {"id": result[0], "role": result[1], "hub_id": result[2], "username": result[3]}
    except Exception as e:
        st.error(f"User lookup failed: {e}")
    return None

def fetch_all_users():
    try:
        conn = get_connection()
        users = pd.read_sql_query(
            "SELECT id, username, email, password, role, hub_id, active FROM users ORDER BY id", conn)
        conn.close()
        return users
    except Exception as e:
        st.error(f"Could not fetch users: {e}")
        return pd.DataFrame()

# ------- Utility DB Methods with Error Handling -------
def safe_query(query, params=(), fetch="all", columns=None):
    try:
        conn = get_connection()
        if conn is None:
            return pd.DataFrame() if fetch in ("all", "one") else None
        if fetch == "df":
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()
            return df
        c = conn.cursor()
        c.execute(query, params)
        if fetch == "one":
            row = c.fetchone()
            conn.close()
            return row
        if fetch == "all":
            rows = c.fetchall()
            conn.close()
            return rows
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame() if fetch in ("all", "one", "df") else None

# ------ Inventory/Hub Logic -------
def fetch_all_hubs():
    df = safe_query("SELECT id, name FROM hubs", fetch="df")
    return df

def fetch_inventory_for_hub(hub_id):
    q = """
        SELECT p.name, p.sku, p.barcode,
        COALESCE(SUM(CASE WHEN il.action='IN' THEN il.quantity ELSE 0 END),0) -
        COALESCE(SUM(CASE WHEN il.action='OUT' THEN il.quantity ELSE 0 END),0) AS Inventory
        FROM hub_skus hs
        JOIN products p ON hs.sku = p.sku
        LEFT JOIN inventory_log il ON hs.sku = il.sku AND il.hub = ?
        WHERE hs.hub_id = ?
        GROUP BY p.name, p.sku, p.barcode
        ORDER BY p.name
        """
    rows = safe_query(q, (hub_id, hub_id), fetch="all")
    if not rows:
        return pd.DataFrame(columns=["Product", "SKU", "Barcode", "Inventory"])
    return pd.DataFrame(rows, columns=["Product", "SKU", "Barcode", "Inventory"])

def fetch_all_inventory():
    q = """
        SELECT h.name AS Hub, p.name AS Product, p.sku, p.barcode,
        COALESCE(SUM(CASE WHEN il.action = 'IN' THEN il.quantity ELSE 0 END), 0) -
        COALESCE(SUM(CASE WHEN il.action = 'OUT' THEN il.quantity ELSE 0 END), 0) AS Inventory
        FROM inventory_log il
        JOIN products p ON il.sku = p.sku
        JOIN hubs h ON il.hub = h.id
        GROUP BY h.name, p.name, p.sku, p.barcode
        ORDER BY h.name, p.name
    """
    return safe_query(q, fetch="df")

def fetch_inventory_history(hub_id):
    q = """
        SELECT sku, date(timestamp) as date, SUM(CASE WHEN action = 'OUT' THEN quantity ELSE 0 END) as total_out
        FROM inventory_log WHERE hub = ?
        GROUP BY sku, date ORDER BY date
    """
    return safe_query(q, (hub_id,), fetch="df")

def fetch_today_orders(hub_id):
    q = """
        SELECT SUM(quantity)
        FROM inventory_log
        WHERE hub = ? AND action = 'OUT' AND date(timestamp) = date('now')
    """
    row = safe_query(q, (hub_id,), fetch="one")
    return row[0] if row and row[0] else 0

def fetch_skus_for_hub(hub_id):
    q = """
        SELECT p.name, p.sku, p.barcode FROM hub_skus hs
        JOIN products p ON hs.sku = p.sku
        WHERE hs.hub_id = ?
        ORDER BY p.name
    """
    return safe_query(q, (hub_id,), fetch="all")

def log_inventory(user_id, sku, action, quantity, hub_id, comment):
    q = """
        INSERT INTO inventory_log (timestamp, sku, action, quantity, hub, user_id, comment)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    return safe_query(q, (datetime.now(), sku, action, quantity, hub_id, user_id, comment), fetch=None)

def fetch_my_supply_requests(hub_id):
    q = "SELECT * FROM supply_requests WHERE hub_id=? ORDER BY timestamp DESC"
    return safe_query(q, (hub_id,), fetch="df")

def insert_supply_request(hub_id, username, notes):
    q = "INSERT INTO supply_requests (hub_id, username, notes, timestamp) VALUES (?, ?, ?, ?)"
    return safe_query(q, (hub_id, username, notes, datetime.now()), fetch=None)

def reply_to_supply_request(request_id, reply_text, admin_username):
    q = "UPDATE supply_requests SET response=?, admin=? WHERE id=?"
    return safe_query(q, (reply_text, admin_username, request_id), fetch=None)

def fetch_all_supply_requests():
    q = "SELECT * FROM supply_requests ORDER BY timestamp DESC"
    return safe_query(q, fetch="df")

def fetch_notifications_for_user(user_role, user_id):
    if not user_id:
        return pd.DataFrame(columns=["created", "message"])
    q = """
        SELECT created, message FROM notifications WHERE user_role=? AND user_id=? ORDER BY created DESC
    """
    return safe_query(q, (user_role, user_id), fetch="df")

def insert_notification(user_role, user_id, message):
    q = """
        INSERT INTO notifications (created, user_role, user_id, message)
        VALUES (?, ?, ?, ?)
    """
    return safe_query(q, (datetime.now(), user_role, user_id, message), fetch=None)

# ----- UI Panels with Search/Filters -----
def render_search_bar(df, columns):
    search = st.text_input("🔍 Search").strip().lower()
    if search:
        mask = pd.concat([(df[col].astype(str).str.lower().str.contains(search)) for col in columns], axis=1).any(axis=1)
        df = df[mask]
    return df

def render_filter_bar(df, columns):
    for col in columns:
        values = sorted(df[col].dropna().unique())
        if len(values) > 1:
            val = st.selectbox(f"Filter by {col}", ["All"] + list(values), key=col+"-filter")
            if val != "All":
                df = df[df[col] == val]
    return df

def render_hub_dashboard(hub_id, username, role):
    st.title("Hub Manager Inventory Dashboard")
    st.info("**Instructions:**\n\n- View all current inventory for your hub\n- Add IN/OUT transactions\n- Track supply requests and HQ replies\n- See daily orders and notifications")
    tabs = st.tabs([
        "Inventory", "Inventory Out Trends", "Supply Notes", "Add Inventory Transaction", "Notifications"
    ])
    with tabs[0]:
        inventory_df = fetch_inventory_for_hub(hub_id)
        st.subheader("📦 My Inventory")
        inventory_df = render_search_bar(inventory_df, ["Product", "SKU", "Barcode"])
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
            history_df = render_search_bar(history_df, ["sku"])
            chart = alt.Chart(history_df).mark_line().encode(
                x='date:T', y='total_out:Q', color='sku:N'
            ).properties(title="Inventory OUT Trends")
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No OUT transactions yet.")
    with tabs[2]:
        st.subheader("📝 Supply Notes / Messages to HQ")
        st.info("Use this tab to message HQ for restock or any issues. HQ responses will show here.")
        with st.form("supply_request_form"):
            note = st.text_area("Message or Restock Note to HQ")
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
        st.subheader("➕ Add Inventory Transaction")
        sku_data = fetch_skus_for_hub(hub_id)
        st.info("Select SKU, IN/OUT, and quantity to log an inventory change.")
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
    with tabs[4]:
        st.subheader("🔔 Notifications")
        notif_df = fetch_notifications_for_user('hub', st.session_state.user["id"])
        if not notif_df.empty:
            notif_df = render_search_bar(notif_df, ["message"])
            st.dataframe(notif_df)
        else:
            st.info("No notifications yet.")

def render_admin_dashboard(username, user_id):
    st.title("HQ Admin Dashboard")
    st.info("**Instructions:**\n\n- Review all inventory across hubs\n- Monitor all supply requests\n- Manage users and notifications\n- Export CSV backups\n- Use search and filters for fast navigation")
    admin_tabs = st.tabs([
        "All Inventory", "Inventory Charts", "All Supply Requests", "User Management", "Notifications"
    ])
    with admin_tabs[0]:
        st.subheader("📊 All Inventory Across Hubs")
        inv = fetch_all_inventory()
        inv = render_filter_bar(inv, ["Hub", "Product"])
        inv = render_search_bar(inv, ["Hub", "Product", "sku", "barcode"])
        st.dataframe(inv)
        if st.button("Export All Inventory as CSV"):
            st.download_button("Download CSV", inv.to_csv(index=False), file_name="all_inventory.csv", mime="text/csv")
    with admin_tabs[1]:
        st.subheader("📈 Graphical Inventory Overview")
        df = fetch_all_inventory()
        df = render_filter_bar(df, ["Hub", "Product"])
        df = render_search_bar(df, ["Hub", "Product", "sku", "barcode"])
        if not df.empty:
            chart = alt.Chart(df).mark_bar().encode(
                x=alt.X('Product:N', sort='-y'),
                y='Inventory:Q',
                color='Hub:N',
                tooltip=['Hub', 'Product', 'Inventory']
            ).properties(width=700, height=400)
            st.altair_chart(chart, use_container_width=True)
            st.dataframe(df)
        else:
            st.info("No inventory data yet.")
    with admin_tabs[2]:
        st.subheader("📬 All Hub Messages/Supply Requests")
        st.info("View, respond to, and manage all messages from hub managers here.")
        reqs = fetch_all_supply_requests()
        reqs = render_search_bar(reqs, ["username", "notes", "response"])
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
        render_user_management_panel()
    with admin_tabs[4]:
        st.subheader("🔔 Notifications")
        st.info("Broadcast messages to managers and staff.")
        notif_df = fetch_notifications_for_user('admin', user_id)
        notif_df = render_search_bar(notif_df, ["message"])
        if not notif_df.empty:
            st.dataframe(notif_df)
        else:
            st.info("No notifications yet.")

def render_user_management_panel():
    st.subheader("👤 User Management")
    st.info("Add, update, activate, or deactivate users. Assign roles and hubs as needed.")
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
            try:
                q = """
                    INSERT INTO users (username, password, email, role, hub_id, active)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                safe_query(q, (username, password, email, role, hub_id, int(active)), fetch=None)
                st.success("User added!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to add user: {e}")

    st.markdown("#### All Users")
    users = render_search_bar(users, ["username", "email", "role"])
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
                    q = """
                        UPDATE users SET username=?, email=?, role=?, hub_id=?, active=?
                        WHERE id=?
                    """
                    safe_query(q, (new_username, new_email, new_role, hub_id, int(new_active), row['id']), fetch=None)
                    st.success("User updated.")
                    st.rerun()
                if row['active']:
                    if st.button("Deactivate", key=f"deactivate_{row['id']}"):
                        safe_query("UPDATE users SET active=0 WHERE id=?", (row['id'],), fetch=None)
                        st.warning("User deactivated.")
                        st.rerun()
                else:
                    if st.button("Activate", key=f"activate_{row['id']}"):
                        safe_query("UPDATE users SET active=1 WHERE id=?", (row['id'],), fetch=None)
                        st.success("User activated.")
                        st.rerun()

# --- Main App Flow ---
if __name__ == "__main__":
    # --- LOGO and Branding
    st.image(LOGO_URL, width=110)
    st.markdown("<h2 style='color:#c14a70;font-weight:800'>TTT Inventory Management</h2>", unsafe_allow_html=True)
    st.caption("Welcome to your real-time stock and shipment portal.")

    # --- Auth
    if 'user' not in st.session_state or st.session_state.user is None:
        user_data = login_flow()
        if user_data:
            st.session_state.user = user_data
        else:
            st.stop()

    # --- Sidebar/logout
    user = st.session_state.user
    st.sidebar.success(f"Logged in as: {user['username']} ({user['role']})")
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.rerun()

    # --- Show role-based dashboards
    if user["role"] == "admin":
        render_admin_dashboard(user["username"], user["id"])
    else:
        render_hub_dashboard(user["hub_id"], user["username"], user["role"])
