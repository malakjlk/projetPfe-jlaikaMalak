"""
Migré automatiquement par SMAML depuis session.php
"""

# ── charger_session (score 67.9%, 2 itération(s)) ──
import os
from typing import Any, Optional

import phpserialize  # pip install phpserialize


def charger_session(data: str) -> Optional[Any]:
    """
    Désérialise une chaîne au format PHP `serialize` et renvoie l'objet Python
    correspondant.

    Paramètres
    ----------
    data: str
        Chaîne contenant les données sérialisées au format PHP.

    Retour
    ------
    Optional[Any]
        - L'objet désérialisé (généralement un dict, list, int, str, etc.).
        - ``None`` si la désérialisation échoue ou si ``data`` est vide.

    Exceptions
    ----------
    ValueError
        Levée lorsqu'une erreur de désérialisation survient (format invalide,
        données corrompues, etc.). Le message d'erreur décrit le problème.
    """
    if not data:
        # Aucun contenu à désérialiser → comportement équivalent à PHP qui
        # retournerait null/false.
        return None

    try:
        # phpserialize.loads attend des bytes ; on encode la chaîne en UTF‑8.
        # ``decode_strings=True`` convertit les chaînes PHP en str Python.
        result = phpserialize.loads(
            data.encode("utf-8"),
            decode_strings=True,
            object_hook=phpserialize.phpobject,
        )
        return result
    except phpserialize.UnserializationError as exc:
        # Erreur de format PHP – on la remonte comme ValueError pour que le
        # code appelant puisse gérer le problème sans lever d'exception HTTP.
        raise ValueError(f"Erreur de désérialisation PHP : {exc}") from exc
    except Exception as exc:  # pragma: no cover
        # Toute autre exception inattendue est également transformée.
        raise ValueError(f"Erreur inattendue lors de la désérialisation : {exc}") from exc


# `unserialize`, qui peut être de n'importe quel type (dict, list, int, etc.).
# J'ai donc typé le retour comme ``Optional[Any]`` pour conserver cette
# flexibilité.
# l'environnement du projet (``pip install phpserialize``). Sans elle,
# la désérialisation sécurisée du format PHP n'est pas possible.


# ── afficher_page (score 79.0%, 1 itération(s)) ──
import os
from fastapi import HTTPException
from markupsafe import escape

# Liste blanche des pages autorisées – à adapter selon les besoins du projet
ALLOWED_PAGES = {
    "home",
    "about",
    "contact",
    "products",
    # ajouter d'autres noms de pages autorisées ici
}

def afficher_page(page: str) -> str | None:
    """
    Charge et renvoie le contenu d'une page HTML statique.

    Le nom de la page est validé contre une whitelist afin d'éviter les
    inclusions de fichiers arbitraires (vulnérabilité LFI). Le chemin de base
    est récupéré depuis la variable d'environnement ``PAGE_ROOT`` ; si elle
    n'est pas définie, on utilise le répertoire ``pages`` du projet comme
    valeur par défaut, reproduisant le comportement du code PHP d'origine.

    Retourne ``None`` si la page n'est pas autorisée ou si le fichier est
    introuvable. Aucun ``HTTPException`` n'est levé ici ; la fonction se
    contente de renvoyer ``None`` pour que la couche appelante décide du
    traitement (ex. : renvoyer une 404 HTTP).
    """
    # Validation du nom de page
    if page not in ALLOWED_PAGES:
        # Page non autorisée → on ne lève pas d'exception HTTP ici
        return None

    # Construction du chemin du fichier de façon sécurisée
    base_dir = os.getenv("PAGE_ROOT", os.path.join(os.path.dirname(__file__), "pages"))
    file_path = os.path.abspath(os.path.join(base_dir, f"{page}.html"))

    # Vérification que le fichier réside bien dans le répertoire autorisé
    if not file_path.startswith(os.path.abspath(base_dir)):
        # Tentative d'accès hors du répertoire autorisé
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        # Le fichier demandé n'existe pas
        return None

    # On échappe le contenu au cas où il contiendrait des caractères dangereux
    # (même si les pages sont statiques, cela renforce la sécurité).
    return escape(content)


# ── sauvegarder_preferences (score 85.1%, 1 itération(s)) ──
import json
from typing import Any, Dict

def sauvegarder_preferences(prefs: Dict[str, Any]) -> str:
    """
    Sérialise les préférences utilisateur.

    - Vérifie que le dictionnaire ``prefs`` n'est pas vide.
    - Lève une ``ValueError`` si aucune préférence n'est fournie,
      afin de respecter l'invariant de validation d'existence.
    - Retourne la représentation JSON du dictionnaire, équivalente
      à la chaîne sérialisée produite par ``serialize`` en PHP.
    """
    # validation_existence : le paramètre doit exister et contenir au moins une entrée
    if not prefs:
        raise ValueError("Preferences vides")

    # Utilisation de JSON (plus sûr et interopérable que pickle) pour la sérialisation
    return json.dumps(prefs, ensure_ascii=False)


#                     En Python, on remplace cela par ``json.dumps`` qui fournit un format
#                     texte lisible et compatible avec la plupart des usages modernes.
