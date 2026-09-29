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
        :raises HTTPException: Si l'ID est vide ou invalide.
        """
        # validation_longueur : vérifie que l'ID n'est pas vide
        if len(id) < 1:
            raise HTTPException(status_code=400, detail="ID invalide")
        return True


# ── SuperAdmin (score 97.6%, 1 itération(s)) ──
from fastapi import HTTPException

class SuperAdmin(Admin):
    def __init__(self) -> None:
        super().__init__()

    def supprimer_compte(self, id: int | float | str) -> bool:
        """
        Supprime un compte en vérifiant que l'identifiant fourni est numérique.
        Accepte les int, float et les chaînes représentant un nombre (ex: "42", "3.14").
        """
        # Conversion compatible avec le comportement de PHP is_numeric()
        if isinstance(id, str):
            try:
                id = float(id) if ('.' in id or 'e' in id.lower()) else int(id)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
        elif not isinstance(id, (int, float)):
            # Cas où le type n'est ni chaîne, ni nombre (ex: None, list, etc.)
            raise HTTPException(status_code=400, detail='Valeur non numérique')

        # À ce stade, `id` est garanti numérique ; la logique de suppression réelle
        # serait implémentée ici (ex: appel à une méthode du parent ou requête DB).
        return True

# elle se contente de valider le type et de retourner True comme le code PHP d'origine.
# comportement de PHP is_numeric(), y compris les notations décimales et exponentielles.
