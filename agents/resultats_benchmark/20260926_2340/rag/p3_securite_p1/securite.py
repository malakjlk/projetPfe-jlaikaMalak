"""
Migré automatiquement par SMAML depuis securite.php
"""

# ── get_user (score 92.6%, 1 itération(s)) ──
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

# Supposons que le modèle ORM User est défini ailleurs dans le projet
from models import User  # import du modèle SQLAlchemy représentant la table `users`


def get_user(id: int, db: Session) -> Optional[User]:
    """
    Récupère un utilisateur par son identifiant.

    Utilise SQLAlchemy pour éviter toute concaténation de requêtes SQL
    (prévention de l'injection SQL).
    """
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    return user


# ce qui correspond à la gestion d'erreur attendue dans un contexte API.


# ── generer_rapport (score 64.3%, 1 itération(s)) ──
import re
import subprocess
from fastapi import HTTPException

def generer_rapport(commande: str) -> str:
    """
    Exécute l'outil ``report_tool`` avec la commande fournie de façon sécurisée.

    Parameters
    ----------
    commande: str
        La commande à passer à ``report_tool``. Elle doit être composée uniquement
        de caractères alphanumériques, tirets, underscores et points afin d'éviter
        toute injection de commande.

    Returns
    -------
    str
        La sortie standard de ``report_tool``.

    Raises
    ------
    HTTPException
        - 400 si la commande contient des caractères interdits.
        - 500 si l'exécution du processus échoue.
    """
    # Validation stricte pour prévenir l'injection de commande (CWE‑78)
    if not re.fullmatch(r"[A-Za-z0-9._-]+", commande):
        raise HTTPException(status_code=400, detail="Commande invalide")

    try:
        result = subprocess.run(
            ["report_tool", commande],
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,
        )
    except subprocess.SubprocessError as exc:
        raise HTTPException(status_code=500, detail=f"Erreur d'exécution: {exc}")

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"report_tool a retourné une erreur (code {result.returncode})",
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
    Utilise une requête paramétrée via SQLAlchemy pour éviter toute injection SQL.
    """
    if not nom:
        raise HTTPException(status_code=400, detail="Le paramètre 'nom' est requis")

    # Utilisation de l'opérateur LIKE avec des paramètres sécurisés
    produits = (
        db.query(Produit)
        .filter(Produit.nom.ilike(f"%{nom}%"))  # ilike pour recherche insensible à la casse
        .all()
    )
    return produits
