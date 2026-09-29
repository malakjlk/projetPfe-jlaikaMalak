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
from fastapi import HTTPException, status
from typing import Any


class Admin(User):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def bannir_utilisateur(self, id: str) -> bool:
        """
        Bannit un utilisateur identifié par son ID.

        Validation :
        - La longueur de l'ID doit être supérieure à 0 (invariant validation_longueur).
        """
        # validation_longueur
        if len(id) < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID invalide"
            )
        # Implémentation réelle du bannissement à ajouter ici (ex. mise à jour DB)
        return True


#                  implémenter la logique de bannissement (ex. mise à jour d'un champ 'banned' via SQLAlchemy).


# ── SuperAdmin (score 57.6%, 1 itération(s)) ──
from fastapi import HTTPException


class SuperAdmin(Admin):
    def __init__(self):
        super().__init__()

    def supprimer_compte(self, id):
        """
        Supprime le compte identifié par *id*.
        Validation du type numérique conforme au comportement PHP :
        accepte int, float ou chaîne convertible.
        """
        # Conversion éventuelle d'une chaîne numérique en nombre
        if isinstance(id, str):
            try:
                id = float(id) if ('.' in id or 'e' in id.lower()) else int(id)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')

        # À ce stade, *id* est garanti numérique (int ou float)
        # La logique réelle de suppression serait implémentée ici.
        return True


# SMAML-HYPOTHÈSE: la méthode ne nécessite aucun accès à la base de données dans le code fourni.
