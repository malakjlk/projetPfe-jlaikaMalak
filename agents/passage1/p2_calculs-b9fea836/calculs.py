"""
Migré automatiquement par SMAML depuis calculs.php
"""

# ── diviser (score 99.4%, 2 itération(s)) ──
from typing import Union

Number = Union[int, float, str]


def _coerce_numeric(value: Number) -> Union[int, float]:
    """
    Convertit une valeur numérique ou une chaîne représentant un nombre
    en int ou float, en suivant le comportement de PHP qui accepte les
    chaînes numériques. Lève une ``Exception`` si la conversion échoue.
    """
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            # PHP convertit en int si la chaîne ne contient pas de point ou d'exposant
            return float(value) if ('.' in value or 'e' in value.lower()) else int(value)
        except ValueError:
            raise Exception('Valeur non numérique')
    raise Exception('Type de valeur inattendu')


def diviser(a: Number, b: Number) -> Union[int, float]:
    """
    Retourne le résultat de la division de ``a`` par ``b``.

    - Les deux paramètres peuvent être des nombres ou des chaînes numériques,
      comme en PHP où le cast implicite est autorisé.
    - Lève ``Exception`` avec le même message que le code PHP d'origine
      lorsqu'une division par zéro est tentée.
    """
    a_num = _coerce_numeric(a)
    b_num = _coerce_numeric(b)

    if b_num == 0:
        raise Exception("Division par zero")
    return a_num / b_num

#                    donc on accepte les chaînes numériques en suivant le
#                    pattern de conversion indiqué.
#                 compatible avec le contrat d'origine, même si
#                 ``ValueError`` serait plus idiomatique en Python.


# ── formater_prix (score 100.0%, 1 itération(s)) ──
from typing import Union

def formater_prix(montant: Union[int, float, str]) -> str:
    if isinstance(montant, bool):
        raise ValueError("Montant invalide")

    if isinstance(montant, str):
        try:
            valeur = float(montant) if ('.' in montant or 'e' in montant.lower()) else int(montant)
        except ValueError:
            raise ValueError("Montant invalide")
    elif isinstance(montant, (int, float)):
        valeur = montant
    else:
        raise ValueError("Montant invalide")

    return f"{valeur:,.2f} EUR"


# ── calculer_remise (score 97.6%, 3 itération(s)) ──
from typing import Union
from fastapi import HTTPException


def calculer_remise(prix: Union[float, int, str], pourcentage: Union[float, int, str]) -> float:
    if isinstance(prix, str):
        try:
            prix = float(prix) if ('.' in prix or 'e' in prix.lower()) else int(prix)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique')
    elif not isinstance(prix, (int, float)):
        raise ValueError("Prix invalide")

    if isinstance(pourcentage, str):
        try:
            pourcentage = float(pourcentage) if ('.' in pourcentage or 'e' in pourcentage.lower()) else int(pourcentage)
        except ValueError:
            raise HTTPException(status_code=400, detail='Valeur non numérique')
    elif not isinstance(pourcentage, (int, float)):
        raise ValueError("Pourcentage invalide")

    if pourcentage < 0 or pourcentage > 100:
        raise ValueError("Pourcentage invalide")

    return prix - (prix * pourcentage / 100)
