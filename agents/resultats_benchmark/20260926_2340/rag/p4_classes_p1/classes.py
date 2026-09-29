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

        # Validation_intervalle : le prix ne doit pas être négatif
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
    Convertit le texte fourni en majuscules.
    Accepte les types texte ou numériques (similaire à PHP qui convertit
    automatiquement les nombres en chaînes lorsqu'ils sont concaténés).
    """
    # Conversion éventuelle d'un nombre en chaîne
    if not isinstance(texte, str):
        texte = str(texte)
    return texte.upper()


def tronquer(texte: Union[str, int, float], longueur: Union[int, str]) -> str:
    """
    Retourne le texte tronqué à la longueur spécifiée.
    La validation de la longueur suit la contrainte « validation_intervalle » :
    la valeur doit être supérieure ou égale à 1.
    Les paramètres numériques peuvent être fournis sous forme de chaîne,
    conformément au comportement de PHP.
    """
    # Conversion du texte en chaîne si nécessaire
    if not isinstance(texte, str):
        texte = str(texte)

    # Gestion de la conversion de la longueur (acceptation des chaînes numériques)
    if isinstance(longueur, str):
        try:
            longueur = int(longueur) if longueur.isdigit() else float(longueur)
        except ValueError:
            raise HTTPException(status_code=400, detail="Valeur non numérique")
    # Après conversion, on s'assure que la longueur est un entier
    try:
        longueur = int(longueur)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Valeur non numérique")

    # Validation de l'intervalle (longueur < 1)
    if longueur < 1:
        raise HTTPException(status_code=400, detail="Longueur invalide")

    return texte[:longueur]


# mais on les convertit en entier car le découpage de chaîne en Python nécessite un int.
