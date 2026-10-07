"""
Migré automatiquement par SMAML depuis securite.php
"""

# ── get_user (score 84.1%, 1 itération(s)) ──
import os
from typing import Optional, Dict, Any

from sqlalchemy import text
from sqlalchemy.engine import Engine, ResultProxy

# On suppose qu'un module du projet fournit une fonction permettant d'obtenir
# une instance d'Engine SQLAlchemy déjà configurée (ex. get_engine()).
# Cette fonction doit être importée depuis le module approprié du projet.
# Si le nom ou le module diffèrent, il faut ajuster l'import ci‑dessous.
from db_connection import get_engine  # type: ignore

def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Récupère un utilisateur depuis la table ``users`` en fonction de son identifiant.

    Retourne un dictionnaire contenant les colonnes de la ligne trouvée,
    ou ``None`` si aucun enregistrement ne correspond.

    Lève ``ConnectionError`` si la connexion à la base échoue.
    """
    # Construction sécurisée de la requête grâce à des paramètres nommés.
    sql = text("SELECT * FROM users WHERE id = :uid")

    try:
        engine: Engine = get_engine()
    except Exception as exc:
        # Erreur de connexion ou de configuration du moteur.
        raise ConnectionError("Impossible d'établir la connexion à la base de données") from exc

    with engine.connect() as connection:
        result: ResultProxy = connection.execute(sql, {"uid": user_id})
        row = result.fetchone()
        if row is None:
            return None
        # Convertit le RowProxy en dictionnaire standard.
        return dict(row)


# ── generer_rapport (score 82.0%, 1 itération(s)) ──
import os
import shlex
import subprocess
from typing import Optional

def generer_rapport(commande: str) -> Optional[str]:
    """
    Exécute l'outil ``report_tool`` avec la commande fournie de façon sécurisée
    et renvoie la sortie texte du processus.

    Parameters
    ----------
    commande: str
        Arguments à passer à ``report_tool``. Doit être composé uniquement de
        caractères alphanumériques, tirets, underscores, points et espaces.
        Tout autre caractère déclenchera une ``ValueError`` afin d'éviter
        toute injection de commande.

    Returns
    -------
    Optional[str]
        Le texte produit par ``report_tool``. Retourne ``None`` si le processus
        ne produit aucune sortie.

    Raises
    ------
    ValueError
        Si la chaîne ``commande`` contient des caractères interdits.
    subprocess.CalledProcessError
        Si l'exécution du processus échoue (code de retour non‑zéro).
    """
    # Validation très stricte pour prévenir les injections (CWE‑78)
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_. ")
    if not set(commande).issubset(allowed_chars):
        raise ValueError("Commande contenant des caractères non autorisés")

    # Découpage sûr des arguments (équivalent à shell‑splitting sans le shell)
    args = shlex.split(commande)

    # Construction de la liste d'arguments complète
    cmd = ["report_tool", *args]

    # Exécution du processus sans passer par le shell
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,               # on gère le code retour manuellement
    )

    # Si le processus a échoué, on lève une exception explicite
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr
        )

    return result.stdout if result.stdout else None

# hypothèse raisonnable du format attendu pour les arguments de ``report_tool``.
# processus ; le code appelant doit gérer cette exception selon la logique métier.


# ── chercher_produit (score 73.1%, 2 itération(s)) ──
import os
from typing import List, Dict, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Result

def _get_engine() -> Engine:
    """
    Crée un moteur SQLAlchemy à partir des variables d'environnement.
    Les noms d'environnement sont inspirés des paramètres du code PHP d'origine.
    """
    db_user = os.getenv("DB_USER", "root")
    db_password = os.getenv("DB_PASSWORD", "")
    db_host = os.getenv("DB_HOST", "localhost")
    db_name = os.getenv("DB_NAME", "ma_base")
    db_port = os.getenv("DB_PORT", "3306")
    # Exemple d'URL MySQL compatible SQLAlchemy
    url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    return create_engine(url, future=True)


def chercher_produit(nom: str) -> Optional[List[Dict[str, any]]]:
    """
    Recherche les produits dont le nom contient la chaîne fournie.
    Retourne une liste de dictionnaires représentant les lignes trouvées,
    ou ``None`` si aucune correspondance n'est trouvée ou en cas d'erreur de connexion.
    """
    if not isinstance(nom, str):
        raise ValueError("Le paramètre 'nom' doit être une chaîne de caractères")

    engine = _get_engine()
    try:
        with engine.connect() as connexion:
            # Utilisation d'une requête paramétrée pour éviter l'injection SQL
            stmt = text(
                "SELECT * FROM produits WHERE nom LIKE :pattern"
            )
            # Le pattern ajoute les jokers % autour du terme recherché
            result: Result = connexion.execute(stmt, {"pattern": f"%{nom}%"})
            rows = result.mappings().all()
            if not rows:
                return None
            # Convertir chaque Mapping en dict standard
            return [dict(row) for row in rows]
    except Exception as exc:
        # En cas d'échec de connexion ou d'exécution, on renvoie None
        # (comportement similaire à mysql_query qui retourne false)
        return None


#                  donc on crée un moteur local avec les variables d'environnement.
#                  erreur survient, reproduisant le comportement de ``mysql_query`` qui renvoie false.
