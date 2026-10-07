"""
Tests de bout en bout de la nouvelle orchestration à 4 phases.

    py -X utf8 test_orchestration.py

Le Développeur est SIMULÉ (il remplace l'appel au LLM) ; tous les autres
agents sont les vrais : Analyste, Architecte, Testeur, Comparateur,
Vérificateur (Z3), Auditeur (Bandit), Réviseur.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))

# Le Développeur simulé porte un nom distinct (developpeur_simule.py)
# pour ne JAMAIS pouvoir écraser le vrai. Le test le copie lui-même,
# sous le nom attendu, dans un dossier temporaire.
SOURCE_SIMULEE = os.path.join(ICI, "developpeur_simule.py")
SIMU = tempfile.mkdtemp(prefix="smaml_simu_")

# Le projet de test : test_php_project (le tien), sinon projet_test.
PROJET = next((os.path.join(ICI, d) for d in ("test_php_project", "projet_test")
               if os.path.isdir(os.path.join(ICI, d))),
              os.path.join(ICI, "test_php_project"))
resultats = []
DERNIERE_EXECUTION = {}

# Vérification préalable : les deux dossiers de test doivent être en place.
manquants = [chemin for chemin in
             (SOURCE_SIMULEE, os.path.join(PROJET, "db.php"),
              os.path.join(PROJET, "utils.php"), os.path.join(PROJET, "login.php"))
             if not os.path.exists(chemin)]
if manquants:
    print("Fichiers de test introuvables :")
    for chemin in manquants:
        print(f"  [X] {chemin}")
    print("\nIl faut, à côté de test_orchestration.py :")
    print("  developpeur_simule.py")
    print("  test_php_project\\db.php, utils.php, login.php")
    raise SystemExit(1)
# Fichiers du système nécessaires, et marque de leur bonne version.
NECESSAIRES = {
    "orchestration.py": "\"jugement\"", "outils_agents.py": "rapport_juge",
    "agent_juge.py": "def juger", "etalonnage_juge.py": "def kappa_pondere",
    "manager_llm.py": "class ManagerLLM", "reconciliation.py": "reconcilier_testeur = ",
    "supervision.py": "class Superviseur", "espace_partage.py": "class BailPerdu",
    "fournisseurs_llm.py": "modeles: dict = None", "cache_smaml.py": "def avec_cache",
    "configuration.py": "", "modernisation.py": "", "portee_verification.py": "",
    "agent_analyste.py": "def analyser_projet", "agent_architecte.py": "louvain_communities",
    "agent_testeur.py": "def verifier_coherence_projet",
    "agent_testeur_differentiel.py": "", "agent_verification_formelle.py": "",
    "agent_auditeur.py": "", "agent_reviseur.py": "rapport_juge",
}
problemes = []
for nom, marque in NECESSAIRES.items():
    chemin = os.path.join(ICI, nom)
    if not os.path.exists(chemin):
        problemes.append(f"[X] {nom} : absent du dossier")
    elif marque and marque not in open(chemin, encoding="utf-8", errors="ignore").read():
        problemes.append(f"[X] {nom} : ancienne version (il manque « {marque} »)")
try:
    import networkx  # noqa: F401
except ImportError:
    problemes.append("[X] networkx : non installé (py -m pip install networkx)")
try:
    import mypy  # noqa: F401
except ImportError:
    problemes.append("[X] mypy : non installé (py -m pip install mypy)")
if problemes:
    print("Le système n'est pas complet dans ce dossier :")
    for p in problemes:
        print(f"  {p}")
    raise SystemExit(1)

shutil.copy(SOURCE_SIMULEE, os.path.join(SIMU, "agent_developpeur.py"))
print(f"Projet de test : {PROJET}")


def verifier(nom, condition):
    resultats.append((nom, bool(condition)))
    print(f"   {'[OK]' if condition else '[ECHEC]'} {nom}")


def lancer(arguments, **env_sup):
    """Lance l'orchestration dans un processus séparé, comme en vrai."""
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([SIMU, ICI]),
               SMAML_STOCKAGE="sqlite", SMAML_CACHE="0", SMAML_MODE="direct",
               SMAML_DELAI_INACTIVITE="120", PYTHONIOENCODING="utf-8",
               # Le juge est testé à part (test_juge.py), avec des réponses
               # simulées : ici, il appellerait le vrai modèle à chaque module.
               SMAML_JUGE="0", SMAML_ENTREES_IA="0")
    env.update({k: str(v) for k, v in env_sup.items()})
    # Lancement depuis un dossier neutre, via -c : le Développeur simulé
    # passe ainsi avant le vrai dans le chemin de recherche de Python.
    commande = ("import orchestration, sys; "
                f"orchestration.principal({list(arguments)!r})")
    execution = subprocess.run([sys.executable, "-X", "utf8", "-c", commande],
                               cwd=tempfile.gettempdir(), env=env,
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=900)
    DERNIERE_EXECUTION["sortie"] = (execution.stdout or "") + (execution.stderr or "")
    return execution


