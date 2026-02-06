from database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE vocabulary ADD COLUMN stage VARCHAR DEFAULT 'Unassigned'"))
            print("Successfully added 'stage' column to vocabulary table.")
        except Exception as e:
            print(f"Migration failed (might already exist): {e}")

if __name__ == "__main__":
    migrate()
