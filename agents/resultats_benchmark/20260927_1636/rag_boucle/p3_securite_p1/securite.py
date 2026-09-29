"""
Migré automatiquement par SMAML depuis securite.php
"""

# ── get_user (score 92.6%, 1 itération(s)) ──
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

# Supposons que le modèle SQLAlchemy `User` est défini ailleurs dans le projet
from models import User  # import du modèle ORM existant


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


# SMAML-HYPOTHÈSE: le modèle `User` possède un champ `id` de type entier.
# ce qui correspond à la gestion d'erreur attendue dans un contexte API.


# ── generer_rapport (score 80.0%, 1 itération(s)) ──
import re
import subprocess
from fastapi import HTTPException
from typing import List


def _validate_command(command: str) -> List[str]:
    """
    Valide la chaîne de commande reçue depuis l'appel PHP.
    - Aucun caractère spécial n'est autorisé (seuls les caractères alphanumériques,
      les tirets, les underscores, les points et les espaces sont permis).
    - La commande est découpée en une liste d'arguments pour `subprocess.run`
      afin d'éviter toute injection de commande.
    """
    if not command or not isinstance(command, str):
        raise HTTPException(status_code=400, detail="Commande invalide")

    # Autoriser uniquement les caractères sûrs et les espaces entre les arguments
    if not re.fullmatch(r"[A-Za-z0-9_\-./ ]+", command):
        raise HTTPException(
            status_code=400,
            detail="Commande contenant des caractères interdits"
        )

    # Découpage simple sur les espaces (les arguments contenant des espaces
    # doivent être encodés différemment côté appelant)
    args = command.strip().split()
    return args


def generer_rapport(commande: str) -> str:
    """
    Exécute l'outil `report_tool` avec la commande fournie et renvoie la sortie.
    Utilise `subprocess.run` avec une liste d'arguments et `shell=False`
    pour prévenir les injections de commande (CWE‑78).
    """
    # Validation et transformation de la chaîne de commande en liste d'arguments
    args = _validate_command(commande)

    # Construction de la commande complète
    full_cmd = ["report_tool"] + args

    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Timeout lors de l'exécution de la commande: {exc}"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'exécution de la commande: {exc}"
        )

    if result.returncode != 0:
        # Retourner l'erreur du processus comme HTTP 400
        raise HTTPException(
            status_code=400,
            detail=f"Erreur du rapport: {result.stderr.strip()}"
        )

    return result.stdout


#                     ce qui suppose que `report_tool` n'accepte que des arguments sans espaces.
#                 il faudra adapter le protocole d'appel (ex. encodage JSON) pour les transmettre correctement.


# ── chercher_produit (score 92.6%, 1 itération(s)) ──
from typing import List
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from models import Produit  # modèle SQLAlchemy représentant la table `produits`


def chercher_produit(nom: str, db: Session) -> List[Produit]:
    """
    Recherche les produits dont le nom contient la chaîne fournie.
    Utilise une requête paramétrée via SQLAlchemy pour éviter toute injection SQL.
    """
    if not nom:
        raise HTTPException(status_code=400, detail="Le paramètre 'nom' ne peut pas être vide.")

    # Construction sécurisée de la requête avec l'opérateur LIKE
    stmt = select(Produit).where(Produit.nom.ilike(f"%{nom}%"))
    try:
        result = db.execute(stmt).scalars().all()
    except Exception as exc:
        # En cas d'erreur d'exécution, on renvoie une erreur HTTP 500 générique
        raise HTTPException(status_code=500, detail="Erreur lors de la recherche du produit.") from exc

    return result
