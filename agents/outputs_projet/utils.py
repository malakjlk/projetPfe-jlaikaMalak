"""
Migré automatiquement par SMAML depuis utils.php
"""

# ── validate_password (score 97.2%, 1 itération(s)) ──
from fastapi import HTTPException, status


def validate_password(password: str) -> bool:
    """
    Vérifie que le mot de passe fourni respecte la contrainte de longueur minimale.
    Lève une HTTPException 400 si la validation échoue.
    """
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe trop court"
        )
    return True


# ── sanitize_input (score 100.0%, 1 itération(s)) ──
from markupsafe import escape
from typing import AnyStr

def sanitize_input(data: AnyStr) -> str:
    """
    Assainit la donnée d'entrée en échappant les caractères spéciaux HTML.
    Equivalent de PHP `htmlspecialchars`.
    """
    return escape(data)
