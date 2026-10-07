"""
Tests du LLM juge, de son intégration dans le Réviseur, et de l'étalonnage.

    py -X utf8 test_juge.py

Aucun appel réseau : les réponses du juge sont simulées. Le Testeur et
l'Auditeur, eux, sont les vrais.
"""
import io
import json
import contextlib
import os
import tempfile

os.environ["SMAML_CACHE"] = "0"
import agent_juge as juge
os.environ["SMAML_LIMITEUR"] = "0"   # réponses simulées : pas de quota à protéger
import fournisseurs_llm as fl
from agent_reviseur import agent_reviseur
from agent_testeur import agent_testeur
from agent_auditeur import agent_auditeur
import etalonnage_juge as et

resultats = []


def verifier(nom, condition):
    resultats.append((nom, bool(condition)))
    print(f"   {'[OK]' if condition else '[ECHEC]'} {nom}")


def reponse_juge(notes):
    contenu = {"criteres": {c: {"justification": "ok", "note": n}
                            for c, n in zip(juge.GRILLE, notes)},
               "synthese": "test"}
    return 200, json.dumps({"choices": [{"message": {"content": json.dumps(contenu)}}]}), {}


def transport(notes, modeles_vus=None):
    def envoyer(url, cle, charge):
        if modeles_vus is not None:
            modeles_vus.append(charge["model"])
        return reponse_juge(notes)
    return envoyer


os.environ.update({"GROQ_TOKEN": "x", "GEMINI_API_KEY": "y",
                   # Réglages fixés pour le test : il ne dépend pas de la
                   # configuration personnelle de la machine.
                   "SMAML_CHAINE_JUGE": "groq",
                   "SMAML_MODELE_JUGE": "qwen/qwen3.8-27b"})
fl.EN_PANNE.clear()

print("\n── Lecture du jugement ──")
j = juge.analyser_reponse(json.dumps({"criteres": {c: {"justification": "x", "note": 5}
                                                   for c in juge.GRILLE}}))
verifier("un jugement valide est lu, critère par critère", len(j["criteres"]) == 5)
verifier("échelle : tout à 5 → 100, tout à 3 → 50, tout à 1 → 0",
         juge.score_sur_100({c: {"note": 5} for c in juge.GRILLE}) == 100
         and juge.score_sur_100({c: {"note": 3} for c in juge.GRILLE}) == 50
         and juge.score_sur_100({c: {"note": 1} for c in juge.GRILLE}) == 0)
avec_reflexion = ("<think>Je pèse {les critères} un par un.</think>\n"
                  + json.dumps({"criteres": {c: {"justification": "x", "note": 4}
                                             for c in juge.GRILLE}}))
verifier("la réflexion <think> du modèle est ignorée, seul le jugement est lu",
         juge.score_sur_100(juge.analyser_reponse(avec_reflexion)["criteres"]) == 75)
for texte, nom in (("pas de json", "une réponse sans JSON est rejetée"),
                   (json.dumps({"criteres": {c: {"note": 7} for c in juge.GRILLE}}),
                    "une note hors échelle est rejetée")):
    try:
        juge.analyser_reponse(texte)
        verifier(nom, False)
    except ValueError:
        verifier(nom, True)

print("── Appel du juge ──")
vus = []
r = juge.juger("<?php ?>", "def f(): pass", transport=transport([4, 4, 3, 4, 2], vus))
verifier("le juge rend une évaluation", r["statut"] == "evalue" and r["score"] == 60.0)
verifier("le juge utilise le modèle configuré, d'une autre famille que gpt-oss",
         vus and vus[0] == juge.modele_juge() and juge.famille(vus[0]) != "OpenAI")
fl.EN_PANNE.clear()
r = juge.juger("<?php ?>", "def g(): pass",
               transport=lambda u, c, ch: (503, "overloaded", {}))
verifier("juge en panne : statut « indisponible », sans bloquer", r["statut"] == "indisponible")
fl.EN_PANNE.clear()

print("── Intégration dans le Réviseur ──")
BON = '''def validate_password(password: str) -> bool:
    """Vérifie la longueur."""
    if len(password) < 8:
        raise ValueError("trop court")
    return True
'''
CASSE = "def validate_password(password)\n    return True\n"
module = {"nom_python": "validate_password", "nom_original": "validatePassword",
          "parametres": ["$password"]}
inv = [{"type": "validation_longueur", "description": "longueur >= 8",
        "code": "if (strlen($password) < 8) throw", "fonction": "validatePassword"}]


def reviser(code, rapport_juge, iteration=1):
    with contextlib.redirect_stdout(io.StringIO()):
        rt = agent_testeur(code, module, inv, [])
        ra = agent_auditeur(code, inv, module)
        return agent_reviseur(rt, ra, module, iteration_actuelle=iteration,
                              max_iterations=5, rapport_juge=rapport_juge)


def jugement(score):
    return {"statut": "evalue", "score": score, "criteres": {
        "architecture": {"note": 2, "justification": "erreurs HTTP dans la couche de données"},
        "documentation": {"note": 5, "justification": "complète"}}}


