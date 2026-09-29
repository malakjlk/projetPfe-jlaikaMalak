"""
Migré automatiquement par SMAML depuis utilisateurs.php
"""

# ── User (score 100.0%, 1 itération(s)) ──
from typing import Optional

class User:
    def __init__(self, nom: Optional[str] = None, email: Optional[str] = None) -> None:
        self.nom: Optional[str] = nom
        self.email: Optional[str] = email

    def obtenir_nom(self) -> Optional[str]:
        """Retourne le nom de l'utilisateur."""
        return self.nom


# ── Admin (score 97.9%, 1 itération(s)) ──
from fastapi import HTTPException, status


class Admin(User):
    def __init__(self) -> None:
        super().__init__()

    def bannir_utilisateur(self, id: str) -> bool:
        """
        Banni un utilisateur identifié par son ID.

        Validation de la longueur de l'ID conformément à l'invariant `validation_longueur`.
        """
        # validation_longueur : l'ID doit contenir au moins un caractère
        if len(id) < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID invalide"
            )
        # Implémentation réelle du bannissement à ajouter ici (ex. mise à jour DB)
        return True


# le vrai bannissement (mise à jour en base) sera implémenté ailleurs dans le projet.


# ── SuperAdmin (score 97.6%, 1 itération(s)) ──
from fastapi import HTTPException

class SuperAdmin(Admin):
    def __init__(self) -> None:
        super().__init__()

    def supprimer_compte(self, id: int | float | str) -> bool:
        """
        Supprime le compte identifié par ``id``.
        Accepte les nombres ou les chaînes numériques, comme le fait PHP avec is_numeric().
        """
        # Conversion compatible PHP : accepte int, float ou chaîne convertible
        if isinstance(id, str):
            try:
                id = float(id) if ('.' in id or 'e' in id.lower()) else int(id)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
        elif not isinstance(id, (int, float)):
            # Cas où id serait d'un autre type (ex. bool, list, etc.)
            raise HTTPException(status_code=400, detail='Valeur non numérique')

        # Ici, la logique réelle de suppression serait implémentée.
        # Pour l'instant, on retourne simplement True comme dans le code PHP d'origine.
        return True
