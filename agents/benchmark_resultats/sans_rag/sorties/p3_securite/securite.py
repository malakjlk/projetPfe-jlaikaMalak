"""
Migré automatiquement par SMAML depuis securite.php
"""

# ── get_user (score 86.0%, 1 itération(s)) ──
from pydantic import BaseModel
from sqlalchemy import Column, Integer
from sqlalchemy.ext.declarative import declarative_base
from fastapi import HTTPException
from typing import Optional

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)

class UserResponse(BaseModel):
    id: Optional[int] = None

def get_user(id: int):
    try:
        user = User.query.filter(User.id == id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return UserResponse(id=user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── generer_rapport (score 77.6%, 2 itération(s)) ──
from subprocess import run
from typing import Optional

def generer_rapport(commande: str) -> str:
    try:
        sortie = run(["report_tool", commande], shell=False, capture_output=True, text=True, timeout=5)
        if sortie.returncode != 0:
            raise RuntimeError(f"Erreur d'exécution de la commande : {sortie.stderr}")
        return sortie.stdout
    except Exception as e:
        raise RuntimeError(f"Erreur lors de la génération du rapport : {str(e)}")


# ── chercher_produit (score 86.0%, 1 itération(s)) ──
from pydantic import BaseModel
from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base
from fastapi import HTTPException
from typing import Optional

Base = declarative_base()

class Produit(Base):
    __tablename__ = 'produits'
    nom = Column(String)

class ProduitModel(BaseModel):
    nom: Optional[str] = None

def chercher_produit(nom: str):
    try:
        produit = Produit.__table__.select().where(Produit.__table__.c.nom.like(f'%{nom}%')).execute().fetchall()
        return produit
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
