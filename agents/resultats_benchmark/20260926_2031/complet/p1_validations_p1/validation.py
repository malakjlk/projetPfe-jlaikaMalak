"""
Migré automatiquement par SMAML depuis validation.php
"""

# ── validate_password (score 86.2%, 1 itération(s)) ──
import re
from fastapi import HTTPException, status

def validate_password(password: str) -> bool:
    """
    Valide un mot de passe selon les règles métier.
    - Longueur minimale de 8 caractères.
    - Au moins une majuscule.
    Lève une HTTPException avec le code 422 en cas d'erreur.
    """
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mot de passe trop court"
        )
    # Vérification de la présence d'au moins une majuscule via expression régulière
    if not re.match(r".*[A-Z].*", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Majuscule requise"
        )
    return True


# ── valider_email (score 80.2%, 1 itération(s)) ──
import re
from fastapi import HTTPException

def valider_email(email: str) -> bool:
    """
    Valide le format d'une adresse e‑mail.
    Lève une HTTPException 400 si le format est invalide.
    Retourne True si l'e‑mail est valide.
    """
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise HTTPException(status_code=400, detail='Email invalide')
    return True

#                 pourrait devoir être adaptée si elle est appelée hors d'une route API.


# ── valider_age (score 80.2%, 1 itération(s)) ──
from fastapi import HTTPException

def valider_age(age) -> bool:
    """
    Valide que l'âge fourni est numérique et supérieur ou égal à 18.
    Accepte les int, float ou les chaînes numériques (ex: "42", "3.14").
    """
    # Conversion du paramètre pour reproduire le comportement is_numeric de PHP
    if isinstance(age, str):
        try:
            age = float(age) if ('.' in age or 'e' in age.lower()) else int(age)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique')
    elif not isinstance(age, (int, float)):
        # Tout autre type (ex: None, list, dict) n'est pas accepté
        raise HTTPException(status_code=400, detail='Valeur non numérique')

    # Vérification de l'intervalle (âge minimum)
    if age < 18:
        raise HTTPException(status_code=400, detail='Doit être majeur')
    
    return True

#                  car le code PHP original ne le spécifiait pas.
