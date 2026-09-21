"""
Migré automatiquement par SMAML depuis classes.php
"""

# ── PanierAchat (score 92.0%, 1 itération(s)) ──
from pydantic import BaseModel
from fastapi import HTTPException

class PanierAchat:
    def __init__(self):
        self.articles = []
        self.total = 0

    def ajouter_article(self, nom: str, prix: str):
        if isinstance(prix, str):
            try:
                prix = float(prix) if ('.' in prix or 'e' in prix.lower()) else int(prix)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
        if prix < 0:
            raise HTTPException(status_code=400, detail='Prix négatif')
        self.articles.append(nom)
        self.total += prix
        return True

    def obtenir_total(self) -> float:
        return self.total


# ── outils_texte (score 92.0%, 1 itération(s)) ──
from fastapi import HTTPException
from typing import Optional

def majuscules(texte: str) -> str:
    return texte.upper()

def tronquer(texte: str, longueur: str) -> str:
    if isinstance(longueur, str):
        try:
            longueur = float(longueur) if ('.' in longueur or 'e' in longueur.lower()) else int(longueur)
        except ValueError:
            raise HTTPException(status_code=400, detail='Longueur non numérique')
    if longueur < 1:
        raise HTTPException(status_code=400, detail='Longueur invalide')
    return texte[:int(longueur)]
