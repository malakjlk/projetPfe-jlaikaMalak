"""
Migré automatiquement par SMAML depuis utils.php
"""

# ── hash_password (score 81.8%, 1 itération(s)) ──
from pydantic import ValidationError
from fastapi import HTTPException
from typing import Optional
import bcrypt

def hash_password(password: str) -> str:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Trop court")
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
