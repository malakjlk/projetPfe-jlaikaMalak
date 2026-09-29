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

        Parameters
        ----------
        nom : str
            Nom de l'article.
        prix : int | float | str
            Prix de l'article, accepte les chaînes numériques comme en PHP.
        """
        # Conversion du paramètre numérique selon le comportement PHP
        if isinstance(prix, str):
            try:
                prix = float(prix) if ('.' in prix or 'e' in prix.lower()) else int(prix)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')

        # Validation : le prix ne doit pas être négatif
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

def majuscules(texte: str) -> str:
    """
    Convertit le texte en majuscules.
    """
    # Aucun traitement spécial requis pour les types numériques ici,
    # car la fonction PHP attend une chaîne.
    return texte.upper()


def tronquer(texte: str, longueur) -> str:
    """
    Retourne le texte tronqué à la longueur spécifiée.
    La validation accepte les entiers ou les chaînes numériques,
    conformément au comportement de PHP.
    """
    # Conversion de `longueur` selon la règle de compatibilité PHP
    if isinstance(longueur, str):
        try:
            longueur = float(longueur) if ('.' in longueur or 'e' in longueur.lower()) else int(longueur)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique')
    # Validation de l'intervalle (longueur < 1) – invariant de sécurité
    if longueur < 1:
        raise HTTPException(status_code=400, detail='Longueur invalide')
    # Troncature du texte
    return texte[:int(longueur)]


# car le code PHP original attend uniquement une chaîne de caractères.
