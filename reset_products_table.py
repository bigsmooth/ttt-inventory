import sqlite3

conn = sqlite3.connect("barcodes.db")
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS products")
conn.commit()
conn.close()

print("✅ Old 'products' table dropped.")
