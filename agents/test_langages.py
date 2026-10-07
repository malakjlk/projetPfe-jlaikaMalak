"""
Tests des adaptateurs de langage — noyau commun, PHP et COBOL.

    py -X utf8 test_langages.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

# Vérification préalable : les fichiers du lot 5 dans leur bonne version.
VERSIONS = {"langages.py": "class AdaptateurFortran", "orchestration.py": "traduire_donnees",
            "agent_analyste.py": "_analyser_projet_adaptateur",
            "agent_architecte.py": "langage_source", "outils_agents.py": "langage_source",
            "agent_reviseur.py": "def verrous_bloquants",
            "reconciliation.py": "contre-exemple"}
anciens = [f"[X] {nom} : absent ou ancienne version (il manque « {marque} »)"
           for nom, marque in VERSIONS.items()
           if not os.path.exists(os.path.join(ICI, nom))
           or marque not in open(os.path.join(ICI, nom), encoding="utf-8", errors="ignore").read()]
if anciens:
    print("Fichiers à mettre à jour avant le test :")
    for ligne in anciens:
        print(f"  {ligne}")
    raise SystemExit(1)

from langages import adaptateur, detecter_langages

COBOL = os.path.join(ICI, "test_cobol_project")
FORTRAN = os.path.join(ICI, "test_fortran_project")
PHP = os.path.join(ICI, "test_php_project")
resultats = []


def fichier(dossier, nom):
    """Chemin d'un fichier, quelle que soit la casse de son nom."""
    return next((os.path.join(dossier, f) for f in os.listdir(dossier)
                 if f.upper() == nom.upper()), os.path.join(dossier, nom))


def verifier(nom, condition):
    resultats.append((nom, bool(condition)))
    print(f"   {'[OK]' if condition else '[ECHEC]'} {nom}")


tmp = tempfile.mkdtemp()
java = os.path.join(tmp, "java")
os.makedirs(java)
for nom in ("A.java", "B.java"):
    open(os.path.join(java, nom), "w").write("class X {}")

print("\n── Détection du langage ──")
verifier("un projet COBOL est reconnu", detecter_langages(COBOL)["principal"] == "cobol")
verifier("un projet PHP est reconnu", detecter_langages(PHP)["principal"] == "php")
d = detecter_langages(java)
verifier("un projet Java est reconnu mais REFUSÉ clairement, avec son nom",
         d["principal"] is None and d["non_pris_en_charge"] == {"Java": 2})

print("\n── Adaptateur COBOL ──")
c = adaptateur("cobol")
r = c.analyser(open(fichier(COBOL, "GESTCLI.cbl")).read())
verifier("les paragraphes deviennent des unités, avec leurs PERFORM",
         [f["nom"] for f in r["fonctions"]] == ["MAIN-PARA", "VERIFIER-MDP", "CHERCHER-CLIENT"]
         and r["fonctions"][0]["appelle"] == ["VERIFIER-MDP"])
verifier("un PIC 9(7)V99 est signalé comme décimal à virgule fixe (Decimal, jamais float)",
         any("Decimal" in d.get("remarque", "") for d in r["variables_globales"]))
verifier("le SQL dynamique (PREPARE) est signalé, au format commun (CWE-89)",
         r["failles_potentielles"][0]["cwe"] == "CWE-89"
         and r["failles_potentielles"][0]["fonction"] == "CHERCHER-CLIENT")
verifier("la garde de longueur du mot de passe est un invariant à préserver",
         r["invariants_securite"][0]["type"] == "validation_longueur")
# Seuls les fichiers COBOL, et une recherche insensible à la casse :
# sous Windows, GESTCLI.CBL et GESTCLI.cbl désignent le même fichier.
fichiers_cobol = [os.path.join(COBOL, f) for f in sorted(os.listdir(COBOL))
                  if f.lower().endswith(c.extensions)]
