"""
Migré automatiquement par SMAML depuis session.php
"""

# ── charger_session (score 98.9%, 1 itération(s)) ──
import json
from typing import Any, Dict

def charger_session(data: str) -> Dict[str, Any]:
    """
    Désérialise une session au format JSON en un dictionnaire Python.
    Utilise json.loads pour éviter la désérialisation dangereuse (pickle).
    """
    try:
        session = json.loads(data)
    except json.JSONDecodeError as exc:
        # En cas de données mal formées, on lève une exception générique.
        # Dans un contexte FastAPI, on pourrait lever HTTPException(status_code=400, detail=str(exc))
        raise ValueError(f"Impossible de désérialiser la session : {exc}") from exc

    if not isinstance(session, dict):
        # La fonction attend un objet JSON représentant un mapping.
        raise TypeError("La session désérialisée doit être un dictionnaire")

    return session

# SMAML-HYPOTHÈSE: la session est stockée sous forme JSON et représente un dictionnaire générique.


# ── afficher_page (score 83.0%, 1 itération(s)) ──
from fastapi import HTTPException
from pathlib import Path
from markupsafe import escape

# Liste blanche des pages autorisées – à adapter selon les besoins du projet
ALLOWED_PAGES = {
    "home",
    "about",
    "contact",
    "products",
    # ajouter d'autres noms de page sans l'extension ici
}

def afficher_page(page: str) -> str:
    """
    Charge et renvoie le contenu d'une page HTML dynamique.

    Args:
        page: Nom de la page demandé (sans extension).

    Returns:
        Le contenu HTML de la page.

    Raises:
        HTTPException 404 si la page n'est pas dans la liste blanche.
        HTTPException 500 si la lecture du fichier échoue.
    """
    # Sécurité : on ne charge que des pages explicitement autorisées
    if page not in ALLOWED_PAGES:
        raise HTTPException(status_code=404, detail="Page non trouvée")

    # Construction sécurisée du chemin du fichier
    file_path = Path("pages") / f"{page}.html"

    # Vérification que le fichier existe et est bien un fichier régulier
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Page non trouvée")

    try:
        # Lecture du fichier en mode texte UTF‑8
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        # En cas d'erreur I/O, on renvoie une erreur serveur générique
        raise HTTPException(status_code=500, detail="Impossible de lire la page") from exc

    # On échappe le contenu au cas où il contiendrait des caractères dangereux
    # (exemple de précaution supplémentaire, même si le fichier est contrôlé).
    return escape(content)


# ── sauvegarder_preferences (score 70.7%, 1 itération(s)) ──
import json
from typing import Any, Dict

from fastapi import HTTPException, status


def sauvegarder_preferences(prefs: Dict[str, Any]) -> str:
    """
    Sérialise les préférences en JSON après validation.

    - Vérifie que le dictionnaire `prefs` n'est pas vide (validation_existence).
    - Utilise `json.dumps` pour éviter la désérialisation dangereuse (insecure_deserialization).
    - Lève une `HTTPException` avec le code 400 si les préférences sont vides.
    """
    if not prefs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Preferences vides"
        )

    try:
        # json.dumps est sûr pour la sérialisation de données fiables
        serialized = json.dumps(prefs)
    except (TypeError, ValueError) as exc:
        # SMAML-HYPOTHÈSE: les préférences peuvent contenir des types non JSON‑serialisables,
        # on considère cela comme une erreur de requête.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de sérialiser les préférences: {exc}"
        ) from exc

    return serialized
