"""
Migré automatiquement par SMAML depuis session.php
"""

# ── charger_session (score 92.4%, 1 itération(s)) ──
import json
from typing import Any, Dict

from fastapi import HTTPException, status


def charger_session(data: str) -> Dict[str, Any]:
    """
    Désérialise de façon sécurisée les données de session au format JSON.

    Args:
        data: Chaîne JSON représentant la session.

    Returns:
        Un dictionnaire contenant les données de session.

    Raises:
        HTTPException: Si la désérialisation échoue (JSON invalide).
    """
    try:
        session: Dict[str, Any] = json.loads(data)
    except json.JSONDecodeError as exc:
        # La donnée fournie n'est pas un JSON valide → on renvoie une erreur 400
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Données de session invalides."
        ) from exc

    return session


# ── afficher_page (score 83.0%, 1 itération(s)) ──
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
import json  # pour éviter toute désérialisation insecure si besoin futur

def afficher_page(page: str) -> HTMLResponse:
    """
    Charge et renvoie le contenu d'un fichier HTML dynamique.
    Le fichier recherché doit être nommé `<page>.php` et se situer dans le
    répertoire `templates/` du projet.
    """
    # Construction sécurisée du chemin : on empêche les traversées de répertoires
    base_dir = Path(__file__).parent / "templates"
    target_path = (base_dir / f"{page}.php").resolve()

    # Vérifier que le chemin résolu reste bien dans le répertoire autorisé
    if not str(target_path).startswith(str(base_dir.resolve())):
        raise HTTPException(status_code=400, detail="Chemin de page invalide")

    # Lecture du fichier, gestion d’erreur si le fichier n’existe pas
    try:
        content = target_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Page non trouvée")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Erreur de lecture du fichier: {exc}")

    # Retourner le contenu comme réponse HTML
    return HTMLResponse(content=content)


# ── sauvegarder_preferences (score 70.7%, 1 itération(s)) ──
import json
from fastapi import HTTPException

def sauvegarder_preferences(prefs: dict) -> str:
    """
    Sauvegarde les préférences en les sérialisant au format JSON.

    - Vérifie que le dictionnaire `prefs` n'est pas vide (validation_existence).
    - Utilise `json.dumps` pour éviter la désérialisation dangereuse (CWE‑502).
    - Lève une `HTTPException` 400 si les préférences sont vides.
    """
    # validation_existence : on s'assure que la variable existe et n'est pas vide
    if not prefs:
        raise HTTPException(status_code=400, detail="Preferences vides")

    # Sérialisation sécurisée en JSON (pas de pickle)
    try:
        serialized = json.dumps(prefs)
    except (TypeError, ValueError) as exc:
        # Si les données ne sont pas sérialisables en JSON, on renvoie une erreur claire
        raise HTTPException(status_code=400, detail=f"Impossible de sérialiser les préférences: {exc}")

    return serialized
