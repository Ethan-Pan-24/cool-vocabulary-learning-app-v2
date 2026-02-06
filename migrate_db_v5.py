from sqlalchemy import create_engine, text
from database import URSQLALCHEMY_DATABASE_URL

engine = create_engine(URSQLALCHEMY_DATABASE_URL)

def run_migration():
    with engine.connect() as conn:
        print("Migrating Database v5...")
        
        # 1. Add custom_distractors to vocabulary
        try:
            conn.execute(text("ALTER TABLE vocabulary ADD COLUMN custom_distractors VARCHAR"))
            print("Added custom_distractors to vocabulary")
        except Exception as e:
            print(f"Skipped vocabulary update: {e}")
            
        # 2. Add nasa_details_json to quiz_results
        try:
            conn.execute(text("ALTER TABLE quiz_results ADD COLUMN nasa_details_json TEXT"))
            print("Added nasa_details_json to quiz_results")
        except Exception as e:
            print(f"Skipped quiz_results update: {e}")
            
        print("Migration v5 completed.")

if __name__ == "__main__":
    run_migration()
