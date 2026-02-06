from database import engine, Base
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        try:
            # Check if column exists
            result = conn.execute(text("PRAGMA table_info(quiz_results)"))
            columns = [row[1] for row in result.fetchall()]
            
            if "is_deleted" not in columns:
                print("Adding 'is_deleted' column to quiz_results...")
                conn.execute(text("ALTER TABLE quiz_results ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
                print("Column added successfully.")
            else:
                print("'is_deleted' column already exists.")
                
        except Exception as e:
            print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
