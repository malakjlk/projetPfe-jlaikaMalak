"""
Migré automatiquement par SMAML depuis validation.php
"""

# ── validate_password (score 98.2%, 1 itération(s)) ──
import re
from fastapi import HTTPException, status

def validate_password(password: str) -> bool:
    """
    Valide un mot de passe selon les règles métier.
    - Au moins 8 caractères.
    - Contient au moins une majuscule.
    Lève une HTTPException avec le code 422 (Unprocessable Entity) en cas d'erreur.
    """
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mot de passe trop court"
        )
    # Vérification du format : présence d'au moins une majuscule
    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Majuscule requise"
        )
    return True


# ── valider_email (score 98.0%, 1 itération(s)) ──
import re
from fastapi import HTTPException

def valider_email(email: str) -> bool:
    """
    Valide le format d'une adresse e‑mail.
    Lève une HTTPException 400 si le format est invalide.
    Retourne True lorsque l'e‑mail est valide.
    """
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise HTTPException(status_code=400, detail='Email invalide')
    return True


# ── valider_age (score 98.2%, 1 itération(s)) ──
from fastapi import HTTPException

def valider_age(age) -> bool:
    """
    Valide que l'âge fourni est numérique et supérieur ou égal à 18.
    Accepte les int, float et les chaînes représentant des nombres,
    conformément au comportement de PHP `is_numeric`.
    """
    # Conversion du paramètre pour accepter les chaînes numériques comme PHP le fait
    if isinstance(age, str):
        try:
            age = float(age) if ('.' in age or 'e' in age.lower()) else int(age)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique')
    elif not isinstance(age, (int, float)):
        # Tout autre type (ex: None, bool, list…) n'est pas considéré comme numérique
        raise HTTPException(status_code=400, detail='Valeur non numérique')

    # Vérification de la borne minimale
    if age < 18:
        raise HTTPException(status_code=400, detail='Doit être majeur')

    return True
