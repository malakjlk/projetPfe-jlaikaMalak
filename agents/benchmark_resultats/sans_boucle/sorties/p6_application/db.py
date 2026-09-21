"""
Migré automatiquement par SMAML depuis db.php
"""

# ── get_user_by_email (score 92.0%, 1 itération(s)) ──
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException

class User(BaseModel):
    id: int
    email: str
    password: str

def get_user_by_email(db: Session, email: str):
    user = db.execute(select(User).where(User.email == email)).scalar()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    return user
