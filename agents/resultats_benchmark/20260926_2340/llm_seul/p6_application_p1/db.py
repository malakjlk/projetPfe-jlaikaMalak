"""
Migré automatiquement par SMAML depuis db.php
"""

# ── get_user_by_email (score 100.0%, 1 itération(s)) ──
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound

# Supposons que le modèle SQLAlchemy User est déjà défini ailleurs dans le projet.
# Nous l'importons avec son nom exact.
from models import User  # type: ignore  # SMAML-HYPOTHESE: le module contenant le modèle s'appelle «models»

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """
    Récupère l'utilisateur dont l'adresse e‑mail correspond à *email*.

    Cette fonction utilise SQLAlchemy avec des requêtes paramétrées afin d'éviter
    toute injection SQL. Elle renvoie l'instance ORM ``User`` contenant au moins
    les champs ``id`` et ``password`` attendus par les appelants.

    Args:
        db: Session SQLAlchemy active.
        email: Adresse e‑mail recherchée.

    Returns:
        L'objet ``User`` correspondant ou ``None`` si aucun enregistrement n'est trouvé.
    """
    try:
        # Utilisation d'une requête ORM sécurisée, sans concaténation de chaînes.
        user = db.query(User).filter(User.email == email).one()
        return user
    except NoResultFound:
        # Aucun utilisateur trouvé → on retourne None (ou on pourrait lever HTTPException 404).
        return None
