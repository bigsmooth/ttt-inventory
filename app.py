import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import altair as alt

DB_FILE = "barcodes.db"
LOGO_URL = "https://i.imgur.com/Y7SgqZR.jpeg"

st.set_page_config(page_title="Thick Thigh Tribe Inventory", page_icon="🧦", layout="wide")
st.image(LOGO_URL, width=150)

# --- DB HELPERS ---
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

def insert_supply_request(hub_id, username, notes):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS supply_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hub_id INTEGER,
            username TEXT,
            notes TEXT,
            timestamp DATETIME
        )
    """)
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
        WHERE hub = ? AND action = 'OUT' AND date(timestamp) = date('now', 'localtime')
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

# --- DASHBOARDS ---
def render_hub_dashboard(hub_id):
    tab1, tab2, tab3 = st.tabs(["Inventory", "Orders & History", "Send Notes to HQ"])

    # --- INVENTORY TAB ---
    with tab1:
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

    # --- ORDERS & HISTORY TAB ---
    with tab2:
        history_df = fetch_full_inventory_log(hub_id)
        st.dataframe(history_df)
        out_df = history_df[history_df['action'] == 'OUT']
        if not out_df.empty:
            out_df['date'] = pd.to_datetime(out_df['timestamp']).dt.date
            orders_today = out_df[out_df['date'] == datetime.now().date()]['quantity'].sum()
            st.success(f"✅ Orders Processed Today: {orders_today}")
        chart_df = fetch_inventory_history(hub_id)
        if not chart_df.empty:
            chart = alt.Chart(chart_df).mark_line().encode(
                x='date:T',
                y='total_out:Q',
                color='sku:N'
            ).properties(title="Inventory OUT Trends")
            st.altair_chart(chart, use_container_width=True)

    # --- SUPPLY NOTES TAB ---
    with tab3:
        st.subheader("Send Notes or Supply Requests to HQ")
        note = st.text_area("Type your message or request here")
        if st.button("Send to HQ"):
            insert_supply_request(hub_id, st.session_state.user['username'], note)
            st.success("Sent to HQ!")
        st.write("Your previous messages:")
        notes_df = fetch_all_supply_requests()
        hub_notes = notes_df[notes_df['hub_id'] == hub_id]
        if not hub_notes.empty:
            st.dataframe(hub_notes[["timestamp", "notes"]])

def render_admin_dashboard():
    st.title("🧦 TTT Inventory HQ Admin Dashboard")

    tabs = st.tabs([
        "All Inventory",
        "All Orders/OUT+IN",
        "All Supply Notes/Requests",
        "🧩 Assign/Remove SKUs"
    ])
    
    # Tab 1: All Inventory
    with tabs[0]:
        st.subheader("All Inventory Across Hubs")
        st.dataframe(fetch_all_inventory())

    # Tab 2: All Inventory Actions (Log)
    with tabs[1]:
        st.subheader("All Orders/OUT+IN")
        all_log = pd.read_sql_query(
            "SELECT * FROM inventory_log ORDER BY timestamp DESC",
            get_connection()
        )
        st.dataframe(all_log)
    
    # Tab 3: All Hub Supply Notes/Requests
    with tabs[2]:
        st.subheader("All Hub Messages/Supply Requests")
        st.dataframe(fetch_all_supply_requests())
    
    # Tab 4: Assign or Remove SKUs
    with tabs[3]:
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


# --- LOGIN FLOW ---
if 'user' not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("🧦 Thick Thigh Tribe Inventory Login")
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
