"""
Migré automatiquement par SMAML depuis login.php
"""

# ── login (score 98.2%, 1 itération(s)) ──
import re
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from db import get_user_by_email
from utils import hash_password


def login(email: str, password: str, db: Session) -> int:
    """
    Authentifie un utilisateur à partir de son email et de son mot de passe.
    Retourne l'identifiant de l'utilisateur si les informations sont valides.
    """
    # validation_format : vérification du format d'email
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email invalide"
        )

    # récupération de l'utilisateur en base (comparaison_authentification)
    user = get_user_by_email(email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects"
        )

    # comparaison du hash du mot de passe fourni avec celui stocké
    if user.password != hash_password(password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects"
        )

    return user.id
