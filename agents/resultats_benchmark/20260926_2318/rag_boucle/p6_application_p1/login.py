"""
Migré automatiquement par SMAML depuis login.php
"""

# ── login (score 98.2%, 1 itération(s)) ──
import re
from fastapi import HTTPException
from sqlalchemy.orm import Session

from db import get_user_by_email
from utils import hash_password


def login(email: str, password: str, db: Session) -> int:
    """
    Authentifie un utilisateur à partir de son email et de son mot de passe.

    - Vérifie le format de l'email.
    - Récupère l'utilisateur en base via `get_user_by_email`.
    - Compare le hash du mot de passe fourni avec celui stocké.
    - Retourne l'identifiant de l'utilisateur en cas de succès.
    """
    # validation_format
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise HTTPException(status_code=400, detail='Email invalide')

    # récupération de l'utilisateur (get_user_by_email attend deux arguments)
    user = get_user_by_email(email, db)
    if not user:
        raise HTTPException(status_code=401, detail='Identifiants incorrects')

    # comparaison_authentification
    if user.password != hash_password(password):
        raise HTTPException(status_code=401, detail='Identifiants incorrects')

    return user.id
