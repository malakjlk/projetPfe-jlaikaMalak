"""
Migré automatiquement par SMAML depuis utils.php
"""

# ── hash_password (score 90.0%, 1 itération(s)) ──
import os
import bcrypt

def hash_password(password: str) -> str:
    """
    Hache le mot de passe en respectant les contraintes de sécurité.

    - validation_longueur : le mot de passe doit contenir au moins 8 caractères.
    - hachage_mot_de_passe : le mot de passe n'est jamais retourné en clair.
    """
    if len(password) < 8:
        raise ValueError("Trop court")
    # bcrypt.gensalt() utilise un facteur de coût par défaut (12) qui correspond
    # à la configuration sécurisée de PHP PASSWORD_DEFAULT.
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

# comme équivalent à PASSWORD_DEFAULT de PHP dans la plupart des environnements.
# ce qui doit être capturé par la couche appelante (ex. route FastAPI) pour
# transformer l'erreur en réponse HTTP appropriée.
