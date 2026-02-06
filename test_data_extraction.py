import sys
sys.path.insert(0, 'c:/Users/s0418/Desktop/vocabulary_system')

from database import get_db, QuizResult, User
from sqlalchemy.orm import Session
import traceback
import json

# Create a database session
db = next(get_db())

print("=" * 60)
print("TESTING EFFICIENCY ANALYSIS LOGIC")
print("=" * 60)

try:
    # Get quiz results
    course_id = 1
    results = db.query(QuizResult).filter(
        QuizResult.course_id == course_id,
        QuizResult.is_deleted == False
    ).all()
    
    print(f"\nFound {len(results)} quiz results for course {course_id}")
    
    if len(results) < 2:
        print("ERROR: Insufficient data. Need at least 2 quiz results.")
    else:
        # Extract data
        data_points = []
        for i, result in enumerate(results):
            print(f"\n--- Processing result {i+1} ---")
            print(f"Result ID: {result.id}")
            print(f"User ID: {result.user_id}")
            print(f"Translation score: {result.translation_score}")
            print(f"Sentence score: {result.sentence_score}")
            print(f"NASA TLX score: {result.nasa_tlx_score}")
            print(f"NASA details JSON: {result.nasa_details_json}")
            print(f"Group: {result.group}")
            
            user = db.query(User).filter(User.id == result.user_id).first()
            if not user:
                print(f"WARNING: User {result.user_id} not found!")
                continue
            
            # Calculate quiz score percentage
            total_score = (result.translation_score or 0) + (result.sentence_score or 0)
            max_possible = 200.0
            quiz_score_pct = (total_score / max_possible * 100) if max_possible > 0 else 0
            
            print(f"Quiz score: {quiz_score_pct}%")
            
            # Get NASA mental demand
            nasa_mental = 50
            try:
                nasa_details = json.loads(result.nasa_details_json or "{}")
                nasa_mental = nasa_details.get("mental", 50)
                print(f"NASA mental (from JSON): {nasa_mental}")
            except Exception as e:
                print(f"Error parsing NASA JSON: {e}")
                nasa_mental = result.nasa_tlx_score or 50
                print(f"NASA mental (fallback): {nasa_mental}")
            
            data_points.append({
                "user_id": user.id,
                "name": user.name or f"User {user.id}",
                "group": result.group or "Unknown",
                "quiz_score": quiz_score_pct,
                "nasa_mental": nasa_mental
            })
        
        print(f"\n\nSuccessfully processed {len(data_points)} data points")
        print("Data points:", json.dumps(data_points, indent=2))
        
except Exception as e:
    print(f"\n\nEXCEPTION: {type(e).__name__}")
    print(f"Error: {str(e)}")
    print("\nFull traceback:")
    traceback.print_exc()

finally:
    db.close()

print("\n" + "=" * 60)
