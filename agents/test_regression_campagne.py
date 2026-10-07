"""
Test de non-régression — le scénario réel de la campagne passage1.

    py -X utf8 test_regression_campagne.py

Symptôme observé : une nouvelle campagne affichait des failles
« persistantes » (CWE-78 sur get_user…) alors que le code produit les
avait toutes corrigées. Cause : l'identifiant d'un projet ne dépendait que
de son chemin d'entrée ; l'espace partagé étant persistant, toute nouvelle
campagne reprenait l'état de la PREMIÈRE, avec son ancien plan.

Ce test rejoue le code réellement produit par le LLM sur securite.php.
"""
import json, os, shutil, subprocess, sys, tempfile
ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
if "projet_id.txt" not in open(os.path.join(ICI, "ordonnanceur.py"), encoding="utf-8").read():
    sys.exit("ordonnanceur.py : ancienne version (la reprise doit dépendre du dossier du run)")
import metriques as mt
import ordonnanceur as oo

resultats = []


def verifier(nom, condition):
    resultats.append((nom, bool(condition)))
    print(f"   {'[OK]' if condition else '[ECHEC]'} {nom}")


PHP = '<?php\nfunction getUser($id) {\n    $sql = "SELECT * FROM users WHERE id=" . $id;\n    $result = mysql_query($sql);\n    return mysql_fetch_array($result);\n}\n\nfunction genererRapport($commande) {\n    $sortie = shell_exec("report_tool " . $commande);\n    return $sortie;\n}\n\nfunction chercherProduit($nom) {\n    $sql = "SELECT * FROM produits WHERE nom LIKE \\"%" . $nom . "%\\"";\n    return mysql_query($sql);\n}\n'
racine = tempfile.mkdtemp(prefix="regression_")
projet = os.path.join(racine, "corpus", "p3_securite")
os.makedirs(projet)
open(os.path.join(projet, "securite.php"), "w", encoding="utf-8").write(PHP)
codes = {
 "get_user": "from sqlalchemy import create_engine, text\nmoteur = create_engine('sqlite://')\n\n"
             "def get_user(id):\n    with moteur.connect() as c:\n"
             "        ligne = c.execute(text('SELECT * FROM users WHERE id = :id'), {'id': id}).mappings().first()\n"
             "        return dict(ligne) if ligne else None\n",
 "generer_rapport": "import subprocess\n\ndef generer_rapport(commande):\n"
             "    if not commande or any(not (c.isalnum() or c in '-_.') for c in commande):\n        return None\n"
             "    try:\n        r = subprocess.run(['report_tool', commande], capture_output=True, text=True, timeout=30, shell=False)\n"
             "    except (OSError, subprocess.SubprocessError):\n        return None\n"
             "    return r.stdout if r.returncode == 0 else None\n",
 "chercher_produit": "from sqlalchemy import create_engine, text\nmoteur = create_engine('sqlite://')\n\n"
             "def chercher_produit(nom):\n    with moteur.connect() as c:\n"
             "        lignes = c.execute(text('SELECT * FROM produits WHERE nom LIKE :p'), {'p': f'%{nom}%'}).mappings().all()\n"
             "        return [dict(l) for l in lignes] or None\n"}
json.dump(codes, open(os.path.join(racine, "codes.json"), "w"))
simu = os.path.join(racine, "simu")
os.makedirs(simu)
shutil.copy(os.path.join(ICI, "developpeur_simule.py"), os.path.join(simu, "agent_developpeur.py"))
env = dict(os.environ, PYTHONPATH=os.pathsep.join([simu, ICI]), SMAML_STOCKAGE="sqlite",
           SMAML_STOCKAGE_SQLITE=os.path.join(racine, "stockage_persistant.db"), SMAML_CACHE="0",
           SMAML_MODE="direct", SMAML_JUGE="0", SMAML_ENTREES_IA="0", SMAML_MUTATION="0",
           SIMU_CODES=os.path.join(racine, "codes.json"), PYTHONIOENCODING="utf-8")

print("\n── 1. Une ancienne campagne laisse un état périmé dans le stockage persistant ──")
ancien_id = oo.identifiant(projet)
script = ("import agent_architecte as a, orchestration as o\n"
          "orig = a.planifier_projet\n"
          "def ancien(analyse):\n"
          "    plan = orig(analyse)\n"
          "    for f in plan['fichiers']:\n"
          "        f['failles'] = [{k: v for k, v in x.items() if k != 'fonction'} for x in f['failles']]\n"
          "    return plan\n"
          "a.planifier_projet = ancien\n"
          f"o.migrer_projet({projet!r}, {os.path.join(racine, 'ancienne')!r}, 3, projet={ancien_id!r})\n")
