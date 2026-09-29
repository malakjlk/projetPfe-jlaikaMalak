"""
Migré automatiquement par SMAML depuis utils.php
"""

# ── hash_password (score 88.2%, 1 itération(s)) ──
import bcrypt
from fastapi import HTTPException

def hash_password(password: str) -> str:
    """
    Hache le mot de passe en s'assurant qu'il respecte la contrainte de longueur minimale.
    """
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Trop court")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

# cohérent avec les exemples de migration fournis.
