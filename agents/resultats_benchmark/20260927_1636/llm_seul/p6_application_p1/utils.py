"""
Migré automatiquement par SMAML depuis utils.php
"""

# ── hash_password (score 88.2%, 1 itération(s)) ──
from typing import Any
from fastapi import HTTPException, status
from passlib.context import CryptContext

# Contexte de hachage compatible avec le comportement de PHP password_hash (bcrypt par défaut)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """
    Hache le mot de passe en respectant les règles de validation.
    - validation_longueur : le mot de passe doit contenir au moins 8 caractères.
    - hachage_mot_de_passe : le mot de passe n'est jamais retourné en clair.
    """
    if len(password) < 8:
        # Utilisation de HTTPException pour propager l'erreur côté API
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trop court"
        )
    return pwd_context.hash(password)
