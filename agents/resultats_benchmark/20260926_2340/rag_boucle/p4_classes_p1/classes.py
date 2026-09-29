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

        Le paramètre ``prix`` accepte les nombres ou les chaînes numériques,
        conformément au comportement de PHP qui convertit automatiquement les
        chaînes numériques en nombres.
        """
        # Conversion du prix si c'est une chaîne (pattern PHP is_numeric)
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


# même si PHP aurait pu le traiter comme float dans certains cas.
# ce qui correspond à la gestion d'exceptions attendue dans un contexte FastAPI.


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
    # Conversion éventuelle d'un nombre en chaîne
    if not isinstance(texte, str):
        texte = str(texte)
    return texte.upper()


def tronquer(texte: Union[str, int, float], longueur: Union[int, str]) -> str:
    """
    Retourne les `longueur` premiers caractères du texte.
    - `longueur` doit être > 0 (validation_intervalle).
    - Accepte les chaînes numériques pour `longueur` afin de reproduire le
      comportement PHP de conversion implicite.
    """
    # Conversion du texte en chaîne si nécessaire
    if not isinstance(texte, str):
        texte = str(texte)

    # Gestion de la conversion de `longueur` (acceptation des chaînes numériques)
    if isinstance(longueur, str):
        try:
            # PHP accepte les entiers et les flottants dans les contextes numériques ;
            # on les convertit en int après validation.
            longueur = int(longueur) if longueur.isdigit() else int(float(longueur))
        except ValueError:
            raise HTTPException(status_code=400, detail="Valeur non numérique pour la longueur")
    elif not isinstance(longueur, int):
        # Si ce n'est pas un int déjà, on tente de le convertir (ex: float)
        try:
            longueur = int(longueur)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Valeur non numérique pour la longueur")

    # Validation de l'intervalle (longueur > 0)
    if longueur < 1:
        raise HTTPException(status_code=400, detail="Longueur invalide")

    return texte[:longueur]

# même si le code PHP original ne les manipulait que comme chaînes.
# (ex: "5.0") en les castant en int, ce qui reproduit la permissivité de PHP.
