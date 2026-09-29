"""
Migré automatiquement par SMAML depuis db.php
"""

# ── connect_database (score 97.6%, 1 itération(s)) ──
import logging
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException

logger = logging.getLogger(__name__)

def connect_database() -> "Engine":
    """
    Crée et retourne un moteur SQLAlchemy connecté à la base de données MySQL.
    En cas d'échec, lève une HTTPException 503 (Service Unavailable) afin
    de remplacer le comportement `die()` de PHP.
    """
    host = "localhost"
    user = "root"
    password = ""
    database = "users_db"

    # Construction de l'URL de connexion SQLAlchemy
    url = f"mysql+pymysql://{user}:{password}@{host}/{database}"

    try:
        engine = create_engine(url, future=True)
        # Test de connexion immédiat
        with engine.connect() as conn:
            pass
        return engine
    except SQLAlchemyError as exc:
        logger.critical("Erreur connexion DB : %s", exc)
        # Remplace `die("Erreur connexion DB")` par une exception HTTP
        raise HTTPException(status_code=503, detail="Service unavailable")


# ── get_user_by_email (score 97.9%, 2 itération(s)) ──
from fastapi import HTTPException
from sqlalchemy.orm import Session

# Le modèle SQLAlchemy représentant la table `users` doit être importé depuis le module où il est défini.
# Ici on suppose qu'il s'appelle `User` et qu'il possède au moins les champs `email` et `password`.
from models import User  # type: ignore  # SMAML-HYPOTHESE: le modèle s'appelle bien `User` dans le projet


def get_user_by_email(email: str, db: Session):
    """
    Récupère un utilisateur à partir de son adresse e‑mail.

    Utilise l'ORM SQLAlchemy avec des filtres paramétrés afin d'éviter toute injection SQL.
    Lève une HTTPException 404 si aucun utilisateur n'est trouvé.
    Retourne l'instance SQLAlchemy `User`, qui inclut le champ `password` requis par les appelants.
    """
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Utilisateur non trouvé"
        )
    return user

# elle ne crée pas de connexion elle‑même, conformément à l'instruction d'utiliser `connect_database()`
# directement dans le contexte appelant si nécessaire.
