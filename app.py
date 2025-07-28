# TTT Inventory System — HQ Admin Dashboard Cleaned & Validated

# ✅ Features:
# - HQ Admin: SKU assignment/removal
# - Bulk inventory updates (IN/OUT)
# - Internal notification sender

import streamlit as st
import pandas as pd

def render_admin_dashboard(username):
    admin_tabs = st.tabs([
        "All Inventory", "Inventory Charts", "All Supply Requests", "User Management",
        "Notifications", "Messaging", "SKU Assignment", "Bulk Inventory Update", "Send Notification"
    ])

    # --- Notifications ---
    with admin_tabs[4]:
        st.subheader("🔔 Notifications")
        notif_df = fetch_notifications_for_user('admin', st.session_state.user['id'])
        if not notif_df.empty:
            st.dataframe(notif_df)
        else:
            st.info("No notifications yet.")

    # --- Messaging ---
    with admin_tabs[5]:
        render_admin_messages()

    # --- SKU Assignment ---
    with admin_tabs[6]:
        st.subheader("📂 Assign/Remove SKUs for Hubs")
        hubs = fetch_all_hubs()
        hub_map = {row['name']: row['id'] for _, row in hubs.iterrows()}
        all_skus = pd.read_sql_query("SELECT sku, name FROM products ORDER BY name", get_connection())

        if hubs.empty or all_skus.empty:
            st.warning("No hubs or SKUs available.")
        else:
            selected_hub = st.selectbox("Choose Hub", list(hub_map.keys()))
            selected_sku = st.selectbox("Choose SKU to Assign", all_skus['sku'] + " - " + all_skus['name'])
            sku_code = selected_sku.split(" - ")[0]
            if st.button("Assign SKU"):
                try:
                    conn = get_connection()
                    conn.execute("INSERT OR IGNORE INTO hub_skus (sku, hub_id) VALUES (?, ?)", (sku_code, hub_map[selected_hub]))
                    conn.commit()
                    st.success("SKU assigned.")
                except Exception as e:
                    st.error(f"Assign failed: {e}")
                finally:
                    conn.close()

            st.markdown("---")
            st.markdown("### 🔍 Remove SKUs from Hub")
            assigned_skus = pd.read_sql_query("""
                SELECT hs.id, p.sku, p.name FROM hub_skus hs
                JOIN products p ON p.sku = hs.sku
                WHERE hs.hub_id = ? ORDER BY p.name
            """, get_connection(), params=(hub_map[selected_hub],))
            for _, row in assigned_skus.iterrows():
                if st.button(f"Remove {row['name']} ({row['sku']})", key=f"remove_{row['id']}"):
                    try:
                        conn = get_connection()
                        conn.execute("DELETE FROM hub_skus WHERE id = ?", (row['id'],))
                        conn.commit()
                        st.success("SKU removed.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Removal failed: {e}")
                    finally:
                        conn.close()

    # --- Bulk Inventory Update ---
    with admin_tabs[7]:
        st.subheader("📦 Bulk Inventory Transaction")
        hubs = fetch_all_hubs()
        hub_map = {row['name']: row['id'] for _, row in hubs.iterrows()}
        hub = st.selectbox("Choose Hub", list(hub_map.keys()))
        hub_id = hub_map[hub]
        sku_data = fetch_skus_for_hub(hub_id)

        if sku_data:
            st.markdown("### Bulk Entry Table")
            form = st.form("bulk_form")
            df = pd.DataFrame(sku_data, columns=["Name", "SKU", "Barcode"])
            df['Action'] = "IN"
            df['Quantity'] = 0
            edited_df = form.data_editor(df, num_rows="dynamic")
            comment = form.text_input("Optional Comment for all")
            submitted = form.form_submit_button("Submit Bulk Transaction")

            if submitted:
                try:
                    for _, row in edited_df.iterrows():
                        if row['Quantity'] > 0 and row['Action'] in ["IN", "OUT"]:
                            log_inventory(
                                user_id=st.session_state.user['id'],
                                sku=row['SKU'],
                                action=row['Action'],
                                quantity=int(row['Quantity']),
                                hub_id=hub_id,
                                comment=comment
                            )
                    st.success("Bulk inventory update completed.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Bulk update failed: {e}")
        else:
            st.info("No SKUs assigned to this hub.")

    # --- Manual Notification ---
    with admin_tabs[8]:
        st.subheader("📣 Send Notification")
        users = fetch_all_users()
        if users.empty:
            st.info("No users found.")
        else:
            user_options = {f"{row['username']} ({row['role']})": row['id'] for _, row in users.iterrows()}
            selected_user = st.selectbox("Send To User", list(user_options.keys()))
            message = st.text_area("Message")
            if st.button("Send Notification"):
                try:
                    insert_notification(
                        user_role="admin",
                        user_id=user_options[selected_user],
                        message=message
                    )
                    st.success("Notification sent.")
                except Exception as e:
                    st.error(f"Failed to send notification: {e}")

    # -- Placeholder tabs --
    with admin_tabs[0]:
        pass
    with admin_tabs[1]:
        pass
    with admin_tabs[2]:
        pass
    with admin_tabs[3]:
        render_user_management_panel()
