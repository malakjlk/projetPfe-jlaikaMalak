"""
Migré automatiquement par SMAML depuis calculs.php
"""

# ── diviser (score 98.0%, 1 itération(s)) ──
from fastapi import HTTPException
from typing import Union

def diviser(a: Union[int, float, str], b: Union[int, float, str]) -> float:
    """
    Divise deux valeurs en reproduisant le comportement PHP qui accepte les
    chaînes numériques. Lève une HTTPException 400 si la conversion échoue
    ou si le diviseur vaut zéro.
    """
    # Conversion des paramètres numériques (compatible PHP)
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

    # Vérification du diviseur
    if b == 0:
        raise HTTPException(status_code=400, detail='Division par zero')

    return a / b


# ── formater_prix (score 98.0%, 1 itération(s)) ──
from fastapi import HTTPException

def formater_prix(montant) -> str:
    """
    Formate un montant en euros avec séparateurs de milliers et deux décimales.
    Accepte les nombres (int, float) ainsi que les chaînes numériques,
    reproduisant le comportement de PHP `is_numeric`.
    """
    # Conversion du paramètre pour accepter les chaînes numériques comme PHP le fait
    if isinstance(montant, str):
        try:
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
            # Rejette tout type non numérique (ex: None, bool, list, etc.)
            raise HTTPException(status_code=400, detail='Valeur non numérique')

    # Validation de l'intervalle du pourcentage (invariant de sécurité)
    if pourcentage < 0 or pourcentage > 100:
        raise HTTPException(status_code=400, detail='Pourcentage invalide')

    # Calcul de la remise
    try:
        # Utilisation de la fonction déjà définie dans ce fichier si besoin futur
        # (exemple d'appel éventuel) : prix_remise = diviser(prix * pourcentage, 100)
        # Mais ici on effectue le calcul directement pour plus de clarté.
        resultat = prix - (prix * pourcentage / 100)
    except Exception as exc:
        # Capture d'éventuelles erreurs arithmétiques (ex: division par zéro improbable ici)
        raise HTTPException(status_code=500, detail=str(exc))

    # Formattage éventuel du prix via la fonction existante dans ce module
    # (décommenter si le formatage est requis dans le contexte d'utilisation)
    # resultat = formater_prix(resultat)

    return resultat

# mais la fonction formater_prix est disponible si besoin.
# incluant la prise en charge des notations exponentielles.
