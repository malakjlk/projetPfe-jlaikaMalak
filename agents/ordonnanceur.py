"""
Ordonnanceur de campagnes — SMAML
==================================
Plusieurs projets à migrer : dans quel ordre, et combien à la fois ?

    py -X utf8 ordonnanceur.py projet1.zip projet2 projet3.zip --travailleurs 2 --sortie campagne
    py -X utf8 ordonnanceur.py … --refaire        refait aussi les projets déjà terminés

1. FILE DE PRIORITÉ — avant toute migration, chaque projet est analysé
   (sans LLM) et classé :
      d'abord le nombre de failles CRITIQUES (le plus urgent à corriger),
      puis le nombre total de failles,
      puis la TAILLE, du plus petit au plus grand (livrer vite ce qui
      peut l'être).
2. TRAVAILLEURS EN PARALLÈLE — chaque projet est migré dans son PROPRE
   PROCESSUS : un projet qui plante n'arrête pas les autres.
3. DÉBIT PARTAGÉ — tous les processus passent par le même limiteur
   (limiteur.py) : ensemble, ils respectent le quota des fournisseurs.
4. REPRISE — un projet déjà terminé n'est pas refait ; un projet
   interrompu reprend où il s'était arrêté (espace partagé persistant).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

ICI = os.path.dirname(os.path.abspath(__file__))


def identifiant(chemin: str) -> str:
    """Identifiant stable d'un projet : la même entrée reprend le même projet."""
    nom = os.path.splitext(os.path.basename(os.path.normpath(chemin)))[0]
    empreinte = hashlib.sha256(os.path.abspath(chemin).encode()).hexdigest()[:8]
    return f"{nom}-{empreinte}"


def evaluer_priorite(chemin: str) -> dict:
    """Analyse rapide, sans LLM : langage, failles, taille."""
    from langages import adaptateur, detecter_langages
    dossier = chemin
    if os.path.isfile(chemin) and chemin.lower().endswith(".zip"):
        dossier = tempfile.mkdtemp(prefix="smaml_priorite_")
        with zipfile.ZipFile(chemin) as archive:
            archive.extractall(dossier)
    if not os.path.isdir(dossier):
        return {"langage": None, "critiques": 0, "failles": 0, "taille": 0,
                "erreur": "entrée introuvable"}
    langage = detecter_langages(dossier)["principal"]
    if not langage:
        return {"langage": None, "critiques": 0, "failles": 0, "taille": 0}
    outil = adaptateur(langage)
    critiques = failles = taille = 0
    for source in outil.lister_sources(dossier):
        try:
            rapport = outil.analyser(open(source, encoding="utf-8", errors="ignore").read())
        except Exception:
            continue
        taille += len(rapport.get("fonctions", [])) + len(rapport.get("classes", []))
        for faille in rapport.get("failles_potentielles", []):
            failles += 1
            critiques += str(faille.get("severity", "")).lower() == "critical"
    return {"langage": langage, "critiques": critiques, "failles": failles, "taille": taille}


def cle_priorite(p: dict) -> tuple:
    """Plus de failles critiques d'abord, puis plus de failles, puis plus petit."""
    return (p.get("langage") is None, -p["critiques"], -p["failles"], p["taille"])


def migrer_projet(chemin: str, sortie: str, projet: str, env: dict) -> dict:
    """Migre UN projet dans son propre processus, et rend son bilan."""
    os.makedirs(sortie, exist_ok=True)
    debut = time.time()
    commande = ("import orchestration; orchestration.principal("
                f"[{os.path.abspath(chemin)!r}, {os.path.abspath(sortie)!r}])")
    # Lancé depuis le dossier de sortie, avec agents/ dans le chemin de
    # recherche : un module de même nom placé avant (en test, le
    # Développeur simulé) garde ainsi la priorité.
    env = dict(env, SMAML_PROJET_ID=projet)
    chemins = [c for c in env.get("PYTHONPATH", "").split(os.pathsep) if c]
    if ICI not in chemins:
        env["PYTHONPATH"] = os.pathsep.join(chemins + [ICI])
    with open(os.path.join(sortie, "journal.txt"), "w", encoding="utf-8") as journal:
        execution = subprocess.run([sys.executable, "-X", "utf8", "-c", commande],
                                   cwd=sortie, env=env, stdout=journal,
                                   stderr=subprocess.STDOUT)
    bilan = {"projet": projet, "source": chemin, "sortie": sortie,
             "debut": round(debut, 2), "fin": round(time.time(), 2),
             "duree_s": round(time.time() - debut, 1), "code_retour": execution.returncode}
    chemin_rapport = os.path.join(sortie, "rapport_migration.json")
    if execution.returncode == 0 and os.path.exists(chemin_rapport):
        stats = json.load(open(chemin_rapport, encoding="utf-8")).get("statistiques", {})
        bilan.update({"statut": "termine", "modules": stats.get("modules"),
                      "modules_livres": stats.get("modules_livres")})
    else:
        bilan.update({"statut": "echec",
                      "raison": f"le processus s'est arrêté (code {execution.returncode}) : "
                                f"voir {os.path.join(sortie, 'journal.txt')}"})
    return bilan


