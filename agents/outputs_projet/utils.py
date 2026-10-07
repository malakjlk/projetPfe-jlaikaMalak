"""
Migré automatiquement par SMAML depuis utils.php
"""

# ── hash_password (score 88.2%, 1 itération(s)) ──
import bcrypt
from fastapi import HTTPException, status

def hash_password(password: str) -> str:
    """
    Hache le mot de passe en respectant les règles de validation.

    - validation_longueur : le mot de passe doit contenir au moins 8 caractères.
    - hachage_mot_de_passe : le mot de passe n'est jamais retourné en clair.
    """
    if len(password) < 8:
        # Utilisation d'une exception HTTP pour être cohérente avec le reste du projet
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trop court"
        )
    # Génération d'un sel bcrypt sécurisé
    salt = bcrypt.gensalt()
    # Hachage du mot de passe et décodage en chaîne UTF‑8
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
    return hashed
