from sqlalchemy import create_engine, text
from database import URSQLALCHEMY_DATABASE_URL

def migrate():
    engine = create_engine(URSQLALCHEMY_DATABASE_URL)
    with engine.connect() as conn:
        try:
            # Add section_stats column
            conn.execute(text("ALTER TABLE quiz_results ADD COLUMN section_stats TEXT DEFAULT '{}'"))
            print("Added section_stats column.")
        except Exception as e:
            print(f"Column might already exist: {e}")

if __name__ == "__main__":
    migrate()
