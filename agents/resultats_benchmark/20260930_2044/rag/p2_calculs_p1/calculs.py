"""
Migré automatiquement par SMAML depuis calculs.php
"""

# ── diviser (score 98.0%, 1 itération(s)) ──
from fastapi import HTTPException
from typing import Union

def diviser(a: Union[int, float, str], b: Union[int, float, str]) -> float:
    """
    Divise deux valeurs en respectant le comportement de PHP qui accepte les
    chaînes numériques. Lève une HTTPException 400 si la conversion échoue
    ou si le diviseur est zéro.
    """
    # Conversion des paramètres numériques ou chaînes numériques
    for name, value in (('a', a), ('b', b)):
        if isinstance(value, str):
            try:
                # PHP convertit automatiquement en int si possible, sinon en float
                converted = float(value) if ('.' in value or 'e' in value.lower()) else int(value)
                if name == 'a':
                    a = converted
                else:
                    b = converted
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Valeur non numérique pour le paramètre '{name}'")
        else:
            # garde la valeur telle quelle (int ou float)
            if name == 'a':
                a = value
            else:
                b = value

    # Vérification du diviseur
    if b == 0:
        raise HTTPException(status_code=400, detail="Division par zero")

    return a / b


# ── formater_prix (score 98.0%, 1 itération(s)) ──
from fastapi import HTTPException

def formater_prix(montant) -> str:
    """
    Formate un montant en euros avec séparateurs de milliers et deux décimales.
    Accepte les nombres (int, float) ainsi que les chaînes numériques,
    reproduisant le comportement de PHP `is_numeric`.
    """
    # Conversion du paramètre pour accepter les chaînes numériques comme le ferait PHP
    if isinstance(montant, str):
        try:
            montant = float(montant) if ('.' in montant or 'e' in montant.lower()) else int(montant)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique')
    elif not isinstance(montant, (int, float)):
        # Tout autre type (ex: list, dict) est rejeté
        raise HTTPException(status_code=400, detail='Valeur non numérique')

    # Formatage avec séparateurs de milliers et deux décimales
    formatted = f"{montant:,.2f} EUR"
    return formatted

# même si la locale française utilise la virgule. Le format demandé suit exactement
# l'exemple PHP avec le point décimal et la virgule comme séparateur de milliers.


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
            # Rejette tout autre type (listes, dicts, objets, …)
            raise HTTPException(status_code=400, detail='Valeur non numérique')

    # Validation de l'intervalle du pourcentage (invariant de sécurité)
    if pourcentage < 0 or pourcentage > 100:
        raise HTTPException(status_code=400, detail='Pourcentage invalide')

    # Calcul de la remise
    try:
        # Utilisation de la fonction déjà définie dans ce module si besoin futur
        # (exemple d'appel possible) : prix = diviser(prix, 1)  # pas nécessaire ici
        resultat = prix - (prix * pourcentage / 100)
    except Exception as exc:
        # Capture d'éventuelles erreurs inattendues (ex. division par zéro impossible ici)
        raise HTTPException(status_code=500, detail=str(exc))

    # Formattage éventuel du prix (fonction déjà présente dans le même fichier)
    # return formater_prix(resultat)  # décommenter si le formatage est requis
    return resultat

#                  le résultat formaté, mais le code PHP original renvoie un nombre brut.
#                  '3.14' → float, '1e3' → float. Tout autre format déclenche une HTTPException.
