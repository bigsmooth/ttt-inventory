import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import altair as alt

DB = "barcodes.db"
st.set_page_config("TTT Inventory System", "🧦", layout="wide")
st.image("https://i.imgur.com/Y7SgqZR.jpeg", width=150)

def db(sql, params=(), df=False):
    conn = sqlite3.connect(DB, check_same_thread=False)
    if df:
        out = pd.read_sql_query(sql, conn, params=params)
    else:
        cur = conn.cursor(); cur.execute(sql, params)
        out = cur.fetchall()
        conn.commit()
    conn.close()
    return out

def login(u, p):
    r = db("SELECT id, role, hub_id FROM users WHERE username=? AND password=? AND active=1",(u,p))
    return r[0] if r else None

def add_log(uid, sku, act, qty, hub, cmt):
    db("INSERT INTO inventory_log (timestamp,sku,action,quantity,hub,user_id,comment) VALUES(?,?,?,?,?,?,?)",
        (datetime.now(),sku,act,qty,hub,uid,cmt))

def hub_skus(hub): 
    return db("SELECT p.name, p.sku FROM hub_skus hs JOIN products p ON hs.sku=p.sku WHERE hs.hub_id=? ORDER BY p.name",(hub,),df=1)

def hub_inventory(hub):
    return db("""
      SELECT p.name, p.sku,
      SUM(CASE WHEN il.action='IN' THEN il.quantity ELSE 0 END)-
      SUM(CASE WHEN il.action='OUT' THEN il.quantity ELSE 0 END) as Stock
      FROM hub_skus hs
      JOIN products p ON hs.sku=p.sku
      LEFT JOIN inventory_log il ON hs.sku=il.sku AND il.hub=?
      WHERE hs.hub_id=?
      GROUP BY p.name, p.sku
      ORDER BY p.name
    """, (hub,hub), df=1)

def history(hub):
    return db("""
      SELECT sku, date(timestamp) as date,
      SUM(CASE WHEN action='OUT' THEN quantity ELSE 0 END) as total_out
      FROM inventory_log WHERE hub=? GROUP BY sku, date
      ORDER BY date
    """, (hub,), df=1)

def all_inventory():
    return db("""
      SELECT h.name as Hub, p.name as Product, p.sku,
      SUM(CASE WHEN il.action='IN' THEN il.quantity ELSE 0 END)-
      SUM(CASE WHEN il.action='OUT' THEN il.quantity ELSE 0 END) as Stock
      FROM inventory_log il
      JOIN products p ON il.sku=p.sku
      JOIN hubs h ON il.hub=h.id
      GROUP BY h.name, p.name, p.sku
      ORDER BY h.name, p.name
    """, df=1)

def notifications(role, uid):
    return db("SELECT created, message FROM notifications WHERE user_role=? AND user_id=? ORDER BY created DESC", (role, uid), df=1)

def assign_sku(sku, hub): db("INSERT OR IGNORE INTO hub_skus (sku, hub_id) VALUES (?,?)", (sku, hub))
def remove_sku(sku, hub): db("DELETE FROM hub_skus WHERE sku=? AND hub_id=?", (sku, hub))
def add_user(u,p,e,r,h,a=1): db("INSERT INTO users (username,password,email,role,hub_id,active) VALUES(?,?,?,?,?,?)",(u,p,e,r,h,a))
def update_user(uid,u,e,r,h,a): db("UPDATE users SET username=?,email=?,role=?,hub_id=?,active=? WHERE id=?",(u,e,r,h,a,uid))
def activate(uid): db("UPDATE users SET active=1 WHERE id=?", (uid,))
def deactivate(uid): db("UPDATE users SET active=0 WHERE id=?", (uid,))

