"""
Migré automatiquement par SMAML depuis classes.php
"""

# ── PanierAchat (score 97.9%, 1 itération(s)) ──
from fastapi import HTTPException
from typing import List, Union


class PanierAchat:
    def __init__(self) -> None:
        self.articles: List[str] = []
        self.total: Union[int, float] = 0

    def ajouter_article(self, nom: str, prix: Union[int, float, str]) -> bool:
        """
        Ajoute un article au panier.

        - Le paramètre ``prix`` accepte les nombres ou les chaînes numériques,
          conformément au comportement de PHP.
        - Lève une ``HTTPException`` 400 si le prix n'est pas numérique
          ou s'il est négatif.
        - Retourne ``True`` comme le code PHP d'origine.
        """
        # Conversion du prix au type numérique (int ou float) comme le ferait PHP
        if isinstance(prix, str):
            try:
                prix = float(prix) if ('.' in prix or 'e' in prix.lower()) else int(prix)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')

        # Validation de l'intervalle (prix ne doit pas être négatif)
        if prix < 0:
            raise HTTPException(status_code=400, detail='Prix negatif')

        self.articles.append(nom)
        self.total += prix
        return True

    def obtenir_total(self) -> Union[int, float]:
        """
        Retourne le total du panier.
        """
        return self.total


# SMAML-HYPOTHÈSE: le prix peut être fourni sous forme de chaîne contenant un exposant (ex. "1e3").
#                  conformément aux exigences de validation d'entrées dans les routes FastAPI.


# ── outils_texte (score 97.9%, 1 itération(s)) ──
from fastapi import HTTPException


def majuscules(texte: str) -> str:
    """
    Convertit le texte en majuscules.
    """
    return texte.upper()


def tronquer(texte: str, longueur) -> str:
    """
    Retourne le texte tronqué à la longueur indiquée.
    La longueur peut être un int, float ou une chaîne numérique,
    conformément au comportement de PHP qui accepte les chaînes numériques.
    """
    # Conversion de la longueur selon le pattern PHP → Python
    if isinstance(longueur, str):
        try:
            longueur = float(longueur) if ('.' in longueur or 'e' in longueur.lower()) else int(longueur)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique')
    # Validation de l'intervalle (longueur doit être >= 1)
    if longueur < 1:
        raise HTTPException(status_code=400, detail='Longueur invalide')
    # On s'assure que la longueur est un entier pour le slicing
    longueur = int(longueur)
    return texte[:longueur]


# même si le PHP original attendait typiquement un entier.
