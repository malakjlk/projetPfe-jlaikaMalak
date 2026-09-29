"""
Migré automatiquement par SMAML depuis db.php
"""

# ── get_user_by_email (score 97.9%, 1 itération(s)) ──
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models import User  # import du modèle SQLAlchemy déjà présent dans le projet

def get_user_by_email(email: str, db: Session) -> User:
    """
    Récupère un utilisateur à partir de son adresse e‑mail.
    Utilise SQLAlchemy pour éviter toute injection SQL.
    Lève une HTTPException 404 si aucun utilisateur n'est trouvé.
    """
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Utilisateur non trouvé"
        )
    return user
