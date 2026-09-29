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
        # La désérialisation a échoué, on lève une exception explicite.
        raise ValueError(f"Impossible de désérialiser la session : {exc}") from exc

    if not isinstance(session, dict):
        # On s'assure que le résultat est bien un mapping, comme attendu pour une session.
        raise TypeError("La session désérialisée doit être un dictionnaire.")

    return session

# convertie au format JSON avant la migration, car `json.loads` est requis pour éviter
# l'insecure_deserialization (CWE‑502).
# `HTTPException`; l'appelant doit gérer ces exceptions et les convertir en réponses HTTP
# appropriées dans le contexte FastAPI.


# ── afficher_page (score 83.0%, 1 itération(s)) ──
from fastapi import HTTPException
from pathlib import Path
from typing import List

# Liste blanche des pages autorisées – à adapter selon les besoins du projet
PAGE_ALLOWLIST: List[str] = [
    "home",
    "about",
    "contact",
    "products",
    # ajouter d'autres noms de pages valides ici
]

def afficher_page(page: str) -> str:
    """
    Charge et renvoie le contenu d'une page HTML statique.

    Parameters
    ----------
    page: str
        Nom de la page demandé (sans extension).

    Returns
    -------
    str
        Le contenu brut du fichier HTML.

    Raises
    ------
    HTTPException
        404 si la page n'est pas dans la liste blanche ou si le fichier est introuvable.
    """
    # Vérification de la liste blanche pour éviter l'inclusion de fichiers arbitraires
    if page not in PAGE_ALLOWLIST:
        raise HTTPException(status_code=404, detail="Page non trouvée")

    # Construction sécurisée du chemin du fichier
    file_path = Path("pages") / f"{page}.html"

    # Vérification que le fichier existe et est bien un fichier régulier
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Page non trouvée")

    # Lecture du fichier en mode texte UTF‑8
    try:
        return file_path.read_text(encoding="utf-8")
    except OSError as exc:
        # En cas d'erreur d'I/O, on renvoie une erreur serveur générique
        raise HTTPException(status_code=500, detail="Impossible de lire la page") from exc

# car le code PHP original utilisait `include` qui injecte le fichier dans la réponse.
# pour chaque nouvelle page ajoutée au répertoire `pages/`.


# ── sauvegarder_preferences (score 70.7%, 1 itération(s)) ──
import json
from fastapi import HTTPException
from typing import Dict, Any

def sauvegarder_preferences(prefs: Dict[str, Any]) -> str:
    """
    Sérialise les préférences en JSON après validation d'existence.
    Lève une HTTPException 400 si le dictionnaire est vide.
    """
    # validation_existence : on vérifie que le dictionnaire n'est pas vide
    if not prefs:
        raise HTTPException(status_code=400, detail="Preferences vides")
    try:
        # Utilisation sécurisée de JSON au lieu de pickle (insecure_deserialization)
        return json.dumps(prefs)
    except (TypeError, ValueError) as exc:
        # Si les données ne sont pas sérialisables en JSON, on renvoie une erreur claire
        raise HTTPException(status_code=500, detail="Erreur de sérialisation des préférences") from exc
