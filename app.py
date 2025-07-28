import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import altair as alt
import secrets, string, io

DB_FILE = "barcodes.db"
LOGO_URL = "https://i.imgur.com/Y7SgqZR.jpeg"

st.set_page_config(page_title="Thick Thigh Tribe Inventory", page_icon="🧦", layout="wide")

# --- UTILITIES ---
def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

# --- AUTH ---
def login(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, role, hub_id, email FROM users WHERE username=? AND password=?", (username, password))
    result = cursor.fetchone()
    conn.close()
    return result

def add_user(username, password, role, hub_id, email):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (username, password, role, hub_id, email)
        VALUES (?, ?, ?, ?, ?)
    """, (username, password, role, hub_id, email))
    conn.commit()
    conn.close()

def fetch_hub_name(hub_id):
    if hub_id is None:
        return "HQ Admin"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM hubs WHERE id = ?", (hub_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "Unknown"

# --- INVENTORY ---
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

def is_sku_assigned_to_hub(hub_id, sku):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM hub_skus WHERE hub_id = ? AND sku = ?", (hub_id, sku))
    result = cursor.fetchone()
    conn.close()
    return result is not None

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

# --- SUPPLY REQUESTS AND NOTES ---
def insert_supply_request(hub_id, username, notes):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS supply_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hub_id INTEGER,
            username TEXT,
            notes TEXT,
            response TEXT,
            admin TEXT,
            timestamp DATETIME
        )
    """)
    cursor.execute("""
        INSERT INTO supply_requests (hub_id, username, notes, response, admin, timestamp)
        VALUES (?, ?, ?, NULL, NULL, ?)
    """, (hub_id, username, notes, datetime.now()))
    conn.commit()
    conn.close()

def fetch_all_supply_requests():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM supply_requests ORDER BY timestamp DESC", conn)
    conn.close()
    return df

