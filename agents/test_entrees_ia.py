"""
Tests des entrées produites par l'IA, de la lecture du pourcentage du
Comparateur, et du test de mutation.

    py -X utf8 test_entrees_ia.py

Aucun appel réseau : les réponses de l'IA sont simulées.
"""
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
os.environ.update({"SMAML_CACHE": "0", "GROQ_TOKEN": "x", "SMAML_CHAINE_ENTREES": "groq"})

VERSIONS = {"entrees_ia.py": "def generer_entrees_ia", "mutation.py": "def comparer_sources",
            "agent_testeur_differentiel.py": "def classer_divergence",
            "outils_agents.py": "dossier_python=espace.get",
            "mutation.py": "non_observable"}
anciens = [f"[X] {n} : absent ou ancienne version" for n, m in VERSIONS.items()
           if not os.path.exists(os.path.join(ICI, n))
           or m not in open(os.path.join(ICI, n), encoding="utf-8", errors="ignore").read()]
if anciens:
    print("Fichiers à mettre à jour avant le test :\n  " + "\n  ".join(anciens))
    raise SystemExit(1)

import entrees_ia
os.environ["SMAML_LIMITEUR"] = "0"   # réponses simulées : pas de quota à protéger
import fournisseurs_llm
from agent_testeur_differentiel import (categoriser_entree, classer_divergence, construire_cas,
                                        generer_cas_de_test, lecture)
from mutation import comparer_sources, generer_mutants

resultats = []


def verifier(nom, condition):
    resultats.append((nom, bool(condition)))
    print(f"   {'[OK]' if condition else '[ECHEC]'} {nom}")


def reponse(contenu):
    return lambda url, cle, charge: (200, json.dumps(
        {"choices": [{"message": {"content": contenu}}]}), {})


print("\n── Entrées produites par l'IA ──")
fournisseurs_llm.EN_PANNE.clear()
proposition = json.dumps({"entrees": [
    {"arguments": ["Motdepasse12"], "categorie": "nominal", "intention": "usage normal"},
    {"arguments": ["1234567"], "categorie": "limite", "intention": "juste sous le minimum"},
    {"arguments": ["12345678"], "categorie": "limite", "intention": "exactement le minimum"},
    {"arguments": ["a", "b"], "categorie": "nominal", "intention": "mauvais nombre d'arguments"},
    {"arguments": [{"objet": 1}], "categorie": "attaque", "intention": "valeur non simple"},
    {"arguments": ["1234567"], "categorie": "limite", "intention": "doublon"}]})
r = entrees_ia.generer_entrees_ia("<?php function f($p){} ?>", "f", 1,
                                  transport=reponse("<think>je réfléchis</think>" + proposition))
verifier("l'IA propose des entrées classées, avec leur intention",
         r["statut"] == "genere" and r["entrees"][1]["categorie"] == "limite"
         and r["entrees"][1]["intention"] == "juste sous le minimum")
verifier("les entrées mal formées ou en double sont écartées, sans échec",
         len(r["entrees"]) == 3)
fournisseurs_llm.EN_PANNE.clear()
r = entrees_ia.generer_entrees_ia("<?php ?>", "g", 1, transport=lambda u, c, ch: (503, "x", {}))
verifier("IA indisponible : liste vide, le Comparateur garde ses entrées fixes",
         r["statut"] == "indisponible" and r["entrees"] == [])

print("\n── Les entrées fixes sont GARDÉES, celles de l'IA s'ajoutent ──")
cas = construire_cas(1, False, [{"arguments": ["Motdepasse12"], "categorie": "nominal",
                                 "intention": "x", "origine": "ia"},
                                {"arguments": ["12345678"], "categorie": "limite",
                                 "intention": "doublon d'une entrée fixe", "origine": "ia"}])
verifier("les 15 entrées fixes restent, l'IA ajoute ce qui est nouveau (sans doublon)",
         sum(c["origine"] == "fixe" for c in cas) == 15
         and sum(c["origine"] == "ia" for c in cas) == 1)
verifier("chaque entrée fixe reçoit une catégorie",
         categoriser_entree(["éàçùè"]) == "caracteres_speciaux"
         and categoriser_entree(["' OR 1=1 --"]) == "attaque"
         and categoriser_entree([""]) == "limite")

print("\n── Lire le pourcentage : chaque divergence expliquée ──")
encodage = classer_divergence(["éàçùè"], "caracteres_speciaux",
                              {"type": "divergence_acceptation", "php": "accepte",
                               "python": "rejette (Mot de passe trop court)"})
