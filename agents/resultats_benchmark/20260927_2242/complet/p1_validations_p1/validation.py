"""
Migré automatiquement par SMAML depuis validation.php
"""

# ── validate_password (score 0.0%, 1 itération(s)) ──
import re
from fastapi import HTTPException, status

def validate_password(password: str) -> bool:
    """
    Valide un mot de passe selon les règles métier.
    - Longueur minimale de 8 caractères.
    - Au moins une majuscule.
    Lève une HTTPException avec le code 422 en cas d'erreur.
    """
    # validation_longueur
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mot de passe trop court"
        )
    # validation_format (majuscule)
    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Majuscule requise"
        )
    return True


# ── valider_email (score 0.0%, 1 itération(s)) ──



# ── valider_age (score 0.0%, 1 itération(s)) ──

