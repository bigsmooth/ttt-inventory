import sqlite3
import os
from datetime import datetime

# Load session
session_file = "session.txt"
if not os.path.exists(session_file):
    print("❌ No active session. Please login first using login.py.")
    exit()

with open(session_file, "r") as f:
    lines = f.readlines()
    session = {line.split(":")[0].strip(): line.split(":")[1].strip() for line in lines if ":" in line}

user_id = int(session.get("user_id"))
username = session.get("username")
role = session.get("role")
hub_id = session.get("hub_id")

conn = sqlite3.connect("barcodes.db")
cursor = conn.cursor()

# Fetch hub name
cursor.execute("SELECT name FROM hubs WHERE id = ?", (hub_id,))
hub_name_result = cursor.fetchone()
hub_name = hub_name_result[0] if hub_name_result else "Unknown Hub"

print(f"\n🏬 You are logged in as: {username} ({role})")
if role == "user":
    print(f"🔒 You are restricted to your hub: {hub_name} (ID: {hub_id})")
else:
    # Admin can choose hub
    cursor.execute("SELECT id, name FROM hubs")
    hubs = cursor.fetchall()
    print("\n🏬 Available Hubs:")
    for hub in hubs:
        print(f"{hub[0]}: {hub[1]}")
    try:
        hub_id = int(input("\n🏷️ Enter Hub ID: ").strip())
    except ValueError:
        print("❌ Invalid hub ID.")
        conn.close()
        exit()
    # Update hub name after input
    cursor.execute("SELECT name FROM hubs WHERE id = ?", (hub_id,))
    hub_name_result = cursor.fetchone()
    hub_name = hub_name_result[0] if hub_name_result else "Unknown Hub"

# SKU input
sku = input("\n🔢 Enter SKU: ").strip().upper()

# Enforce SKU assignment
cursor.execute("SELECT 1 FROM hub_skus WHERE hub_id = ? AND sku = ?", (hub_id, sku))
if not cursor.fetchone():
    print(f"❌ SKU '{sku}' is not assigned to your hub ({hub_name}).")
    conn.close()
    exit()

# IN/OUT Action
action = input("⬆️⬇️ Action (IN or OUT): ").strip().upper()
if action not in ["IN", "OUT"]:
    print("❌ Invalid action. Must be 'IN' or 'OUT'.")
    conn.close()
    exit()

# Quantity
try:
    qty = int(input("🔁 Quantity: ").strip())
except ValueError:
    print("❌ Quantity must be a number.")
    conn.close()
    exit()

# Log inventory
timestamp = datetime.now()
cursor.execute(
    "INSERT INTO inventory_log (timestamp, sku, action, quantity, hub, user_id) VALUES (?, ?, ?, ?, ?, ?)",
    (timestamp, sku, action, qty, hub_id, user_id)
)
conn.commit()
print(f"✅ Inventory action logged for {sku} by {username} at {hub_name}.")

conn.close()
