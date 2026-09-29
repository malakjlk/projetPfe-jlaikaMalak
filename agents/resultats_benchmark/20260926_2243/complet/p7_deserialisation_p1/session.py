"""
Migré automatiquement par SMAML depuis session.php
"""

# ── charger_session (score 93.2%, 1 itération(s)) ──
import json
from typing import Any, Dict

from fastapi import HTTPException, status


def charger_session(data: str) -> Dict[str, Any]:
    """
    Désérialise une session au format JSON en un dictionnaire Python.
    La désérialisation utilise `json.loads` afin d'éviter les vulnérabilités
    liées à `pickle` (CWE‑502). Une vérification d'existence de la variable
    d'entrée est effectuée (validation_existence).
    """
    # validation_existence : on s'assure que le paramètre `data` est fourni
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le paramètre 'data' est requis."
        )

    try:
        session: Dict[str, Any] = json.loads(data)
    except json.JSONDecodeError as exc:
        # Gestion sécurisée de l'erreur de désérialisation
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Impossible de désérialiser la session : {exc.msg}"
        ) from exc

    return session

#                  le désérialiseur sécurisé recommandé est `json.loads`.
#                  définir un modèle Pydantic approprié si la structure de la session
#                  est connue dans le projet.


# ── afficher_page (score 0.0%, 1 itération(s)) ──
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

    - Le nom de la page est validé contre une liste blanche (ALLOWED_PAGES) pour
      éviter l'inclusion de fichiers arbitraires (protection contre Path Traversal).
    - Le fichier est recherché dans le répertoire `pages/` du projet.
    - En cas d'absence ou de page non autorisée, une HTTPException 404 est levée.
    - Le contenu est retourné tel quel (HTML déjà sécurisé côté source). Si le
      contenu devait contenir des données dynamiques, il faudrait les échapper
      avec `escape` avant l'injection dans le template.
    """
    # validation_existence : on s'assure que le paramètre est fourni
    if not page:
        raise HTTPException(status_code=400, detail="Le nom de la page est requis")

    # Protection contre l'inclusion de fichiers non prévus
    if page not in ALLOWED_PAGES:
        raise HTTPException(status_code=404, detail="Page non trouvée")

    # Construction sécurisée du chemin du fichier
    file_path = Path("pages") / f"{page}.html"

    # Vérification que le fichier existe réellement et qu'il est bien un fichier
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Fichier de page introuvable")

    try:
        # Lecture du fichier en texte UTF‑8
        content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        # Erreur d'accès disque ou de lecture
        raise HTTPException(status_code=500, detail="Impossible de lire la page") from exc

    # Retour du contenu brut ; aucune désérialisation dangereuse n'est effectuée
    return content


# ── sauvegarder_preferences (score 0.0%, 1 itération(s)) ──

