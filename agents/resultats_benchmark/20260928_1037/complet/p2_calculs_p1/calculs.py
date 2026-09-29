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
    for name, value in (('a', a), ('b', b)):
        if isinstance(value, str):
            try:
                # Détection du type décimal ou scientifique
                converted = float(value) if ('.' in value or 'e' in value.lower()) else int(value)
                if name == 'a':
                    a = converted
                else:
                    b = converted
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
        else:
            # Accepter int ou float directement
            if name == 'a':
                a = value
            else:
                b = value

    # Validation de l'intervalle : b ne doit pas être zéro
    if b == 0:
        raise HTTPException(status_code=400, detail='Division par zero')

    return a / b


# ── formater_prix (score 0.0%, 1 itération(s)) ──
from fastapi import HTTPException

def formater_prix(montant) -> str:
    """
    Formate un montant en euros avec séparateurs de milliers et deux décimales.
    Accepte les nombres (int, float) ainsi que les chaînes numériques,
    comme le fait PHP avec is_numeric().
    """
    # Conversion du paramètre en nombre (int ou float) si c'est une chaîne
    if isinstance(montant, str):
        try:
            montant = float(montant) if ('.' in montant or 'e' in montant.lower()) else int(montant)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique')
    # Vérification du type numérique après conversion
    if not isinstance(montant, (int, float)):
        raise HTTPException(status_code=400, detail='Valeur non numérique')
    # Formatage avec séparateurs de milliers et deux décimales
    return f"{montant:,.2f} EUR"


# ── calculer_remise (score 0.0%, 1 itération(s)) ──