def rapport(dossier):
    chemin = os.path.join(dossier, "rapport_migration.json")
    if not os.path.exists(chemin):
        # La migration a échoué : on montre pourquoi.
        print("\n   [X] La migration n'a pas produit de rapport. Fin de sa sortie :\n")
        for ligne in DERNIERE_EXECUTION.get("sortie", "").splitlines()[-30:]:
            print(f"     {ligne}")
        raise SystemExit(1)
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def modules(r):
    return {m["nom_python"]: m for f in r["fichiers_migres"] for m in f["modules"]}


def diagnostiquer(r):
    """Pour chaque module non livré : décision, score, critères, relais."""
    for nom, m in modules(r).items():
        if m["decision_finale"] == "LIVRER":
            continue
        print(f"\n     [ATTENTION] {nom} : {m['decision_finale']} ({m['score_final']:.1f} %), "
              f"coordonné par {m.get('coordonne_par')}")
        for relais in m.get("relais") or []:
            print(f"        relais {relais.get('coordinateur')} : {relais.get('issue')} "
                  f"— {str(relais.get('raison', ''))[:160]}")
        for c in ((m.get("confiance") or {}).get("criteres") or []):
            etat = f"{c['score']:.0f} %" if c.get("mesure") else f"non mesuré ({c.get('raison', '')[:60]})"
            print(f"        {c['nom']:<15} {etat}")
        eq = m.get("equivalence") or {}
        for div in (eq.get("divergences") or [])[:2]:
            print(f"        divergence : entrée {str(div.get('entree'))[:30]} → "
                  f"PHP {str(div.get('php'))[:40]} / Python {str(div.get('python'))[:60]}")


tmp = tempfile.mkdtemp()

# ── 1. Cas nominal ─────────────────────────────────────
print("\n── 1. Migration complète (mode direct) ──")
sortie = os.path.join(tmp, "s1")
lancer([PROJET, sortie], SMAML_STOCKAGE_SQLITE=os.path.join(tmp, "e1.db"))
r = rapport(sortie)
m = modules(r)
diagnostiquer(r)
verifier("phase 1 : les 3 fichiers PHP sont reçus",
         len(r["reception"]["fichiers_php"]) == 3)
verifier("phase 2 : l'ordre suit les dépendances (db et utils avant login)",
         [f["source"] for f in r["fichiers_migres"]] == ["db.php", "utils.php", "login.php"])
verifier("phases 3-4 : les 5 modules sont livrés", r["statistiques"]["modules_livres"] == 5)
verifier("les 3 fichiers Python sont écrits",
         all(os.path.exists(os.path.join(sortie, f)) for f in ("db.py", "utils.py", "login.py")))
verifier("phase 4 projet : le projet produit est cohérent", r["coherence_projet"]["coherent"])
verifier("phase 4 projet : les contrats de types entre modules sont respectés",
         r["coherence_projet"]["typage"]["statut"] == "teste"
         and r["coherence_projet"]["typage"]["coherent"])
verifier("chaque module indique qui l'a coordonné",
         all(x["coordonne_par"] == "coordinateur_fixe" for x in m.values()))
