"""
Benchmark SMAML — Évaluation quantitative du pipeline
======================================================
Lance la migration sur TOUT le corpus de test et produit :
  - benchmark_resultats/<config>/resultats_projets.csv  (1 ligne/projet)
  - benchmark_resultats/<config>/resultats_modules.csv  (1 ligne/module)
  - benchmark_resultats/<config>/resume.json
  - un tableau récapitulatif dans la console (à coller au rapport)

Usage :
    python benchmark.py                      # configuration complète
    python benchmark.py --config sans_boucle # ablation : 1 seule itération
    python benchmark.py --config sans_rag    # ablation : RAG désactivé
    python benchmark.py --config sans_patrons# ablation : patrons désactivés
    python benchmark.py --corpus corpus_benchmark --config complet

Étude d'ablation = lancer les 4 configurations puis comparer les
CSV : la différence de score mesure la CONTRIBUTION de chaque
composant (RAG, boucle corrective, patrons de prompt).

NOTE ablation RAG/patrons : ces deux configurations reposent sur
les variables d'environnement SMAML_SANS_RAG / SMAML_SANS_PATRONS,
qui doivent être lues dans agent_developpeur.py (voir README des
modifications). La config 'sans_boucle' fonctionne sans aucune
modification (max_iterations=1).
"""

import argparse
import csv
import json
import os
import statistics
import sys
import time

CONFIGS = {
    "complet": {
        "description": "Pipeline complet (RAG + boucle corrective + patrons)",
        "max_iterations": 5,
        "env": {},
    },
    "sans_boucle": {
        "description": "Ablation : boucle corrective désactivée (1 itération)",
        "max_iterations": 1,
        "env": {},
    },
    "sans_rag": {
        "description": "Ablation : récupération RAG désactivée",
        "max_iterations": 5,
        "env": {"SMAML_SANS_RAG": "1"},
    },
    "sans_patrons": {
        "description": "Ablation : patrons de correction/validation désactivés",
        "max_iterations": 5,
        "env": {"SMAML_SANS_PATRONS": "1"},
    },
}


def lister_projets(dossier_corpus: str) -> list:
    """Chaque sous-dossier du corpus = un projet à migrer."""
    projets = []
    for nom in sorted(os.listdir(dossier_corpus)):
        chemin = os.path.join(dossier_corpus, nom)
        if os.path.isdir(chemin):
            projets.append((nom, chemin))
    return projets


def extraire_metriques_projet(nom: str, rapport: dict,
                              duree: float) -> tuple:
    """
    Transforme le rapport_migration d'UN projet en :
      - une ligne projet (agrégats)
      - des lignes module (détail)
    """
    lignes_modules = []
    scores, iterations = [], []
    equivalences = []
    prouvees = refutees = 0
    modules_livres = modules_total = 0

    for fichier in rapport.get("fichiers_migres", []):
        for m in fichier.get("modules", []):
            modules_total += 1
            if m.get("decision_finale") == "LIVRER":
                modules_livres += 1
            scores.append(m.get("score_final", 0.0))
            iterations.append(m.get("iterations", 0))

            eq = m.get("equivalence") or {}
            eq_score = ""
            if eq.get("statut") == "teste":
                eq_score = round(eq.get("score_equivalence", 0.0) * 100, 1)
                equivalences.append(eq.get("score_equivalence", 0.0) * 100)

            vf = m.get("verification_formelle") or {}
            vf_prouvees = vf_refutees = 0
            for prop in vf.get("proprietes", []):
                if prop.get("statut") == "prouvee":
                    vf_prouvees += 1
                    prouvees += 1
                elif prop.get("statut") == "refutee":
                    vf_refutees += 1
                    refutees += 1

            lignes_modules.append({
                "projet": nom,
                "fichier": fichier.get("cible", ""),
                "module": m.get("nom_python", ""),
                "decision": m.get("decision_finale", ""),
                "score_final": round(m.get("score_final", 0.0), 1),
                "iterations": m.get("iterations", 0),
                "equivalence_pct": eq_score,
                "proprietes_prouvees": vf_prouvees,
                "proprietes_refutees": vf_refutees,
            })

    stats = rapport.get("statistiques", {})
    coherent = rapport.get("coherence_projet", {}).get("coherent", "")
    ligne_projet = {
        "projet": nom,
        "fichiers_total": stats.get("total_fichiers", 0),
        "fichiers_livres": stats.get("fichiers_livres", 0),
        "modules_total": modules_total,
        "modules_livres": modules_livres,
        "score_moyen": round(statistics.mean(scores), 1) if scores else 0,
        "iterations_moyennes": round(statistics.mean(iterations), 2)
        if iterations else 0,
        "iterations_totales": sum(iterations),
        "equivalence_moyenne_pct": round(statistics.mean(equivalences), 1)
        if equivalences else "",
        "proprietes_prouvees": prouvees,
        "proprietes_refutees": refutees,
        "corrections_projet": len(rapport.get("corrections_projet", [])),
        "projet_coherent": coherent,
        "duree_s": round(duree, 1),
    }
    return ligne_projet, lignes_modules


