"""
Migré automatiquement par SMAML depuis utilisateurs.php
"""

# ── User (score 92.0%, 1 itération(s)) ──
from pydantic import BaseModel
from typing import Optional

class UserBase(BaseModel):
    nom: Optional[str] = None
    email: Optional[str] = None

class User:
    def __init__(self, nom: Optional[str] = None, email: Optional[str] = None):
        self.nom = nom
        self.email = email

    def obtenir_nom(self) -> Optional[str]:
        return self.nom


# ── Admin (score 92.0%, 1 itération(s)) ──
from pydantic import BaseModel
from fastapi import HTTPException

class Admin(User):
    def __init__(self):
        super().__init__()

    def bannir_utilisateur(self, id: str) -> bool:
        if len(id) < 1:
            raise HTTPException(status_code=400, detail="ID invalide")
        return True


# ── SuperAdmin (score 92.0%, 1 itération(s)) ──
from fastapi import HTTPException

class SuperAdmin(Admin):
    def __init__(self):
        super().__init__()

    def supprimer_compte(self, id):
        if isinstance(id, str):
            try:
                id = float(id) if ('.' in id or 'e' in id.lower()) else int(id)
            except ValueError:
                raise HTTPException(status_code=400, detail='ID non numérique')
        if not isinstance(id, (int, float)):
            raise HTTPException(status_code=400, detail='ID non numérique')
        return True
