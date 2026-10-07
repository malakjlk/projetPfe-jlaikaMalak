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


# ── outils_texte (score 97.9%, 1 itération(s)) ──
from fastapi import HTTPException


def majuscules(texte: str) -> str:
    """
    Convertit le texte en majuscules.
    """
    return texte.upper()


def tronquer(texte: str, longueur: int) -> str:
    """
    Retourne le texte tronqué à la longueur spécifiée.
    La longueur doit être supérieure ou égale à 1.
    """
    # Compatibilité PHP : accepter les chaînes numériques pour `longueur`
    if isinstance(longueur, str):
        try:
            longueur = int(longueur) if longueur.isdigit() else float(longueur)
        except ValueError:
            raise HTTPException(status_code=400, detail="Valeur non numérique")
    if not isinstance(longueur, (int, float)):
        raise HTTPException(status_code=400, detail="Valeur non numérique")
    # PHP considère les valeurs décimales comme valides, on les convertit en int
    longueur = int(longueur)

    if longueur < 1:
        raise HTTPException(status_code=400, detail="Longueur invalide")
    return texte[:longueur]


#                     afin de reproduire le comportement permissif de PHP concernant les
#                     conversions de type implicites.
