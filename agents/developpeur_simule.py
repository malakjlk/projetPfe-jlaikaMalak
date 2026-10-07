"""
Développeur SIMULÉ pour les tests : remplace l'appel au LLM par des
codes Python écrits à l'avance. Tout le reste du système est réel.

Comportement réglable par variables d'environnement :
  SIMU_COMPTEUR   fichier où chaque génération est comptée
  SIMU_PLANTAGE   numéro de génération à laquelle le PROCESSUS s'arrête net
  SIMU_DEFAUT     « validate_password » : 1re version sans la garde
  SIMU_IMPORT     « login » : 1re version avec un import inventé
"""
import os
import re

DERNIER_APPEL = {"fournisseur": "simulation", "modele": "simu", "bascule": False}

CODES = {
 "connect_database": '''import sqlite3
from fastapi import HTTPException

def connect_database():
    """Ouvre la connexion."""
    try:
        return sqlite3.connect("app.db")
    except sqlite3.Error:
        raise HTTPException(status_code=503, detail="Base indisponible")
''',
 "get_user_by_email": '''import sqlite3
from typing import Optional

def get_user_by_email(email: str) -> Optional[dict]:
    """Retourne la ligne complète de l'utilisateur, comme fetch_assoc en PHP."""
    conn = connect_database()
    curseur = conn.execute("SELECT * FROM users WHERE email = ?", (email,))
    ligne = curseur.fetchone()
    if ligne is None:
        return None
    colonnes = [description[0] for description in curseur.description]
    return dict(zip(colonnes, ligne))
''',
 "validate_password": '''from fastapi import HTTPException

def validate_password(password: str) -> bool:
    """Vérifie la longueur minimale."""
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Mot de passe trop court")
    return True
''',
 "sanitize_input": '''import html

def sanitize_input(data: str) -> str:
    """Échappe le HTML."""
    return html.escape(data)
''',
 "login": '''from db import get_user_by_email
from utils import validate_password

def login(email: str, password: str) -> str:
    """Authentifie l'utilisateur."""
    validate_password(password)
    user = get_user_by_email(email)
    if user and user["password"] == password:
        return "Connexion réussie"
    return "Email ou mot de passe incorrect"
''',
}

DEFAUT = {"validate_password": '''def validate_password(password: str) -> bool:
    """Version fautive : la garde de longueur a été oubliée."""
    return True
'''}

IMPORT_INVENTE = {"login": '''from .models import User
from utils import validate_password

def login(email: str, password: str) -> str:
    validate_password(password)
    return "Connexion réussie"
'''}


def _compter():
    chemin = os.getenv("SIMU_COMPTEUR")
    if not chemin:
        return 0
    n = (int(open(chemin).read() or 0) if os.path.exists(chemin) else 0) + 1
    open(chemin, "w").write(str(n))
    return n


def generer_code_python(code_php, module, invariants, failles,
                        contexte_projet="", feedback=None):
    n = _compter()
    if os.getenv("SIMU_PLANTAGE") and n == int(os.getenv("SIMU_PLANTAGE")):
        os._exit(1)            # plantage brutal du processus entier
    nom = module["nom_python"]
    # Rejouer du code RÉEL produit par le LLM (fichier JSON {module: code}),
    # pour reproduire un run réel sans appeler le LLM.
    if os.getenv("SIMU_CODES"):
        import json as _json
        reels = _json.load(open(os.environ["SIMU_CODES"], encoding="utf-8"))
        if nom in reels:
            return "# SMAML-HYPOTHESE: code réel rejoué\n" + reels[nom]
    if os.getenv("SIMU_DEFAUT") == nom and not feedback:
        code = DEFAUT[nom]
    elif os.getenv("SIMU_IMPORT_TENACE") == nom:
        # Un import inventé que les vérifications du MODULE laissent passer,
        # mais que le contrôle du PROJET détecte — et qui n'est jamais corrigé.
        code = CODES[nom].replace("from db import get_user_by_email",
                                  "from db import get_user_by_email\nfrom models import User")
    elif os.getenv("SIMU_IMPORT") == nom and "CORRECTION REQUISE" not in (contexte_projet or "") \
            and not (feedback and feedback.get("instructions")):
        code = IMPORT_INVENTE[nom]
    elif nom in CODES:
        code = CODES[nom]
    else:
        # Module inconnu (autre langage, autre projet) : une traduction
        # générique, pour faire traverser le noyau commun.
        code = (f"from decimal import Decimal\n\n"
                f"def {nom}(valeur: Decimal = Decimal(\"0\")) -> Decimal:\n"
                f"    \"\"\"Traduction simulée de l'unité {module.get('nom_original')}.\"\"\"\n"
                f"    return valeur\n")
    return "# SMAML-HYPOTHESE: simulation de test\n" + code


def nettoyer_code(code):
    return re.sub(r"^```(?:python)?|```$", "", code or "", flags=re.M).strip() + "\n"


def extraire_metadonnees(code):
    def lignes(marque):
        return [l.split(":", 1)[1].strip() for l in code.splitlines()
                if l.strip().startswith(f"# {marque}:")]
    return {"hypotheses_faites": lignes("SMAML-HYPOTHESE"),
            "points_incertains": lignes("SMAML-INCERTAIN"),
            "points_attention": lignes("SMAML-ATTENTION")}


def extraire_dependances(code):
    return sorted({m.group(1) for m in re.finditer(r"^\s*(?:from|import)\s+(\w+)", code, re.M)})