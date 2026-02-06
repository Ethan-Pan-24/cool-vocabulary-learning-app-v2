import sqlite3
import json

conn = sqlite3.connect('vocab_system_v2.db')
cursor = conn.cursor()
cursor.execute('SELECT id, name, stage_config FROM courses')
for row in cursor.fetchall():
    print(f"ID: {row[0]}, Name: {row[1]}")
    try:
        config = json.loads(row[2])
        print(json.dumps(config, indent=2, ensure_ascii=False))
    except:
        print(f"Raw: {row[2]}")
    print("-" * 20)
conn.close()
