"""
Migré automatiquement par SMAML depuis securite.php
"""

# ── get_user (score 76.7%, 5 itération(s)) ──
from fastapi import HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

# On suppose que le modèle SQLAlchemy `User` est disponible dans le namespace du projet.
# Il doit être importé depuis le module où il est défini.
# Exemple d'import possible (à adapter selon l'arborescence réelle) :
# from .models import User
# Si le modèle porte un autre nom ou se trouve dans un autre module, ajustez l'import en conséquence.
# -------------------------------------------------------------

def get_user(id: int, db: Session) -> Optional[Dict[str, Any]]:
    """
    Récupère un utilisateur à partir de son identifiant.

    Args:
        id: Identifiant de l'utilisateur recherché.
        db: Session SQLAlchemy active.

    Returns:
        Un dictionnaire représentant l'utilisateur, ou `None` si aucun résultat n'est trouvé.

    Raises:
        HTTPException: Si l'identifiant fourni n'est pas valide.
    """
    if id <= 0:
        raise HTTPException(status_code=400, detail="Identifiant d'utilisateur invalide")

    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    # Conversion explicite en dict pour éviter de retourner l'objet ORM directement.
    # On suppose que le modèle `User` possède un attribut `__dict__` ou une méthode `to_dict`.
    # Si ce n'est pas le cas, adaptez la sérialisation selon votre implémentation.
    return (
        user.to_dict()
        if hasattr(user, "to_dict")
        else {c.key: getattr(user, c.key) for c in user.__table__.columns}
    )


# ── generer_rapport (score 70.0%, 1 itération(s)) ──
import shlex
import subprocess
from fastapi import HTTPException
from typing import Optional

def generer_rapport(commande: str) -> str:
    """
    Exécute l'outil ``report_tool`` avec la commande fournie de manière sécurisée
    et renvoie la sortie standard.

    Parameters
    ----------
    commande: str
        La partie de la ligne de commande à passer à ``report_tool``.
        Elle doit être une chaîne contenant uniquement des caractères sûrs
        (alphanumériques, tirets, underscores, points et espaces).

    Returns
    -------
    str
        La sortie du processus.

    Raises
    ------
    HTTPException
        - 400 si la commande contient des caractères interdits.
        - 500 si l'exécution du processus échoue.
    """
    # Validation très basique pour éviter l'injection de commande
    if not all(c.isalnum() or c in "-_ ./" for c in commande):
        raise HTTPException(status_code=400, detail="Commande invalide")

    # Découpage sécurisé de la chaîne en arguments
    try:
        args = shlex.split(commande)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Erreur de parsing de la commande: {exc}")

    # Construction de la commande complète sans passer par le shell
    cmd = ["report_tool"] + args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,
        )
    except subprocess.SubprocessError as exc:
        raise HTTPException(status_code=500, detail=f"Erreur d'exécution du rapport: {exc}")

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"report_tool a échoué avec le code {result.returncode}: {result.stderr.strip()}",
        )

    return result.stdout

# ce qui peut être insuffisant selon les besoins réels de l'application.


# ── chercher_produit (score 92.6%, 1 itération(s)) ──
from typing import List
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models import Produit  # modèle SQLAlchemy représentant la table `produits`


def chercher_produit(nom: str, db: Session) -> List[Produit]:
    """
    Recherche les produits dont le nom contient la chaîne fournie.
    Utilise une requête paramétrée via SQLAlchemy afin d'éviter toute injection SQL.
    """
    if not nom:
        raise HTTPException(status_code=400, detail="Le paramètre 'nom' est requis")

    try:
        # Utilisation de l'opérateur LIKE avec les paramètres de SQLAlchemy.
        # Le caractère `%` est ajouté côté Python, pas dans la requête brute.
        pattern = f"%{nom}%"
        produits = (
            db.query(Produit)
            .filter(Produit.nom.ilike(pattern))  # recherche insensible à la casse
            .all()
        )
        return produits
    except Exception as exc:
        # En cas d'erreur inattendue, on renvoie une erreur 500 générique.
        raise HTTPException(status_code=500, detail="Erreur lors de la recherche de produits") from exc
