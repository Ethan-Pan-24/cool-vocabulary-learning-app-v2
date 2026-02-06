from database import SessionLocal, Vocabulary

db = SessionLocal()
try:
    num = db.query(Vocabulary).delete()
    db.commit()
    print(f"Deleted {num} vocabulary items.")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
