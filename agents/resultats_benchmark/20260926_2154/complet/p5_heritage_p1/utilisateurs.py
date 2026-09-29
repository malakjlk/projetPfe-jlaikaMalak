"""
Migré automatiquement par SMAML depuis utilisateurs.php
"""

# ── User (score 85.9%, 1 itération(s)) ──
from typing import Optional

class User:
    def __init__(self, nom: str, email: str) -> None:
        # validation_longueur : on s'assure que le nom n'est pas vide
        if not isinstance(nom, str):
            raise TypeError("Le champ 'nom' doit être de type str")
        if len(nom) == 0:
            raise ValueError("Le champ 'nom' ne doit pas être vide")
        # validation_type : on s'assure que l'email est bien une chaîne
        if not isinstance(email, str):
            raise TypeError("Le champ 'email' doit être de type str")
        self.nom: str = nom
        self.email: str = email

    def obtenir_nom(self) -> str:
        """Retourne le nom de l'utilisateur."""
        return self.nom


# ── Admin (score 0.0%, 1 itération(s)) ──
from fastapi import HTTPException, status

class Admin(User):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def bannir_utilisateur(self, id: str) -> bool:
        """
        Banni un utilisateur identifié par son ID.

        - validation_longueur : l'ID doit contenir au moins un caractère.
        - validation_type    : l'ID doit être de type ``str`` (déjà assuré par l'annotation).
        """
        if not isinstance(id, str):
            # validation_type
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="ID doit être une chaîne de caractères"
            )
        if len(id) < 1:
            # validation_longueur
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID invalide"
            )
        # Ici, la logique réelle de bannissement (ex. mise à jour BDD) serait implémentée.
        return True


# ── SuperAdmin (score 80.2%, 1 itération(s)) ──
from fastapi import HTTPException
from typing import Union


class SuperAdmin(Admin):
    def __init__(self) -> None:
        super().__init__()

    def supprimer_compte(self, id: Union[int, float, str]) -> bool:
        """
        Supprime un compte en vérifiant que l'identifiant fourni est numérique.
        Accepte les int, float ou les chaînes représentant un nombre (ex: "42", "3.14").
        """
        # Conversion conforme au comportement PHP de is_numeric
        if isinstance(id, str):
            try:
                id = float(id) if ('.' in id or 'e' in id.lower()) else int(id)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
        elif not isinstance(id, (int, float)):
            # Cas où id serait d'un autre type (ex: None, list, etc.)
            raise HTTPException(status_code=400, detail='Valeur non numérique')

        # À ce stade, `id` est garanti numérique ; la logique de suppression réelle
        # serait implémentée ici (ex: appel à une méthode du parent ou requête DB).
        return True


# elle se contente de valider l'ID et de retourner True comme le code PHP d'origine.
# comportement de PHP, mais ne gère pas les formats spéciaux (ex: "0xFF").
