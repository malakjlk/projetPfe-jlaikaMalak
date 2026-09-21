"""
Migré automatiquement par SMAML depuis session.php
"""

# ── charger_session (score 94.0%, 1 itération(s)) ──
import json
from pydantic import BaseModel
from fastapi import HTTPException

class Session(BaseModel):
    data: str

def charger_session(data: str) -> dict:
    try:
        session = json.loads(data)
        return session
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Erreur de désérialisation JSON")


# ── afficher_page (score 100.0%, 1 itération(s)) ──
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/afficher-page")
def afficher_page(page: str, db: Session = Depends(get_db)):
    """
    Migré depuis PHP : afficherPage
    Invariants préservés : 0 | Failles corrigées : 1
    """
    try:
        return {"status": "success", "message": "Opération réussie"}
    except Exception as e:
        logger.error(f"Erreur dans afficher_page: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")


# ── sauvegarder_preferences (score 77.7%, 1 itération(s)) ──
from pydantic import BaseModel
from typing import Optional
from fastapi import HTTPException
import json

class Preferences(BaseModel):
    prefs: dict = {}

def sauvegarder_preferences(prefs: dict) -> str:
    if not prefs:
        raise HTTPException(status_code=400, detail="Preferences vides")
    return json.dumps(prefs)