graphe = c.dependances(fichiers_cobol)
principal = next((k for k in graphe if os.path.basename(k).upper() == "GESTCLI.CBL"), None)
if principal is None:
    print(f"      (contenu du dossier : {os.listdir(COBOL)})")
verifier("dépendances : CALL vers CALCTAX et COPY de CLIENT",
         principal is not None and
         sorted(os.path.basename(x).upper() for x in graphe[principal])
         == ["CALCTAX.CBL", "CLIENT.CPY"])
verifier("la consigne au Développeur traite les pièges du COBOL",
         "Decimal" in c.consigne_traduction() and "PERFORM" in c.consigne_traduction())

print("\n── Adaptateur PHP : le code existant, derrière la même interface ──")
p = adaptateur("php").analyser(open(os.path.join(PHP, "utils.php")).read())
verifier("l'adaptateur PHP produit le même format de rapport",
         [f["nom"] for f in p["fonctions"]] == ["validatePassword", "sanitizeInput"])

print("\n── Migration COBOL complète, par le noyau commun ──")
simu = os.path.join(tmp, "simu")
os.makedirs(simu)
shutil.copy(os.path.join(ICI, "developpeur_simule.py"), os.path.join(simu, "agent_developpeur.py"))
sortie = os.path.join(tmp, "sortie")
env = dict(os.environ, PYTHONPATH=os.pathsep.join([simu, ICI]), SMAML_STOCKAGE="sqlite",
           SMAML_STOCKAGE_SQLITE=os.path.join(tmp, "e.db"), SMAML_CACHE="0",
           SMAML_MODE="direct", SMAML_JUGE="0", SMAML_ENTREES_IA="0", PYTHONIOENCODING="utf-8")
subprocess.run([sys.executable, "-X", "utf8", "-c",
                f"import orchestration; orchestration.migrer_projet({COBOL!r}, {sortie!r}, 2)"],
               cwd=tmp, env=env, capture_output=True, timeout=900)
rapport = json.load(open(os.path.join(sortie, "rapport_migration.json"), encoding="utf-8"))
modules = {m["nom_python"]: m for f in rapport["fichiers_migres"] for m in f["modules"]}
verifier("le langage est détecté à la réception", rapport["reception"]["langage"] == "cobol")
# Noms comparés sans tenir compte de la casse : sous Windows, Calctax.cbl
# et CALCTAX.cbl sont le même fichier.
ordre = [f["source"].upper() for f in rapport["fichiers_migres"]]
verifier("ordre de migration : CALCTAX avant GESTCLI, qui l'appelle",
         "CALCTAX.CBL" in ordre and "GESTCLI.CBL" in ordre
         and ordre.index("CALCTAX.CBL") < ordre.index("GESTCLI.CBL"))
verifier("les noms COBOL deviennent des noms Python valides",
         {"calcul_taxe", "verifier_mdp", "main_para"} <= set(modules))
verifier("le Comparateur dit honnêtement qu'il ne peut pas exécuter le COBOL",
         all(m["equivalence"]["statut"] == "non_testable" for m in modules.values()))
verifier("une garde COBOL absente du Python n'est PAS livrée (verrou)",
         modules["verifier_mdp"]["decision_finale"] != "LIVRER")

print("\n── Copybook : données traduites sans LLM ──")
client = next(f for f in rapport["fichiers_migres"] if f["source"].upper() == "CLIENT.CPY")
if "donnees" not in client:
    print("      [X] le copybook n'a pas été traduit. Contenu lu dans Client.cpy :")
    for ligne in open(fichier(COBOL, "CLIENT.cpy"), encoding="utf-8",
                      errors="replace").read().splitlines() or ["(fichier vide)"]:
        print(f"        |{ligne}")
    client["donnees"] = {"classes": []}
verifier("le copybook CLIENT devient une dataclass ClientRec, traduite sans LLM",
         client["donnees"]["classes"] == ["ClientRec"])