verifier("éàçùè : reconnu comme différence d'encodage (octets ou caractères), pas comme bug",
         encodage[0] == "difference_encodage" and "strlen" in encodage[1])
securite = classer_divergence(["<script>"], "attaque",
                              {"type": "divergence_acceptation", "php": "accepte",
                               "python": "rejette (entrée refusée)"})
verifier("une attaque bloquée par le Python : durcissement de sécurité",
         securite[0] == "durcissement_securite")
verifier("un écart sur une entrée normale : bug probable, à corriger",
         classer_divergence(["Motdepasse12"], "nominal",
                            {"type": "valeurs_differentes"})[0] == "bug_probable")
rapport = {"cas_testes": 13, "cas_equivalents": 10, "score_equivalence": 10 / 13,
           "par_categorie": {"nominal": {"testes": 8, "equivalents": 8},
                             "caracteres_speciaux": {"testes": 2, "equivalents": 1},
                             "attaque": {"testes": 3, "equivalents": 1}},
           "divergences": [{"classement": "difference_encodage"},
                           {"classement": "durcissement_securite"},
                           {"classement": "durcissement_securite"}]}
texte = lecture(rapport)
print(f"      « {texte} »")
verifier("le pourcentage est décomposé par catégorie et ses écarts sont expliqués",
         texte.startswith("77 %") and "cas nominaux 8/8" in texte and "difference encodage" in texte)
verifier("le chiffre brut n'est jamais modifié par l'explication",
         rapport["score_equivalence"] == 10 / 13)

print("\n── Test de mutation : quelles entrées détectent les bugs ? ──")
MOT_DE_PASSE = '''def validate_password(password: str) -> bool:
    if len(password) < 8:
        raise ValueError("Mot de passe trop court")
    return True
'''
mutants = generer_mutants(MOT_DE_PASSE, "validate_password")
verifier("des mutants sont produits : borne déplacée, garde supprimée…",
         any("Lt → LtE" in d for d, _ in mutants) and any("garde" in d for d, _ in mutants))
m = comparer_sources(MOT_DE_PASSE, "validate_password",
                     {"fixes": generer_cas_de_test(1, False), "ia": [["Motdepasse12"]]})
verifier("les entrées fixes, qui contiennent les bornes 7 et 8, tuent la mutation de borne",
         m["statut"] == "mesure" and m["scores"]["fixes"]["score"] >= m["scores"]["ia"]["score"])

AGE = '''def verifier_age(age: int) -> bool:
    if age < 18:
        raise ValueError("mineur")
    if age > 120:
        raise ValueError("âge invalide")
    return True
'''
m = comparer_sources(AGE, "verifier_age",
                     {"fixes": generer_cas_de_test(1, False),
                      "ia": [[30], [17], [18], [120], [121], [-1]]})
print(f"      âge — fixes : {m['scores']['fixes']['score']:.0%}, IA : {m['scores']['ia']['score']:.0%}, "
      f"hybride : {m['scores']['hybride']['score']:.0%}")
verifier("pour une fonction qui attend un NOMBRE, les entrées fixes (des textes) ne testent rien",
         m["scores"]["fixes"]["score"] == 0)
verifier("les entrées de l'IA, qui visent les bornes 18 et 120, détectent les bugs",
         m["scores"]["ia"]["score"] >= 0.75 and m["detectes_seulement_par_ia"])
verifier("l'hybride fait au moins aussi bien que chaque source seule",
         m["scores"]["hybride"]["score"] >= max(m["scores"]["fixes"]["score"],
                                                m["scores"]["ia"]["score"]))

print("\n── Modules qui dépendent d'autres fichiers du projet ──")
import tempfile
from agent_testeur_differentiel import executer_fonction_python
projet_py = tempfile.mkdtemp()
open(os.path.join(projet_py, "db.py"), "w", encoding="utf-8").write(
    "def get_user_by_email(email):\n"
    "    return {'email': email, 'password': 'secret12'} if email == 'a@b.c' else None\n")
LOGIN = ("from db import get_user_by_email\n\n"
         "def login(email, password):\n"
         "    user = get_user_by_email(email)\n"
         "    if user and user['password'] == password:\n"
         "        return 'Connexion réussie'\n"
         "    return 'Email ou mot de passe incorrect'\n")
