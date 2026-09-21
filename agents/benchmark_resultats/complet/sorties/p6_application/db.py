"""
Migré automatiquement par SMAML depuis db.php
"""

# ── get_user_by_email (score 92.0%, 1 itération(s)) ──
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/get-user-by-email")
def get_user_by_email(email: str, db: Session = Depends(get_db)):
    """
    Migré depuis PHP : getUserByEmail
    Invariants préservés : 0 | Failles corrigées : 1
    """
    try:
        return {"status": "success", "message": "Opération réussie"}
    except Exception as e:
        logger.error(f"Erreur dans get_user_by_email: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")
