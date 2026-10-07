"""
Migré automatiquement par SMAML depuis login.php
"""

# ── login (score 98.2%, 1 itération(s)) ──
import re
from fastapi import HTTPException
from sqlalchemy.orm import Session

from db import get_user_by_email  # fonction existante du projet
from utils import hash_password   # fonction existante du projet


def login(email: str, password: str, db: Session) -> int:
    """
    Authentifie un utilisateur à partir de son email et de son mot de passe.
    Retourne l'identifiant de l'utilisateur si les vérifications réussissent.
    """
    # validation_format : vérification du format d'email (sans Pydantic)
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise HTTPException(status_code=400, detail='Email invalide')

    # récupération de l'utilisateur en base (comparaison_authentification)
    user = get_user_by_email(email, db)
    if not user:
        raise HTTPException(status_code=401, detail='Identifiants incorrects')

    # comparaison du mot de passe hashé
    if user.password != hash_password(password):
        raise HTTPException(status_code=401, detail='Identifiants incorrects')

    return user.id
