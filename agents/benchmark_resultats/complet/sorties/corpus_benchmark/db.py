"""
Migré automatiquement par SMAML depuis db.php
"""

# ── get_user_by_email (score 92.0%, 1 itération(s)) ──
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from fastapi import HTTPException
from typing import Optional

# Définition du modèle de données
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String)
    password = Column(String)

# Création d'une session pour la base de données
engine = create_engine('sqlite:///database.db')
Session = sessionmaker(bind=engine)
session = Session()

class UserModel(BaseModel):
    id: Optional[int] = None
    email: Optional[str] = None
    password: Optional[str] = None

def get_user_by_email(email: str) -> UserModel:
    try:
        user = session.query(User).filter(User.email == email).first()
        if user:
            return UserModel(id=user.id, email=user.email, password=user.password)
        else:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
