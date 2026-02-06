import sqlite3
import json

# Connect to database
conn = sqlite3.connect('vocab_system_v2.db')
cursor = conn.cursor()

# Check quiz results
print("=" * 60)
print("CHECKING QUIZ RESULTS DATA")
print("=" * 60)

# Total count
cursor.execute('SELECT COUNT(*) FROM quiz_results WHERE is_deleted = 0')
total = cursor.fetchone()[0]
print(f"\nTotal quiz results: {total}")

# By course
cursor.execute('''
    SELECT course_id, COUNT(*) as count
    FROM quiz_results 
    WHERE is_deleted = 0 
    GROUP BY course_id
''')
by_course = cursor.fetchall()
print(f"\nBy course: {by_course}")

# Check if results have required fields
cursor.execute('''
    SELECT 
        id,
        user_id,
        course_id,
        translation_score,
        sentence_score,
        nasa_tlx_score,
        nasa_details_json,
        "group"
    FROM quiz_results 
    WHERE is_deleted = 0 
    LIMIT 5
''')

results = cursor.fetchall()
print(f"\nSample quiz results (first 5):")
print("ID | UserID | CourseID | Trans_Score | Sent_Score | NASA_TLX | NASA_JSON | Group")
print("-" * 100)
for r in results:
    json_preview = (r[6][:20] + "...") if r[6] else "None"
    print(f"{r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {json_preview} | {r[7]}")

conn.close()
print("\n" + "=" * 60)
