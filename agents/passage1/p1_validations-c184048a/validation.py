"""
Migré automatiquement par SMAML depuis validation.php
"""

# ── validate_password (score 100.0%, 2 itération(s)) ──
import re
from typing import Any

def validate_password(password: str) -> bool:
    """
    Valide un mot de passe selon les règles métier héritées du code PHP d'origine.

    Règles appliquées :
    - La longueur doit être d'au moins 8 caractères. (validation_longueur)
    - Le mot de passe doit contenir au moins une majuscule. (validation_format)

    Exceptions levées :
    - ValueError: si la longueur est insuffisante.
    - ValueError: si aucune majuscule n'est présente.

    Args:
        password: Le mot de passe à valider.

    Returns:
        True si le mot de passe satisfait toutes les règles.

    """
    # validation_longueur
    if len(password) < 8:
        raise ValueError("Mot de passe trop court")

    # validation_format (majuscule)
    if not re.search(r"[A-Z]", password):
        raise ValueError("Majuscule requise")

    return True

# aucune autre contrainte (chiffre, caractères spéciaux) n'est ajoutée ici.


# ── valider_email (score 96.4%, 2 itération(s)) ──
import re


def valider_email(email: str) -> bool:
    """
    Valide le format d'une adresse email.

    Args:
        email (str): L'adresse email à vérifier.

    Returns:
        bool: True si l'adresse email est valide.

    Raises:
        ValueError: Si le format de l'email est invalide.
    """
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not isinstance(email, str) or not re.match(pattern, email):
        raise ValueError("Email invalide")
    return True


# ── valider_age (score 98.2%, 2 itération(s)) ──
from typing import Any, Union
from fastapi import HTTPException


def valider_age(age: Any) -> bool:
    """
    Valide que l'âge fourni est numérique et supérieur ou égal à 18 ans.

    Args:
        age (Any): Valeur représentant l'âge (entier, flottant ou chaîne numérique).

    Returns:
        bool: True si la validation réussit.

    Raises:
        HTTPException: 
            - 400 avec le détail "Age non numerique" si la valeur n'est pas un nombre.
            - 400 avec le détail "Doit etre majeur" si l'âge est inférieur à 18.
    """
    if isinstance(age, bool):
        raise HTTPException(status_code=400, detail="Age non numerique")

    if isinstance(age, str):
        try:
            age = float(age) if ('.' in age or 'e' in age.lower()) else int(age)
        except ValueError:
            raise HTTPException(status_code=400, detail="Age non numerique")
    elif not isinstance(age, (int, float)):
        raise HTTPException(status_code=400, detail="Age non numerique")

    if age < 18:
        raise HTTPException(status_code=400, detail="Doit etre majeur")

    return True
