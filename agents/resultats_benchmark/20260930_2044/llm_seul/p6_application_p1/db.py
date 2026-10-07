"""
Migré automatiquement par SMAML depuis db.php
"""

# ── get_user_by_email (score 82.0%, 1 itération(s)) ──
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

# Import du modèle SQLAlchemy déjà présent dans le projet
from models import User  # le modèle doit contenir au moins les colonnes `id` et `password`

# Modèle de réponse Pydantic strict
class UserOut(BaseModel):
    id: int
    password: str


def get_user_by_email(db: Session, email: str) -> UserOut:
    """
    Récupère un utilisateur à partir de son adresse e‑mail en utilisant SQLAlchemy
    avec une requête paramétrée afin d'éviter toute injection SQL.
    """
    stmt = select(User).where(User.email == email)
    result = db.execute(stmt).scalar_one_or_none()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    # On ne retourne que les champs nécessaires (id, password)
    return UserOut(id=result.id, password=result.password)
