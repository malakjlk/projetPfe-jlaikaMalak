"""
Migré automatiquement par SMAML depuis calculs.php
"""

# ── diviser (score 98.0%, 1 itération(s)) ──
from fastapi import HTTPException

def diviser(a, b):
    """
    Divise deux valeurs numériques en respectant le comportement de PHP
    qui accepte les chaînes contenant des nombres.
    """
    # Conversion des paramètres numériques (acceptation des chaînes numériques)
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

#                 ce qui correspond à la gestion d'exception attendue dans un contexte FastAPI.


# ── formater_prix (score 98.0%, 1 itération(s)) ──
from fastapi import HTTPException

def formater_prix(montant) -> str:
    """
    Formate un montant monétaire en euros avec séparateurs de milliers
    et deux décimales, en respectant le comportement PHP de is_numeric().
    """
    # Acceptation des nombres ou des chaînes numériques (comportement PHP)
    if isinstance(montant, str):
        try:
            # Conversion en int ou float selon le contenu de la chaîne
            montant = float(montant) if ('.' in montant or 'e' in montant.lower()) else int(montant)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique')
    elif not isinstance(montant, (int, float)):
        # Tout autre type (ex: list, dict, None) est rejeté
        raise HTTPException(status_code=400, detail='Valeur non numérique')

    # Formatage avec séparateurs de milliers et deux décimales
    formatted = f"{montant:,.2f} EUR"
    return formatted


# ── calculer_remise (score 76.2%, 1 itération(s)) ──
from fastapi import HTTPException

def calculer_remise(prix, pourcentage):
    """
    Calcule le prix après application d'une remise.
    Accepte les nombres ou les chaînes numériques, comme le fait PHP.
    """
    # Conversion des paramètres au type numérique (int ou float) selon la logique PHP
    for name, value in (('prix', prix), ('pourcentage', pourcentage)):
        if isinstance(value, str):
            try:
                # PHP accepte les notations décimales et scientifiques
                converted = float(value) if ('.' in value or 'e' in value.lower()) else int(value)
                if name == 'prix':
                    prix = converted
                else:
                    pourcentage = converted
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
        else:
            # Si ce n'est pas une chaîne, on garde la valeur telle quelle (int ou float)
            if name == 'prix':
                prix = value
            else:
                pourcentage = value

    # Validation de l'intervalle du pourcentage (invariant de sécurité)
    if pourcentage < 0 or pourcentage > 100:
        raise HTTPException(status_code=400, detail='Pourcentage invalide')

    # Calcul de la remise
    try:
        # Utilisation de la fonction déjà définie dans le même fichier si besoin
        # (exemple d'utilisation éventuelle de `diviser` pour la division)
        remise = prix - (prix * pourcentage / 100)
    except Exception as exc:
        # En cas d'erreur inattendue (ex. division par zéro impossible ici)
        raise HTTPException(status_code=500, detail=str(exc))

    # Optionnel : formatage du prix final avec la fonction du même module
    # (décommenter la ligne suivante si le projet attend un formatage spécifique)
    # remise = formater_prix(remise)

    return remise

#                     car le code PHP original ne formatte pas le prix.
#                  conformément aux exigences du projet.
