import sqlite3

conn = sqlite3.connect("barcodes.db")
c = conn.cursor()

# Add columns if they don't exist
try:
    c.execute("ALTER TABLE users ADD COLUMN email TEXT")
except sqlite3.OperationalError:
    pass

try:
    c.execute("ALTER TABLE users ADD COLUMN active INTEGER DEFAULT 1")
except sqlite3.OperationalError:
    pass

conn.commit()
conn.close()
print("✅ Users table upgraded!")
