"""
Migré automatiquement par SMAML depuis utils.php
"""

# ── hash_password (score 88.2%, 1 itération(s)) ──
from typing import AnyStr
from fastapi import HTTPException, status
import bcrypt

def hash_password(password: AnyStr) -> str:
    """
    Hache le mot de passe en respectant les invariants de sécurité.

    - validation_longueur : le mot de passe doit contenir au moins 8 caractères.
    - hachage_mot_de_passe : le mot de passe est retourné sous forme de hash bcrypt.
    """
    # Vérification de la longueur minimale (invariant validation_longueur)
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trop court"
        )

    # bcrypt attend des bytes ; on encode si nécessaire
    if isinstance(password, str):
        password_bytes = password.encode("utf-8")
    else:
        password_bytes = password

    # Génération du sel et du hash (invariant hachage_mot_de_passe)
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())

    # Retourner le hash sous forme de chaîne décodable
    return hashed.decode("utf-8")
