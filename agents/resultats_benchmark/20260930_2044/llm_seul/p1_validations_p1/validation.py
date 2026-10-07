"""
Migré automatiquement par SMAML depuis validation.php
"""

# ── validate_password (score 98.2%, 1 itération(s)) ──
import re
from fastapi import HTTPException, status

def validate_password(password: str) -> bool:
    """
    Valide le mot de passe selon les règles de sécurité.
    - longueur minimale de 8 caractères (validation_longueur)
    - présence d'au moins une majuscule (validation_format)
    Lève une HTTPException avec le code 400 en cas d'échec.
    """
    # validation_longueur
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe trop court"
        )
    # validation_format
    if not re.match(r".*[A-Z].*", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
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
    Retourne True si l'e‑mail est valide.
    """
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise HTTPException(status_code=400, detail='Email invalide')
    return True


# ── valider_age (score 98.2%, 1 itération(s)) ──
from fastapi import HTTPException

def valider_age(age):
    """
    Valide que l'âge fourni est numérique et supérieur ou égal à 18.
    Accepte les int, float et les chaînes représentant des nombres,
    conformément au comportement de PHP `is_numeric`.
    """
    # Conversion du paramètre pour accepter les chaînes numériques
    if isinstance(age, str):
        try:
            age = float(age) if ('.' in age or 'e' in age.lower()) else int(age)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique')

    # Vérification du type numérique (int ou float)
    if not isinstance(age, (int, float)):
        raise HTTPException(status_code=400, detail='Valeur non numérique')

    # Vérification de la borne minimale (majeur)
    if age < 18:
        raise HTTPException(status_code=400, detail='Doit être majeur')

    return True

#                  pourrait simplement ne rien retourner en cas de succès.
