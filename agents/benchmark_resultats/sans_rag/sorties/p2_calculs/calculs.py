"""
Migré automatiquement par SMAML depuis calculs.php
"""

# ── diviser (score 92.0%, 1 itération(s)) ──
from pydantic import BaseModel
from fastapi import HTTPException

def diviser(a, b):
    if isinstance(a, str):
        try:
            a = float(a) if ('.' in a or 'e' in a.lower()) else int(a)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique pour a')
    if isinstance(b, str):
        try:
            b = float(b) if ('.' in b or 'e' in b.lower()) else int(b)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique pour b')
    if b == 0:
        raise HTTPException(status_code=400, detail='Division par zero')
    return a / b


# ── formater_prix (score 92.0%, 1 itération(s)) ──
from pydantic import BaseModel
from fastapi import HTTPException

def formater_prix(montant):
    if isinstance(montant, str):
        try:
            montant = float(montant) if ('.' in montant or 'e' in montant.lower()) else int(montant)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique')
    return f"{montant:,.2f} EUR"


# ── calculer_remise (score 92.0%, 1 itération(s)) ──
from pydantic import BaseModel
from fastapi import HTTPException

def calculer_remise(prix: str, pourcentage: str) -> float:
    if isinstance(prix, str):
        try:
            prix = float(prix) if ('.' in prix or 'e' in prix.lower()) else int(prix)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique pour le prix')
            
    if isinstance(pourcentage, str):
        try:
            pourcentage = float(pourcentage) if ('.' in pourcentage or 'e' in pourcentage.lower()) else int(pourcentage)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique pour le pourcentage')
            
    if pourcentage < 0 or pourcentage > 100:
        raise HTTPException(status_code=400, detail='Pourcentage invalide')
        
    return prix - (prix * pourcentage / 100)