def campagne(chemins: list, dossier_sortie: str, travailleurs: int = 2,
             refaire: bool = False, env: dict = None) -> dict:
    env = dict(env or os.environ)
    os.makedirs(dossier_sortie, exist_ok=True)

    # 1. File de priorité
    projets = []
    for chemin in chemins:
        projets.append({"chemin": chemin, "projet": identifiant(chemin),
                        "priorite": evaluer_priorite(chemin)})
    projets.sort(key=lambda p: cle_priorite(p["priorite"]))
    print(f"Campagne : {len(projets)} projet(s), {travailleurs} travailleur(s)\n")
    print("Ordre de passage :")
    for rang, p in enumerate(projets, 1):
        pr = p["priorite"]
        print(f"  {rang}. {os.path.basename(os.path.normpath(p['chemin'])):<28} "
              f"{pr['critiques']} faille(s) critique(s), {pr['failles']} au total, "
              f"taille {pr['taille']}" + ("" if pr["langage"] else "  — langage non pris en charge"))

    # 2. Travailleurs en parallèle ; 4. reprise des projets déjà terminés
    def traiter(p):
        sortie = os.path.join(dossier_sortie, p["projet"])
        rapport = os.path.join(sortie, "rapport_migration.json")
        if not refaire and os.path.exists(rapport):
            return {"projet": p["projet"], "source": p["chemin"], "sortie": sortie,
                    "statut": "deja_termine"}
        if p["priorite"].get("erreur") or not p["priorite"]["langage"]:
            return {"projet": p["projet"], "source": p["chemin"], "statut": "ignore",
                    "raison": p["priorite"].get("erreur", "langage non pris en charge")}
        # Reprise ou départ à zéro : c'est LE DOSSIER DU RUN qui décide.
        # L'identifiant est écrit dans le dossier au démarrage. Dossier
        # présent (run interrompu) : on reprend avec cet identifiant. Dossier
        # absent (jamais lancé, supprimé, ou --refaire) : identifiant NEUF.
        # L'espace partagé (Redis) survit à la suppression d'un dossier :
        # sans cette règle, supprimer passage1 et relancer reprenait l'état
        # de l'ancien passage1 au lieu de regénérer.
        if refaire:
            shutil.rmtree(sortie, ignore_errors=True)
        fichier_id = os.path.join(sortie, "projet_id.txt")
        if os.path.exists(fichier_id):
            projet_id = open(fichier_id, encoding="utf-8").read().strip()
        else:
            projet_id = f"{p['projet']}-{time.strftime('%Y%m%d%H%M%S')}-{os.getpid()}"
            os.makedirs(sortie, exist_ok=True)
            with open(fichier_id, "w", encoding="utf-8") as f:
                f.write(projet_id)
        return migrer_projet(p["chemin"], sortie, projet_id, env)

    # Les projets sont soumis dans l'ordre de priorité : le premier
    # travailleur libre prend toujours le plus prioritaire restant.
    with ThreadPoolExecutor(max_workers=max(1, travailleurs)) as pool:
        bilans = list(pool.map(traiter, projets))
    for p, b in zip(projets, bilans):
        b["priorite"] = p["priorite"]

    resultat = {"travailleurs": travailleurs, "projets": bilans,
                "termines": sum(b["statut"] in ("termine", "deja_termine") for b in bilans),
                "echecs": sum(b["statut"] == "echec" for b in bilans)}
    with open(os.path.join(dossier_sortie, "campagne.json"), "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, indent=2)

    print("\nBilan :")
    for b in bilans:
        detail = (f"{b.get('modules_livres')}/{b.get('modules')} module(s) livré(s), {b['duree_s']} s"
                  if b["statut"] == "termine" else b.get("raison", ""))
        print(f"  {b['statut']:<13} {os.path.basename(os.path.normpath(b['source'])):<28} {detail}")
    print(f"\n{resultat['termines']}/{len(bilans)} projet(s) terminé(s), "
          f"{resultat['echecs']} échec(s). Détail : {dossier_sortie}/campagne.json")
    return resultat


if __name__ == "__main__":
    analyseur = argparse.ArgumentParser(description="Campagne de migration multi-projets")
    analyseur.add_argument("projets", nargs="+")
    analyseur.add_argument("--travailleurs", type=int, default=2)
    analyseur.add_argument("--sortie", default="campagne")
    analyseur.add_argument("--refaire", action="store_true")
    a = analyseur.parse_args()
    campagne(a.projets, a.sortie, a.travailleurs, a.refaire)