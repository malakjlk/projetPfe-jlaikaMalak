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
        # On s'attend à ce que la session soit un objet JSON (dict en Python).
        raise TypeError("La session désérialisée doit être un dictionnaire.")

    return session


# ── afficher_page (score 83.0%, 1 itération(s)) ──
from fastapi import HTTPException
from pathlib import Path
from markupsafe import escape

# Liste blanche des pages autorisées – à adapter selon les besoins du projet
PAGE_ALLOWLIST = {
    "home",
    "about",
    "contact",
    "products",
}

def afficher_page(page: str) -> str:
    """
    Charge et renvoie le contenu d'une page HTML statique.

    Le nom de la page est fourni par l'utilisateur (ex. via un paramètre de requête).
    Pour éviter les vulnérabilités d'inclusion de fichiers (LFI), le nom est
    vérifié contre une liste blanche et le chemin est résolu de façon sécurisée.
    """
    # Vérification de la liste blanche
    if page not in PAGE_ALLOWLIST:
        raise HTTPException(status_code=404, detail="Page non trouvée")

    # Construction sécurisée du chemin du fichier
    base_dir = Path(__file__).parent / "pages"
    file_path = (base_dir / f"{page}.html").resolve()

    # S'assurer que le fichier réside bien dans le répertoire autorisé
    if not str(file_path).startswith(str(base_dir.resolve())):
        raise HTTPException(status_code=400, detail="Chemin de page invalide")

    try:
        content = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Page non trouvée")
    except OSError:
        raise HTTPException(status_code=500, detail="Erreur de lecture de la page")

    # Échappement du contenu si besoin (exemple de bonne pratique)
    # Ici on suppose que le fichier contient déjà du HTML sûr.
    return content

# SMAML-HYPOTHÈSE: le répertoire contenant les pages s'appelle « pages » et les fichiers sont au format .html.


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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de sérialisation des préférences: {exc}"
        )
    return serialized

#                  même si le code PHP original utilisait Exception.
