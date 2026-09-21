"""
Migré automatiquement par SMAML depuis login.php
"""

# ── login (score 92.0%, 1 itération(s)) ──
from fastapi import HTTPException
import re
from db import get_user_by_email
from utils import hash_password

def login(email: str, password: str) -> int:
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise HTTPException(status_code=400, detail='Email invalide')
    user = get_user_by_email(email, password)
    if user is None or user["password"] != hash_password(password):
        raise HTTPException(status_code=401, detail='Identifiants incorrects')
    return user["id"]
