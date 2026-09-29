"""
Migré automatiquement par SMAML depuis db.php
"""

# ── get_user_by_email (score 0.0%, 1 itération(s)) ──
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models import User  # import du modèle SQLAlchemy déjà présent dans le projet

def get_user_by_email(email: str, db: Session) -> User:
    """
    Récupère un utilisateur à partir de son adresse e‑mail.
    Utilise l'ORM SQLAlchemy pour éviter toute injection SQL.
    """
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Utilisateur non trouvé"
        )
    return user

#                  afin de conserver un comportement explicite pour les appelants.
