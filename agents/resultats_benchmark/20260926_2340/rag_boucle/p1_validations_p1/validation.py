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
    """
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe trop court"
        )
    # Validation par expression régulière pour la présence d'une majuscule
    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Majuscule requise"
        )
    return True

# même si le code PHP original levait une Exception générique.


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
    Accepte les int, float et les chaînes représentant un nombre,
    conformément au comportement de PHP is_numeric().
    """
    # Conversion du paramètre pour accepter les chaînes numériques
    if isinstance(age, str):
        try:
            age = float(age) if ('.' in age or 'e' in age.lower()) else int(age)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique')
    # Vérification du type après conversion
    if not isinstance(age, (int, float)):
        raise HTTPException(status_code=400, detail='Valeur non numérique')
    # Contrôle de l'intervalle (âge minimum requis)
    if age < 18:
        raise HTTPException(status_code=400, detail='Doit être majeur')
    return True

#                     car le code PHP d'origine ne le spécifiait pas.
