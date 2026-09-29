"""
Migré automatiquement par SMAML depuis calculs.php
"""

# ── diviser (score 98.0%, 1 itération(s)) ──
from fastapi import HTTPException
from typing import Union

def diviser(a: Union[int, float, str], b: Union[int, float, str]) -> float:
    """
    Divise deux valeurs numériques en respectant le comportement de PHP
    qui accepte les chaînes numériques.
    """
    # Conversion des paramètres numériques ou chaînes numériques
    for name, value in (('a', a), ('b', b)):
        if isinstance(value, str):
            try:
                # Convertit en int si possible, sinon en float
                converted = float(value) if ('.' in value or 'e' in value.lower()) else int(value)
                if name == 'a':
                    a = converted
                else:
                    b = converted
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
        else:
            # garde la valeur telle quelle (int ou float)
            if name == 'a':
                a = value
            else:
                b = value

    # Vérification de la division par zéro
    if b == 0:
        raise HTTPException(status_code=400, detail='Division par zero')
    return a / b

# aucune logique supplémentaire n'est requise au-delà de la conversion et de la vérification du zéro.


# ── formater_prix (score 98.0%, 1 itération(s)) ──
from fastapi import HTTPException

def formater_prix(montant) -> str:
    """
    Formate un montant en euros avec séparateurs de milliers et deux décimales.
    Accepte les int, float ou les chaînes représentant un nombre (ex: "42", "3.14").
    Lève une HTTPException 400 si la valeur n'est pas numérique.
    """
    # Conversion compatible PHP : accepte les chaînes numériques
    if isinstance(montant, str):
        try:
            montant = float(montant) if ('.' in montant or 'e' in montant.lower()) else int(montant)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique')
    elif not isinstance(montant, (int, float)):
        # Cas où le type n'est ni chaîne, ni nombre
        raise HTTPException(status_code=400, detail='Valeur non numérique')

    # Formatage avec séparateurs de milliers et deux décimales
    formatted = f"{montant:,.2f} EUR"
    return formatted


# ── calculer_remise (score 97.2%, 1 itération(s)) ──
from fastapi import HTTPException

def calculer_remise(prix, pourcentage):
    """
    Calcule le prix après application d'une remise.
    Accepte les nombres ou les chaînes numériques, comme le fait PHP.
    """
    # Conversion des paramètres au type numérique (int ou float) si nécessaire
    for _var_name, _var_value in (('prix', prix), ('pourcentage', pourcentage)):
        if isinstance(_var_value, str):
            try:
                # Convertit en int si pas de point décimal ni notation exponentielle,
                # sinon en float (comportement similaire à PHP)
                converted = float(_var_value) if ('.' in _var_value or 'e' in _var_value.lower()) else int(_var_value)
                if _var_name == 'prix':
                    prix = converted
                else:
                    pourcentage = converted
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
        else:
            # Si ce n'est pas une chaîne, on garde la valeur telle quelle (int ou float)
            if _var_name == 'prix':
                prix = _var_value
            else:
                pourcentage = _var_value

    # Validation de l'intervalle du pourcentage (invariant de sécurité)
    if pourcentage < 0 or pourcentage > 100:
        raise HTTPException(status_code=400, detail='Pourcentage invalide')

    # Calcul de la remise
    try:
        # Utilisation de la fonction déjà définie dans ce fichier pour la division,
        # afin de profiter d'éventuelles protections centralisées.
        remise = diviser(prix * pourcentage, 100)
    except Exception as e:
        # Propagation d'éventuelles erreurs de division (ex. division par zéro)
        raise HTTPException(status_code=500, detail=str(e))

    resultat = prix - remise

    # Formattage du prix final si besoin (fonction déjà disponible dans le même module)
    return formater_prix(resultat)