verifier("chaque module porte son journal et son attestation de portée",
         all(x["etat_structure"]["journal"] is not None and x["portee_verification"]
             for x in m.values()))
verifier("le découpage en services est proposé", r["decoupage_services"] is not None)

# ── 2. Boucle de correction ────────────────────────────
print("\n── 2. Boucle de correction (garde oubliée) ──")
sortie = os.path.join(tmp, "s2")
lancer([PROJET, sortie], SMAML_STOCKAGE_SQLITE=os.path.join(tmp, "e2.db"),
       SIMU_DEFAUT="validate_password")
r2 = rapport(sortie)
diagnostiquer(r2)
vp = modules(r2)["validate_password"]
verifier("la garde oubliée est détectée et le module corrigé, puis livré",
         vp["decision_finale"] == "LIVRER" and vp["iterations"] >= 2)
verifier("les deux versions du code sont conservées",
         vp["etat_structure"]["versions"].get("code_python") == 2)
verifier("les vérifications ont été refaites sur le nouveau code",
         vp["etat_structure"]["versions"].get("rapport_testeur") == 2)

# ── 3. Import inventé par le LLM ───────────────────────
print("\n── 3. Import inventé, détecté au niveau du projet ──")
sortie = os.path.join(tmp, "s3")
lancer([PROJET, sortie], SMAML_STOCKAGE_SQLITE=os.path.join(tmp, "e3.db"),
       SIMU_IMPORT="login")
r = rapport(sortie)
login = modules(r)["login"]
verifier("l'import inventé est intercepté avant le résultat final "
         "(boucle du module ou contrôle du projet)",
         login["iterations"] >= 2 or any(c["fichier"] == "login.php"
                                         for c in r["corrections_projet"]))
verifier("après correction, le projet est cohérent", r["coherence_projet"]["coherent"])
with open(os.path.join(sortie, "login.py"), encoding="utf-8") as f:
    verifier("le fichier corrigé ne contient plus l'import inventé",
             ".models" not in f.read())

# ── 3 ter. Import inventé que le Développeur ne corrige jamais ──
print("\n── 3 ter. Défaut d'intégration qui persiste après les corrections ──")
sortie = os.path.join(tmp, "s3t")
lancer([PROJET, sortie], SMAML_STOCKAGE_SQLITE=os.path.join(tmp, "e3t.db"),
       SIMU_IMPORT_TENACE="login")
r = rapport(sortie)
login = modules(r)["login"]
verifier("un module qui ne peut pas s'importer n'est PAS livré : validation humaine",
         login["decision_finale"] == "VALIDATION_HUMAINE" and login["categorie_echec"] == "integration")
verifier("les autres modules, eux, restent livrés",
         all(m["decision_finale"] == "LIVRER" for n, m in modules(r).items() if n != "login"))

# ── 3 bis. Le contrôle de cohérence du projet, seul ────
print("\n── 3 bis. Contrôle de cohérence du projet produit ──")
sys.path.insert(0, ICI)
from agent_testeur import verifier_coherence_projet
defaut = os.path.join(tmp, "defaut")
os.makedirs(defaut)
with open(os.path.join(defaut, "utils.py"), "w", encoding="utf-8") as f:
    f.write("def validate_password(p):\n    return True\n")
with open(os.path.join(defaut, "login.py"), "w", encoding="utf-8") as f:
    f.write("from .models import User\nfrom utils import validate_password\n")
coherence = verifier_coherence_projet(defaut)
verifier("le Testeur détecte l'import d'un module inexistant",
         not coherence["coherent"] and any("models" in str(c)
                                           for c in coherence["imports_casses"]))
with open(os.path.join(defaut, "db.py"), "w", encoding="utf-8") as f:
    f.write("from models import User\nfrom fastapi import HTTPException\n")
coherence = verifier_coherence_projet(defaut)
verifier("cas réel : « from models import User » est détecté comme module inventé",
         any("models" in str(c) and "db.py" in str(c) for c in coherence["imports_casses"]))
