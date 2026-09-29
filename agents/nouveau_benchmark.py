"""
Benchmark et étude d'ablation — SMAML
======================================
Lance la migration des projets du corpus dans plusieurs configurations,
collecte les métriques et produit un tableau comparatif.

    py -X utf8 benchmark.py                          toutes les configurations
    py -X utf8 benchmark.py --config llm_seul rag    seulement celles-ci
    py -X utf8 benchmark.py --repetitions 3          moyenne sur 3 passages
    py -X utf8 benchmark.py --projets p1 p3          seulement ces projets
    py -X utf8 benchmark.py --estimer                un seul module, pour
                                                     mesurer la consommation

Chaque migration tourne dans un PROCESSUS SÉPARÉ, avec ses propres
variables d'environnement. C'est ce qui garantit que la configuration
est bien celle annoncée : les interrupteurs sont lus au démarrage du
pipeline, pas après. Un plantage ou un quota épuisé n'emporte alors que
la mesure en cours, pas toute la série.

Le cache est DÉSACTIVÉ pendant les mesures : un résultat relu fausserait
les temps et le nombre d'appels au LLM.
"""

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime

from configuration import CONFIGURATIONS

DOSSIER = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(DOSSIER, "corpus_benchmark")
RESULTATS = os.path.join(DOSSIER, "resultats_benchmark")


# ─── Corpus ──────────────────────────────────────────

def lister_projets(filtres=None) -> list:
    """Les projets du corpus : un dossier = un projet."""
    if not os.path.isdir(CORPUS):
        raise SystemExit(f"Corpus introuvable : {CORPUS}")
    projets = []
    for nom in sorted(os.listdir(CORPUS)):
        chemin = os.path.join(CORPUS, nom)
        if not os.path.isdir(chemin):
            continue
        if filtres and not any(f in nom for f in filtres):
            continue
        fichiers = [os.path.join(r, f)
                    for r, _, noms in os.walk(chemin)
                    for f in noms if f.lower().endswith(".php")]
        if fichiers:
            projets.append({"nom": nom, "chemin": chemin,
                            "fichiers": len(fichiers)})
    if not projets:
        raise SystemExit("Aucun projet PHP trouvé dans le corpus.")
    return projets


