import sqlite3
from datetime import datetime

conn = sqlite3.connect('vocab_system_v2.db')
cursor = conn.cursor()

try:
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS image_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            course_id INTEGER,
            image_url VARCHAR,
            vocab_id INTEGER,
            action VARCHAR,
            timestamp DATETIME,
            context VARCHAR,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (course_id) REFERENCES courses (id),
            FOREIGN KEY (vocab_id) REFERENCES vocabulary (id)
        )
    ''')
    print("Table 'image_interactions' created successfully.")
except sqlite3.Error as e:
    print(f"Error creating table: {e}")

conn.commit()
conn.close()
