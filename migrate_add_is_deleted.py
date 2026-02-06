from database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE vocabulary ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
            print("Added is_deleted to vocabulary")
        except Exception as e:
            print(f"Skipping vocabulary (might exist): {e}")

if __name__ == "__main__":
    migrate()
