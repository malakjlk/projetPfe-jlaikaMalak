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

# SMAML-HYPOTHÈSE: Le constructeur (__init__) attend les deux attributs obligatoires `nom` et `email` car le code PHP ne les initialise pas explicitement.


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
        # validation_longueur
        if len(id) < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID invalide"
            )
        # Implémentation réelle du bannissement à ajouter ici (ex. mise à jour DB)
        return True


#                  implémenter la logique de bannissement (ex. mise à jour du statut utilisateur).


# ── SuperAdmin (score 97.6%, 1 itération(s)) ──
from fastapi import HTTPException

class SuperAdmin(Admin):
    def __init__(self):
        super().__init__()

    def supprimer_compte(self, id):
        # Acceptation des chaînes numériques comme le fait PHP is_numeric
        if isinstance(id, str):
            try:
                id = float(id) if ('.' in id or 'e' in id.lower()) else int(id)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
        elif not isinstance(id, (int, float)):
            # Cas où id n'est ni chaîne convertible, ni nombre
            raise HTTPException(status_code=400, detail='Valeur non numérique')

        # Aucun traitement supplémentaire n'est spécifié dans le code PHP d'origine.
        return True
