"""
Migré automatiquement par SMAML depuis utils.php
"""

# ── hash_password (score 55.6%, 5 itération(s)) ──
from fastapi import HTTPException
from validation import validate_password

def hash_password(password: str) -> str:
    if not validate_password(password):
        raise HTTPException(status_code=400, detail="Trop court")
    # Utilisation de la fonction hashpw du module hashlib pour simuler le comportement de password_hash
    import hashlib
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), b'salt', 100000).hex()
