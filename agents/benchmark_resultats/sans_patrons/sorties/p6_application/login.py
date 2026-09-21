"""
Migré automatiquement par SMAML depuis login.php
"""

# ── login (score 76.0%, 1 itération(s)) ──
from pydantic import EmailStr
from fastapi import HTTPException
from db import get_user_by_email
from utils import hash_password
from typing import Optional

def login(email: EmailStr, password: str) -> int:
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=400, detail="Email invalide")
    if user["password"] != hash_password(password):
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    return user["id"]
