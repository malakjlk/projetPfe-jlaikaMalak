"""
Migré automatiquement par SMAML depuis utils.php
"""

# ── hash_password (score 88.2%, 1 itération(s)) ──
from typing import AnyStr
from fastapi import HTTPException, status
import bcrypt

def hash_password(password: AnyStr) -> str:
    """
    Hache le mot de passe en respectant les contraintes de sécurité.

    - validation_longueur : le mot de passe doit contenir au moins 8 caractères.
    - hachage_mot_de_passe : le mot de passe est retourné sous forme de hash bcrypt.
    """
    if len(password) < 8:
        # On utilise HTTPException pour être cohérent avec la gestion d'erreurs du projet
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trop court"
        )
    # bcrypt attend des bytes ; on encode si nécessaire
    pwd_bytes = password.encode() if isinstance(password, str) else password
    hashed = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt())
    return hashed.decode()  # on renvoie une chaîne de caractères
