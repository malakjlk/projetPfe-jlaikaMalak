"""
Migré automatiquement par SMAML depuis session.php
"""

# ── charger_session (score 92.4%, 1 itération(s)) ──
import json
from typing import Any, Dict

from fastapi import HTTPException, status


def charger_session(data: str) -> Dict[str, Any]:
    """
    Désérialise une session encodée en JSON.

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
import os
from fastapi import HTTPException
from fastapi.responses import HTMLResponse

def afficher_page(page: str) -> HTMLResponse:
    """
    Charge et renvoie le contenu d'un fichier HTML dynamique.
    Le fichier recherché doit se situer dans le répertoire `templates/` et
    porter l'extension `.html`. Cette fonction remplace l'ancienne inclusion PHP
    `include($page . ".php")`.

    Parameters
    ----------
    page: str
        Nom du fichier (sans extension) à inclure.

    Returns
    -------
    HTMLResponse
        Réponse contenant le contenu du fichier demandé.

    Raises
    ------
    HTTPException
        - 404 si le fichier n'existe pas.
        - 400 si le nom fourni contient des caractères de traversée de répertoire.
    """
    if ".." in page or "/" in page or "\\" in page:
        raise HTTPException(status_code=400, detail="Nom de page invalide")

    # Construction sécurisée du chemin absolu du fichier
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "templates"))
    file_path = os.path.abspath(os.path.join(base_dir, f"{page}.html"))

    # Vérifier que le chemin résolu reste bien dans le répertoire autorisé
    if not file_path.startswith(base_dir):
        raise HTTPException(status_code=400, detail="Chemin de fichier non autorisé")

    # Lire le fichier de façon sûre
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Page non trouvée")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Erreur d'accès au fichier: {e}")

    return HTMLResponse(content=content)


# ── sauvegarder_preferences (score 70.7%, 1 itération(s)) ──
import json
from fastapi import HTTPException
from typing import Any, Dict

def sauvegarder_preferences(prefs: Dict[str, Any]) -> str:
    """
    Sérialise les préférences en JSON sécurisé.

    - Vérifie que le dictionnaire `prefs` n'est pas vide (validation_existence).
    - Utilise `json.dumps` au lieu de `pickle` pour éviter la désérialisation non sécurisée.
    - En cas d'erreur, lève une `HTTPException` avec le code 400.
    """
    # validation_existence : on s'assure que les préférences existent et ne sont pas vides
    if not prefs:
        raise HTTPException(status_code=400, detail="Preferences vides")

    try:
        # sérialisation sécurisée en JSON
        return json.dumps(prefs)
    except (TypeError, ValueError) as exc:
        # si les données ne sont pas sérialisables en JSON, on renvoie une erreur HTTP
        raise HTTPException(status_code=400, detail=f"Erreur de sérialisation des préférences: {exc}")

#   j'ai donc choisi `Dict[str, Any]` pour couvrir les cas les plus courants.
#   afin d'être cohérente avec la gestion d'erreurs attendue dans le reste du projet.
