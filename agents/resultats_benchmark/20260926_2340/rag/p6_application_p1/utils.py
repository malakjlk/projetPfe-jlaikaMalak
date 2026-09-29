"""
Migré automatiquement par SMAML depuis utils.php
"""

# ── hash_password (score 88.2%, 1 itération(s)) ──
import bcrypt
from fastapi import HTTPException, status

def hash_password(password: str) -> str:
    """
    Hache le mot de passe en respectant les contraintes de sécurité.

    - validation_longueur : le mot de passe doit contenir au moins 8 caractères.
    - hachage_mot_de_passe : le mot de passe n'est jamais retourné en clair.
    """
    if len(password) < 8:
        # Utilisation d'une HTTPException pour être cohérent avec le reste de l'API
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trop court"
        )
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")
