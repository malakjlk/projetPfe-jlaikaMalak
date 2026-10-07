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


#                  implémenter la logique de bannissement (ex. mise à jour du statut utilisateur).


# ── SuperAdmin (score 97.6%, 1 itération(s)) ──
from fastapi import HTTPException

class SuperAdmin(Admin):
    def __init__(self):
        super().__init__()

    def supprimer_compte(self, id):
        """
        Supprime un compte en vérifiant que l'identifiant fourni est numérique.
        Accepte les int, float et les chaînes représentant un nombre (ex: "42", "3.14").
        """
        # Conversion compatible PHP : accepte les chaînes numériques
        if isinstance(id, str):
            try:
                id = float(id) if ('.' in id or 'e' in id.lower()) else int(id)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
        elif not isinstance(id, (int, float)):
            # Cas où id n'est ni chaîne, ni nombre
            raise HTTPException(status_code=400, detail='Valeur non numérique')

        # À ce stade, id est garanti numérique (int ou float)
        # Implémentation réelle de la suppression du compte à ajouter ici.
        return True

# donc la suppression effective du compte est laissée à implémenter ultérieurement.
# où is_numeric('3.14') est vrai, même si l'ID d'un compte est généralement entier.