verifier("une vraie bibliothèque (fastapi) n'est pas signalée",
         not any("fastapi" in str(c) for c in coherence["imports_casses"]))
verifier("et valide l'import d'un module qui existe",
         any("validate_password" in str(v) for v in coherence["imports_valides"]))

# ── 3 quater. Contrats entre modules : typage statique ──
print("\n── 3 quater. Typage statique du projet produit (mypy) ──")
from agent_testeur import verifier_typage_projet
reel = os.path.join(tmp, "cas_reel")
os.makedirs(reel)
with open(os.path.join(reel, "db.py"), "w", encoding="utf-8") as f:
    f.write("from typing import Optional\nfrom pydantic import BaseModel\n\n"
            "class User(BaseModel):\n    email: str\n    password: str\n\n"
            "def get_user_by_email(email: str) -> Optional[User]:\n    return None\n")
with open(os.path.join(reel, "login.py"), "w", encoding="utf-8") as f:
    f.write("from db import get_user_by_email\n\n"
            "def login(email: str, password: str) -> str:\n"
            "    user = get_user_by_email(email)\n"
            "    if user and user[\"password\"] == password:\n"
            "        return \"Connexion réussie\"\n"
            "    return \"Email ou mot de passe incorrect\"\n")
typage = verifier_typage_projet(reel)
verifier("cas réel du 2e run : un objet lu comme un dictionnaire est détecté",
         typage["statut"] == "teste" and any(e["code"] == "index" and e["module"] == "login.py"
                                             for e in typage["erreurs"]))
with open(os.path.join(reel, "db.py"), "w", encoding="utf-8") as f:
    f.write("from typing import Any, Dict, Optional\n\n"
            "def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:\n    return None\n")
typage = verifier_typage_projet(reel)
verifier("contrat respecté (un dict renvoyé, un dict lu) : aucune fausse alerte",
         typage["statut"] == "teste" and typage["coherent"])

# ── 3 ter. Contexte PHP pour le Comparateur ────────────
print("\n── 3 quinquies. Contexte PHP : le fichier et ses dépendances ──")
import orchestration
from agent_analyste import analyser_projet
from agent_architecte import planifier_projet
contexte = orchestration.contexte_php_resolu(PROJET, "login.php",
                                             planifier_projet(analyser_projet(PROJET)))
verifier("login.php est exécutable seul : plus aucun require ni include",
         "require" not in contexte.lower() and "include" not in contexte.lower())
verifier("les fonctions dont il dépend sont présentes (utils.php, db.php)",
         all(f"function {n}" in contexte for n in ("validatePassword", "getUserByEmail")))
verifier("un seul bloc PHP, sans balise fermante intermédiaire",
         contexte.count("<?php") == 1 and "?>" not in contexte)

# ── 4. Plantage brutal, puis reprise ───────────────────
print("\n── 4. Plantage brutal du programme, puis reprise ──")
sortie = os.path.join(tmp, "s4")
base = os.path.join(tmp, "e4.db")
compteur = os.path.join(tmp, "compteur.txt")
plante = lancer([PROJET, sortie], SMAML_STOCKAGE_SQLITE=base, SMAML_PROJET_ID="reprise",
                SIMU_COMPTEUR=compteur, SIMU_PLANTAGE=3)
verifier("le programme s'arrête net à la 3e génération", plante.returncode != 0)
avant = int(open(compteur).read())
repris = lancer(["--reprendre", "reprise", sortie], SMAML_STOCKAGE_SQLITE=base,
                SIMU_COMPTEUR=compteur)
apres = int(open(compteur).read())
r = rapport(sortie)
diagnostiquer(r)
verifier("la reprise termine le projet : 5 modules livrés",
         r["statistiques"]["modules_livres"] == 5)
verifier("les 2 modules terminés avant le plantage ne sont PAS regénérés",
         apres - avant == 3)

ok = sum(1 for _, x in resultats if x)
print(f"\n{ok}/{len(resultats)} vérifications réussies")
shutil.rmtree(tmp, ignore_errors=True)
if ok != len(resultats):
    raise SystemExit(1)