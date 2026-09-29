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
            Prix de l'article. Les chaînes numériques sont acceptées comme en PHP.

        Returns
        -------
        bool
            Toujours True si l'ajout réussit.

        Raises
        ------
        HTTPException
            Si le prix est négatif ou non numérique.
        """
        # Conversion compatible PHP : accepter les chaînes numériques
        if isinstance(prix, str):
            try:
                prix = float(prix) if ('.' in prix or 'e' in prix.lower()) else int(prix)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')

        # Validation de l'intervalle (prix < 0)
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


# SMAML-HYPOTHÈSE: le prix peut être fourni sous forme de chaîne numérique, comme le comportement PHP le permet.


# ── outils_texte (score 97.9%, 1 itération(s)) ──
from fastapi import HTTPException
from typing import Union


def majuscules(texte: Union[str, int, float]) -> str:
    """
    Convertit le texte fourni en majuscules.
    Accepte les chaînes ainsi que les valeurs numériques (int, float) qui seront
    converties en chaîne avant la mise en majuscules, afin de reproduire le
    comportement permissif de PHP qui accepte les nombres comme chaînes.
    """
    # Conversion éventuelle d'un nombre en chaîne (PHP le ferait implicitement)
    if not isinstance(texte, str):
        texte = str(texte)

    return texte.upper()


def tronquer(texte: Union[str, int, float], longueur: Union[int, str]) -> str:
    """
    Retourne le texte tronqué à la longueur spécifiée.
    - `texte` peut être une chaîne ou une valeur numérique (convertie en chaîne).
    - `longueur` accepte un entier ou une chaîne représentant un entier,
      conformément à la conversion PHP de valeurs numériques.
    - Lève une HTTPException 400 si la longueur est inférieure à 1 ou non numérique.
    """
    # Gestion permissive du paramètre `longueur` (compatible PHP)
    if isinstance(longueur, str):
        try:
            longueur = int(longueur)
        except ValueError:
            raise HTTPException(status_code=400, detail="Valeur non numérique")
    elif not isinstance(longueur, int):
        # Si ce n'est ni int ni str, on tente de le convertir comme PHP le ferait
        try:
            longueur = int(longueur)
        except Exception:
            raise HTTPException(status_code=400, detail="Valeur non numérique")

    if longueur < 1:
        raise HTTPException(status_code=400, detail="Longueur invalide")

    # Conversion du texte en chaîne si nécessaire (PHP accepte les nombres)
    if not isinstance(texte, str):
        texte = str(texte)

    return texte[:longueur]


#   afin de reproduire le comportement de PHP qui convertit implicitement les nombres en chaînes.
#   correspondant à l'exception générique en PHP.
