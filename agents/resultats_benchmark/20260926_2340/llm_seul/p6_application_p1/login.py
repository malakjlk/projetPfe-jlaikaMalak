"""
Migré automatiquement par SMAML depuis login.php
"""

# ── login (score 98.2%, 1 itération(s)) ──
import re
from fastapi import HTTPException
from db import get_user_by_email
from utils import hash_password

def login(email: str, password: str) -> int:
    """
    Authentifie un utilisateur à partir de son email et de son mot de passe.
    Retourne l'identifiant de l'utilisateur si les informations sont valides.
    """
    # validation_format
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise HTTPException(status_code=400, detail='Email invalide')

    # get_user_by_email attend deux arguments (email, db_session)
    user = get_user_by_email(email, None)

    if not user:
        raise HTTPException(status_code=401, detail='Identifiants incorrects')

    # comparaison_authentification
    if user["password"] != hash_password(password):
        raise HTTPException(status_code=401, detail='Identifiants incorrects')

    return user["id"]
