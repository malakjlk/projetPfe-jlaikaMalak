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
    Récupère un utilisateur à partir de son identifiant.

    Args:
        id: Identifiant de l'utilisateur recherché.
        db: Session SQLAlchemy active.

    Returns:
        Instance de `User` ou `None` si aucun enregistrement ne correspond.

    Raises:
        HTTPException 404 si l'utilisateur n'est pas trouvé.
    """
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    return user


# ── generer_rapport (score 80.0%, 1 itération(s)) ──
import subprocess
from typing import List
from fastapi import HTTPException

def generer_rapport(commande: str) -> str:
    """
    Exécute l'outil ``report_tool`` avec la commande fournie et renvoie la sortie.
    La fonction utilise ``subprocess.run`` avec une liste d'arguments afin d'éviter
    toute injection de commande (CWE‑78). Une validation très basique est appliquée
    sur la chaîne ``commande`` pour s'assurer qu'elle ne contient que des caractères
    alphanumériques, des tirets, des underscores et des points.
    """
    # Validation simple de la commande pour limiter les caractères autorisés.
    # Cette hypothèse (SMAML-HYPOTHESE) repose sur le fait que le tool accepte
    # uniquement des options sous forme de mots ou de chemins simples.
    if not commande or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_. " for c in commande):
        raise HTTPException(status_code=400, detail="Commande invalide")

    # Construction sécurisée de la ligne de commande sous forme de liste.
    args: List[str] = ["report_tool"] + commande.split()

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,  # impératif pour éviter l'injection de commande
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Timeout lors de l'exécution du rapport") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Erreur lors de l'exécution du rapport") from exc

    if result.returncode != 0:
        # Le tool a renvoyé une erreur ; on transmet le message d'erreur.
        raise HTTPException(
            status_code=500,
            detail=f"Erreur du tool report_tool : {result.stderr.strip()}",
        )

    return result.stdout

# tirets, underscores, points et espaces, supposant que le tool n'accepte pas d'options
# plus complexes.
# conformément aux contraintes du projet.


# ── chercher_produit (score 92.6%, 1 itération(s)) ──
from typing import List
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models import Produit  # modèle SQLAlchemy représentant la table `produits`


def chercher_produit(nom: str, db: Session) -> List[Produit]:
    """
    Recherche les produits dont le nom contient la chaîne fournie.
    Utilise une requête paramétrée via SQLAlchemy pour éviter toute injection SQL.
    """
    if not nom:
        raise HTTPException(status_code=400, detail="Le paramètre 'nom' ne peut pas être vide.")

    try:
        # Utilisation de `ilike` pour une recherche insensible à la casse similaire à LIKE "%nom%"
        produits = (
            db.query(Produit)
            .filter(Produit.nom.ilike(f"%{nom}%"))
            .all()
        )
        return produits
    except Exception as exc:
        # En cas d'erreur inattendue, on renvoie une erreur serveur générique.
        raise HTTPException(status_code=500, detail="Erreur lors de la recherche de produits.") from exc
