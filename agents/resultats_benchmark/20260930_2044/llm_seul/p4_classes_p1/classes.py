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
        Convertit une valeur numérique ou une chaîne numérique en int/float,
        en suivant le comportement de PHP (conversion automatique).
        """
        if isinstance(value, str):
            try:
                # PHP convertit en float si la chaîne contient un point décimal ou un exposant
                return float(value) if ('.' in value or 'e' in value.lower()) else int(value)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
        # valeur déjà numérique
        return value

    def ajouter_article(self, nom: str, prix: Union[int, float, str]) -> bool:
        """
        Ajoute un article au panier.
        - `nom` reste une chaîne.
        - `prix` accepte int, float ou chaîne numérique (ex: "42", "3.14").
        - Lève une HTTPException 400 si le prix est négatif ou non numérique.
        """
        prix_coerce = self._coerce_numeric(prix)

        if prix_coerce < 0:
            raise HTTPException(status_code=400, detail='Prix negatif')

        self.articles.append(nom)
        self.total += prix_coerce
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
    conformément au comportement PHP.
    """
    # Conversion de `longueur` selon le pattern PHP → Python
    if isinstance(longueur, str):
        try:
            longueur = float(longueur) if ('.' in longueur or 'e' in longueur.lower()) else int(longueur)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique')
    # Validation de l'intervalle (longueur doit être >= 1)
    if longueur < 1:
        raise HTTPException(status_code=400, detail='Longueur invalide')
    # Troncature du texte
    return texte[:int(longueur)]


# car le code PHP original utilise uniquement `strtoupper` sur une chaîne.
# même si une valeur flottante était fournie, afin de reproduire le comportement de `substr` de PHP.
