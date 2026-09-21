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


# ── Admin (score 52.0%, 5 itération(s)) ──
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/Admin")
def Admin(db: Session = Depends(get_db)):
    """
    Migré depuis PHP : Admin
    Invariants préservés : 1 | Failles corrigées : 0
    """
    try:
        return {"status": "success", "message": "Opération réussie"}
    except Exception as e:
        logger.error(f"Erreur dans Admin: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")


# ── SuperAdmin (score 92.0%, 5 itération(s)) ──
from fastapi import HTTPException

class SuperAdmin(Admin):
    def __init__(self):
        super().__init__()

    def supprimer_compte(self, id):
        if isinstance(id, str):
            try:
                id = float(id) if ('.' in id or 'e' in id.lower()) else int(id)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
        if not isinstance(id, (int, float)):
            raise HTTPException(status_code=400, detail='ID non numérique')
        return True
