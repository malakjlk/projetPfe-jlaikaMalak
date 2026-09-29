"""
Migré automatiquement par SMAML depuis calculs.php
"""

# ── diviser (score 98.0%, 1 itération(s)) ──
from fastapi import HTTPException
from typing import Union

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
from typing import Union

def formater_prix(montant: Union[int, float, str]) -> str:
    """
    Formate un montant monétaire en euros avec séparateurs de milliers
    et deux décimales, en reproduisant le comportement de PHP
    `number_format($montant, 2)`.

    Le paramètre accepte les types numériques natifs ainsi que les
    chaînes représentant un nombre (ex. "42", "3.14", "1e3").
    """
    # Conversion des chaînes numériques en type numérique réel
    if isinstance(montant, str):
        try:
            # Décider entre int et float selon le contenu de la chaîne
            montant = float(montant) if ('.' in montant or 'e' in montant.lower()) else int(montant)
        except ValueError:
            raise HTTPException(status_code=400, detail="Valeur non numérique")

    # Vérification du type après conversion
    if not isinstance(montant, (int, float)):
        raise HTTPException(status_code=400, detail="Montant invalide")

    # Formatage avec séparateurs de milliers et deux décimales
    formatted = f"{montant:,.2f} EUR"
    return formatted

# même si la locale française utilise la virgule. Cette hypothèse suit le
# comportement standard de `number_format` sans spécifier de locale.
# valeurs non numériques afin de respecter les exigences de validation_type.


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
                value = float(value) if ('.' in value or 'e' in value.lower()) else int(value)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
            if name == 'prix':
                prix = value
            else:
                pourcentage = value

    # Validation de l'intervalle du pourcentage (0 ≤ pourcentage ≤ 100)
    if pourcentage < 0 or pourcentage > 100:
        raise HTTPException(status_code=400, detail='Pourcentage invalide')

    # Calcul de la remise
    remise = prix - (prix * pourcentage / 100)

    return remise

# car le code PHP original ne formatte pas le prix.
