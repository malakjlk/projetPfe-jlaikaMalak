"""
Migré automatiquement par SMAML depuis login.php
"""

# ── login (score 98.2%, 1 itération(s)) ──
import re
from fastapi import HTTPException
from sqlalchemy.orm import Session

from db import get_user_by_email  # fonction existante attend (email, db)
from utils import hash_password   # fonction existante pour hacher le mot de passe


def login(email: str, password: str, db: Session) -> int:
    """
    Authentifie un utilisateur à partir de son email et de son mot de passe.

    - Validation du format d'email (pattern simple, pas de Pydantic).
    - Recherche de l'utilisateur en base via la fonction partagée `get_user_by_email`.
    - Comparaison du hash du mot de passe fourni avec celui stocké.
    - Retourne l'identifiant de l'utilisateur en cas de succès.
    """
    # validation_format
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise HTTPException(status_code=400, detail='Email invalide')

    # récupération de l'utilisateur (comparaison_authentification)
    user = get_user_by_email(email, db)
    if not user:
        raise HTTPException(status_code=401, detail='Identifiants incorrects')

    if user.password != hash_password(password):
        raise HTTPException(status_code=401, detail='Identifiants incorrects')

    return user.id
