import sqlite3

def migrate():
    conn = sqlite3.connect("vocab_system_v2.db")
    cursor = conn.cursor()

    try:
        # Add quiz_config column to courses table
        # It will store JSON string, default empty list "[]"
        print("Adding quiz_config column to courses table...")
        cursor.execute("ALTER TABLE courses ADD COLUMN quiz_config TEXT DEFAULT '[]'")
        print("Success.")
    except sqlite3.OperationalError as e:
        print(f"Column might already exist: {e}")
    except Exception as e:
        print(f"Error: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