def archiver(projet: dict, dossier: str) -> str:
    """Crée le .zip attendu par le pipeline."""
    chemin_zip = os.path.join(dossier, f"{projet['nom']}.zip")
    with zipfile.ZipFile(chemin_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for racine, _, noms in os.walk(projet["chemin"]):
            for nom in noms:
                if nom.lower().endswith(".php"):
                    complet = os.path.join(racine, nom)
                    archive.write(complet, os.path.relpath(
                        complet, os.path.dirname(projet["chemin"])))
    return chemin_zip


# ─── Exécution d'une migration ───────────────────────

def executer(projet: dict, config: str, sortie: str,
             chemin_zip: str, duree_max: int) -> dict:
    """Lance UNE migration dans un processus séparé."""
    environnement = dict(os.environ)
    environnement.update({
        "SMAML_CONFIG": config,
        "SMAML_CACHE": "0",        # jamais de cache pendant une mesure
        "SMAML_STRICT": "1",       # une panne du LLM ne doit pas passer
        "SMAML_BASCULE": "0",      # un seul modèle, résultats comparables
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    })

    debut = time.time()
    journal = os.path.join(sortie, "journal.txt")
    with open(journal, "w", encoding="utf-8") as f:
        try:
            processus = subprocess.run(
                [sys.executable, "-X", "utf8",
                 os.path.join(DOSSIER, "pipeline_complet.py"),
                 chemin_zip, sortie],
                stdout=f, stderr=subprocess.STDOUT, env=environnement,
                timeout=duree_max, cwd=DOSSIER)
            code_retour = processus.returncode
            interrompu = False
        except subprocess.TimeoutExpired:
            code_retour, interrompu = -1, True
    duree = time.time() - debut

    chemin_rapport = os.path.join(sortie, "rapport_migration.json")
    rapport = None
    if os.path.exists(chemin_rapport):
        with open(chemin_rapport, encoding="utf-8") as f:
            rapport = json.load(f)

    return {"duree_s": round(duree, 1), "code_retour": code_retour,
            "interrompu": interrompu, "rapport": rapport,
            "journal": journal}


# ─── Métriques ───────────────────────────────────────

def mesurer(rapport: dict) -> dict:
    """
    Extrait les métriques d'un rapport de migration.
    Ce sont celles attendues au chapitre expérimental : génération,
    livraison, corrections, sécurité, équivalence, cas non testables.
    """
    modules = [m for f in (rapport or {}).get("fichiers_migres", [])
               for m in f.get("modules", [])]
    if not modules:
        return {"modules": 0}

    def critere(module, nom):
        # Le détail des critères vient soit du champ direct
        # (mode direct), soit de l'état structuré (mode orchestré).
        criteres = ((module.get("confiance") or {}).get("criteres")
                    or (((module.get("etat_structure") or {})
                         .get("derniere_decision") or {})
                        .get("confiance") or {}).get("criteres") or [])
        for c in criteres:
            if c["nom"] == nom and c.get("mesure"):
                return c["score"]
        return None

    livres = [m for m in modules if m.get("decision_finale") == "LIVRER"]
    scores = [m.get("score_final") or 0 for m in modules]
    corrections = [(m.get("iterations") or 1) - 1 for m in modules]

    equivalences = [m.get("equivalence") or {} for m in modules]
    testables = [e for e in equivalences if e.get("statut") == "teste"]
    non_testables = len(equivalences) - len(testables)
    injections = sum(len(e.get("injections_bloquees") or [])
                     for e in equivalences)
    divergences = sum(len(e.get("divergences") or []) for e in testables)

    proprietes = [p for m in modules
                  for p in ((m.get("verification_formelle") or {})
                            .get("proprietes") or [])]

    def moyenne(valeurs):
        valeurs = [v for v in valeurs if v is not None]
        return round(statistics.mean(valeurs), 1) if valeurs else None

    scores_modernisation = [(m.get("modernisation") or {}).get("score")
                            for m in modules]

    return {
        "modules": len(modules),
        "taux_livraison": round(100 * len(livres) / len(modules), 1),
        "modernisation": moyenne(scores_modernisation),
        "score_confiance_moyen": moyenne(scores),
        "critere_fonctionnel": moyenne([critere(m, "fonctionnel") for m in modules]),
        "critere_securite": moyenne([critere(m, "securite") for m in modules]),
        "critere_comportemental": moyenne([critere(m, "comportemental") for m in modules]),
        "critere_proprietes": moyenne([critere(m, "proprietes") for m in modules]),
        "corrections_moyennes": round(statistics.mean(corrections), 2),
        "modules_sans_correction": sum(1 for c in corrections if c == 0),
        "equivalence_moyenne": moyenne([
            (e.get("score_equivalence") or 0) * 100 for e in testables]),
        "cas_non_testables": non_testables,
        "injections_neutralisees": injections,
        "divergences": divergences,
        "proprietes_prouvees": sum(1 for p in proprietes
                                   if p.get("statut") == "prouvee"),
        "proprietes_refutees": sum(1 for p in proprietes
                                   if p.get("statut") == "refutee"),
        "escalades_humaines": sum(
            1 for m in modules
            if m.get("decision_finale") == "ESCALADE_HUMAINE"),
        "categories_echec": {
            categorie: sum(1 for m in modules
                           if m.get("categorie_echec") == categorie)
            for categorie in ("bug_simple", "ambiguite", "limite_structurelle")
        },
    }


def agreger(mesures: list) -> dict:
    """Moyenne des mesures d'une configuration, tous projets confondus."""
    valides = [m for m in mesures if m.get("modules")]
    if not valides:
        return {"modules": 0, "migrations_reussies": 0}
    agrege = {"migrations_reussies": len(valides),
              "migrations_totales": len(mesures)}
    # Union des clés de TOUS les projets : se fier au premier ferait
    # disparaître une métrique absente de ce seul projet.
    numeriques = sorted({c for mesure in valides for c, v in mesure.items()
                         if isinstance(v, (int, float))})
    for cle in numeriques:
        valeurs = [m[cle] for m in valides if m.get(cle) is not None]
        if valeurs:
            agrege[cle] = round(statistics.mean(valeurs), 1)
    return agrege


# ─── Affichage ───────────────────────────────────────

LIGNES_TABLEAU = [
    ("taux_livraison", "Taux de livraison (%)"),
    ("score_confiance_moyen", "Score de confiance (%)"),
    ("modernisation", "Modernisation (%)"),
    ("critere_fonctionnel", "  dont fonctionnel"),
    ("critere_securite", "  dont sécurité"),
    ("critere_comportemental", "  dont comportemental"),
    ("critere_proprietes", "  dont propriétés"),
    ("corrections_moyennes", "Corrections par module"),
    ("equivalence_moyenne", "Équivalence (%)"),
    ("cas_non_testables", "Cas non testables"),
    ("injections_neutralisees", "Injections neutralisées"),
    ("proprietes_prouvees", "Propriétés prouvées"),
    ("proprietes_refutees", "Propriétés réfutées"),
    ("escalades_humaines", "Escalades humaines"),
    ("duree_s", "Durée moyenne (s)"),
]


def afficher_tableau(resultats: dict):
    configs = list(resultats)
    largeur = max(26, *(len(c) + 2 for c in configs))
    print("\n" + "=" * (30 + largeur * len(configs)))
    print("COMPARAISON DES CONFIGURATIONS")
    print("=" * (30 + largeur * len(configs)))
    entete = f"{'Métrique':<30}" + "".join(f"{c:<{largeur}}" for c in configs)
    print(entete)
    print("-" * len(entete))
    for cle, libelle in LIGNES_TABLEAU:
        ligne = f"{libelle:<30}"
        for config in configs:
            valeur = resultats[config]["agrege"].get(cle)
            ligne += f"{('—' if valeur is None else valeur):<{largeur}}"
        print(ligne)
    print()


# ─── Programme principal ─────────────────────────────

def main():
    analyseur = argparse.ArgumentParser(description="Benchmark SMAML")
    analyseur.add_argument("--config", nargs="+", default=list(CONFIGURATIONS),
                           choices=list(CONFIGURATIONS))
    analyseur.add_argument("--projets", nargs="+", default=None,
                           help="filtres sur les noms de projets")
    analyseur.add_argument("--repetitions", type=int, default=1,
                           help="passages par configuration (LLM non "
                                "déterministe : 3 recommandés)")
    analyseur.add_argument("--duree-max", type=int, default=3600,
                           help="secondes avant d'abandonner une migration")
    analyseur.add_argument("--estimer", action="store_true",
                           help="un seul projet, une seule configuration, "
                                "pour mesurer la consommation")
    args = analyseur.parse_args()

    projets = lister_projets(args.projets)
    configs = args.config[:1] if args.estimer else args.config
    if args.estimer:
        projets = projets[:1]

    horodatage = datetime.now().strftime("%Y%m%d_%H%M")
    dossier_serie = os.path.join(RESULTATS, horodatage)
    os.makedirs(dossier_serie, exist_ok=True)

    print("=" * 60)
    print("BENCHMARK SMAML")
    print("=" * 60)
    print(f"  Projets       : {', '.join(p['nom'] for p in projets)}")
    print(f"  Configurations: {', '.join(configs)}")
    print(f"  Répétitions   : {args.repetitions}")
    print(f"  Résultats     : {dossier_serie}")
    print("  Cache désactivé, mode strict, aucun basculement de modèle.\n")

    resultats = {}
    dossier_zips = tempfile.mkdtemp(prefix="smaml_bench_")
    try:
        archives = {p["nom"]: archiver(p, dossier_zips) for p in projets}

        for config in configs:
            print(f"\n{'━' * 60}\n  CONFIGURATION : {config} — "
                  f"{CONFIGURATIONS[config]['titre']}\n{'━' * 60}")
            mesures, details = [], []
            for repetition in range(1, args.repetitions + 1):
                for projet in projets:
                    etiquette = (f"{projet['nom']} "
                                 f"(passage {repetition}/{args.repetitions})")
                    print(f"  ▶ {etiquette}…", end=" ", flush=True)
                    sortie = os.path.join(
                        dossier_serie, config,
                        f"{projet['nom']}_p{repetition}")
                    os.makedirs(sortie, exist_ok=True)

                    execution = executer(projet, config, sortie,
                                         archives[projet["nom"]],
                                         args.duree_max)
                    mesure = mesurer(execution["rapport"])
                    mesure["duree_s"] = execution["duree_s"]
                    mesures.append(mesure)
                    details.append({"projet": projet["nom"],
                                    "passage": repetition,
                                    "duree_s": execution["duree_s"],
                                    "interrompu": execution["interrompu"],
                                    "code_retour": execution["code_retour"],
                                    "mesures": mesure})

                    if execution["interrompu"]:
                        print(f"interrompu après {args.duree_max}s")
                    elif not mesure.get("modules"):
                        print(f"échec (voir {execution['journal']})")
                    else:
                        print(f"{mesure['modules']} module(s), "
                              f"{mesure['taux_livraison']}% livrés, "
                              f"score {mesure['score_confiance_moyen']}%, "
                              f"{execution['duree_s']}s")

            resultats[config] = {"agrege": agreger(mesures),
                                 "details": details}
            resultats[config]["agrege"]["duree_s"] = round(statistics.mean(
                [d["duree_s"] for d in details]), 1)
    finally:
        shutil.rmtree(dossier_zips, ignore_errors=True)

    chemin = os.path.join(dossier_serie, "benchmark.json")
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump({"horodatage": horodatage,
                   "projets": projets, "repetitions": args.repetitions,
                   "resultats": resultats}, f, indent=2, ensure_ascii=False)

    afficher_tableau(resultats)
    print(f"Résultats détaillés : {chemin}")
    if args.repetitions < 3 and not args.estimer:
        print("Note : avec moins de 3 passages, les écarts entre "
              "configurations peuvent venir du hasard (le LLM n'est pas "
              "déterministe).")


if __name__ == "__main__":
    main()