"""
Migré automatiquement par SMAML depuis session.php
"""

# ── charger_session (score 83.9%, 1 itération(s)) ──
import json
from typing import Any, Dict

def charger_session(data: str) -> Dict[str, Any]:
    """
    Désérialise une session à partir d'une chaîne JSON.
    Remplace l'ancienne utilisation de `unserialize` (PHP) qui était vulnérable.
    Retourne un dictionnaire représentant la session.
    """
    try:
        session = json.loads(data)
    except json.JSONDecodeError as exc:
        # En cas de données corrompues ou non‑JSON, on lève une exception générique.
        # Dans un contexte FastAPI, on pourrait lever HTTPException(status_code=400, detail=str(exc))
        raise ValueError(f"Impossible de désérialiser la session : {exc}") from exc

    if not isinstance(session, dict):
        # On s'assure que la structure attendue est bien un dictionnaire.
        raise ValueError("La session désérialisée n'est pas un objet JSON valide (dict attendu)")

    return session

# ce qui correspond à un dict JSON en Python.
# dans l'application finale, il faudra éventuellement convertir cela en HTTPException.


# ── afficher_page (score 83.0%, 1 itération(s)) ──
from fastapi import HTTPException
from pathlib import Path
from markupsafe import escape

# Liste blanche des pages autorisées – à adapter selon les besoins du projet
ALLOWED_PAGES = {"home", "about", "contact", "products"}

def afficher_page(page: str) -> str:
    """
    Charge et renvoie le contenu d'une page HTML statique.

    Le nom de la page est fourni par l'utilisateur, il est donc
    strictement limité à la liste blanche `ALLOWED_PAGES` afin
    d'éviter les attaques de type Path Traversal.
    """
    # Vérification de la whitelist
    if page not in ALLOWED_PAGES:
        raise HTTPException(status_code=404, detail="Page non trouvée")

    # Construction sécurisée du chemin du fichier
    file_path = Path("pages") / f"{page}.html"

    # Vérification que le fichier existe et est bien un fichier
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Fichier de page introuvable")

    # Lecture du contenu du fichier
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Erreur de lecture du fichier") from exc

    # Retour du contenu tel quel (le HTML est déjà sécurisé côté source)
    return content


#   autorisées dans le projet, similaire aux exemples fournis.
#   du processus FastAPI ; il faut s'assurer que ce répertoire existe en production.


# ── sauvegarder_preferences (score 84.2%, 1 itération(s)) ──
import json
from typing import Any, Dict

from fastapi import HTTPException, status


def sauvegarder_preferences(prefs: Dict[str, Any]) -> str:
    """
    Sérialise les préférences en JSON après validation.

    - Vérifie que le dictionnaire n'est pas vide (validation_existence).
    - Utilise JSON pour éviter la désérialisation dangereuse (insecure_deserialization).
    - Lève une HTTPException 400 si les préférences sont vides.
    """
    if not prefs:
        # La fonction PHP levait une Exception générique, on utilise HTTPException pour le contexte API.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Preferences vides"
        )
    try:
        # json.dumps est sûr pour la sérialisation ; la désérialisation se fera avec json.loads ailleurs.
        return json.dumps(prefs)
    except (TypeError, ValueError) as exc:
        # Si les données ne sont pas sérialisables en JSON, on renvoie une erreur claire.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de sérialisation des préférences: {exc}"
        )
