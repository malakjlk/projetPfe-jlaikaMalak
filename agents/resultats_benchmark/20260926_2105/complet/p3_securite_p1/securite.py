"""
Migré automatiquement par SMAML depuis securite.php
"""

# ── get_user (score 92.6%, 1 itération(s)) ──
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

# Supposons que le modèle SQLAlchemy `User` est déjà défini ailleurs dans le projet
from models import User  # import du modèle ORM existant


def get_user(id: int, db: Session) -> Optional[User]:
    """
    Récupère un utilisateur par son identifiant.

    Utilise SQLAlchemy ORM pour éviter toute concaténation de requêtes SQL
    et ainsi prévenir les vulnérabilités d'injection SQL (CWE‑89).
    """
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    return user


#                  ce qui correspond à la gestion d'erreur attendue dans une API FastAPI.


# ── generer_rapport (score 70.0%, 1 itération(s)) ──
import shlex
import subprocess
from fastapi import HTTPException
from typing import Optional


def generer_rapport(commande: str) -> str:
    """
    Exécute l'outil ``report_tool`` avec la commande fournie et renvoie la sortie.
    La fonction évite toute injection de commande en ne passant jamais de chaîne
    directement au shell : la commande est découpée en arguments avec ``shlex.split``
    et exécutée avec ``subprocess.run`` (``shell=False``).
    """
    if not commande:
        raise HTTPException(status_code=400, detail="Commande vide")

    # Découpage sécurisé de la chaîne de commande en liste d'arguments.
    # ``shlex.split`` gère correctement les guillemets et les espaces.
    try:
        args = shlex.split(commande)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Commande invalide: {exc}")

    # Préparation de la commande complète : le binaire ``report_tool`` suivi des arguments.
    full_cmd = ["report_tool", *args]

    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,  # protection contre l'injection de commande
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Timeout lors de l'exécution du rapport")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Erreur d'exécution du rapport: {exc}")

    if result.returncode != 0:
        # On renvoie l'erreur du processus comme détail HTTP 500.
        raise HTTPException(
            status_code=500,
            detail=f"Erreur du rapport (code {result.returncode}): {result.stderr.strip()}",
        )

    return result.stdout


#   à passer à ``report_tool`` (sans le nom du binaire), comme le faisait le code PHP.
#   découpage avec ``shlex.split``; il faut s'assurer que les valeurs proviennent d'une source fiable.


# ── chercher_produit (score 92.6%, 1 itération(s)) ──
from typing import List
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from models import Produit  # le modèle SQLAlchemy représentant la table `produits`


def chercher_produit(nom: str, db: Session) -> List[Produit]:
    """
    Recherche les produits dont le nom contient la chaîne fournie.

    Args:
        nom: Chaîne à rechercher dans le champ `nom` de la table `produits`.
        db: Session SQLAlchemy active.

    Returns:
        Liste d'instances `Produit` correspondant aux critères.

    Raises:
        HTTPException 400: Si le paramètre `nom` est vide.
    """
    if not nom:
        raise HTTPException(status_code=400, detail="Le paramètre 'nom' ne doit pas être vide.")

    # Utilisation d'une requête paramétrée via l'ORM pour éviter toute injection SQL.
    stmt = select(Produit).where(Produit.nom.ilike(f"%{nom}%"))
    result = db.execute(stmt).scalars().all()
    return result
