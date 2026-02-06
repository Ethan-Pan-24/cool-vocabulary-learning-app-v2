from fastapi import Request, Depends
from sqlalchemy.orm import Session
from database import get_db, User
from utils import ADMIN_EMAILS

async def get_current_user_req(request: Request, db: Session = Depends(get_db)):
    email = request.cookies.get("user_email")
    if not email:
        return None
    user = db.query(User).filter(User.email == email).first()
    if user:
        # Inject is_admin property dynamically for convenience
        user.is_admin = user.email in ADMIN_EMAILS
    return user
