from database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE courses ADD COLUMN stage_config TEXT DEFAULT '[]'"))
            print("Added stage_config to courses")
        except Exception as e:
            print(f"Skipping courses (might exist): {e}")

        try:
            conn.execute(text("ALTER TABLE quiz_results ADD COLUMN stage_timing_json TEXT DEFAULT '{}'"))
            print("Added stage_timing_json to quiz_results")
        except Exception as e:
            print(f"Skipping quiz_results (might exist): {e}")

if __name__ == "__main__":
    migrate()
