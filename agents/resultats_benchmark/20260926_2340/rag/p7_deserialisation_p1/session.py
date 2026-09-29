"""
Migré automatiquement par SMAML depuis session.php
"""

# ── charger_session (score 98.9%, 1 itération(s)) ──
import json
from typing import Any, Dict

def charger_session(data: str) -> Dict[str, Any]:
    """
    Désérialise les données de session au format JSON de façon sécurisée.
    Retourne un dictionnaire représentant la session.
    """
    try:
        session = json.loads(data)
    except json.JSONDecodeError as exc:
        # La désérialisation a échoué, on lève une exception générique.
        raise ValueError(f"Impossible de désérialiser la session : {exc}") from exc

    if not isinstance(session, dict):
        # On s'assure que le résultat est bien un mapping, comme attendu pour une session.
        raise TypeError("La session désérialisée doit être un dictionnaire.")

    return session


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
    # ajouter d'autres noms de pages ici
}

def afficher_page(page: str) -> str:
    """
    Charge et renvoie le contenu d'une page HTML statique.

    Le nom de la page est fourni par l'utilisateur (ex. via un paramètre de requête).
    Pour éviter les vulnérabilités d'inclusion de fichiers (LFI), le nom est
    comparé à une liste blanche. Le fichier est ensuite lu depuis le répertoire
    ``pages/`` et son contenu est retourné sous forme de chaîne.

    Args:
        page: Nom de la page demandé (sans extension).

    Returns:
        Le contenu HTML de la page.

    Raises:
        HTTPException 404 si la page n'est pas dans la liste blanche.
        HTTPException 500 si le fichier ne peut pas être lu.
    """
    # Validation du nom de page contre la liste blanche
    if page not in PAGES_AUTORISEES:
        raise HTTPException(status_code=404, detail="Page non trouvée")

    # Construction sécurisée du chemin du fichier
    chemin_fichier = Path("pages") / f"{page}.html"

    # Vérification que le fichier existe et est bien un fichier régulier
    if not chemin_fichier.is_file():
        raise HTTPException(status_code=404, detail="Page non trouvée")

    try:
        # Lecture du fichier en mode texte UTF‑8
        contenu = chemin_fichier.read_text(encoding="utf-8")
        # On échappe le contenu au cas où il contiendrait des caractères dangereux
        # (ex. si le fichier était généré dynamiquement). Cela ne modifie pas le HTML
        # déjà sûr, mais protège contre d'éventuelles injections.
        return escape(contenu)
    except Exception as e:
        # En cas d'erreur de lecture, on renvoie une erreur serveur générique.
        raise HTTPException(status_code=500, detail="Erreur interne du serveur") from e


# ── sauvegarder_preferences (score 70.7%, 1 itération(s)) ──
import json
from fastapi import HTTPException, status
from typing import Dict, Any

def sauvegarder_preferences(prefs: Dict[str, Any]) -> str:
    """
    Sérialise les préférences en JSON après validation d'existence.
    Lève une HTTPException 400 si le dictionnaire est vide.
    """
    # validation_existence : vérifie que l'objet existe et n'est pas vide
    if not prefs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Preferences vides"
        )
    # Utilisation sécurisée de JSON au lieu de pickle (insecure_deserialization)
    try:
        serialized = json.dumps(prefs)
    except (TypeError, ValueError) as exc:
        # Si les données ne sont pas sérialisables en JSON, on renvoie une erreur claire
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de sérialisation des préférences: {exc}"
        )
    return serialized