subprocess.run([sys.executable, "-c", script], cwd=racine, env=env, capture_output=True, timeout=600)
ancienne = mt.calculer([os.path.join(racine, "ancienne")])["securite"]
verifier("l'ancienne campagne montre les fausses failles persistantes (le symptôme réel)",
         len(ancienne["failles_persistantes_detail"]) == 4)

print("\n── 2. La nouvelle campagne passage1 repart de zéro ──")
r = oo.campagne([projet], os.path.join(racine, "passage1"), travailleurs=1, env=env)
verifier("passage1 a son propre identifiant : l'ancien état n'est pas repris",
         r["projets"][0]["projet"] != ancien_id)
securite = mt.calculer([os.path.join(racine, "passage1")])["securite"]
verifier("plus aucune fausse faille persistante", securite["failles_persistantes_detail"] == [])
rapport = json.load(open(os.path.join(r["projets"][0]["sortie"], "rapport_migration.json"), encoding="utf-8"))
attribution = {m["nom_python"]: [x.get("cwe") for x in (m["rapport_testeur"].get("failles") or {})
                                  .get("failles_corrigees", [])]
               for f in rapport["fichiers_migres"] for m in f["modules"]}
verifier("chaque module reçoit SA faille et la corrige : get_user CWE-89, generer_rapport CWE-78, "
         "chercher_produit CWE-89",
         attribution == {"get_user": ["CWE-89"], "generer_rapport": ["CWE-78"],
                          "chercher_produit": ["CWE-89"]})
verifier("les trois modules sont livrés",
         all(m["decision_finale"] == "LIVRER" for f in rapport["fichiers_migres"] for m in f["modules"]))

print("\n── 3. Une campagne interrompue, relancée dans le même dossier, reprend ──")
r2 = oo.campagne([projet], os.path.join(racine, "passage1"), travailleurs=1, env=env)
verifier("la même campagne relancée ne refait pas le projet terminé",
         r2["projets"][0]["statut"] == "deja_termine")

print("\n── 4. Dossier supprimé puis campagne relancée : tout est REGÉNÉRÉ ──")
import time
def jeu_de_codes(version):
    chemin = os.path.join(racine, f"codes_{version}.json")
    json.dump({nom: f"# version {version}\n" + code for nom, code in codes.items()},
              open(chemin, "w"))
    return dict(env, SIMU_CODES=chemin)
passage = os.path.join(racine, "passage_rmdir")
r_a = oo.campagne([projet], passage, travailleurs=1, env=jeu_de_codes("A"))
id_a = r_a["projets"][0]["projet"]
shutil.rmtree(passage)                                          # rmdir /s /q passage1
time.sleep(1.1)
r_b = oo.campagne([projet], passage, travailleurs=1, env=jeu_de_codes("B"))
produit = open(os.path.join(r_b["projets"][0]["sortie"], "securite.py"), encoding="utf-8").read()
verifier("après rmdir, le projet est regénéré (le code produit est la version B, pas l'ancienne A)",
         "# version B" in produit and "# version A" not in produit)
verifier("… avec un identifiant neuf, l'état resté dans le stockage n'est pas repris",
         r_b["projets"][0]["projet"] != id_a)

print("\n── 5. Run interrompu, dossier encore présent : il REPREND ──")
interrompu = os.path.join(racine, "passage_interrompu")
r_1 = oo.campagne([projet], interrompu, travailleurs=1, env=jeu_de_codes("A"))
os.remove(os.path.join(r_1["projets"][0]["sortie"], "rapport_migration.json"))   # coupé avant la fin
r_2 = oo.campagne([projet], interrompu, travailleurs=1, env=jeu_de_codes("B"))
repris = open(os.path.join(r_2["projets"][0]["sortie"], "securite.py"), encoding="utf-8").read()
verifier("le run interrompu reprend avec SON identifiant, sans regénérer ce qui était fait",
         r_2["projets"][0]["projet"] == r_1["projets"][0]["projet"]
         and "# version A" in repris and r_2["projets"][0]["statut"] == "termine")

ok = sum(1 for _, x in resultats if x)
print(f"\n{ok}/{len(resultats)} vérifications réussies")
shutil.rmtree(racine, ignore_errors=True)
if ok != len(resultats):
    raise SystemExit(1)