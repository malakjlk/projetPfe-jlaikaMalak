"""
Migré automatiquement par SMAML depuis utilisateurs.php
"""

# ── User (score 92.0%, 1 itération(s)) ──
from pydantic import BaseModel
from typing import Optional

class User(BaseModel):
    nom: Optional[str] = None
    email: Optional[str] = None

    def obtenir_nom(self) -> str:
        return self.nom


# ── Admin (score 92.0%, 1 itération(s)) ──
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional

class Admin(User):
    def __init__(self):
        super().__init__()

    def bannir_utilisateur(self, id: str) -> bool:
        if len(id) < 1:
            raise HTTPException(status_code=400, detail="ID invalide")
        return True


# ── SuperAdmin (score 92.0%, 1 itération(s)) ──
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional

class SuperAdmin(Admin):
    def __init__(self):
        super().__init__()

    def supprimer_compte(self, id: int) -> bool:
        if not isinstance(id, int):
            raise HTTPException(status_code=400, detail="ID non numérique")
        return True
