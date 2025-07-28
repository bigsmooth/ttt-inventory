import sqlite3

conn = sqlite3.connect("barcodes.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    sku TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    barcode TEXT
)
""")

conn.commit()
conn.close()

print("✅ products table is ready.")
