"""
Migré automatiquement par SMAML depuis calculs.php
"""

# ── diviser (score 98.0%, 1 itération(s)) ──
from typing import Union
from fastapi import HTTPException

def diviser(a: Union[int, float, str], b: Union[int, float, str]) -> float:
    """
    Division sécurisée similaire à la fonction PHP `diviser`.
    Accepte les nombres ou les chaînes numériques, comme le fait PHP.
    """
    # Conversion des paramètres au type numérique (int ou float) si nécessaire
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

    # Vérification de la division par zéro
    if b == 0:
        raise HTTPException(status_code=400, detail='Division par zero')

    return a / b


# ── formater_prix (score 98.0%, 1 itération(s)) ──
from fastapi import HTTPException

def formater_prix(montant) -> str:
    """
    Formate un montant en euros avec deux décimales et séparateurs de milliers.
    Accepte les nombres (int, float) ainsi que les chaînes numériques,
    reproduisant le comportement de PHP `is_numeric`.
    """
    # Conversion des chaînes numériques en type numérique (int ou float)
    if isinstance(montant, str):
        try:
            montant = float(montant) if ('.' in montant or 'e' in montant.lower()) else int(montant)
        except ValueError:
            raise HTTPException(status_code=400, detail="Valeur non numérique")
    # Vérification du type après conversion
    if not isinstance(montant, (int, float)):
        raise HTTPException(status_code=400, detail="Montant invalide")
    # Formatage avec séparateurs de milliers et deux décimales
    return f"{montant:,.2f} EUR"


# ── calculer_remise (score 76.2%, 1 itération(s)) ──
from fastapi import HTTPException

def calculer_remise(prix, pourcentage):
    """
    Calcule le prix après application d'une remise.
    Accepte les nombres ou les chaînes numériques, comme le fait PHP.
    """
    # Conversion des paramètres en nombres (int ou float) si ce sont des chaînes
    for name, value in (('prix', prix), ('pourcentage', pourcentage)):
        if isinstance(value, str):
            try:
                # Convertit en int si pas de point/exposant, sinon en float
                converted = float(value) if ('.' in value or 'e' in value.lower()) else int(value)
                if name == 'prix':
                    prix = converted
                else:
                    pourcentage = converted
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
        elif not isinstance(value, (int, float)):
            # Rejette tout type non numérique (ex: None, bool, list, etc.)
            raise HTTPException(status_code=400, detail='Valeur non numérique')

    # Validation de l'intervalle du pourcentage (invariant de sécurité)
    if pourcentage < 0 or pourcentage > 100:
        raise HTTPException(status_code=400, detail='Pourcentage invalide')

    # Calcul de la remise
    remise = prix - (prix * pourcentage / 100)

    return remise
