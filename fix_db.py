
import sqlite3
import os

DB_FILE = "vocab_system_v2.db"

def migrate_db():
    if not os.path.exists(DB_FILE):
        print(f"Database {DB_FILE} not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(vocabulary)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "display_order" not in columns:
            print("Adding display_order column...")
            cursor.execute("ALTER TABLE vocabulary ADD COLUMN display_order INTEGER DEFAULT 0")
            conn.commit()
            print("Migration successful.")
        else:
            print("Column display_order already exists.")
            
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_db()
