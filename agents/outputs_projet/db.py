"""
Migré automatiquement par SMAML depuis db.php
"""

# ── connect_database (score 94.0%, 1 itération(s)) ──
from typing import Any
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from fastapi import HTTPException, status

def connect_database() -> Engine:
    """
    Initialise une connexion à la base de données MySQL en utilisant SQLAlchemy.
    Lève une HTTPException avec le statut 500 si la connexion échoue,
    remplaçant le `die()` de PHP.
    """
    host: str = "localhost"
    user: str = "root"
    password: str = ""
    database: str = "users_db"

    # Construction de l'URL de connexion SQLAlchemy
    url: str = f"mysql+pymysql://{user}:{password}@{host}/{database}"

    try:
        engine: Engine = create_engine(url, echo=False, future=True)
        # Test rapide de la connexion
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return engine
    except Exception as exc:
        # En cas d'échec, on lève une exception HTTP 500 au lieu de `die()`
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur connexion DB"
        ) from exc


# ── get_user_by_email (score 67.1%, 3 itération(s)) ──
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# La fonction connect_database() est déjà définie dans ce même fichier (db.py)
# Elle doit retourner une instance de Session SQLAlchemy.

def get_user_by_email(email: str) -> Dict[str, Any]:
    """
    Récupère l'utilisateur dont l'adresse e‑mail correspond à *email*.
    Retourne un dictionnaire contenant les colonnes de la table `users`,
    incluant notamment le champ `password` requis par les appelants.
    """
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'e‑mail fourni est vide."
        )

    try:
        db: Session = connect_database()          # connexion déjà fournie
        # Utilisation d'une requête paramétrée via l'ORM pour éviter toute injection SQL
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur non trouvé."
            )
        # Conversion de l'objet ORM en dictionnaire brut
        return {
            "id": user.id,
            "email": user.email,
            "password": user.password,
            # Ajoutez d'autres champs si nécessaire
        }
    except SQLAlchemyError as exc:
        # Gestion générique des erreurs de base de données
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur lors de la récupération de l'utilisateur."
        ) from exc
