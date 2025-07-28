import sqlite3

conn = sqlite3.connect("barcodes.db")
cursor = conn.cursor()

# Add email column if it doesn't exist
cursor.execute("PRAGMA table_info(users)")
columns = [col[1] for col in cursor.fetchall()]
if "email" not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
    print("✅ Added 'email' column to users table.")
else:
    print("ℹ️ 'email' column already exists.")

# Add any other columns your app needs (add more as you go)
# Example: comment column to inventory_log table
cursor.execute("PRAGMA table_info(inventory_log)")
columns = [col[1] for col in cursor.fetchall()]
if "comment" not in columns:
    cursor.execute("ALTER TABLE inventory_log ADD COLUMN comment TEXT")
    print("✅ Added 'comment' column to inventory_log table.")
else:
    print("ℹ️ 'comment' column already exists.")

conn.commit()
conn.close()
print("🚀 DB upgrade complete.")
