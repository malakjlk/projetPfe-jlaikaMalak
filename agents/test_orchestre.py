"""
Test rapide du mode orchestré sur UN fichier PHP.
Usage : py test_orchestre.py chemin\vers\fichier.php

Affiche le journal (avec la justification du Manager pour chaque
activation), le statut final et les points d'attention, puis
enregistre tout dans resultat_test.json.
"""
import sys
import json

from agent_analyste import analyser_code_php
from agent_architecte import planifier_migration
from agent_developpeur import extraire_code_module, extraire_code_classe
from crewai_pipeline import migrer_module_orchestre

if len(sys.argv) < 2:
    print("Usage : py test_orchestre.py fichier.php")
    sys.exit(1)

with open(sys.argv[1], "r", encoding="utf-8", errors="ignore") as f:
    code = f.read()

analyse = analyser_code_php(code)
plan = planifier_migration(analyse, code)
if not plan["modules"]:
    print("Aucune fonction ni classe trouvée dans ce fichier.")
    sys.exit(1)

module = plan["modules"][0]
extraire = (extraire_code_classe if module["type"] == "classe"
            else extraire_code_module)
code_module = extraire(code, module["nom_original"])

print(f"\n>>> Module testé : {module['nom_original']}\n")
res = migrer_module_orchestre(code_module, module, analyse,
                             code_php_complet=code)
etat = res["etat_structure"]

print("\n" + "=" * 60)
print(f"STATUT : {etat['statut']}  |  décision : "
      f"{res['decision'].get('decision')}  |  catégorie : "
      f"{res['decision'].get('categorie_echec')}")
print("=" * 60)

print("\nJOURNAL (agent — issue — justification du Manager) :")
for j in etat["journal"]:
    print(f"  {j['ordre']:>2}. {j['agent']:<27} {j['issue']:<16} "
          f"← {j.get('justification_manager')}")

vides = sum(1 for j in etat["journal"] if not j.get("justification_manager"))
if etat["journal"] and vides == len(etat["journal"]):
    print("\n⚠️  Aucune justification capturée : envoie ta version de "
          "CrewAI (py -m pip show crewai).")

depots = (res.get("historique") or {}).get("code_python") or []
if depots:
    d = depots[-1]
    print("\nDÉPÔT DU DÉVELOPPEUR (schéma complet) :")
    print(f"  dépendances       : {d.get('dependances')}")
    print(f"  hypothèses faites : {d.get('hypotheses_faites')}")
    print(f"  points incertains : {d.get('points_incertains')}")
    print(f"  points d'attention: {d.get('points_attention')}")
    print(f"  versions de code conservées : {len(depots)}")

print("\nPOINTS D'ATTENTION :")
for p in etat["points_attention"]:
    print(f"  - {p}")

import cache_smaml
print("\n" + cache_smaml.resume())

with open("resultat_test.json", "w", encoding="utf-8") as f:
    json.dump({"etat_structure": etat, "decision": res["decision"],
               "historique_versions": etat["versions"]},
              f, ensure_ascii=False, indent=2, default=str)
print("\nDétails complets enregistrés dans resultat_test.json")