"""
Migré automatiquement par SMAML depuis classes.php
"""

# ── PanierAchat (score 80.2%, 1 itération(s)) ──
from typing import List, Union
from fastapi import HTTPException


class PanierAchat:
    def __init__(self) -> None:
        self.articles: List[str] = []
        self.total: float = 0.0

    def ajouter_article(self, nom: str, prix: Union[int, float, str]) -> bool:
        """
        Ajoute un article au panier.

        Le paramètre ``prix`` accepte les nombres ou les chaînes numériques,
        conformément au comportement de PHP qui convertit automatiquement les
        chaînes numériques en nombres.
        """
        # Conversion du prix au type numérique (int ou float) comme le ferait PHP
        if isinstance(prix, str):
            try:
                prix = float(prix) if ('.' in prix or 'e' in prix.lower()) else int(prix)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique pour le prix')
        # Validation de la borne inférieure (< 0)
        if prix < 0:
            raise HTTPException(status_code=400, detail='Prix negatif')
        # Ajout de l'article
        self.articles.append(nom)
        self.total += float(prix)
        return True

    def obtenir_total(self) -> float:
        """Retourne le total du panier."""
        return self.total


# ── outils_texte (score 80.2%, 1 itération(s)) ──
from fastapi import HTTPException
from typing import Union


def majuscules(texte: Union[str, int, float]) -> str:
    """
    Convertit le texte fourni en majuscules.
    Accepte les chaînes ainsi que les valeurs numériques (int, float) qui seront
    d'abord converties en chaîne, afin de reproduire le comportement PHP où
    les nombres sont automatiquement castés en chaîne lors de l'appel à strtoupper().
    """
    # Conversion explicite en chaîne pour gérer les entrées numériques
    texte_str = str(texte)
    return texte_str.upper()


def tronquer(texte: Union[str, int, float], longueur: Union[int, str]) -> str:
    """
    Retourne les `longueur` premiers caractères du texte.
    - `texte` peut être une chaîne ou une valeur numérique (convertie en chaîne).
    - `longueur` accepte un entier ou une chaîne numérique, conformément au
      comportement PHP qui accepte les chaînes numériques.
    - Lève une HTTPException 400 si `longueur` n'est pas numérique ou < 1,
      reproduisant l'exception PHP d'argument invalide.
    """
    # Gestion de la conversion de `longueur` selon les règles de compatibilité PHP
    if isinstance(longueur, str):
        try:
            # PHP accepte les chaînes numériques, on les convertit en int
            longueur_val = int(longueur) if longueur.isdigit() else int(float(longueur))
        except ValueError:
            raise HTTPException(status_code=400, detail="Valeur non numérique pour la longueur")
    else:
        longueur_val = longueur

    # Validation de la borne inférieure (doit être > 0)
    if longueur_val < 1:
        raise HTTPException(status_code=400, detail="Longueur invalide, doit être >= 1")

    # Conversion du texte en chaîne (pour gérer les entrées numériques)
    texte_str = str(texte)

    # Troncature
    return texte_str[:longueur_val]


# ce qui correspond à l'exception générique PHP dans le code source.
