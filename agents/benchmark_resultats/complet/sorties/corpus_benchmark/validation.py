"""
Migré automatiquement par SMAML depuis validation.php
"""

# ── validate_password (score 92.0%, 1 itération(s)) ──
import re
from fastapi import HTTPException

def validate_password(password: str) -> bool:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Mot de passe trop court")
    if not re.match(r".*[A-Z].*", password):
        raise HTTPException(status_code=400, detail="Majuscule requise")
    return True


# ── valider_email (score 92.0%, 1 itération(s)) ──
import re
from fastapi import HTTPException

def valider_email(email: str) -> bool:
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise HTTPException(status_code=400, detail='Email invalide')
    return True


# ── valider_age (score 88.4%, 1 itération(s)) ──
from pydantic import BaseModel
from fastapi import HTTPException

def valider_age(age: int) -> bool:
    if not isinstance(age, int):
        raise HTTPException(status_code=400, detail="Age non numérique")
    if age < 18:
        raise HTTPException(status_code=400, detail="Doit être majeur")
    return True
