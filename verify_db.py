import sqlite3

conn = sqlite3.connect('vocab_system_v2.db')
cursor = conn.cursor()

def check_table(table_name):
    print(f"\nColumns in {table_name}:")
    cursor.execute(f"PRAGMA table_info({table_name})")
    for col in cursor.fetchall():
        print(f" - {col[1]} ({col[2]})")

check_table('courses')
check_table('quiz_results')
check_table('vocabulary')

conn.close()
