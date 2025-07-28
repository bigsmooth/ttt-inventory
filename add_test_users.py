import sqlite3

conn = sqlite3.connect("barcodes.db")
cursor = conn.cursor()

# Add admin user (if doesn't already exist)
cursor.execute("INSERT OR IGNORE INTO users (username, password, role, hub_id) VALUES (?, ?, ?, ?)",
               ("admin", "admin123", "admin", 1))

# Add hub manager (user role)
cursor.execute("INSERT OR IGNORE INTO users (username, password, role, hub_id) VALUES (?, ?, ?, ?)",
               ("hub2mgr", "hub2pass", "user", 2))

conn.commit()
conn.close()
print("✅ Test users added.")
