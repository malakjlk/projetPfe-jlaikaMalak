"""
Migré automatiquement par SMAML depuis db.php
"""

# ── get_user_by_email (score 97.9%, 1 itération(s)) ──
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

# Supposons que le modèle SQLAlchemy User est déjà défini ailleurs dans le projet.
# Nous l'importons avec son nom exact.
from models import User  # <-- le module et le nom exact doivent exister dans le projet


def get_user_by_email(email: str, db: Session) -> Optional[User]:
    """
    Récupère un utilisateur à partir de son adresse e‑mail.

    - Utilise SQLAlchemy avec des requêtes paramétrées pour éviter les injections SQL.
    - Lève une HTTPException 404 si aucun utilisateur n'est trouvé.
    - Retourne l'instance ORM `User` contenant au minimum les champs `id` et `password`
      (exigence des appelants).
    """
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'adresse e‑mail doit être fournie."
        )

    stmt = select(User).where(User.email == email)
    result = db.execute(stmt).scalar_one_or_none()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé."
        )
    return result


# SMAML-HYPOTHÈSE: le modèle `User` possède déjà les attributs `id`, `email` et `password`.
