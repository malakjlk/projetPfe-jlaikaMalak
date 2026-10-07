"""
Migré automatiquement par SMAML depuis includes/db.php
"""

# ── get_user_by_email (score 99.2%, 2 itération(s)) ──
import os
from typing import Optional, Dict, Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, ResultProxy

# Connexion à la base de données (créée une fois, réutilisée par les appels suivants)
_DB_URL = os.getenv("DB_URL", "mysql+pymysql://user:password@localhost/dbname")
_engine: Optional[Engine] = None


def _get_engine() -> Engine:
    """Retourne l'engine SQLAlchemy partagé."""
    global _engine
    if _engine is None:
        _engine = create_engine(_DB_URL, future=True)
    return _engine


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Récupère un utilisateur à partir de son adresse e‑mail.

    Args:
        email: Adresse e‑mail recherchée.

    Returns:
        Un dictionnaire contenant les colonnes de l'utilisateur (au moins
        ``id`` et ``password``) si l'utilisateur existe, sinon ``None``.

    Exceptions:
        - ``ConnectionError`` : problème lors de la connexion ou de l'exécution
          de la requête.
        - ``ValueError`` : e‑mail fourni vide ou invalide.
    """
    if not email:
        raise ValueError("L'adresse e‑mail ne doit pas être vide")

    engine = _get_engine()
    query = text("SELECT * FROM users WHERE email = :email LIMIT 1")

    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"email": email})
            row = result.fetchone()
            if row is None:
                return None
            # Convertit le RowProxy en dict ordinaire
            return dict(row._mapping)
    except Exception as exc:
        # On encapsule toute erreur d'accès DB dans une exception métier
        raise ConnectionError(f"Erreur lors de la récupération de l'utilisateur par e‑mail: {exc}") from exc


# on crée un engine partagé via une variable d'environnement.
# mais ne lève jamais ``HTTPException`` afin de respecter la séparation des
# couches (couche d'accès aux données vs couche API).
