"""
Migration script to add image_ratings table
"""
from sqlalchemy import create_engine, text

SQLALCHEMY_DATABASE_URL = "sqlite:///./vocab_system_v2.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

def migrate():
    with engine.connect() as conn:
        try:
            # Create image_ratings table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS image_ratings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    course_id INTEGER,
                    vocab_id INTEGER,
                    image_url VARCHAR,
                    rating INTEGER,
                    rated_at DATETIME,
                    question_context VARCHAR,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (course_id) REFERENCES courses (id),
                    FOREIGN KEY (vocab_id) REFERENCES vocabulary (id)
                )
            """))
            conn.commit()
            print("✓ image_ratings 表創建成功")
        except Exception as e:
            print(f"✗ 創建表時發生錯誤: {e}")

if __name__ == "__main__":
    print("開始數據庫遷移：添加 image_ratings 表...")
    migrate()
    print("遷移完成！")
