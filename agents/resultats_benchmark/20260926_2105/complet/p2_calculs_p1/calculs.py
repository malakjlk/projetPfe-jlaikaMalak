"""
Migré automatiquement par SMAML depuis calculs.php
"""

# ── diviser (score 83.2%, 1 itération(s)) ──
from fastapi import HTTPException
from typing import Union

def diviser(a: Union[int, float, str], b: Union[int, float, str]) -> float:
    """
    Divise deux valeurs numériques en respectant le comportement de PHP
    qui accepte les chaînes numériques.
    """
    # Conversion des paramètres en nombres (int ou float) si ce sont des chaînes
    if isinstance(a, str):
        try:
            a = float(a) if ('.' in a or 'e' in a.lower()) else int(a)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique pour le paramètre a')
    if isinstance(b, str):
        try:
            b = float(b) if ('.' in b or 'e' in b.lower()) else int(b)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique pour le paramètre b')

    # Validation de type numérique (déjà assurée par la conversion ci‑dessus)
    # Validation de l'intervalle : b ne doit pas être nul
    if b == 0:
        raise HTTPException(status_code=400, detail='Division par zero')

    return a / b


# ── formater_prix (score 83.2%, 1 itération(s)) ──
from fastapi import HTTPException
from typing import Union

def formater_prix(montant: Union[int, float, str]) -> str:
    """
    Formate un montant monétaire en euros avec séparateurs de milliers
    et deux décimales, en reproduisant le comportement de `number_format`
    de PHP.
    """
    # Conversion du paramètre pour accepter les chaînes numériques comme PHP le fait
    if isinstance(montant, str):
        try:
            montant = float(montant) if ('.' in montant or 'e' in montant.lower()) else int(montant)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique')
    # Validation du type numérique (int ou float)
    if not isinstance(montant, (int, float)):
        raise HTTPException(status_code=400, detail='Valeur non numérique')
    # Formatage avec séparateurs de milliers et deux décimales
    return f"{montant:,.2f} EUR"


# ── calculer_remise (score 98.2%, 1 itération(s)) ──
from fastapi import HTTPException
from typing import Union

def calculer_remise(prix: Union[int, float, str],
                    pourcentage: Union[int, float, str]) -> float:
    """
    Calcule le prix après application d'une remise.
    Accepte les nombres ou les chaînes numériques, comme le fait PHP.
    """

    # Conversion des paramètres numériques éventuels (compatibilité PHP)
    if isinstance(prix, str):
        try:
            prix = float(prix) if ('.' in prix or 'e' in prix.lower()) else int(prix)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique pour le prix')
    if isinstance(pourcentage, str):
        try:
            pourcentage = float(pourcentage) if ('.' in pourcentage or 'e' in pourcentage.lower()) else int(pourcentage)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique pour le pourcentage')

    # Validation du type numérique (invariant de sécurité)
    if not isinstance(prix, (int, float)):
        raise HTTPException(status_code=400, detail='Prix doit être numérique')
    if not isinstance(pourcentage, (int, float)):
        raise HTTPException(status_code=400, detail='Pourcentage doit être numérique')

    # Validation de l'intervalle du pourcentage (invariant de sécurité)
    if pourcentage < 0 or pourcentage > 100:
        raise HTTPException(status_code=400, detail='Pourcentage invalide')

    # Calcul de la remise
    remise = prix * pourcentage / 100
    resultat = prix - remise

    return float(resultat)


# afin de garantir une précision décimale cohérente avec les calculs monétaires.