seul = executer_fonction_python(LOGIN, "login", ["a@b.c", "secret12"])
avec = executer_fonction_python(LOGIN, "login", ["a@b.c", "secret12"], dossier_python=projet_py)
inconnu_seul = executer_fonction_python(LOGIN, "login", ["inconnu@x.y", "secret12"])
inconnu_avec = executer_fonction_python(LOGIN, "login", ["inconnu@x.y", "secret12"],
                                        dossier_python=projet_py)
verifier("avant : db.py était remplacé par un module FACTICE — login tournait contre un faux",
         inconnu_seul.get("resultat") != inconnu_avec.get("resultat"))
verifier("maintenant : le VRAI db.py, déjà migré, est utilisé — bon mot de passe accepté",
         avec["ok"] and avec["resultat"] == "Connexion réussie")
verifier("… et un e-mail inconnu correctement refusé, comme dans le PHP",
         inconnu_avec["resultat"] == "Email ou mot de passe incorrect")
m = comparer_sources(LOGIN, "login", {"fixes": [["a@b.c", "secret12"], ["x", "y"]],
                                      "ia": [["a@b.c", "faux"]]}, dossier_python=projet_py)
verifier("le test de mutation s'applique aussi aux modules dépendants",
         m["statut"] == "mesure" and m["mutants"] > 0)
m = comparer_sources("def connecter(hote):\n    raise ConnectionError('pas de base')\n",
                     "connecter", {"fixes": [["a"], ["b"]], "ia": [["c"]]})
verifier("une fonction qui échoue sur toutes les entrées est signalée non observable",
         m["statut"] == "non_observable")

print("\n── Robustesse : un agent non bloquant ne fait jamais tomber le module ──")
open(os.path.join(projet_py, "config_db.py"), "w", encoding="utf-8").write(
    "import sys\ntry:\n    raise ConnectionError()\nexcept Exception:\n"
    "    sys.exit('Erreur connexion DB')\n")
try:
    r = executer_fonction_python("from config_db import x\ndef f(a):\n    return a\n", "f", ["a"],
                                 dossier_python=projet_py)
    verifier("un fichier qui fait sys.exit() dès l'import n'interrompt plus le Comparateur",
             not r["ok"] and "SystemExit" in r["exception"])
except BaseException:
    verifier("un fichier qui fait sys.exit() dès l'import n'interrompt plus le Comparateur", False)

import agent_testeur_differentiel
import outils_agents as oa
from espace_partage import EspaceModule, StockageSQLite
espace = EspaceModule("robustesse", "m", StockageSQLite(os.path.join(projet_py, "e.db")))
oa.preparer_module(espace, {"nom_python": "f", "nom_original": "f", "parametres": ["$a"]},
                   {"code_php_module": "<?php function f($a) { return $a; } ?>",
                    "max_iterations": 3})
espace.deposer("code_python", "def f(a):\n    return a\n", "Développeur", dependances=[],
               hypotheses_faites=[], points_incertains=[], points_attention=[])
original = agent_testeur_differentiel.tester_equivalence
def plantage(*args, **kwargs):
    raise SystemExit("panne interne du Comparateur")
agent_testeur_differentiel.tester_equivalence = plantage
os.environ["SMAML_ENTREES_IA"] = "0"
try:
    message = oa.realiser(espace, "rapport_differentiel")
    verifier("un Comparateur qui plante dépose un rapport « erreur », le module continue",
             espace["rapport_differentiel"]["statut"] == "erreur" and "non mesurée" in message)
except BaseException as e:
    verifier(f"un Comparateur qui plante dépose un rapport « erreur » ({type(e).__name__})", False)
finally:
    agent_testeur_differentiel.tester_equivalence = original

print("\n── Base de données : le code legacy et le code moderne s'exécutent ──")
import sqlite3
import doublures_bdd
base_test = os.path.join(projet_py, "test.db")
cx = sqlite3.connect(base_test)
cx.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, password TEXT)")
cx.execute("INSERT INTO users (email, password) VALUES ('a@b.c', 'secret12')")
cx.commit(); cx.close()
MODERNE = ("from sqlalchemy import create_engine, select, text\n"
           "from sqlalchemy.orm import Session\n\n"
           "moteur = create_engine('mysql+pymysql://root:@localhost/users_db')\n\n"
           "def get_user(email):\n"
           "    with Session(moteur) as session:\n"
           "        ligne = session.execute(text('SELECT email, password FROM users WHERE email = :e'),"
           " {'e': email}).mappings().first()\n"
           "        return dict(ligne) if ligne else None\n")
r = executer_fonction_python(MODERNE, "get_user", ["a@b.c"], chemin_bdd=base_test)
verifier("Python : le VRAI SQLAlchemy (select, Session) s'exécute sur la base de test",
         r["ok"] and r["resultat"] == {"email": "a@b.c", "password": "secret12"})
