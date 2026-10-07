"""
Migré automatiquement par SMAML depuis session.php
"""

# ── charger_session (score 98.9%, 1 itération(s)) ──
import json
from typing import Any, Dict

def charger_session(data: str) -> Dict[str, Any]:
    """
    Désérialise une session au format JSON.

    Args:
        data: Chaîne JSON représentant la session.

    Returns:
        Un dictionnaire contenant les données de session.

    Raises:
        ValueError: Si le JSON fourni est invalide.
    """
    try:
        session = json.loads(data)
    except json.JSONDecodeError as exc:
        # La désérialisation JSON a échoué → on lève une erreur explicite
        raise ValueError("Données de session non valides") from exc

    if not isinstance(session, dict):
        # On s'assure que le résultat est bien un mapping, comme attendu pour une session
        raise ValueError("La session désérialisée doit être un dictionnaire")

    return session

#                 dans un contexte interne (ex. service FastAPI) où le gestionnaire d'erreurs pourra convertir
#                 l'exception en réponse HTTP appropriée.


# ── afficher_page (score 83.0%, 1 itération(s)) ──
from fastapi import HTTPException
from pathlib import Path
from markupsafe import escape

# Liste blanche des pages autorisées – à adapter selon les besoins du projet
PAGES_AUTORISEES = {
    "home",
    "about",
    "contact",
    "products",
    # ajouter d'autres noms de pages sans l'extension ici
}

def afficher_page(page: str) -> str:
    """
    Charge et renvoie le contenu d'une page HTML statique.

    Args:
        page: Nom de la page demandé (sans extension).

    Returns:
        Le contenu HTML de la page.

    Raises:
        HTTPException 404 si la page n'est pas dans la liste blanche.
        HTTPException 500 si la lecture du fichier échoue.
    """
    # Sécurité : on ne garde que les pages explicitement autorisées
    if page not in PAGES_AUTORISEES:
        raise HTTPException(status_code=404, detail="Page non trouvée")

    # Construction sécurisée du chemin du fichier
    chemin_fichier = Path("pages") / f"{page}.html"

    # Vérification que le chemin reste dans le répertoire autorisé
    try:
        chemin_fichier = chemin_fichier.resolve(strict=True)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Page non trouvée")

    if not str(chemin_fichier).startswith(str(Path("pages").resolve())):
        # Protection contre les tentatives de traversal (../)
        raise HTTPException(status_code=400, detail="Chemin de page invalide")

    # Lecture du fichier
    try:
        contenu = chemin_fichier.read_text(encoding="utf-8")
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Erreur lors de la lecture de la page") from exc

    # On échappe le contenu au cas où il contiendrait des caractères dangereux
    # (exemple de précaution supplémentaire)
    return escape(contenu)


# ── sauvegarder_preferences (score 70.7%, 1 itération(s)) ──
import json
from typing import Any, Dict

from fastapi import HTTPException, status


def sauvegarder_preferences(prefs: Dict[str, Any]) -> str:
    """
    Sérialise les préférences en JSON après validation d'existence.

    Args:
        prefs: Dictionnaire contenant les préférences à sauvegarder.

    Returns:
        Une chaîne JSON représentant les préférences.

    Raises:
        HTTPException: Si le dictionnaire est vide.
        HTTPException: Si la sérialisation JSON échoue.
    """
    # validation_existence : vérifie que l'objet existe et n'est pas vide
    if not prefs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Preferences vides"
        )

    try:
        # Utilisation sécurisée de JSON au lieu de pickle (insecure_deserialization)
        serialized = json.dumps(prefs)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de sérialisation des préférences: {exc}"
        ) from exc

    return serialized
