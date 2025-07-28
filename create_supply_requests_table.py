import sqlite3

DB_FILE = "barcodes.db"

conn = sqlite3.connect(DB_FILE)
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

conn.commit()
conn.close()

print("✅ supply_requests table created.")
