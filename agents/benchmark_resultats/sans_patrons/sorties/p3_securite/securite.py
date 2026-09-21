"""
Migré automatiquement par SMAML depuis securite.php
"""

# ── get_user (score 86.0%, 1 itération(s)) ──
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from fastapi import HTTPException
from typing import Optional

# Configuration de la base de données
SQLALCHEMY_DATABASE_URL = "sqlite:///example.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modèle de données pour les utilisateurs
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)

# Modèle Pydantic pour les utilisateurs
class UserModel(BaseModel):
    id: Optional[int] = None

def get_user(id: int):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        return user
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ── generer_rapport (score 46.4%, 5 itération(s)) ──
from subprocess import run, PIPE
from typing import Optional

def generer_rapport(commande: str) -> str:
    try:
        sortie = run(["report_tool", commande], stdout=PIPE, stderr=PIPE, check=True)
        return sortie.stdout.decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erreur lors de la génération du rapport")


# ── chercher_produit (score 86.0%, 1 itération(s)) ──
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException
from typing import Optional

from sqlalchemy.orm import Session

class Produit(BaseModel):
    id: int
    nom: str

def chercher_produit(nom: str, db_session: Session):
    try:
        produits = db_session.execute(select(Produit).where(Produit.nom.like(f"%{nom}%"))).all()
        return produits
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Erreur lors de la recherche de produits")
