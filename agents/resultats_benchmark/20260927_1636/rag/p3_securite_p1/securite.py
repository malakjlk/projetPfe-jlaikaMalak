"""
Migré automatiquement par SMAML depuis securite.php
"""

# ── get_user (score 92.6%, 1 itération(s)) ──
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

# Supposons que le modèle ORM User est défini ailleurs dans le projet
from models import User  # import du modèle SQLAlchemy User


def get_user(id: int, db: Session) -> Optional[User]:
    """
    Récupère un utilisateur par son identifiant.

    Utilise SQLAlchemy ORM pour éviter toute concaténation de requêtes SQL
    et ainsi prévenir les vulnérabilités d'injection SQL.
    """
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    return user


# ce qui correspond à la gestion d'erreur attendue dans un contexte API.


# ── generer_rapport (score 79.3%, 1 itération(s)) ──
import subprocess
from typing import List
from fastapi import HTTPException

def generer_rapport(commande: str) -> str:
    """
    Exécute l'outil ``report_tool`` avec la commande fournie et renvoie la sortie.
    La fonction utilise ``subprocess.run`` avec une liste d'arguments afin d'éviter
    toute injection de commande (CWE‑78). Une validation très basique est appliquée
    pour s'assurer que la commande ne contient que des caractères alphanumériques,
    des tirets, des underscores et des points.
    """
    # Validation simple de la commande pour limiter les caractères autorisés.
    # Cette hypothèse repose sur le fait que ``report_tool`` accepte uniquement
    # des options sous forme de mots courts (ex: "summary", "detail-2023").
    if not commande or not all(c.isalnum() or c in "-_." for c in commande):
        raise HTTPException(status_code=400, detail="Commande invalide")

    try:
        result = subprocess.run(
            ["report_tool", commande],
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Timeout lors de l'exécution du rapport") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Erreur lors de l'exécution du rapport") from exc

    if result.returncode != 0:
        # Le processus a renvoyé une erreur ; on transmet le message d'erreur.
        raise HTTPException(
            status_code=500,
            detail=f"Erreur du tool report_tool : {result.stderr.strip()}",
        )

    return result.stdout


# tirets, underscores et points, supposant que ``report_tool`` n'accepte pas d'options plus complexes.
# si le besoin apparaît, il faudra adapter la signature pour accepter une liste d'arguments.


# ── chercher_produit (score 92.6%, 1 itération(s)) ──
from typing import List

from fastapi import HTTPException
from sqlalchemy.orm import Session

# Le modèle SQLAlchemy représentant la table `produits`.
# On suppose qu'il est déclaré ailleurs dans le projet.
from models import Produit


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
    produits = (
        db.query(Produit)
        .filter(Produit.nom.ilike(f"%{nom}%"))
        .all()
    )
    return produits
