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
from fastapi import HTTPException, status
from typing import Any


class Admin(User):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def bannir_utilisateur(self, id: str) -> bool:
        """
        Banni un utilisateur identifié par son ID.

        Validation :
        - La longueur de l'ID doit être supérieure à 0 (invariant validation_longueur).
        """
        if len(id) < 1:
            # L'ID fourni est vide ou invalide
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID invalide"
            )
        # Implémentation réelle du bannissement à ajouter ici (ex. mise à jour DB)
        return True


#                  implémenter la logique de bannissement (ex. mise à jour d'un champ 'banned' via SQLAlchemy).


# ── SuperAdmin (score 97.6%, 1 itération(s)) ──
from fastapi import HTTPException

class SuperAdmin(Admin):
    def __init__(self) -> None:
        super().__init__()

    def supprimer_compte(self, id: int | str) -> bool:
        """
        Supprime le compte identifié par ``id``.
        Validation du type numérique compatible PHP : accepte les int,
        float et les chaînes convertibles en nombre.
        """
        # Conversion compatible PHP pour les chaînes numériques
        if isinstance(id, str):
            try:
                id = float(id) if ('.' in id or 'e' in id.lower()) else int(id)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
        elif not isinstance(id, (int, float)):
            # Cas où le type n'est ni chaîne, ni nombre
            raise HTTPException(status_code=400, detail='Valeur non numérique')

        # Ici, la logique réelle de suppression serait implémentée.
        # Pour l'exemple, on renvoie simplement True comme en PHP.
        return True
