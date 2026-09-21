"""
Migré automatiquement par SMAML depuis calculs.php
"""

# ── diviser (score 88.4%, 1 itération(s)) ──
from pydantic import BaseModel
from fastapi import HTTPException

def diviser(a: float, b: float) -> float:
    if b == 0:
        raise HTTPException(status_code=400, detail="Division par zero")
    return a / b


# ── formater_prix (score 87.2%, 1 itération(s)) ──
from pydantic import BaseModel
from fastapi import HTTPException

def formater_prix(montant: float) -> str:
    if not isinstance(montant, (int, float)):
        raise HTTPException(status_code=400, detail="Montant invalide")
    return f"{montant:.2f} EUR"


# ── calculer_remise (score 90.8%, 1 itération(s)) ──
from pydantic import ValidationError
from fastapi import HTTPException

def calculer_remise(prix: float, pourcentage: float) -> float:
    if pourcentage < 0 or pourcentage > 100:
        raise HTTPException(status_code=400, detail="Pourcentage invalide")
    return prix - (prix * pourcentage / 100)
