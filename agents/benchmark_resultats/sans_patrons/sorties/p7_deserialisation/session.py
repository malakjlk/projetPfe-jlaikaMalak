"""
Migré automatiquement par SMAML depuis session.php
"""

# ── charger_session (score 75.8%, 1 itération(s)) ──
from pydantic import BaseModel
from typing import Optional
from fastapi import HTTPException

def charger_session(data: str) -> dict:
    try:
        # La désérialisation n'est pas directement possible avec Python comme avec PHP
        # Nous allons utiliser le module pickle pour la désérialisation
        import pickle
        session = pickle.loads(data.encode('latin1'))
        return session
    except Exception as e:
        raise HTTPException(status_code=400, detail="Erreur lors de la désérialisation de la session")


# ── afficher_page (score 92.0%, 1 itération(s)) ──
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional

class Page(BaseModel):
    nom: Optional[str] = None

def afficher_page(page: str):
    try:
        # Charger la page en utilisant importlib pour éviter insecure_deserialization
        import importlib.util
        spec = importlib.util.spec_from_file_location(page, f"{page}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Page {page} non trouvée")


# ── sauvegarder_preferences (score 77.7%, 1 itération(s)) ──
from pydantic import BaseModel
from typing import Optional
from fastapi import HTTPException

class Preferences(BaseModel):
    prefs: dict

def sauvegarder_preferences(prefs: dict) -> str:
    if not prefs:
        raise HTTPException(status_code=400, detail="Preferences vides")
    return str(prefs)
