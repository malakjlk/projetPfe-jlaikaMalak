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
        # La donnée fournie n'est pas du JSON valide → on lève une exception générique.
        raise ValueError(f"Données de session invalides: {exc}") from exc

    if not isinstance(session, dict):
        # On s'attend à ce que la session soit représentée sous forme de mapping.
        raise TypeError("La session désérialisée doit être un dictionnaire.")

    return session


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
    # ajouter d'autres noms de pages ici
}

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
        Le contenu HTML de la page.

    Raises
    ------
    HTTPException
        404 – si la page n'est pas dans la liste blanche ou n'existe pas.
    """
    # Sécurité : on ne charge que des pages explicitement autorisées
    if page not in ALLOWED_PAGES:
        raise HTTPException(status_code=404, detail="Page non trouvée")

    # Construction sécurisée du chemin du fichier
    base_path = Path(__file__).parent / "pages"
    file_path = (base_path / f"{page}.html").resolve()

    # Vérifier que le chemin résolu reste bien dans le répertoire autorisé
    if not str(file_path).startswith(str(base_path.resolve())):
        raise HTTPException(status_code=400, detail="Chemin de page invalide")

    try:
        return file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Page non trouvée")
    except OSError:
        raise HTTPException(status_code=500, detail="Erreur lors de la lecture de la page")

# car le code PHP original utilisait `include` qui injecte le fichier dans la réponse.


# ── sauvegarder_preferences (score 70.7%, 1 itération(s)) ──
import json
from fastapi import HTTPException
from typing import Any, Dict


def sauvegarder_preferences(prefs: Dict[str, Any]) -> str:
    """
    Sauvegarde les préférences en les sérialisant de façon sécurisée.

    - Vérifie que le dictionnaire n'est pas vide (validation_existence).
    - Utilise JSON pour la sérialisation afin d'éviter la désérialisation
      dangereuse (CWE‑502).
    """
    if not prefs:
        # Validation d'existence : les préférences ne doivent pas être vides
        raise HTTPException(status_code=400, detail="Preferences vides")
    try:
        # Sérialisation sécurisée en JSON (pas de pickle)
        return json.dumps(prefs)
    except (TypeError, ValueError) as exc:
        # En cas d'objet non sérialisable en JSON
        raise HTTPException(status_code=500, detail="Erreur de sérialisation") from exc


#                 n'instancie pas directement d'application FastAPI.
