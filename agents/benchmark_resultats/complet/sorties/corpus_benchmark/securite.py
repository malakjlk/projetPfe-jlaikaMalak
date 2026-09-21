"""
Migré automatiquement par SMAML depuis securite.php
"""

# ── get_user (score 86.0%, 1 itération(s)) ──
from pydantic import BaseModel
from sqlalchemy import Column, Integer
from sqlalchemy.ext.declarative import declarative_base
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker
from typing import Optional

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)

class UserResponse(BaseModel):
    id: Optional[int] = None

def get_user(id: int, db_session):
    user = db_session.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    return UserResponse(id=user.id)


# ── generer_rapport (score 77.6%, 2 itération(s)) ──
from subprocess import run
from typing import Optional

def generer_rapport(commande: str) -> str:
    try:
        sortie = run(["report_tool", commande], shell=False, capture_output=True, text=True, timeout=5)
        if sortie.returncode != 0:
            raise RuntimeError(f"Erreur lors de la génération du rapport : {sortie.stderr}")
        return sortie.stdout
    except Exception as e:
        raise RuntimeError(f"Erreur lors de la génération du rapport : {str(e)}")


# ── chercher_produit (score 86.0%, 1 itération(s)) ──
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String
from fastapi import HTTPException

# Configuration de la base de données
SQLALCHEMY_DATABASE_URL = "sqlite:///produits.db"

# Création du moteur de base de données
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Création d'une session de base de données
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Création d'une base de données
Base = declarative_base()

# Modèle de produit
class Produit(Base):
    __tablename__ = "produits"
    nom = Column(String, primary_key=True)

# Création des tables de la base de données
Base.metadata.create_all(bind=engine)

# Modèle Pydantic pour le produit
class ProduitModel(BaseModel):
    nom: str

def chercher_produit(nom: str):
    # Création d'une session de base de données
    db = SessionLocal()
    
    # Requête paramétrée pour éviter les injections SQL
    produits = db.query(Produit).filter(Produit.nom.like(f"%{nom}%")).all()
    
    # Fermeture de la session de base de données
    db.close()
    
    # Renvoi des résultats
    return produits
