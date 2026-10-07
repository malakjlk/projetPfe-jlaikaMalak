"""
Migré automatiquement par SMAML depuis securite.php
"""

# ── get_user (score 92.6%, 1 itération(s)) ──
from typing import Optional, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # Hypothèse : la table possède au moins un champ 'name' de type texte.
    name = Column(String, nullable=True)
    # Ajoutez d'autres colonnes si nécessaire.


def get_user(db: Session, user_id: int) -> Dict[str, Any]:
    """
    Récupère un utilisateur depuis la base de données de façon sécurisée.

    Args:
        db: Session SQLAlchemy injectée par le dépendance FastAPI.
        user_id: Identifiant de l'utilisateur recherché.

    Returns:
        Un dictionnaire contenant les données de l'utilisateur.

    Raises:
        HTTPException 404 si l'utilisateur n'existe pas.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found",
        )
    # Conversion explicite en dict pour éviter de retourner l'objet ORM directement.
    return {
        "id": user.id,
        "name": user.name,
        # Ajoutez d'autres champs ici si le modèle en possède davantage.
    }


# ── generer_rapport (score 84.0%, 1 itération(s)) ──
import subprocess
from fastapi import HTTPException
from typing import Optional


def generer_rapport(commande: str) -> str:
    """
    Exécute l'outil `report_tool` avec la commande fournie de façon sécurisée
    (sans passer par le shell) et renvoie la sortie standard.

    Parameters
    ----------
    commande: str
        La partie de la commande à passer à `report_tool`. Elle est traitée
        comme un argument unique afin d'éviter toute injection de commande.

    Returns
    -------
    str
        Le texte retourné par `report_tool`.

    Raises
    ------
    HTTPException
        En cas d'échec de l'exécution (code de retour non‑zéro ou timeout).
    """
    # Construction sécurisée de la liste d'arguments
    args = ["report_tool", commande]

    try:
        result = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=10,  # délai raisonnable pour éviter les blocages
            check=False,  # on gère manuellement le code de retour
        )
    except subprocess.SubprocessError as exc:
        # Erreur d'exécution du sous‑processus (ex. timeout)
        raise HTTPException(status_code=500, detail=f"Erreur d'exécution du rapport : {exc}")

    if result.returncode != 0:
        # Le programme a renvoyé une erreur ; on transmet le message d'erreur
        raise HTTPException(
            status_code=500,
            detail=f"report_tool a échoué avec le code {result.returncode} : {result.stderr.strip()}",
        )

    return result.stdout


# ── chercher_produit (score 76.7%, 1 itération(s)) ──
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException

# On suppose qu'un modèle SQLAlchemy nommé `Produit` est déjà déclaré ailleurs dans le projet.
# Exemple minimal (à ne pas redéfinir ici si le modèle existe déjà) :
# from models import Produit

def chercher_produit(db: Session, nom: str) -> List["Produit"]:
    """
    Recherche les produits dont le nom contient la chaîne fournie.
    Utilise une requête paramétrée via SQLAlchemy pour éviter toute injection SQL.
    """
    try:
        stmt = select(Produit).where(Produit.nom.ilike(f"%{nom}%"))
        result = db.execute(stmt).scalars().all()
        return result
    except Exception as exc:
        # En cas d'erreur d'accès à la base, on renvoie une exception HTTP 500.
        raise HTTPException(status_code=500, detail="Erreur lors de la recherche de produit") from exc