d = reviser(BON, jugement(80))
crit = {c["nom"]: c for c in d["confiance"]["criteres"]}
verifier("le juge devient le 5e critère, avec un poids limité",
         crit["qualite_jugee"]["mesure"] and 0 < crit["qualite_jugee"]["poids"] < 0.2)

d = reviser(CASSE, jugement(100))
crit = {c["nom"]: c for c in d["confiance"]["criteres"]}
verifier("verrou : un juge enthousiaste ne compte pas sur un code inexécutable",
         not crit["qualite_jugee"]["mesure"] and "verrou" in crit["qualite_jugee"]["raison"])
verifier("verrou : le code inexécutable n'est pas livré", d["decision"] != "LIVRER")

# Le cas observé sur le COBOL : un score assez haut pour être livré,
# alors que le Testeur a PROUVÉ l'absence d'une garde obligatoire.
with contextlib.redirect_stdout(io.StringIO()):
    rt = agent_testeur(BON, module, inv, [])
    ra = agent_auditeur(BON, inv, module)
    rt["invariants"]["invariants_manquants"] = [dict(inv[0], obligatoire=True)]
    rt["invariants"]["preuves"] = [{"invariant": inv[0]["description"],
                                    "verdict": "manquant",
                                    "source": "contre-exemple : '' accepté"}]
    d = agent_reviseur(rt, ra, module, iteration_actuelle=1, max_iterations=5)
verifier("verrou : une garde obligatoire manquante empêche la livraison, malgré un score élevé",
         d["decision"] == "ITERER" and d["categorie_echec"] == "verrou"
         and d["score_compose"] >= 65
         and any("garde" in c.lower() for c in (d.get("feedback") or {}).get("instructions", [])))

d = reviser(BON, jugement(5))
consignes = (d.get("feedback") or {}).get("instructions") or []
verifier("désaccord fort : le module est RENVOYÉ au Développeur, pas à un humain",
         d["decision"] == "ITERER" and d["categorie_echec"] == "desaccord_juge")
verifier("les remarques du juge (notes ≤ 3) deviennent la consigne de correction",
         any("couche de données" in c for c in consignes)
         and not any("complète" in c for c in consignes))
d = reviser(BON, jugement(5), iteration=3)
verifier("désaccord PERSISTANT après 2 corrections : validation humaine",
         d["decision"] == "VALIDATION_HUMAINE" and d.get("remarques_juge"))

d = reviser(BON, {"statut": "indisponible", "raison": "quota"})
crit = {c["nom"]: c for c in d["confiance"]["criteres"]}
verifier("juge indisponible : critère non compté, la décision reste possible",
         not crit["qualite_jugee"]["mesure"] and d["decision"] == "LIVRER")

print("── Étalonnage ──")
parfait = et.mesures([1, 2, 3, 4, 5, 3], [1, 2, 3, 4, 5, 3])
verifier("accord parfait : kappa 1 et Spearman 1",
         parfait["kappa_pondere"] == 1.0 and parfait["spearman"] == 1.0)
proche = et.mesures([1, 2, 3, 4, 5, 3], [2, 2, 3, 5, 4, 3])
inverse = et.mesures([1, 2, 3, 4, 5], [5, 4, 3, 2, 1])
verifier("un juge proche obtient un kappa élevé, un juge inversé un kappa négatif",
         proche["kappa_pondere"] > 0.6 and inverse["kappa_pondere"] < 0)
verifier("l'interprétation suit l'échelle de Landis et Koch",
         et.interpreter_kappa(0.85) == "presque parfait"
         and et.interpreter_kappa(0.5) == "modéré")

dossier = tempfile.mkdtemp()
rapport = {"fichiers_migres": [{"source": "utils.php", "modules": [
    {"nom_python": "validate_password", "code_php": "<?php ?>", "code_python": BON,
     "jugement": {"statut": "evalue",
                  "criteres": {c: {"note": 4} for c in juge.GRILLE}}}]}]}
chemin_rapport = os.path.join(dossier, "rapport.json")
json.dump(rapport, open(chemin_rapport, "w", encoding="utf-8"))
grille = os.path.join(dossier, "grille.csv")
with contextlib.redirect_stdout(io.StringIO()):
    et.preparer([chemin_rapport], grille)
contenu = open(grille, encoding="utf-8").read()
verifier("la grille à remplir ne montre PAS les notes du juge (notation à l'aveugle)",
         "note_humaine" in contenu and ",4" not in contenu)
lignes = contenu.splitlines()
remplie = [lignes[0]] + [l + "4" for l in lignes[1:]]
open(grille, "w", encoding="utf-8").write("\n".join(remplie) + "\n")
with contextlib.redirect_stdout(io.StringIO()):
    calcul = et.calculer(grille)
verifier("le calcul d'accord fonctionne sur une grille remplie",
         calcul["global"]["accord_exact"] == 100.0)

ok = sum(1 for _, x in resultats if x)
print(f"\n{ok}/{len(resultats)} vérifications réussies")
if ok != len(resultats):
    raise SystemExit(1)