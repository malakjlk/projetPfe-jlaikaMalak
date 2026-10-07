"""
Migré automatiquement par SMAML depuis securite.php
"""

# ── get_user (score 92.6%, 1 itération(s)) ──
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

# Import du modèle SQLAlchemy représentant la table `users`.
# On suppose qu'il existe dans le module `models`.
from models import User


def get_user(id: int, db: Session) -> Optional[User]:
    """
    Récupère un utilisateur par son identifiant.

    Utilise SQLAlchemy ORM pour éviter toute concaténation de requêtes SQL
    (prévention de l'injection SQL). Lève une HTTPException 404 si l'utilisateur
    n'est pas trouvé.
    """
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    return user


# ── generer_rapport (score 70.0%, 2 itération(s)) ──
import shlex
import subprocess
from fastapi import HTTPException
from typing import Optional


def generer_rapport(commande: str) -> str:
    """
    Exécute l'outil ``report_tool`` avec la commande fournie de façon sécurisée.
    La chaîne ``commande`` est découpée en arguments avec ``shlex.split`` afin
    d'éviter toute injection de commande. Le processus est lancé avec
    ``shell=False`` et un timeout raisonnable.
    """
    if not commande:
        raise HTTPException(status_code=400, detail="Commande vide")

    # Découpage sécurisé des arguments
    try:
        args = shlex.split(commande)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Commande invalide: {exc}")

    # Construction de la liste d'arguments complète
    cmd = ["report_tool"] + args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Timeout lors de l'exécution du rapport")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'exécution du rapport: {exc}")

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur du processus report_tool (code {result.returncode}): {result.stderr.strip()}",
        )

    return result.stdout


# ── chercher_produit (score 92.6%, 1 itération(s)) ──
from typing import List
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models import Produit  # modèle SQLAlchemy représentant la table `produits`


def chercher_produit(nom: str, db: Session) -> List[Produit]:
    """
    Recherche les produits dont le nom contient la chaîne fournie.

    Args:
        nom: Chaîne à rechercher dans le champ `nom` de la table `produits`.
        db: Session SQLAlchemy active.

    Returns:
        Liste d'instances `Produit` correspondant aux critères.

    Raises:
        HTTPException 400 si le paramètre `nom` est vide.
    """
    if not nom:
        raise HTTPException(status_code=400, detail="Le paramètre 'nom' ne doit pas être vide.")

    # Utilisation d'une requête paramétrée via l'ORM pour éviter toute injection SQL.
    produits = (
        db.query(Produit)
        .filter(Produit.nom.ilike(f"%{nom}%"))
        .all()
    )
    return produits