verifier("… et la requête est journalisée, pour l'analyse des injections",
         any("SELECT email" in q for q in r.get("requetes", [])))
import sqlalchemy
verifier("… puis SQLAlchemy est rendu intact (connexion d'origine restaurée)",
         sqlalchemy.create_engine.__name__ == "create_engine")
reecrit = doublures_bdd.reecrire_php("while ($l = mysql_fetch_array($r)) { echo mysql_result($r, 0, 'email'); }")
verifier("PHP : mysql_fetch_array et mysql_result (extension supprimée en PHP 7) sont pris en charge",
         "smaml_ligne_mixte(" in reecrit and "smaml_resultat(" in reecrit
         and "function smaml_ligne_mixte" in doublures_bdd.PRELUDE_PHP)

DI = ("from sqlalchemy import text\nfrom sqlalchemy.orm import Session\n\n"
      "def get_user(email: str, db: Session):\n"
      "    ligne = db.execute(text('SELECT email FROM users WHERE email = :e'), {'e': email}).first()\n"
      "    return ligne[0] if ligne else None\n")
r = executer_fonction_python(DI, "get_user", ["a@b.c"], chemin_bdd=base_test)
verifier("get_user(email, db: Session) : le Comparateur fournit une vraie session sur la base de test",
         r["ok"] and r["resultat"] == "a@b.c")

from agent_testeur_differentiel import comparer
ligne_php = {"ok": True, "resultat": {"0": 1, "id": 1, "1": "a@b.c", "email": "a@b.c"}, "requetes": []}
ligne_py = {"ok": True, "resultat": {"id": 1, "email": "a@b.c"}, "requetes": []}
verifier("mysql_fetch_array (valeurs en double, par numéro et par nom) = la même ligne en Python",
         comparer(ligne_php, ligne_py, 1)["equivalent"])
import sqlalchemy as _sa
_moteur = _sa.create_engine(f"sqlite:///{base_test}")
with _moteur.connect() as _c:
    _row = _c.execute(_sa.text("SELECT id, email FROM users")).mappings().first()
verifier("une ligne SQLAlchemy (RowMapping) se compare comme une ligne, pas comme une ressource",
         comparer({"ok": True, "resultat": {"id": 1, "email": "a@b.c"}, "requetes": []},
                  {"ok": True, "resultat": _row, "requetes": []}, 1)["equivalent"])
_moteur.dispose()

print("\n── Erreurs relevées sur la campagne passage1 ──")
m = comparer_sources("def f(a, b):\n    if a > 5:\n        return a + b\n    return 0\n", "f",
                     {"fixes": [[10, 0]], "ia": [[10, 0.0]]})
verifier("[10, 0] et [10, 0.0] (égaux pour Python) ne font plus planter la mutation (KeyError)",
         m["statut"] == "mesure")
AVEC_FICHIER = "import os\nBASE = os.path.dirname(__file__)\n\ndef f(a):\n    return a > 3\n"
verifier("du code qui utilise __file__ s'exécute dans le Comparateur (NameError)",
         executer_fonction_python(AVEC_FICHIER, "f", [5]) == {"ok": True, "resultat": True, "requetes": []})
verifier("… et dans le test de mutation",
         comparer_sources(AVEC_FICHIER, "f", {"fixes": [[1], [5]], "ia": [[4]]})["statut"] == "mesure")

print("\n── Failles attribuées à leur fonction ──")
import orchestration
plan_fichier = {"fichier": "securite.php", "invariants": [], "failles": [
    {"type": "command_injection", "cwe": "CWE-78", "fonction": "genererRapport"}]}
contexte = orchestration.contexte_module(
    {"nom_python": "get_user", "nom_original": "getUser"}, plan_fichier, "", {}, [], [], set(), 3)
verifier("get_user n'est plus jugé sur l'injection de commande d'une autre fonction",
         contexte["failles"] == [])
contexte = orchestration.contexte_module(
    {"nom_python": "generer_rapport", "nom_original": "genererRapport"}, plan_fichier, "", {}, [], [], set(), 3)
verifier("generer_rapport, lui, garde bien sa faille CWE-78 à corriger",
         [f["cwe"] for f in contexte["failles"]] == ["CWE-78"])

ok = sum(1 for _, x in resultats if x)
print(f"\n{ok}/{len(resultats)} vérifications réussies")
if ok != len(resultats):
    raise SystemExit(1)