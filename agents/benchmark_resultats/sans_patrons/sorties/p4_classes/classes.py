"""
Migré automatiquement par SMAML depuis classes.php
"""

# ── PanierAchat (score 92.0%, 1 itération(s)) ──
from pydantic import BaseModel
from sqlalchemy import Column, Float, String
from sqlalchemy.ext.declarative import declarative_base
from fastapi import HTTPException
from typing import Optional

Base = declarative_base()

class Article(BaseModel):
    nom: Optional[str] = None
    prix: Optional[float] = None

class PanierAchat:
    def __init__(self):
        self.articles = []
        self.total = 0.0

    def ajouter_article(self, nom: str, prix: float):
        if prix < 0:
            raise HTTPException(status_code=400, detail="Prix negatif")
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
