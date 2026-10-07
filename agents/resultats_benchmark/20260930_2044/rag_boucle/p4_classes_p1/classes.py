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

    def ajouter_article(self, nom: str, prix: Union[int, float, str]) -> bool:
        """
        Ajoute un article au panier.

        - ``nom`` : nom de l'article (chaîne)
        - ``prix`` : prix de l'article, accepte int, float ou chaîne numérique
        """
        # Conversion du prix selon le comportement PHP (acceptation des chaînes numériques)
        if isinstance(prix, str):
            try:
                prix = float(prix) if ('.' in prix or 'e' in prix.lower()) else int(prix)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique pour le prix')

        # Validation de l'intervalle (prix ne doit pas être négatif)
        if prix < 0:
            raise HTTPException(status_code=400, detail='Prix negatif')

        self.articles.append(nom)
        self.total += prix
        return True

    def obtenir_total(self) -> Union[int, float]:
        """Retourne le total du panier."""
        return self.total


# ── outils_texte (score 97.9%, 1 itération(s)) ──
from fastapi import HTTPException
from typing import Union


def majuscules(texte: Union[str, int, float]) -> str:
    """
    Convertit le texte en majuscules.
    Accepte les chaînes ou les valeurs numériques (similaire à PHP qui
    convertit automatiquement les nombres en chaînes lorsqu'ils sont
    concaténés ou manipulés comme du texte).
    """
    # Conversion des valeurs numériques en chaîne, comme le ferait PHP
    if not isinstance(texte, str):
        texte = str(texte)

    return texte.upper()


def tronquer(texte: Union[str, int, float], longueur: Union[int, str]) -> str:
    """
    Retourne le texte tronqué à la longueur spécifiée.
    - La longueur doit être supérieure ou égale à 1 (validation_intervalle).
    - Accepte les chaînes numériques pour la longueur, conformément au
      comportement PHP d'acceptation des chaînes numériques.
    """
    # Conversion de la longueur selon le pattern PHP → Python
    if isinstance(longueur, str):
        try:
            longueur = float(longueur) if ('.' in longueur or 'e' in longueur.lower()) else int(longueur)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique')
    # Après conversion, on s'assure que la longueur est un entier
    if isinstance(longueur, float):
        # PHP tronquerait implicitement en entier dans ce contexte
        longueur = int(longueur)

    if longueur < 1:
        raise HTTPException(status_code=400, detail='Longueur invalide')

    # Conversion du texte en chaîne si nécessaire (PHP accepte les nombres)
    if not isinstance(texte, str):
        texte = str(texte)

    return texte[:longueur]
