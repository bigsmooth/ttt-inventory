import sqlite3

DB_FILE = "barcodes.db"

def add_comment_column():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Check if the column already exists
    cursor.execute("PRAGMA table_info(inventory_log);")
    columns = [col[1] for col in cursor.fetchall()]

    if "comment" not in columns:
        cursor.execute("ALTER TABLE inventory_log ADD COLUMN comment TEXT;")
        conn.commit()
        print("✅ 'comment' column added to inventory_log.")
    else:
        print("ℹ️ 'comment' column already exists.")

    conn.close()

if __name__ == "__main__":
    add_comment_column()
