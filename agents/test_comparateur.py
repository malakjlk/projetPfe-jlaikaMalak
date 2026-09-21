"""
Diagnostic du Comparateur — SMAML
Usage : py -X utf8 test_comparateur.py chemin\\vers\\fichier.php

Teste UNIQUEMENT l'agent Comparateur, sans LLM ni CrewAI : quelques
secondes suffisent. Affiche, pour chaque module du fichier, si
l'équivalence est testable et sinon pourquoi.
"""
import subprocess
import sys

from agent_analyste import analyser_code_php
from agent_architecte import planifier_migration
from agent_developpeur import extraire_code_module, extraire_code_classe
from agent_testeur_differentiel import (tester_equivalence, php_disponible,
                                        FONCTIONS_NON_TESTABLES)
import doublures_bdd

if len(sys.argv) < 2:
    print("Usage : py -X utf8 test_comparateur.py fichier.php")
    sys.exit(1)

print("=" * 60)
print("ENVIRONNEMENT")
print("=" * 60)
print(f"  PHP détecté : {php_disponible()}")
try:
    version = subprocess.run(["php", "-v"], capture_output=True,
                             text=True, timeout=10).stdout.splitlines()
    print(f"  Version     : {version[0] if version else '?'}")
    modules = subprocess.run(["php", "-m"], capture_output=True,
                             text=True, timeout=10).stdout.lower()
    print(f"  pdo_sqlite  : {'pdo_sqlite' in modules}")
    if "pdo_sqlite" not in modules:
        print("    ⚠️  Sans pdo_sqlite, la base simulée ne peut pas "
              "fonctionner côté PHP.")
        print("    → active extension=pdo_sqlite dans php.ini")
except Exception as e:
    print(f"  PHP inutilisable : {e}")

with open(sys.argv[1], "r", encoding="utf-8", errors="ignore") as f:
    code = f.read()

analyse = analyser_code_php(code)
plan = planifier_migration(analyse, code)

print("\n" + "=" * 60)
print(f"MODULES DE {sys.argv[1]}")
print("=" * 60)

for module in plan["modules"]:
    nom = module["nom_original"]
    extraire = (extraire_code_classe if module.get("type") == "classe"
                else extraire_code_module)
    extrait = extraire(code, nom) or ""

    print(f"\n── {nom} ({module.get('type')}) ──")
    print(f"  accès base de données : "
          f"{doublures_bdd.code_utilise_bdd(extrait)}")
    bloquants = [m for m in FONCTIONS_NON_TESTABLES if m in extrait]
    print(f"  motifs non testables  : {bloquants or 'aucun'}")

    # Python volontairement neutre : on veut voir SI le test tourne,
    # pas s'il réussit.
    nb = len(module.get("parametres", []))
    params = ", ".join(f"p{i}" for i in range(nb)) if nb else ""
    code_py = f"def {module['nom_python']}({params}):\n    return None\n"

    rapport = tester_equivalence(extrait, code_py, nom,
                                 module["nom_python"], nb,
                                 # fichier complet : résout les appels
                                 # entre fonctions du même fichier
                                 contexte_php=code)
    print(f"  statut   : {rapport['statut']}")
    if rapport.get("raison"):
        print(f"  raison   : {rapport['raison']}")
    print(f"  cas testés : {rapport['cas_testes']} | "
          f"équivalents : {rapport['cas_equivalents']}")
    if rapport.get("base_simulee"):
        print(f"  base simulée : tables "
              f"{rapport['base_simulee']['tables']}")
    if rapport.get("requetes_php"):
        print(f"  1re requête PHP : {rapport['requetes_php'][0][:70]}")
    for d in rapport.get("divergences", [])[:2]:
        print(f"    divergence [{d.get('type')}] "
              f"entrée={str(d.get('entree'))[:40]!r}")

print("\nSi un module affiche « statut : teste », le Comparateur "
      "fonctionne sur ce module.")