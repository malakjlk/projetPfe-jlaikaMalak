"""
Tests du lot 7 : limiteur de débit partagé, file de priorité, travailleurs
en parallèle, isolation des pannes et reprise d'une campagne.

    py -X utf8 test_ordonnanceur.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
for nom, marque in (("limiteur.py", "class Limiteur"), ("ordonnanceur.py", "def campagne"),
                    ("fournisseurs_llm.py", "LIMITEUR.attendre")):
    if not os.path.exists(os.path.join(ICI, nom)) or marque not in \
            open(os.path.join(ICI, nom), encoding="utf-8").read():
        sys.exit(f"{nom} absent ou ancienne version")

import espace_partage as ep
import ordonnanceur as oo
from limiteur import Limiteur

resultats = []


def verifier(nom, condition):
    resultats.append((nom, bool(condition)))
    print(f"   {'[OK]' if condition else '[ECHEC]'} {nom}")


tmp = tempfile.mkdtemp()

print("\n── Limiteur de débit partagé ──")
os.environ["SMAML_LIMITE_RPM_MODELE_A"] = "60"           # 60 appels/min, soit 1 par seconde
base = os.path.join(tmp, "debit.db")
limiteur = Limiteur(ep.StockageSQLite(base))
debut = time.monotonic()
for _ in range(60):
    limiteur.attendre("groq:modele-a")
verifier("les 60 premiers appels passent sans attendre (le seau est plein)",
         time.monotonic() - debut < 5)
attendu = limiteur.attendre("groq:modele-a")
verifier("le 61e attend son tour, au lieu d'être refusé par le fournisseur",
         0.5 <= attendu <= 2.5)
verifier("chaque modèle a son propre seau : un autre modèle n'attend pas",
         limiteur.attendre("groq:modele-b") == 0)
script = (f"import sys, time; sys.path.insert(0, {ICI!r}); import espace_partage as ep; "
          f"from limiteur import Limiteur; l = Limiteur(ep.StockageSQLite({base!r})); "
          f"print(l.attendre('groq:modele-a'))")
attente_autre = float(subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                                     env=dict(os.environ)).stdout.strip() or 0)
verifier("le seau est PARTAGÉ entre processus : un autre processus attend aussi",
         attente_autre >= 0.5)
try:
    import fakeredis
    redis_simule = Limiteur(ep.StockageRedis(fakeredis.FakeRedis()))
    for _ in range(60):
        redis_simule.attendre("groq:modele-a")
    verifier("sur Redis aussi (script atomique) : le 61e appel attend son tour",
             0.5 <= redis_simule.attendre("groq:modele-a") <= 2.5)
except ImportError:
    print("   (fakeredis absent : vérification Redis sautée)")
os.environ["SMAML_LIMITEUR"] = "0"
verifier("désactivable (SMAML_LIMITEUR=0)", limiteur.attendre("groq:modele-a") == 0)
os.environ.pop("SMAML_LIMITEUR")

print("\n── File de priorité ──")
projets = {}
for nom, fichiers in {
    "petit_sans_faille": {"a.php": "<?php function f($x) { return $x; } ?>"},
    "grand_sans_faille": {f"m{i}.php": f"<?php function g{i}($x) {{ return $x; }} ?>" for i in range(5)},
    "faille_critique": {"db.php": open(os.path.join(ICI, "test_php_project", "db.php"),
                                       encoding="utf-8").read()},
}.items():
    dossier = os.path.join(tmp, "entrees", nom)
    os.makedirs(dossier)
    for fichier, contenu in fichiers.items():
        open(os.path.join(dossier, fichier), "w", encoding="utf-8").write(contenu)
    projets[nom] = dossier
ordre = sorted(projets, key=lambda n: oo.cle_priorite(oo.evaluer_priorite(projets[n])))
verifier("ordre : la faille critique d'abord, puis le plus petit, puis le plus grand",
         ordre == ["faille_critique", "petit_sans_faille", "grand_sans_faille"])
verifier("l'identifiant d'un projet est stable (base de la reprise)",
         oo.identifiant(projets["petit_sans_faille"]) == oo.identifiant(projets["petit_sans_faille"]))

print("\n── Campagne : 3 projets, 2 travailleurs, 1 entrée invalide ──")
simu = os.path.join(tmp, "simu")
os.makedirs(simu)
shutil.copy(os.path.join(ICI, "developpeur_simule.py"), os.path.join(simu, "agent_developpeur.py"))
copies = []
for i in range(3):
    copie = os.path.join(tmp, "entrees", f"application_{i}")
    shutil.copytree(os.path.join(ICI, "test_php_project"), copie)
    copies.append(copie)
invalide = os.path.join(tmp, "entrees", "inexistant")
env = dict(os.environ, PYTHONPATH=simu, SMAML_STOCKAGE="sqlite",
           SMAML_STOCKAGE_SQLITE=os.path.join(tmp, "campagne.db"), SMAML_CACHE="0",
           SMAML_MODE="direct", SMAML_JUGE="0", SMAML_ENTREES_IA="0", PYTHONIOENCODING="utf-8")
sortie = os.path.join(tmp, "campagne")
r = oo.campagne(copies + [invalide], sortie, travailleurs=2, env=env)
termines = [b for b in r["projets"] if b["statut"] == "termine"]
verifier("les 3 projets valides sont migrés, tous leurs modules livrés",
         len(termines) == 3 and all(b["modules_livres"] == b["modules"] == 5 for b in termines))
verifier("l'entrée invalide est écartée sans arrêter les autres projets",
         any(b["statut"] == "ignore" for b in r["projets"]))
intervalles = sorted((b["debut"], b["fin"]) for b in termines)
verifier("deux projets ont réellement tourné EN MÊME TEMPS",
         any(intervalles[i + 1][0] < intervalles[i][1] for i in range(len(intervalles) - 1)))
verifier("chaque projet a son journal et son rapport, dans son propre dossier",
         all(os.path.exists(os.path.join(b["sortie"], f)) for b in termines
             for f in ("journal.txt", "rapport_migration.json")))

print("\n── Une nouvelle campagne part de zéro ──")
journal = open(os.path.join(termines[0]["sortie"], "journal.txt"), encoding="utf-8").read()
autre = oo.campagne(copies[:1], os.path.join(tmp, "autre_campagne"), travailleurs=1, env=env)
verifier("le même projet, dans une AUTRE campagne, est migré à neuf (pas repris)",
         autre["projets"][0]["statut"] == "termine")

print("\n── Reprise de la campagne ──")
debut = time.monotonic()
r2 = oo.campagne(copies, sortie, travailleurs=2, env=env)
verifier("relancée, la campagne ne refait pas les projets déjà terminés",
         all(b["statut"] == "deja_termine" for b in r2["projets"]) and time.monotonic() - debut < 30)

ok = sum(1 for _, x in resultats if x)
print(f"\n{ok}/{len(resultats)} vérifications réussies")
shutil.rmtree(tmp, ignore_errors=True)
if ok != len(resultats):
    raise SystemExit(1)