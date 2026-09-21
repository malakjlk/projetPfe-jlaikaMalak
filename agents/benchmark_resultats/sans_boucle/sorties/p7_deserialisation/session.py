"""
Migré automatiquement par SMAML depuis session.php
"""

# ── charger_session (score 90.8%, 1 itération(s)) ──
import json
from pydantic import BaseModel
from fastapi import HTTPException

class Session(BaseModel):
    data: dict = None

def charger_session(data: str) -> Session:
    try:
        session_data = json.loads(data)
        return Session(data=session_data)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Erreur de désérialisation JSON")


# ── afficher_page (score 92.0%, 1 itération(s)) ──
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional

class Page(BaseModel):
    nom: Optional[str] = None

def afficher_page(page: str):
    try:
        # Ici, vous devriez importer le module correspondant à la page
        # Puisqu'on ne peut pas inclure directement un fichier PHP dans Python,
        # nous allons simuler l'inclusion en important un module Python
        # qui correspond à la page demandée.
        # Pour cela, vous devriez avoir un système de mapping entre les noms
        # de pages PHP et les noms de modules Python.
        # Ici, nous allons juste simuler cela avec un exemple.
        if page == "exemple":
            from exemple import afficher_exemple
            afficher_exemple()
        else:
            raise HTTPException(status_code=404, detail="Page non trouvée")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erreur interne")


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
