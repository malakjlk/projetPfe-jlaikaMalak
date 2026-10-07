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
        Bannit un utilisateur identifié par son ID.

        Validation de la longueur de l'ID conformément à l'invariant
        `validation_longueur`. Si l'ID est vide, une HTTPException 400 est levée.
        """
        # validation_longueur
        if len(id) < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID invalide"
            )
        # Ici, la logique de bannissement serait implémentée (ex. mise à jour DB)
        return True


# la vraie logique de bannissement (mise à jour en base) sera ajoutée ailleurs.
# dans le même fichier, conformément aux consignes.


# ── SuperAdmin (score 97.6%, 1 itération(s)) ──
from fastapi import HTTPException

class SuperAdmin(Admin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def supprimer_compte(self, id):
        """
        Supprime le compte identifié par ``id``.
        Validation du type numérique compatible PHP : accepte int, float,
        ou chaîne convertible en nombre.
        """
        # Validation du type numérique selon les règles de migration
        if isinstance(id, str):
            try:
                id = float(id) if ('.' in id or 'e' in id.lower()) else int(id)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
        elif not isinstance(id, (int, float)):
            raise HTTPException(status_code=400, detail='Valeur non numérique')

        # Implémentation réelle de la suppression à venir
        return True

# opération de base de données ; elle se contente de valider l'ID et
# retourne ``True`` comme le code PHP d'origine.
# (ex. "42", "3.14") conformément au comportement de PHP `is_numeric`.
