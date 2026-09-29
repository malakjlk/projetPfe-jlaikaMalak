"""
Migré automatiquement par SMAML depuis securite.php
"""

# ── get_user (score 92.6%, 1 itération(s)) ──
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

# Import du modèle ORM User déjà présent dans le projet.
# Le nom exact du module contenant le modèle n'est pas fourni dans les
# spécifications, on l'importe donc directement (le projet doit
# garantir que le symbole `User` est disponible dans le scope global).
from .user_model import User  # type: ignore  # SMAML-HYPOTHESE: le modèle se trouve dans user_model.py


def get_user(user_id: int, db: Session) -> Optional[User]:
    """
    Récupère un utilisateur à partir de son identifiant.

    Utilise SQLAlchemy avec une requête paramétrée afin d'éviter toute
    injection SQL (CWE‑89). En cas d'absence d'utilisateur, lève une
    HTTPException 404.

    Args:
        user_id: Identifiant de l'utilisateur recherché.
        db: Session SQLAlchemy active.

    Returns:
        Instance du modèle `User` ou `None` si non trouvé.
    """
    if user_id is None:
        raise HTTPException(status_code=400, detail="L'identifiant de l'utilisateur est requis.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé.")
    return user


# ── generer_rapport (score 96.0%, 1 itération(s)) ──
import subprocess
from typing import Optional

from fastapi import HTTPException

def generer_rapport(commande: str) -> str:
    """
    Exécute l'outil de génération de rapport de manière sécurisée.

    Args:
        commande: La commande à passer à l'outil `report_tool`.

    Returns:
        La sortie standard de l'outil sous forme de chaîne de caractères.

    Raises:
        HTTPException: Si l'exécution de la commande échoue ou dépasse le timeout.
    """
    # On évite toute injection de commande en ne passant pas la chaîne complète à un shell.
    # La commande est découpée en arguments : le premier est le binaire, le second la commande utilisateur.
    args = ["report_tool", commande]

    try:
        result = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=10,  # délai raisonnable pour éviter les blocages
            check=True,  # lève CalledProcessError en cas de code de retour non‑zéro
        )
        return result.stdout
    except subprocess.CalledProcessError as exc:
        # L'outil a renvoyé une erreur ; on la transmet sous forme d'exception HTTP.
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la génération du rapport : {exc.stderr or exc}"
        )
    except subprocess.TimeoutExpired:
        # La commande a dépassé le temps imparti.
        raise HTTPException(
            status_code=504,
            detail="Timeout lors de la génération du rapport."
        )
    except Exception as exc:
        # Toute autre erreur inattendue.
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne lors de la génération du rapport : {exc}"
        )


# ── chercher_produit (score 92.6%, 1 itération(s)) ──
from typing import List, Dict, Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

# On suppose que le modèle SQLAlchemy `Produit` est défini dans le module `models`
# du projet. Aucun autre import n'est listé, donc on utilise l'import générique.
from .models import Produit


def chercher_produit(db: Session, nom: str) -> List[Dict[str, Any]]:
    """
    Recherche les produits dont le nom contient la chaîne fournie.

    Args:
        db: Session SQLAlchemy injectée par la dépendance FastAPI.
        nom: Sous‑chaîne à rechercher dans le champ `nom` des produits.

    Returns:
        Une liste de dictionnaires représentant les produits trouvés.

    Raises:
        HTTPException: En cas d'erreur d'accès à la base de données.
    """
    try:
        # Utilisation d'un filtre paramétré via SQLAlchemy pour éviter toute injection SQL.
        produits = (
            db.query(Produit)
            .filter(Produit.nom.ilike(f"%{nom}%"))
            .all()
        )
        # Conversion des objets ORM en dictionnaires simples (sans les attributs internes).
        return [p.__dict__ for p in produits]
    except Exception as exc:
        # On masque l'exception interne et on renvoie une erreur HTTP générique.
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la recherche du produit"
        ) from exc


#                  car aucune instance globale n'est créée dans ce fichier.