espace = {}
exec(open(os.path.join(sortie, client["cible"]), encoding="utf-8").read(), espace)
from decimal import Decimal
enregistrement = espace["ClientRec"](cli_nom="X" * 40, cli_solde=Decimal("12.349"))
verifier("règles du COBOL respectées : PIC X(30) tronqué à 30, PIC 9(7)V99 tronqué à 2 décimales",
         len(enregistrement.cli_nom) == 30 and enregistrement.cli_solde == Decimal("12.34"))

print("\n── Adaptateur Fortran ──")
f90 = adaptateur("fortran")
verifier("un projet Fortran est reconnu", detecter_langages(FORTRAN)["principal"] == "fortran")
geo = f90.analyser(open(fichier(FORTRAN, "geometrie.f90")).read())
verifier("forme libre : le SUBROUTINE et ses arguments, avec sa garde",
         geo["fonctions"][0]["nom"] == "AIRE_CERCLE"
         and geo["fonctions"][0]["parametres"] == ["r", "a"]
         and geo["invariants_securite"][0]["code"] == "r < 0.0d0")
f77 = f90.analyser(open(fichier(FORTRAN, "calcul.f")).read())
remarques = " ".join(d["remarque"] for d in f77["variables_globales"])
verifier("FORTRAN 77 forme fixe : la FUNCTION, sa garde, et ses trois pièges",
         f77["fonctions"][0]["nom"] == "MOYENNE" and "N .LT. 1" in f77["invariants_securite"][0]["code"]
         and "COMMON" in remarques and "précision" in remarques and "entiers" in remarques)
graphe_f = f90.dependances([os.path.join(FORTRAN, x) for x in sorted(os.listdir(FORTRAN))
                            if x.lower().endswith(f90.extensions)])
nommer = lambda chemin: os.path.basename(chemin).lower()
liens = {nommer(k): [nommer(d) for d in v] for k, v in graphe_f.items()}
verifier("dépendances par USE : main → geometrie → constantes",
         liens.get("main.f90") == ["geometrie.f90"] and liens.get("geometrie.f90") == ["constantes.f90"])
verifier("la consigne traite l'indice 1, le rangement par colonnes et la division entière",
         all(m in f90.consigne_traduction() for m in ("INDICE 1", "COLONNES", "//")))

sortie_f = os.path.join(tmp, "sortie_fortran")
env["SMAML_STOCKAGE_SQLITE"] = os.path.join(tmp, "f.db")
subprocess.run([sys.executable, "-X", "utf8", "-c",
                f"import orchestration; orchestration.migrer_projet({FORTRAN!r}, {sortie_f!r}, 2)"],
               cwd=tmp, env=env, capture_output=True, timeout=900)
rapport_f = json.load(open(os.path.join(sortie_f, "rapport_migration.json"), encoding="utf-8"))
ordre_f = [x["source"].lower() for x in rapport_f["fichiers_migres"]]
verifier("migration Fortran complète : constantes, puis geometrie, puis main",
         ordre_f.index("constantes.f90") < ordre_f.index("geometrie.f90") < ordre_f.index("main.f90"))
constantes = next(x for x in rapport_f["fichiers_migres"] if x["source"].lower() == "constantes.f90")
espace_f = {}
exec(open(os.path.join(sortie_f, constantes["cible"]), encoding="utf-8").read(), espace_f)
verifier("les constantes PARAMETER sont traduites sans LLM (pi = 3.14159…)",
         abs(espace_f["PI"] - 3.14159265358979) < 1e-12 and espace_f["MAX_POINTS"] == 100)
modules_f = {m["nom_python"] for x in rapport_f["fichiers_migres"] for m in x["modules"]}
verifier("les unités Fortran deviennent des fonctions Python aux noms valides",
         {"aire_cercle", "moyenne"} <= modules_f)

ok = sum(1 for _, x in resultats if x)
print(f"\n{ok}/{len(resultats)} vérifications réussies")
shutil.rmtree(tmp, ignore_errors=True)
if ok != len(resultats):
    raise SystemExit(1)