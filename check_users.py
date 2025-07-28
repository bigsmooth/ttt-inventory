import sqlite3

conn = sqlite3.connect("barcodes.db")
cursor = conn.cursor()

cursor.execute("SELECT id, username, password, role, hub_id FROM users")
rows = cursor.fetchall()

print("\n📋 Current users in the database:\n")
for row in rows:
    print(f"ID: {row[0]}, Username: {row[1]}, Password: {row[2]}, Role: {row[3]}, Hub: {row[4]}")

conn.close()
