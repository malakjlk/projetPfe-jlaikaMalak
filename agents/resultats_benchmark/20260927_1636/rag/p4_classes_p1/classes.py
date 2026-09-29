"""
Migré automatiquement par SMAML depuis classes.php
"""

# ── PanierAchat (score 97.9%, 1 itération(s)) ──
from typing import List, Union
from fastapi import HTTPException


class PanierAchat:
    def __init__(self) -> None:
        self.articles: List[str] = []
        self.total: Union[int, float] = 0

    def _coerce_numeric(self, value: Union[int, float, str]) -> Union[int, float]:
        """
        Convertit une valeur numérique ou une chaîne numérique en int ou float,
        reproduisant le comportement de PHP qui accepte les chaînes numériques.
        """
        if isinstance(value, str):
            try:
                # Décider entre int et float comme le ferait PHP
                return float(value) if ('.' in value or 'e' in value.lower()) else int(value)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
        return value

    def ajouter_article(self, nom: str, prix: Union[int, float, str]) -> bool:
        """
        Ajoute un article au panier après validation du prix.
        Le prix peut être un nombre ou une chaîne numérique.
        """
        prix_coerce = self._coerce_numeric(prix)

        if prix_coerce < 0:
            raise HTTPException(status_code=400, detail='Prix negatif')

        self.articles.append(nom)
        self.total += prix_coerce
        return True

    def obtenir_total(self) -> Union[int, float]:
        """Retourne le total actuel du panier."""
        return self.total


# sans arrondi supplémentaire, comme le comportement natif de PHP.


# ── outils_texte (score 97.9%, 1 itération(s)) ──
from fastapi import HTTPException
from typing import Union


def majuscules(texte: str) -> str:
    """
    Convertit le texte en majuscules.
    """
    if not isinstance(texte, str):
        raise HTTPException(status_code=400, detail="Le texte doit être une chaîne de caractères")
    return texte.upper()


def tronquer(texte: str, longueur: Union[int, str]) -> str:
    """
    Retourne le texte tronqué à la longueur spécifiée.
    La longueur peut être un entier ou une chaîne représentant un entier,
    conformément au comportement de PHP qui accepte les chaînes numériques.
    """
    # Conversion de la longueur éventuelle chaîne numérique en entier
    if isinstance(longueur, str):
        try:
            longueur = int(longueur) if longueur.isdigit() else int(float(longueur))
        except ValueError:
            raise HTTPException(status_code=400, detail="Valeur non numérique pour la longueur")
    if not isinstance(longueur, int):
        raise HTTPException(status_code=400, detail="La longueur doit être un entier")
    if longueur < 1:
        raise HTTPException(status_code=400, detail="Longueur invalide")
    if not isinstance(texte, str):
        raise HTTPException(status_code=400, detail="Le texte doit être une chaîne de caractères")
    return texte[:longueur]


# même si PHP aurait pu accepter des flottants tronqués implicitement.
