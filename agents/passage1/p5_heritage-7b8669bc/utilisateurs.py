"""
Migré automatiquement par SMAML depuis utilisateurs.php
"""

# ── User (score 97.5%, 2 itération(s)) ──
from typing import Optional


class User:
    """Classe représentant un utilisateur."""

    def __init__(self) -> None:
        self.__nom: Optional[str] = None
        self.__email: Optional[str] = None

    def obtenir_nom(self) -> Optional[str]:
        """Retourne le nom de l'utilisateur."""
        return self.__nom


# ── Admin (score 97.0%, 2 itération(s)) ──
class Admin(User):
    """Classe représentant un administrateur du système."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialise une nouvelle instance d'administrateur."""
        super().__init__(*args, **kwargs)

    def bannir_utilisateur(self, id: str) -> bool:
        """Bannit un utilisateur à partir de son identifiant.

        Args:
            id: L'identifiant de l'utilisateur à bannir.

        Returns:
            bool: True si l'opération a réussi.

        Raises:
            ValueError: Si la longueur de l'identifiant est inférieure à 1.
        """
        if len(str(id)) < 1:
            raise ValueError("ID invalide")
        return True


# ── SuperAdmin (score 92.5%, 3 itération(s)) ──
from typing import Any


class SuperAdmin(Admin):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def supprimer_compte(self, id: Any) -> bool:
        if isinstance(id, str):
            try:
                id = float(id) if ('.' in id or 'e' in id.lower()) else int(id)
            except ValueError:
                raise ValueError("ID non numerique")
        elif not isinstance(id, (int, float)) or isinstance(id, bool):
            raise ValueError("ID non numerique")
        return True
