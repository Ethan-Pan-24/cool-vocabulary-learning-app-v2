from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import sys
import os

# Ensure current directory is in path
sys.path.append(os.getcwd())

# Database URL
DATABASE_URL = "sqlite:///./vocab_system_v2.db"

def migrate():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("Running migration: Add 'attempt' column to quiz_results...")

    try:
        # Check if column exists
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(quiz_results)"))
            columns = [row[1] for row in result.fetchall()]
            
            if "attempt" in columns:
                print("Column 'attempt' already exists. Skipping.")
            else:
                print("Adding 'attempt' column...")
                conn.execute(text("ALTER TABLE quiz_results ADD COLUMN attempt INTEGER DEFAULT 1"))
                print("Column added successfully.")
                
                # Update existing records to have attempt = 1
                # (Ideally we would calculate based on timestamp but for migration 1 is safe default)
                # Actually, if we want to be smarter:
                # Group by user_id, course_id and order by submitted_at -> assign 1, 2, 3...
                # But SQLite update with join/row_number is complex.
                # Let's just set all to 1 for now as legacy data is likely single attempt.
                conn.execute(text("UPDATE quiz_results SET attempt = 1 WHERE attempt IS NULL"))
                conn.commit()
                print("Existing records updated.")

    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    migrate()