def respond_to_supply_request(request_id, response, admin_username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE supply_requests SET response = ?, admin = ? WHERE id = ?
    """, (response, admin_username, request_id))
    conn.commit()
    conn.close()

def fetch_supply_requests_for_hub(hub_id):
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM supply_requests WHERE hub_id = ? ORDER BY timestamp DESC", conn, params=(hub_id,))
    conn.close()
    return df

# --- ADMIN: ASSIGN/REMOVE SKUs, BULK UPLOADS ---
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

# --- BULK UPLOADS ---
def bulk_upload_products(df):
    conn = get_connection()
    cursor = conn.cursor()
    for _, row in df.iterrows():
        cursor.execute(
            "INSERT OR IGNORE INTO products (sku, name, barcode) VALUES (?, ?, ?)",
            (row["sku"], row["name"], str(row["barcode"]))
        )
    conn.commit()
    conn.close()

def bulk_upload_users(df):
    conn = get_connection()
    cursor = conn.cursor()
    for _, row in df.iterrows():
        cursor.execute(
            "INSERT INTO users (username, password, role, hub_id, email) VALUES (?, ?, ?, ?, ?)",
            (row["username"], row["password"], row["role"], int(row["hub_id"]), row["email"])
        )
    conn.commit()
    conn.close()

# --- EXPORT HELPERS ---
def dataframe_csv_download(df, label="Export as CSV"):
    if df is not None and not df.empty:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=label,
            data=csv,
            file_name="export.csv",
            mime="text/csv"
        )

# --- TABS ---
def render_hub_dashboard(hub_id):
    tabs = st.tabs(["➕ Inventory Transaction", "📦 Inventory", "📈 Trends", "📝 Supply Notes"])
    
    with tabs[0]:
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

    with tabs[1]:
        st.subheader("📦 My Inventory")
        inventory_df = pd.DataFrame(fetch_inventory_for_hub(hub_id), columns=["Product", "SKU", "Barcode", "Inventory"])
        st.dataframe(inventory_df)
        low_stock = inventory_df[inventory_df["Inventory"] < 10]
        if not low_stock.empty:
            st.warning("⚠️ The following items are below 10 in stock. Contact HQ for restock:")
            st.dataframe(low_stock)

    with tabs[2]:
        st.subheader("📈 Inventory OUT Trends")
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

    with tabs[3]:
        st.subheader("📝 Supply Notes (to HQ)")
        # Place your supply notes form here!
        # (reuse your previous notes code)


def render_admin_dashboard():
    st.subheader("📦 HQ Admin Dashboard")
    df = pd.read_sql_query("""
        SELECT h.name AS Hub, p.name AS Product, p.sku, p.barcode,
        COALESCE(SUM(CASE WHEN il.action = 'IN' THEN il.quantity ELSE 0 END), 0) -
        COALESCE(SUM(CASE WHEN il.action = 'OUT' THEN il.quantity ELSE 0 END), 0) AS Inventory
        FROM inventory_log il
        JOIN products p ON il.sku = p.sku
        JOIN hubs h ON il.hub = h.id
        GROUP BY h.name, p.name, p.sku, p.barcode
        ORDER BY h.name, p.name
    """, get_connection())
    st.dataframe(df, use_container_width=True)
    dataframe_csv_download(df, label="Export All Inventory as CSV")

def render_supply_notes_tab():
    st.subheader("📬 Supply Notes From Hubs")
    df = fetch_all_supply_requests()
    if not df.empty:
        st.dataframe(df[["timestamp", "hub_id", "username", "notes", "response", "admin"]])
        # Admin can respond inline
        for idx, row in df.iterrows():
            if pd.isnull(row["response"]):
                response = st.text_input(f"Reply to {row['username']} (Request ID {row['id']})", key=f"resp_{row['id']}")
                if st.button(f"Send Response to {row['username']}", key=f"btn_resp_{row['id']}"):
                    respond_to_supply_request(row['id'], response, st.session_state.user['username'])
                    st.success(f"Response sent to {row['username']}")
                    st.rerun()

def render_assign_remove_tab():
    st.subheader("🧩 Assign or Remove SKUs to/from Hubs")
    all_hubs = pd.read_sql_query("SELECT id, name FROM hubs", get_connection())
    all_products = pd.read_sql_query("SELECT sku, name FROM products ORDER BY name", get_connection())
    hub_map = dict(zip(all_hubs['name'], all_hubs['id']))
    product_map = dict(zip(all_products['name'], all_products['sku']))
    selected_hub = st.selectbox("Select Hub", list(hub_map.keys()), key="assign_sku_hub")
    selected_product = st.selectbox("Select Product", list(product_map.keys()), key="assign_sku_prod")
    selected_sku = product_map[selected_product]
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Assign SKU", key="btn_assign"):
            assign_sku_to_hub(selected_sku, hub_map[selected_hub])
            st.success(f"{selected_product} assigned to {selected_hub}")
    with col2:
        if st.button("❌ Remove SKU", key="btn_remove"):
            remove_sku_from_hub(selected_sku, hub_map[selected_hub])
            st.warning(f"{selected_product} removed from {selected_hub}")
    if selected_hub:
        st.markdown(f"### Current SKUs at {selected_hub}")
        hub_id = hub_map[selected_hub]
        current = fetch_skus_for_hub(hub_id)
        st.dataframe(pd.DataFrame(current, columns=["Product", "SKU", "Barcode"]))

def render_user_management_tab():
    st.subheader("🔑 Invite Users & Bulk Upload")
    all_hubs = pd.read_sql_query("SELECT id, name FROM hubs", get_connection())
    hub_map = dict(zip(all_hubs['name'], all_hubs['id']))
    with st.form("invite_user_form", clear_on_submit=True):
        new_email = st.text_input("User's Email")
        new_username = st.text_input("Username")
        new_role = st.selectbox("Role", ["user", "admin"])
        assign_hub = st.selectbox("Assign Hub", list(hub_map.keys())) if new_role == "user" else None
        submit = st.form_submit_button("Send Invite")
        if submit and new_email and new_username:
            temp_pass = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
            hub_id = hub_map[assign_hub] if assign_hub else None
            add_user(new_username, temp_pass, new_role, hub_id, new_email)
            st.success(f"User created. Send this email to {new_email}:")
            st.code(f"""Subject: Your TTT Inventory Account

Hello,

You have been invited to use the TTT Inventory System.

Username: {new_username}
Temporary Password: {temp_pass}

Go to https://tttinventory.info to log in. Please change your password after login.

-Thick Thigh Tribe HQ
""")
    st.markdown("---")
    st.subheader("Bulk Upload Users via CSV")
    st.write("CSV format: username,password,role,hub_id,email")
    csv_file = st.file_uploader("Upload users.csv", type=["csv"], key="user_upload")
    if csv_file:
        df = pd.read_csv(csv_file)
        bulk_upload_users(df)
        st.success(f"{len(df)} users added!")

def render_bulk_product_upload_tab():
    st.subheader("Bulk Upload Products")
    st.write("CSV format: sku,name,barcode")
    prod_file = st.file_uploader("Upload products.csv", type=["csv"], key="prod_upload")
    if prod_file:
        df = pd.read_csv(prod_file)
        bulk_upload_products(df)
        st.success(f"{len(df)} products added!")

# --- LOGIN FLOW & SIDEBAR ---
st.image(LOGO_URL, width=130)
st.title("🧦 Thick Thigh Tribe Inventory")

if 'user' not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
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
                    "username": username,
                    "email": result[3]
                }
                st.rerun()
            else:
                st.error("❌ Invalid username or password")
else:
    user = st.session_state.user
    st.sidebar.success(f"Logged in as: {user['username']} ({user['role']})")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    if user["role"] == "admin":
        admin_tabs = st.tabs([
            "HQ Dashboard",
            "Supply Notes",
            "Assign/Remove SKUs",
            "User Management",
            "Bulk Product Upload"
        ])
        with admin_tabs[0]:
            render_admin_dashboard()
        with admin_tabs[1]:
            render_supply_notes_tab()
        with admin_tabs[2]:
            render_assign_remove_tab()
        with admin_tabs[3]:
            render_user_management_tab()
        with admin_tabs[4]:
            render_bulk_product_upload_tab()
    else:
        hub_tabs = st.tabs([
            "Hub Dashboard",
            "Notes to HQ"
        ])
        with hub_tabs[0]:
            render_hub_dashboard(user["hub_id"], user["username"])
        with hub_tabs[1]:
            render_hub_notes_tab(user["hub_id"], user["username"])
