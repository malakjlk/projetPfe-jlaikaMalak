"""
Migré automatiquement par SMAML depuis calculs.php
"""

# ── diviser (score 98.0%, 1 itération(s)) ──
from fastapi import HTTPException

def diviser(a, b):
    """
    Divise deux valeurs numériques en respectant le comportement de PHP
    qui accepte les chaînes numériques.
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
            montant = float(montant) if ('.' in montant or 'e' in montant.lower()) else int(montant)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique')
    elif not isinstance(montant, (int, float)):
        # Cas où le type n'est ni chaîne ni nombre (ex: None, list, etc.)
        raise HTTPException(status_code=400, detail='Valeur non numérique')

    # Formatage avec séparateurs de milliers et deux décimales
    formatted = f"{montant:,.2f} EUR"
    return formatted


# ── calculer_remise (score 98.2%, 1 itération(s)) ──
from fastapi import HTTPException

def calculer_remise(prix, pourcentage):
    """
    Calcule le prix après application d'une remise.
    Accepte les nombres ou les chaînes numériques, comme le fait PHP.
    """
    # Conversion des paramètres au type numérique (int ou float) si nécessaire
    for name, value in (('prix', prix), ('pourcentage', pourcentage)):
        if isinstance(value, str):
            try:
                # Convertit en int si la chaîne ne contient pas de point ou d'exposant,
                # sinon en float (comportement similaire à PHP)
                converted = float(value) if ('.' in value or 'e' in value.lower()) else int(value)
                if name == 'prix':
                    prix = converted
                else:
                    pourcentage = converted
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
        elif not isinstance(value, (int, float)):
            # Rejette tout type non numérique (ex: bool, list, dict...)
            raise HTTPException(status_code=400, detail='Valeur non numérique')

    # Validation de l'intervalle du pourcentage (invariant de sécurité)
    if pourcentage < 0 or pourcentage > 100:
        raise HTTPException(status_code=400, detail='Pourcentage invalide')

    # Calcul de la remise
    try:
        # Utilisation de la fonction déjà définie dans ce module pour la division,
        # afin de profiter d'éventuelles protections centralisées.
        remise = diviser(prix * pourcentage, 100)
    except Exception as e:
        # Propagation d'éventuelles erreurs de division (ex: division par zéro)
        raise HTTPException(status_code=500, detail=str(e))

    resultat = prix - remise

    # Formattage du prix final si besoin (fonction déjà disponible dans le même fichier)
    # Ici on renvoie la valeur brute ; le formatage pourra être appliqué par l'appelant.
    return resultat

#                     (gestion du zéro) et qu'elle renvoie un float/int compatible.
#                 comportement exact du formatage (locale, décimales) n'est pas précisé.
