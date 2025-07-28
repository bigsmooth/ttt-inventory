import sqlite3

conn = sqlite3.connect("barcodes.db")
cursor = conn.cursor()

# Add columns for admin response if not already there
try:
    cursor.execute("ALTER TABLE supply_requests ADD COLUMN response TEXT")
    cursor.execute("ALTER TABLE supply_requests ADD COLUMN admin TEXT")
except sqlite3.OperationalError:
    pass  # Ignore if already added

# Create shipments table
cursor.execute("""
    CREATE TABLE IF NOT EXISTS shipments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date DATETIME,
        supplier TEXT,
        tracking TEXT,
        hub_id INTEGER,
        product TEXT,
        amount INTEGER
    )
""")
conn.commit()
conn.close()
print("DB updated.")