def user_panel():
    tabs = st.tabs(["Inventory", "Trends", "Add", "Notifications"])
    inv = hub_inventory(st.session_state.u["hub_id"])
    skus = hub_skus(st.session_state.u["hub_id"])
    sku_opts = {f"{r['name']} ({r['sku']})":r['sku'] for _,r in skus.iterrows()}
    with tabs[0]:
        st.dataframe(inv)
    with tabs[1]:
        hist = history(st.session_state.u["hub_id"])
        if not hist.empty: st.altair_chart(alt.Chart(hist).mark_line().encode(x='date:T',y='total_out:Q',color='sku:N'), use_container_width=True)
        else: st.info("No OUT transactions.")
    with tabs[2]:
        sel = st.selectbox("SKU", list(sku_opts))
        act = st.radio("Action", ["IN","OUT"])
        qty = st.number_input("Qty", 1, step=1)
        cmt = st.text_input("Comment")
        if st.button("Submit"):
            add_log(st.session_state.u["id"], sku_opts[sel], act, qty, st.session_state.u["hub_id"], cmt)
            st.success("Recorded."); st.rerun()
    with tabs[3]:
        n = notifications("hub", st.session_state.u["id"])
        st.dataframe(n if not n.empty else pd.DataFrame(columns=["created","message"]))

def admin_panel():
    tabs = st.tabs(["All Inventory","Logs","SKUs","Users","Notifications"])
    with tabs[0]:
        inv = all_inventory(); st.dataframe(inv)
        st.download_button("Download CSV", inv.to_csv(index=False), "all_inventory.csv")
    with tabs[1]:
        logs = db("SELECT * FROM inventory_log ORDER BY timestamp DESC", df=1); st.dataframe(logs)
    with tabs[2]:
        hubs = db("SELECT id,name FROM hubs", df=1)
        prods = db("SELECT sku,name FROM products ORDER BY name", df=1)
        hmap = dict(zip(hubs.name,hubs.id)); pmap = dict(zip(prods.name,prods.sku))
        hub = st.selectbox("Hub", list(hmap))
        prod = st.selectbox("Product", list(pmap))
        if st.button("Assign SKU"): assign_sku(pmap[prod], hmap[hub]); st.success("Assigned."); st.rerun()
        if st.button("Remove SKU"): remove_sku(pmap[prod], hmap[hub]); st.warning("Removed."); st.rerun()
        st.dataframe(hub_skus(hmap[hub]))
    with tabs[3]:
        users = db("SELECT * FROM users ORDER BY id", df=1)
        for idx,row in users.iterrows():
            with st.expander(f"{row['username']} ({row['role']})"):
                u = st.text_input(f"Username_{row['id']}",row['username']); e = st.text_input(f"Email_{row['id']}",row['email'] or "")
                r = st.selectbox(f"Role_{row['id']}",["user","manager","admin","supplier"],index=["user","manager","admin","supplier"].index(row['role']))
                h = st.number_input(f"HubID_{row['id']}",value=row['hub_id'] or 0)
                a = st.checkbox(f"Active_{row['id']}",value=bool(row['active']))
                if st.button("Update",key=f"upd_{row['id']}"): update_user(row['id'],u,e,r,h,int(a)); st.success("Updated."); st.rerun()
                if row['active'] and st.button("Deactivate",key=f"de_{row['id']}"): deactivate(row['id']); st.rerun()
                elif not row['active'] and st.button("Activate",key=f"ac_{row['id']}"): activate(row['id']); st.rerun()
    with tabs[4]:
        n = notifications("admin", st.session_state.u["id"])
        st.dataframe(n if not n.empty else pd.DataFrame(columns=["created","message"]))

# --- LOGIN ---
if "u" not in st.session_state: st.session_state.u = None
if not st.session_state.u:
    st.title("🧦 TTT Inventory Login")
    with st.form("login"):
        u = st.text_input("Username"); p = st.text_input("Password",type="password")
        if st.form_submit_button("Login"):
            res = login(u,p)
            if res: st.session_state.u = dict(id=res[0],role=res[1],hub_id=res[2],username=u); st.rerun()
            else: st.error("❌ Invalid username or password")
else:
    st.sidebar.success(f"Logged in: {st.session_state.u['username']} ({st.session_state.u['role']})")
    if st.sidebar.button("Logout"): st.session_state.clear(); st.rerun()
    if st.session_state.u["role"] == "admin": admin_panel()
    else: user_panel()
