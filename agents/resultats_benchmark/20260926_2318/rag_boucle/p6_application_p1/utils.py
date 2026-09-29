"""
Migré automatiquement par SMAML depuis utils.php
"""

# ── hash_password (score 88.2%, 1 itération(s)) ──
from fastapi import HTTPException, status
import bcrypt

def hash_password(password: str) -> str:
    """
    Hache le mot de passe en respectant les règles de validation.

    - validation_longueur : le mot de passe doit contenir au moins 8 caractères.
    - hachage_mot_de_passe : le mot de passe est retourné sous forme de hash bcrypt.
    """
    if len(password) < 8:
        # Utilisation d'une exception HTTP pour être cohérente avec le reste de l'API.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trop court"
        )
    # Génération d'un sel bcrypt sécurisé puis hachage du mot de passe.
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
    return hashed
