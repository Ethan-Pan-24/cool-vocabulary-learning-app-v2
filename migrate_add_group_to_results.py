from database import engine, Base
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        try:
            # Check if column exists
            result = conn.execute(text("PRAGMA table_info(quiz_results)"))
            columns = [row[1] for row in result.fetchall()]
            
            if "group" not in columns:
                print("Adding 'group' column to quiz_results...")
                conn.execute(text("ALTER TABLE quiz_results ADD COLUMN 'group' VARCHAR"))
                print("Column added successfully.")
            else:
                print("'group' column already exists.")
                
            # Optional: Backfill group for existing records?
            # Existing records rely on Enrollment. We can leave them NULL and handle in code (fallback)
            # or try to backfill. Simple fallback is safer.
            
        except Exception as e:
            print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
