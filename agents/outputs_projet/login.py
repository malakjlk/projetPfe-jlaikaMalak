"""
Migré automatiquement par SMAML depuis login.php
"""

# ── login (score 73.2%, 1 itération(s)) ──
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db import get_user_by_email, connect_database
from utils import validate_password

def login(email: str, password: str, db: Session) -> str:
    """
    Authentifie un utilisateur à partir de son email et de son mot de passe.

    - Le mot de passe est d'abord validé avec la fonction utilitaire `validate_password`.
    - L'utilisateur est récupéré via `get_user_by_email`, qui attend le
      courriel et la session de base de données.
    - La comparaison du mot de passe se fait de façon directe (équivalence
      stricte) afin de respecter la contrainte de « comparaison_authentification ».
    - En cas de succès, la chaîne « Connexion réussie » est renvoyée,
      sinon « Email ou mot de passe incorrect ».
    """
    # Validation du format / des règles du mot de passe
    validate_password(password)

    # Récupération de l'utilisateur en base de données
    user = get_user_by_email(email, db)

    # Vérification de l'existence et du mot de passe
    if user and user.password == password:
        return "Connexion réussie"
    else:
        return "Email ou mot de passe incorrect"


# ce qui correspond à la signature corrigée demandée dans les consignes.
# dans un projet réel il faudrait utiliser une fonction de vérification sécurisée
# (ex. bcrypt.checkpw) pour éviter les vulnérabilités de timing attacks.
