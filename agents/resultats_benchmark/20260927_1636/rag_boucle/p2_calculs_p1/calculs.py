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
    reproduisant le comportement de PHP is_numeric().
    """
    # Conversion du paramètre pour accepter les chaînes numériques comme PHP
    if isinstance(montant, str):
        try:
            montant = float(montant) if ('.' in montant or 'e' in montant.lower()) else int(montant)
        except ValueError:
            raise HTTPException(status_code=400, detail="Valeur non numérique")
    elif not isinstance(montant, (int, float)):
        # Cas où le type n'est ni chaîne, ni nombre (ex: list, dict, etc.)
        raise HTTPException(status_code=400, detail="Valeur non numérique")

    # Formatage avec séparateurs de milliers et deux décimales
    formatted = f"{montant:,.2f} EUR"
    return formatted

# même si la locale française utilise la virgule. Le format f"{x:,.2f}" respecte
# la consigne de garder le point décimal.
# Exception générique pour être cohérente avec les pratiques FastAPI.


# ── calculer_remise (score 76.2%, 1 itération(s)) ──
from fastapi import HTTPException

def calculer_remise(prix, pourcentage):
    """
    Calcule le prix après application d'une remise.
    Accepte les nombres ou les chaînes numériques, comme le fait PHP.
    """
    # Conversion des paramètres au type numérique (int ou float) selon la logique PHP
    for _name, _value in (('prix', prix), ('pourcentage', pourcentage)):
        if isinstance(_value, str):
            try:
                _converted = float(_value) if ('.' in _value or 'e' in _value.lower()) else int(_value)
            except ValueError:
                raise HTTPException(status_code=400, detail='Valeur non numérique')
            if _name == 'prix':
                prix = _converted
            else:
                pourcentage = _converted

    # Validation de l'intervalle du pourcentage (invariant de sécurité)
    if pourcentage < 0 or pourcentage > 100:
        raise HTTPException(status_code=400, detail='Pourcentage invalide')

    # Calcul de la remise
    montant_remise = prix * pourcentage / 100
    prix_final = prix - montant_remise

    # Utilisation éventuelle d'une fonction utilitaire déjà définie dans ce fichier
    # (formater_prix) pour formater le résultat si besoin.
    # Ici on renvoie la valeur brute ; le formatage pourra être appliqué en amont.
    return prix_final

# laissant le formatage éventuel à l'appelant via `formater_prix`.
# y compris la prise en compte du séparateur décimal '.' et de la notation exponentielle.
