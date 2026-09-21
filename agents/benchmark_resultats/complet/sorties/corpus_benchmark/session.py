"""
Migré automatiquement par SMAML depuis session.php
"""

# ── charger_session (score 86.0%, 1 itération(s)) ──
import json
from fastapi import HTTPException

def charger_session(data: str) -> dict:
    try:
        session = json.loads(data)
        return session
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Erreur de désérialisation")


# ── afficher_page (score 92.0%, 1 itération(s)) ──
from fastapi import HTTPException
import json

def afficher_page(page: str):
    try:
        with open(page + ".json", "r") as fichier:
            contenu = json.load(fichier)
            return contenu
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Page non trouvée")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Erreur de désérialisation")


# ── sauvegarder_preferences (score 77.7%, 1 itération(s)) ──
from pydantic import BaseModel
from typing import Optional
from json import JSONDecodeError, dumps, loads
from fastapi import HTTPException

class Preferences(BaseModel):
    prefs: dict = {}

def sauvegarder_preferences(prefs: dict) -> str:
    if not prefs:
        raise HTTPException(status_code=400, detail="Preferences vides")
    return dumps(prefs)
