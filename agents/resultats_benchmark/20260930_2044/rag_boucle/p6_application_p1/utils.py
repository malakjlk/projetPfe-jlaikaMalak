"""
Migré automatiquement par SMAML depuis utils.php
"""

# ── hash_password (score 88.2%, 1 itération(s)) ──
from fastapi import HTTPException, status
import bcrypt

def hash_password(password: str) -> str:
    """
    Hache le mot de passe en respectant la contrainte de longueur minimale.
    """
    if len(password) < 8:
        # La validation de longueur (validation_longueur) échoue
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trop court"
        )
    # hachage_mot_de_passe : le mot de passe n'est jamais retourné en clair
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
