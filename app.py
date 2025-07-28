import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

DB = "barcodes.db"
st.set_page_config(page_title="TTT Inventory", page_icon="🧦", layout="wide")
st.image("https://i.imgur.com/Y7SgqZR.jpeg", width=150)

# --- Simple DB wrapper ---
def db(sql, params=(), df=False):
    conn = sqlite3.connect(DB, check_same_thread=False)
    out = None
    try:
        if df:
            out = pd.read_sql_query(sql, conn, params=params)
        else:
            c = conn.cursor()
            c.execute(sql, params)
            if sql.strip().upper().startswith("SELECT"):
                out = c.fetchall()
            else:
                conn.commit()
    finally:
        conn.close()
    return out

# --- Auth ---
def login(user, pwd):
    r = db("SELECT id, role, hub_id FROM users WHERE username=? AND password=? AND active=1", (user, pwd))
    return r[0] if r else None

# --- Notification fetch: always safe for missing/null user ---
def notifications(role, uid):
    if not uid:
        return pd.DataFrame(columns=["created", "message"])
    return db("SELECT created, message FROM notifications WHERE user_role=? AND user_id=? ORDER BY created DESC", (role, uid), df=True)

# --- User management helpers ---
def users():
    return db("SELECT id, username, email, role, hub_id, active FROM users ORDER BY id", df=True)

def add_user(username, password, email, role, hub_id, active=1):
    db("INSERT INTO users (username, password, email, role, hub_id, active) VALUES (?, ?, ?, ?, ?, ?)", (username, password, email, role, hub_id, active))

def update_user(user_id, username, email, role, hub_id, active):
    db("UPDATE users SET username=?, email=?, role=?, hub_id=?, active=? WHERE id=?", (username, email, role, hub_id, active, user_id))

def deactivate_user(user_id):
    db("UPDATE users SET active=0 WHERE id=?", (user_id,))

def activate_user(user_id):
    db("UPDATE users SET active=1 WHERE id=?", (user_id,))

def hubs():
    return db("SELECT id, name FROM hubs", df=True)

# --- Admin/User panels ---
def user_management():
    st.subheader("👤 User Management")
    df = users()
    hubs_df = hubs()
    hub_map = dict(zip(hubs_df.name, hubs_df.id)) if not hubs_df.empty else {}
    # Add User
    with st.form("add_user_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            username = st.text_input("Username")
            password = st.text_input("Password")
        with c2:
            email = st.text_input("Email")
            role = st.selectbox("Role", ["user", "manager", "admin", "supplier"])
        with c3:
            hub_name = st.selectbox("Assign to Hub", ["None"] + list(hub_map.keys()))
            active = st.checkbox("Active", True)
        submitted = st.form_submit_button("Add User")
        if submitted and username and password:
            hub_id = hub_map.get(hub_name) if hub_name != "None" else None
            add_user(username, password, email, role, hub_id, int(active))
            st.success("User added!")
            st.rerun()
    # List/Edit Users
    for _, row in df.iterrows():
        with st.expander(f"{row['username']} ({row['role']}, {'Active' if row['active'] else 'Inactive'})"):
            c1, c2 = st.columns([3,1])
            with c1:
                newu = st.text_input(f"Username_{row.id}", value=row.username, key=f"u_{row.id}")
                newe = st.text_input(f"Email_{row.id}", value=row.email or "", key=f"e_{row.id}")
                newr = st.selectbox(f"Role_{row.id}", ["user", "manager", "admin", "supplier"], index=["user", "manager", "admin", "supplier"].index(row.role), key=f"r_{row.id}")
                newh = st.selectbox(f"Hub_{row.id}", ["None"] + list(hub_map.keys()), index=(list(hub_map.values()).index(row.hub_id)+1 if row.hub_id in hub_map.values() else 0), key=f"h_{row.id}")
                newa = st.checkbox(f"Active_{row.id}", value=bool(row.active), key=f"a_{row.id}")
            with c2:
                if st.button("Update", key=f"update_{row.id}"):
                    hub_id = hub_map.get(newh) if newh != "None" else None
                    update_user(row.id, newu, newe, newr, hub_id, int(newa))
                    st.success("User updated.")
                    st.rerun()
                if row.active and st.button("Deactivate", key=f"deactivate_{row.id}"):
                    deactivate_user(row.id)
                    st.warning("User deactivated.")
                    st.rerun()
                elif not row.active and st.button("Activate", key=f"activate_{row.id}"):
                    activate_user(row.id)
                    st.success("User activated.")
                    st.rerun()

def admin_panel():
    st.title("🧦 HQ Admin Dashboard")
    st.write("You are logged in as HQ Admin.")
    # Notifications
    n = notifications("admin", st.session_state.u["id"])
    st.subheader("🔔 Notifications")
    if not n.empty:
        st.dataframe(n)
    else:
        st.info("No notifications yet.")
    # User management
    user_management()

# --- Simple login logic ---
if 'u' not in st.session_state:
    st.session_state.u = None

if not st.session_state.u:
    st.title("🧦 TTT Inventory Login")
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        s = st.form_submit_button("Login")
        if s:
            res = login(u, p)
            if res:
                st.session_state.u = {"id": res[0], "role": res[1], "hub_id": res[2], "username": u}
                st.rerun()
            else:
                st.error("❌ Invalid username or password")
else:
    st.sidebar.success(f"Logged in as: {st.session_state.u['username']} ({st.session_state.u['role']})")
    if st.sidebar.button("Logout"):
        st.session_state.u = None
        st.rerun()
    if st.session_state.u["role"] == "admin":
        admin_panel()
    else:
        st.write("Standard hub/manager/supplier dashboard goes here...")
