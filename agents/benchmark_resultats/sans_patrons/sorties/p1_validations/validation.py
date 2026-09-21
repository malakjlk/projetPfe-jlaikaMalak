"""
Migré automatiquement par SMAML depuis validation.php
"""

# ── validate_password (score 92.0%, 1 itération(s)) ──
from pydantic import ValidationError
from fastapi import HTTPException
from typing import Optional

def validate_password(password: str) -> bool:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Mot de passe trop court")
    if not any(char.isupper() for char in password):
        raise HTTPException(status_code=400, detail="Majuscule requise")
    return True


# ── valider_email (score 76.0%, 2 itération(s)) ──
from pydantic import EmailStr
from fastapi import HTTPException

def valider_email(email: str) -> bool:
    try:
        email_valid = EmailStr.validate(email)
        return True
    except ValueError:
        raise HTTPException(status_code=400, detail="Email invalide")


# ── valider_age (score 88.4%, 1 itération(s)) ──
from pydantic import BaseModel
from fastapi import HTTPException

class Age(BaseModel):
    age: int

def valider_age(age: int) -> bool:
    if not isinstance(age, int):
        raise HTTPException(status_code=400, detail="Age non numérique")
    if age < 18:
        raise HTTPException(status_code=400, detail="Doit être majeur")
    return True