def afficher_tableau(lignes: list):
    """Tableau récapitulatif console (copiable dans le rapport)."""
    colonnes = ["projet", "modules_livres", "modules_total", "score_moyen",
                "iterations_moyennes", "equivalence_moyenne_pct",
                "proprietes_prouvees", "proprietes_refutees",
                "corrections_projet", "duree_s"]
    entetes = ["Projet", "Livrés", "Total", "Score", "Itér.",
               "Équiv.%", "Prouvées", "Réfutées", "Corr.proj", "Durée(s)"]
    largeurs = [max(len(e), 8) for e in entetes]
    largeurs[0] = max(len(str(l["projet"])) for l in lignes + [{"projet": "Projet"}])

    def fmt(valeurs):
        return "  ".join(str(v).ljust(w) for v, w in zip(valeurs, largeurs))

    print("\n" + fmt(entetes))
    print("-" * (sum(largeurs) + 2 * len(largeurs)))
    for l in lignes:
        print(fmt([l.get(c, "") for c in colonnes]))


def main():
    parser = argparse.ArgumentParser(description="Benchmark SMAML")
    parser.add_argument("--corpus", default="corpus_benchmark",
                        help="Dossier contenant les projets de test")
    parser.add_argument("--config", default="complet",
                        choices=list(CONFIGS.keys()),
                        help="Configuration (complet ou ablation)")
    args = parser.parse_args()

    config = CONFIGS[args.config]
    # Mode STRICT : interdit le basculement silencieux sur le code de
    # secours. Un run où le LLM a été remplacé par un fallback ne mesure
    # plus le système : il doit être interrompu, pas publié.
    os.environ["SMAML_STRICT"] = "1"
    # Variables d'ablation AVANT l'import du pipeline (le Développeur
    # charge la base RAG au moment de l'import)
    for cle, valeur in config["env"].items():
        os.environ[cle] = valeur

    from pipeline_complet import migrer_projet   # import tardif volontaire

    projets = lister_projets(args.corpus)
    if not projets:
        print(f"Aucun projet trouvé dans {args.corpus}/")
        sys.exit(1)

    print("=" * 60)
    print(f"BENCHMARK SMAML — configuration : {args.config}")
    print(f"  {config['description']}")
    print(f"  {len(projets)} projet(s) dans {args.corpus}/")
    print("=" * 60)

    dossier_resultats = os.path.join("benchmark_resultats", args.config)
    os.makedirs(dossier_resultats, exist_ok=True)

    lignes_projets, lignes_modules = [], []
    for nom, chemin in projets:
        print(f"\n{'#' * 60}\n#  PROJET : {nom}\n{'#' * 60}")
        sortie = os.path.join(dossier_resultats, "sorties", nom)
        debut = time.time()
        try:
            rapport = migrer_projet(
                chemin, dossier_sortie=sortie,
                max_iterations=config["max_iterations"]
            )
        except Exception as e:
            if "MODE STRICT" in str(e):
                print(f"\n{'!' * 60}")
                print("  BENCHMARK INTERROMPU — LLM indisponible")
                print(f"  {str(e)[:200]}")
                print("  Aucun résultat partiel n'est enregistré : une")
                print("  configuration incomplète n'est pas comparable.")
                print(f"{'!' * 60}")
                sys.exit(2)
            print(f"  ❌ ÉCHEC du projet {nom} : {e}")
            lignes_projets.append({"projet": nom, "erreur": str(e)[:200]})
            continue
        duree = time.time() - debut
        ligne, modules = extraire_metriques_projet(nom, rapport, duree)
        lignes_projets.append(ligne)
        lignes_modules.extend(modules)

    # ── Sauvegarde CSV + JSON ──
    champs_projet = ["projet", "fichiers_total", "fichiers_livres",
                     "modules_total", "modules_livres", "score_moyen",
                     "iterations_moyennes", "iterations_totales",
                     "equivalence_moyenne_pct", "proprietes_prouvees",
                     "proprietes_refutees", "corrections_projet",
                     "projet_coherent", "duree_s", "erreur"]
    with open(os.path.join(dossier_resultats, "resultats_projets.csv"),
              "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=champs_projet)
        w.writeheader()
        w.writerows(lignes_projets)

    if lignes_modules:
        with open(os.path.join(dossier_resultats, "resultats_modules.csv"),
                  "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(lignes_modules[0].keys()))
            w.writeheader()
            w.writerows(lignes_modules)

    # ── Résumé global de la configuration ──
    valides = [l for l in lignes_projets if "erreur" not in l]
    resume = {
        "configuration": args.config,
        "description": config["description"],
        "projets_testes": len(lignes_projets),
        "projets_reussis": len(valides),
        "score_moyen_global": round(statistics.mean(
            [l["score_moyen"] for l in valides]), 1) if valides else 0,
        "iterations_moyennes_globales": round(statistics.mean(
            [l["iterations_moyennes"] for l in valides]), 2)
        if valides else 0,
        "total_proprietes_prouvees": sum(
            l["proprietes_prouvees"] for l in valides),
        "total_proprietes_refutees": sum(
            l["proprietes_refutees"] for l in valides),
        "total_corrections_projet": sum(
            l["corrections_projet"] for l in valides),
        "duree_totale_s": round(sum(l["duree_s"] for l in valides), 1),
    }
    with open(os.path.join(dossier_resultats, "resume.json"),
              "w", encoding="utf-8") as f:
        json.dump(resume, f, indent=2, ensure_ascii=False)

    afficher_tableau(valides)
    print(f"\nRésumé ({args.config}) :")
    for cle, valeur in resume.items():
        print(f"  {cle} : {valeur}")
    print(f"\nRésultats détaillés dans {dossier_resultats}/")


if __name__ == "__main__":
    main()