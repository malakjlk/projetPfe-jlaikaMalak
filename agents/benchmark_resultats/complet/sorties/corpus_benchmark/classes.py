"""
Migré automatiquement par SMAML depuis classes.php
"""

# ── PanierAchat (score 92.0%, 1 itération(s)) ──
from pydantic import BaseModel
from typing import Optional
from fastapi import HTTPException

class Article(BaseModel):
    nom: str
    prix: float

class PanierAchat:
    def __init__(self):
        self.articles = []
        self.total = 0.0

    def ajouter_article(self, nom: str, prix: float):
        if prix < 0:
            raise HTTPException(status_code=400, detail="Prix négatif")
        self.articles.append(nom)
        self.total += prix
        return True

    def obtenir_total(self) -> float:
        return self.total


# ── outils_texte (score 92.0%, 1 itération(s)) ──
from fastapi import HTTPException

def majuscules(texte: str) -> str:
    return texte.upper()

def tronquer(texte: str, longueur: int) -> str:
    if longueur < 1:
        raise HTTPException(status_code=400, detail="Longueur invalide")
    return texte[:longueur]
