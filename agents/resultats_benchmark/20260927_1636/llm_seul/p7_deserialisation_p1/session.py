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
import json  # pour éviter toute désérialisation insecure (CWE‑502)

def afficher_page(page: str) -> HTMLResponse:
    """
    Charge et renvoie le contenu d'un fichier HTML/templating correspondant
    au nom fourni, similaire à `include($page . ".php")` en PHP.

    Le fichier recherché doit se situer dans le répertoire `templates/` du
    projet. Le chemin est construit de façon sécurisée afin d'éviter les
    attaques de type Path Traversal.
    """
    # Construction sécurisée du chemin du fichier
    base_dir = Path(__file__).parent / "templates"
    try:
        # Normalisation du nom de page (évite les caractères de chemin)
        safe_name = Path(page).name  # ne garde que le dernier composant
        target_path = (base_dir / f"{safe_name}.php").resolve()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Nom de page invalide") from exc

    # Vérification que le fichier réside bien dans le répertoire autorisé
    if not str(target_path).startswith(str(base_dir.resolve())):
        raise HTTPException(status_code=403, detail="Accès interdit au fichier demandé")

    # Lecture du fichier
    if not target_path.is_file():
        raise HTTPException(status_code=404, detail="Page non trouvée")

    try:
        content = target_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Erreur de lecture du fichier") from exc

    # Retourner le contenu tel quel (similaire à l'include PHP)
    return HTMLResponse(content=content)

# SMAML-HYPOTHÈSE: le répertoire contenant les fichiers à inclure s'appelle « templates/ »


# ── sauvegarder_preferences (score 70.7%, 1 itération(s)) ──
import json
from fastapi import HTTPException
from typing import Any, Dict

def sauvegarder_preferences(prefs: Dict[str, Any]) -> str:
    """
    Sérialise les préférences en JSON après validation d'existence.
    Lève une HTTPException 400 si le dictionnaire est vide.
    """
    # validation_existence : on vérifie que l'objet existe et n'est pas vide
    if not prefs:
        raise HTTPException(status_code=400, detail="Preferences vides")
    
    try:
        # Utilisation sécurisée de JSON au lieu de pickle (insecure_deserialization)
        serialized = json.dumps(prefs)
    except (TypeError, ValueError) as e:
        # En cas d'objet non sérialisable, on renvoie une erreur explicite
        raise HTTPException(status_code=500, detail=f"Erreur de sérialisation des préférences: {e}")
    
    return serialized
