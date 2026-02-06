import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import Base, User, Course, QuizResult, Vocabulary, Enrollment, SessionLocal
import json

db = SessionLocal()

print("--- DEBUGGING USER DATA ---")

# Get most recent result
result = db.query(QuizResult).order_by(QuizResult.submitted_at.desc()).first()

if result:
    print(f"Result ID: {result.id}, User ID: {result.user_id}, Course ID: {result.course_id}")
    print(f"Stored Group: {result.group}")
    print("\n--- RAW TIMINGS (stage_timing_json) ---")
    print(result.stage_timing_json)
    
    # Get Course Config
    course = db.query(Course).filter(Course.id == result.course_id).first()
    if course:
        print("\n--- COURSE CONFIG (stage_config) ---")
        print(course.stage_config)
        
        try:
            config = json.loads(course.stage_config)
            print("\nParsed Config Structure:", type(config))
            if isinstance(config, dict):
                print("Keys:", config.keys())
                # Check group config
                group_conf = config.get(result.group, config.get("Common", []))
                print(f"Config for Group '{result.group}':")
                for idx, item in enumerate(group_conf):
                    print(f"  Index {idx}: {item}")
        except Exception as e:
            print("Error parsing config:", e)

else:
    print("No results found.")
