"""
Migré automatiquement par SMAML depuis utilisateurs.php
"""

# ── User (score 100.0%, 1 itération(s)) ──
from typing import Optional

class User:
    def __init__(self, nom: str, email: str) -> None:
        self.nom: str = nom
        self.email: str = email

    def obtenir_nom(self) -> str:
        """Retourne le nom de l'utilisateur."""
        return self.nom

# SMAML-HYPOTHÈSE: Le constructeur (__init__) reçoit les deux attributs obligatoires (nom, email) car le code PHP ne les initialise pas explicitement.


# ── Admin (score 97.9%, 1 itération(s)) ──
from fastapi import HTTPException
from typing import Any


class Admin(User):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def bannir_utilisateur(self, id: str) -> bool:
        """
        Banni un utilisateur identifié par son ID.

        :param id: Identifiant de l'utilisateur à bannir.
        :return: True si l'opération est considérée valide.
        :raises HTTPException: Si l'ID fourni est vide ou invalide.
        """
        # validation_longueur : on vérifie que la chaîne n'est pas vide
        if len(id) < 1:
            raise HTTPException(status_code=400, detail="ID invalide")
        return True


# ── SuperAdmin (score 97.6%, 1 itération(s)) ──
from fastapi import HTTPException

class SuperAdmin(Admin):
    def __init__(self):
        super().__init__()

    def supprimer_compte(self, id):
        # Acceptation des chaînes numériques comme le fait PHP
        if isinstance(id, str):
            try:
                id = float(id) if ('.' in id or 'e' in id.lower()) else int(id)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
        elif not isinstance(id, (int, float)):
            # Cas où le type n'est ni int, ni float, ni chaîne convertible
            raise HTTPException(status_code=400, detail='Valeur non numérique')

        # La logique originale ne fait que valider le type et retourne True
        return True
