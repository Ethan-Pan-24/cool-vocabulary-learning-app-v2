import sqlite3

conn = sqlite3.connect('vocab_system_v2.db')
cursor = conn.cursor()

try:
    cursor.execute('ALTER TABLE courses ADD COLUMN quiz_time_limit INTEGER DEFAULT 5')
    print("Column 'quiz_time_limit' added successfully.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("Column 'quiz_time_limit' already exists.")
    else:
        print(f"Error: {e}")

conn.commit()
conn.close()
