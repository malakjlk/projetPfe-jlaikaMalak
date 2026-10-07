"""
Migré automatiquement par SMAML depuis login.php
"""

# ── login (score 93.9%, 1 itération(s)) ──
import os
import re
from fastapi import HTTPException

# Fonctions déjà présentes dans le projet
from db import get_user_by_email          # get_user_by_email(email) -> dict | None
from utils import hash_password           # hash_password(password) -> str


def login(email: str, password: str) -> int:
    """
    Authentifie un utilisateur.

    - Vérifie le format de l'email.
    - Récupère l'utilisateur en base via ``get_user_by_email``.
    - Compare le hash du mot de passe fourni avec celui stocké.
    - Retourne l'ID de l'utilisateur en cas de succès.

    Lève ``HTTPException`` avec le code 400 pour un email invalide
    et 401 pour des identifiants incorrects, conformément aux
    invariants de sécurité.
    """
    # Validation du format d'email (invariant validation_format)
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise HTTPException(status_code=400, detail='Email invalide')

    # Accès aux données (pas de SQL inline, on utilise la fonction du projet)
    user = get_user_by_email(email)  # type: ignore[assignment]  # renvoie dict ou None

    # Si l'utilisateur n'existe pas ou le mot de passe ne correspond pas
    if not user or user.get("password") != hash_password(password):
        # Comparaison d'authentification (invariant comparaison_authentification)
        raise HTTPException(status_code=401, detail='Identifiants incorrects')

    # Le PHP renvoie l'ID de l'utilisateur ; on renvoie le même type
    return user["id"]


#                  au moins les clés ``id`` et ``password``.
#                  utilisé dans la base de données (ex. bcrypt, argon2, etc.).
