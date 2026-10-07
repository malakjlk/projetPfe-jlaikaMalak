"""
Tests des métriques d'évaluation.

    py -X utf8 test_metriques.py

CodeBLEU est vérifié si SMAML_PYTHON_CODEBLEU désigne un environnement
virtuel où « codebleu » est installé ; sinon, le test vérifie que
l'absence est signalée clairement.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
if not os.path.exists(os.path.join(ICI, "metriques.py")) or "def pass_at_k" not in \
        open(os.path.join(ICI, "metriques.py"), encoding="utf-8").read():
    sys.exit("metriques.py absent ou ancienne version")
import metriques as mt

resultats = []


def verifier(nom, condition):
    resultats.append((nom, bool(condition)))
    print(f"   {'[OK]' if condition else '[ECHEC]'} {nom}")


print("\n── pass@k : l'estimateur sans biais de Chen et al. (2021) ──")
verifier("1 génération correcte sur 3 : pass@1 = 1/3, pass@3 = 1",
         abs(mt.pass_at_k(3, 1, 1) - 1 / 3) < 1e-9 and mt.pass_at_k(3, 1, 3) == 1.0)
verifier("aucune génération correcte : pass@k = 0", mt.pass_at_k(5, 0, 3) == 0.0)


def module(nom, decision="LIVRER", iterations=1, equivalence=1.0, code="def f():\n    return 1\n",
           modele="openai/gpt-oss-120b", tokens=(1000, 400), duree=30.0):
    return {"nom_python": nom, "decision_finale": decision, "iterations": iterations,
            "code_python": code, "duree_s": duree,
            "modele_generation": {"modele": modele, "bascule": modele.startswith("gemini")},
            "tokens_generation": {"entree": tokens[0], "sortie": tokens[1], "appels": 1},
            "equivalence": {"statut": "teste", "score_equivalence": equivalence,
                            "injections_bloquees": ["' OR 1=1"],
                            "mutation": {"statut": "mesure", "scores": {
                                "fixes": {"score": 0.5}, "ia": {"score": 1.0}, "hybride": {"score": 1.0}},
                                "detectes_seulement_par_ia": ["borne"]}},
            "rapport_testeur": {"failles": {"failles_corrigees": [1], "failles_persistantes": []},
                                "invariants": {"invariants_verifies": [1, 2], "invariants_manquants": [3]}},
            "verification_formelle": {"proprietes": [{"statut": "prouvee"}]},
            "coordonne_par": "manager_principal", "relais": [{"issue": "termine"}],
            "jugement": {"statut": "evalue", "score": 80, "modele": "qwen/qwen3.8-27b"},
            "etat_structure": {"journal": [{"issue": "execute"}, {"issue": "refus_prerequis"}]}}


passage1 = {"fichiers_migres": [{"source": "utils.php", "modules": [
    module("valider"), module("nettoyer", iterations=2, equivalence=0.5)]}]}
passage2 = {"fichiers_migres": [{"source": "utils.php", "modules": [
    module("valider"), module("nettoyer", code="def f(:\n", decision="ARRET_ECHEC",
                              modele="gemini-3.8-flash")]}]}
tmp = tempfile.mkdtemp()
chemins = []
for i, rapport in enumerate((passage1, passage2)):
    dossier = os.path.join(tmp, f"passage{i}")
    os.makedirs(dossier)
    json.dump(rapport, open(os.path.join(dossier, "rapport_migration.json"), "w"))
    chemins.append(dossier)
m = mt.calculer(chemins)
f = m["fonctionnelles"]

print("\n── Fonctionnelles ──")
verifier("le taux de syntaxe valide repère le code qui ne s'analyse pas (3 sur 4)",
         f["taux_syntaxe_valide"] == 0.75)
verifier("computational accuracy : moyenne des équivalences mesurées",
         f["computational_accuracy"] == round((1 + 0.5 + 1 + 1) / 4, 3))
verifier("deux passages = deux échantillons par module : pass@1 et pass@2 calculés",
         f["echantillons_par_module"] == 2 and f["pass@1"] == 0.5 and f["pass@2"] == 0.5)
verifier("score de mutation par source d'entrées",
         {k: f["mutation"][k] for k in ("fixes", "ia", "hybride")} == {"fixes": 0.5, "ia": 1.0, "hybride": 1.0})

# Les deux erreurs relevées sur la première campagne réelle
non_execute = module("connexion")
non_execute["equivalence"] = {"statut": "non_testable", "raison": "dépend de la base",
                              "mutation": {"statut": "mesure", "scores": {
                                  "fixes": {"score": 0.2}, "hybride": {"score": 0.2}}}}
passage3 = {"fichiers_migres": [{"source": "db.php", "modules": [non_execute, module("lire")]}]}
dossier3 = os.path.join(tmp, "passage3")
os.makedirs(dossier3)
json.dump(passage3, open(os.path.join(dossier3, "rapport_migration.json"), "w"))
f3 = mt.calculer([dossier3])["fonctionnelles"]
verifier("le taux d'exécution compte les modules NON exécutés, avec leur raison (1 sur 2)",
         f3["taux_execution"] == 0.5 and f3["non_mesurables_par_raison"] == {"dépend de la base": 1})
verifier("mutation : un module sans entrées IA est exclu de la comparaison des sources",
         f3["mutation"]["modules_compares"] == 1
         and f3["mutation"]["hybride"] >= f3["mutation"]["ia"])

print("\n── Sécurité ──")
s = m["securite"]
verifier("failles corrigées, gardes préservées, injections bloquées, propriétés prouvées",
         s["failles_corrigees"] == 4 and s["gardes_preservees"] == "8/12"
         and s["injections_bloquees"] == 4 and s["proprietes_prouvees"] == 4)

print("\n── Par LLM ──")
l = m["par_llm"]
verifier("le Développeur est évalué PAR MODÈLE : gpt-oss et le secours Gemini séparés",
         set(l["developpeur"]) == {"openai/gpt-oss-120b", "gemini-3.8-flash"}
         and l["developpeur"]["gemini-3.8-flash"]["bascules"] == 1)
verifier("le Manager : sollicitations et refus de phase, par coordinateur",
         l["manager"]["manager_principal"]["refus_de_phase"] == 4
         and l["manager"]["manager_principal"]["sollicitations_par_module"] == 2)
verifier("le juge et le générateur d'entrées ont leurs mesures",
         l["juge"]["disponibilite"] == 1.0 and l["generateur_entrees"]["bugs_detectes_seulement_par_ia"] == 4)

print("\n── Coût ──")
verifier("tokens et temps cumulés", m["cout"]["tokens_entree"] == 4000
         and m["cout"]["duree_totale_s"] == 120.0)

print("\n── CodeBLEU, dans un environnement isolé ──")
candidats, references = os.path.join(tmp, "c"), os.path.join(tmp, "r")
os.makedirs(candidats); os.makedirs(references)
reference = "def valider(mot):\n    if len(mot) < 8:\n        raise ValueError('court')\n    return True\n"
open(os.path.join(references, "a.py"), "w").write(reference)
open(os.path.join(candidats, "a.py"), "w").write(reference)
cb = mt.codebleu(candidats, references)
if os.getenv("SMAML_PYTHON_CODEBLEU"):
    verifier("traduction identique à la référence : CodeBLEU proche de 1",
             cb["statut"] == "mesure" and cb["codebleu"] > 0.95)
    open(os.path.join(candidats, "a.py"), "w").write("def valider(x):\n    return x\n")
    verifier("traduction éloignée : CodeBLEU nettement plus bas",
             mt.codebleu(candidats, references)["codebleu"] < 0.6)
else:
    verifier("sans environnement CodeBLEU, l'absence est signalée avec la marche à suivre",
             cb["statut"] == "codebleu_absent" and "venv" in cb["raison"])

print("\n── De bout en bout : deux vrais passages sur ton projet ──")
simu = os.path.join(tmp, "simu")
os.makedirs(simu)
shutil.copy(os.path.join(ICI, "developpeur_simule.py"), os.path.join(simu, "agent_developpeur.py"))
sorties = []
for i in range(2):
    sortie = os.path.join(tmp, f"reel{i}")
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([simu, ICI]), SMAML_STOCKAGE="sqlite",
               SMAML_STOCKAGE_SQLITE=os.path.join(tmp, f"e{i}.db"), SMAML_CACHE="0",
               SMAML_MODE="direct", SMAML_JUGE="0", SMAML_ENTREES_IA="0", PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, "-X", "utf8", "-c", "import orchestration; orchestration."
                    f"migrer_projet({os.path.join(ICI, 'test_php_project')!r}, {sortie!r}, 2)"],
                   cwd=tmp, env=env, capture_output=True, timeout=900)
    sorties.append(sortie)
reel = mt.calculer(sorties)
verifier("10 modules, 2 échantillons chacun, pass@1 et pass@2 calculés",
         reel["fonctionnelles"]["modules"] == 10 and "pass@2" in reel["fonctionnelles"])
verifier("le temps de chaque module est relevé", reel["cout"]["duree_moyenne_s"] is not None)
campagne = os.path.join(tmp, "campagne")
os.makedirs(campagne)
for i, sortie in enumerate(sorties):
    shutil.copytree(sortie, os.path.join(campagne, f"projet-{i}"))
verifier("un dossier de campagne entier se lit d'un coup",
         mt.calculer([campagne])["fonctionnelles"]["modules"] == 10)

ok = sum(1 for _, x in resultats if x)
print(f"\n{ok}/{len(resultats)} vérifications réussies")
shutil.rmtree(tmp, ignore_errors=True)
if ok != len(resultats):
    raise SystemExit(1)