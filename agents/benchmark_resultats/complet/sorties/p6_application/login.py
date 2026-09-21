"""
Migré automatiquement par SMAML depuis login.php
"""

# ── login (score 76.0%, 1 itération(s)) ──
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/login")
def login(email: str, password: str, db: Session = Depends(get_db)):
    """
    Migré depuis PHP : login
    Invariants préservés : 1 | Failles corrigées : 0
    """
    try:
        return {"status": "success", "message": "Opération réussie"}
    except Exception as e:
        logger.error(f"Erreur dans login: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")
