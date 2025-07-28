import sqlite3

conn = sqlite3.connect("barcodes.db")
cursor = conn.cursor()
cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
conn.commit()
conn.close()
print("✅ Email column added to users table.")
