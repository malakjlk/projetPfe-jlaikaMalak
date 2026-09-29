"""
Migré automatiquement par SMAML depuis securite.php
"""

# ── get_user (score 92.6%, 1 itération(s)) ──
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String
from pydantic import BaseModel

# --- Modèle SQLAlchemy représentant la table `users` ---
class User:
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # Exemple de colonnes supplémentaires ; à adapter selon le schéma réel
    name = Column(String, nullable=True)
    email = Column(String, nullable=True)


# --- Schéma Pydantic utilisé pour la réponse ---
class UserSchema(BaseModel):
    id: int
    name: Optional[str] = None
    email: Optional[str] = None

    class Config:
        orm_mode = True


def get_user(user_id: int, db: Session) -> UserSchema:
    """
    Récupère un utilisateur à partir de son identifiant.

    - Utilise une requête paramétrée via l'ORM SQLAlchemy pour éviter les injections SQL.
    - Lève une HTTPException 404 si l'utilisateur n'existe pas.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found",
        )
    return UserSchema.from_orm(user)


# ── generer_rapport (score 83.2%, 1 itération(s)) ──
import subprocess
from fastapi import HTTPException
from typing import Optional


def generer_rapport(commande: str) -> str:
    """
    Exécute l'outil `report_tool` avec la commande fournie de manière sécurisée
    (sans passer par le shell) et renvoie la sortie standard.

    Parameters
    ----------
    commande: str
        La commande à transmettre à `report_tool`. Elle est passée comme
        argument unique de la ligne de commande.

    Returns
    -------
    str
        Le texte produit par `report_tool`.

    Raises
    ------
    HTTPException
        Si l'exécution du processus échoue (code de retour non‑zéro) ou si
        un timeout survient.
    """
    try:
        # Utilisation de subprocess.run avec shell=False pour éviter toute injection de commande.
        result = subprocess.run(
            ["report_tool", commande],
            capture_output=True,
            text=True,
            timeout=30,               # limite de temps raisonnable
            check=False,              # on gère manuellement les erreurs
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Timeout lors de la génération du rapport") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Erreur interne lors de la génération du rapport") from exc

    if result.returncode != 0:
        # On renvoie le message d'erreur du processus dans la réponse HTTP.
        raise HTTPException(
            status_code=400,
            detail=f"Erreur du tool report_tool : {result.stderr.strip() or 'Code de retour non‑zéro'}",
        )

    return result.stdout


# même si en PHP elle pouvait contenir plusieurs sous‑commandes séparées par des espaces.


# ── chercher_produit (score 92.6%, 1 itération(s)) ──
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException

# On suppose que le modèle ORM `Produit` est déjà déclaré ailleurs dans le projet.
from models import Produit  # type: ignore  # IMPORT EXACTE DU MODÈLE EXISTANT


def chercher_produit(nom: str, db: Session) -> List[Produit]:
    """
    Recherche les produits dont le nom contient la chaîne fournie (insensible à la casse).

    Args:
        nom: Chaîne à rechercher dans le champ `nom` de la table `produits`.
        db:  Session SQLAlchemy injectée par le routeur FastAPI.

    Returns:
        Liste d'instances `Produit` correspondant aux critères.

    Raises:
        HTTPException: En cas d'erreur d'accès à la base de données.
    """
    try:
        # Utilisation d'un filtre paramétré via SQLAlchemy pour éviter toute injection SQL.
        # `ilike` permet la recherche insensible à la casse avec le pattern `%nom%`.
        produits = (
            db.query(Produit)
            .filter(Produit.nom.ilike(f"%{nom}%"))
            .all()
        )
        return produits
    except Exception as exc:
        # On encapsule toute exception dans une HTTPException afin de respecter le contrat API.
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la recherche du produit."
        ) from exc
