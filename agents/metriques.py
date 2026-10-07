"""
Métriques d'évaluation — SMAML
===============================
Calcule, à partir des rapports de migration, des métriques comparables
à celles de la littérature sur la traduction de code par LLM.

    py -X utf8 metriques.py sortie1 [sortie2 …] [--json metriques.json]
    py -X utf8 metriques.py --codebleu dossier_candidats dossier_references

Plusieurs dossiers de sortie d'un MÊME projet (passages répétés) donnent
plusieurs échantillons par module : c'est ce qui permet pass@k.

Quatre familles
---------------
FONCTIONNELLES
  taux de syntaxe valide    le code produit s'analyse sans erreur
  taux d'exécution          le code a réellement tourné sur des entrées
                            (parmi les modules où l'exécution était possible)
  computational accuracy    même sortie que le PHP — l'équivalence
                            comportementale, sous son nom standard
                            (Roziere et al., TransCoder, 2020)
  pass@1 / pass@k           correct dès la première génération, sans
                            correction (estimateur sans biais, Chen et al., 2021)
  score de mutation         bugs injectés détectés, par source d'entrées
SÉCURITÉ
  failles corrigées, failles persistantes, gardes préservées, injections
  bloquées, propriétés prouvées et réfutées
PAR LLM
  Développeur (par modèle), Manager, juge, générateur d'entrées
COÛT
  tokens et temps, par module et au total
"""

from __future__ import annotations

import ast
import json
import os
import sys
from math import comb


# ═══ LECTURE DES RAPPORTS ══════════════════════════════

def charger(chemins: list) -> list:
    """
    Accepte des rapports, des dossiers de sortie, ou un dossier de
    CAMPAGNE : ses sous-dossiers contenant un rapport sont tous lus.
    """
    fichiers = []
    for chemin in chemins:
        direct = os.path.join(chemin, "rapport_migration.json")
        if os.path.isfile(chemin):
            fichiers.append(chemin)
        elif os.path.isfile(direct):
            fichiers.append(direct)
        elif not os.path.exists(chemin):
            print(f"[ATTENTION] {chemin} n'existe pas : ignoré", file=sys.stderr)
        elif os.path.isdir(chemin):                        # dossier de campagne
            fichiers += sorted(os.path.join(chemin, d, "rapport_migration.json")
                               for d in os.listdir(chemin)
                               if os.path.isfile(os.path.join(chemin, d, "rapport_migration.json")))
    rapports = []
    for fichier in fichiers:
        with open(fichier, encoding="utf-8") as f:
            rapports.append(json.load(f))
    return rapports


def modules(rapport: dict):
    for fichier in rapport.get("fichiers_migres", []):
        for module in fichier.get("modules", []):
            yield fichier["source"], module


def _taux(numerateur: int, denominateur: int):
    return round(numerateur / denominateur, 3) if denominateur else None


def _moyenne(valeurs: list):
    valeurs = [v for v in valeurs if v is not None]
    return round(sum(valeurs) / len(valeurs), 3) if valeurs else None


# ═══ pass@k ═══════════════════════════════════════════

def pass_at_k(n: int, c: int, k: int) -> float:
    """
    Estimateur sans biais de pass@k (Chen et al., 2021) : probabilité qu'au
    moins une de k générations soit correcte, sachant c correctes sur n.
    """
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def correct_premier_jet(module: dict) -> bool:
    """Correct dès la première génération : livré sans aucune correction."""
    return module.get("decision_finale") == "LIVRER" and (module.get("iterations") or 1) == 1


# ═══ LES QUATRE FAMILLES ═══════════════════════════════

def fonctionnelles(rapports: list) -> dict:
    tous = [(src, m) for r in rapports for src, m in modules(r)]
    syntaxe = []
    for _, m in tous:
        try:
            ast.parse(m.get("code_python") or "")
            syntaxe.append(True)
        except SyntaxError:
            syntaxe.append(False)
    equivalences = [m.get("equivalence") or {} for _, m in tous]
    executes = [e for e in equivalences if e.get("statut") == "teste"]
    non_mesurables = [e for e in equivalences if e.get("statut") != "teste"]
    scores = [e.get("score_equivalence") for e in executes]

    # pass@k : les passages d'un même projet sont des échantillons du module
    echantillons = {}
    for src, m in tous:
        echantillons.setdefault(f"{src}::{m.get('nom_python')}", []).append(correct_premier_jet(m))
    n_min = min((len(v) for v in echantillons.values()), default=0)
    pass_k = {}
    for k in sorted({1, 3, 5} | {n_min}):
        if 1 <= k <= n_min:
            pass_k[f"pass@{k}"] = _moyenne([pass_at_k(len(v), sum(v), k)
                                            for v in echantillons.values()])

    # Pourquoi un module n'a pas été exécuté : à dire, pas à cacher.
    raisons = {}
    for e in non_mesurables:
        raison = e.get("raison") or e.get("statut") or "comparaison absente"
        raisons[raison[:170]] = raisons.get(raison[:170], 0) + 1

    # Mutation : les sources se comparent sur le MÊME ensemble de modules,
    # ceux où les trois ont été mesurées. Sinon la moyenne de l'IA (calculée
    # sans les modules où elle était indisponible) et celle de l'hybride ne
    # portent pas sur les mêmes modules, et l'hybride peut paraître moins bon.
    mutations = [(m.get("equivalence") or {}).get("mutation") or {} for _, m in tous]
    mesurees = [mu for mu in mutations if mu.get("statut") == "mesure"
                and all(source in mu.get("scores", {}) for source in ("fixes", "ia", "hybride"))]
    return {
        "modules": len(tous),
        "echantillons_par_module": n_min,
        "taux_syntaxe_valide": _taux(sum(syntaxe), len(syntaxe)),
        # Part des modules dont le code a RÉELLEMENT tourné sur des entrées.
        "taux_execution": _taux(len(executes), len(tous)),
        "modules_executes": len(executes),
        "modules_non_mesurables": len(non_mesurables),
        "non_mesurables_par_raison": raisons,
        "computational_accuracy": _moyenne(scores),
        "taux_equivalence_totale": _taux(sum(1 for s in scores if s == 1.0), len(scores)),
        **pass_k,
        "taux_livraison": _taux(sum(m.get("decision_finale") == "LIVRER" for _, m in tous), len(tous)),
        "iterations_moyennes": _moyenne([m.get("iterations") for _, m in tous]),
        "mutation": {**{source: _moyenne([mu["scores"][source]["score"] for mu in mesurees])
                        for source in ("fixes", "ia", "hybride")},
                     "modules_compares": len(mesurees)} if mesurees else None,
        "lectures_equivalence": [e.get("lecture") for e in executes if e.get("lecture")],
    }


def securite(rapports: list) -> dict:
    corrigees = persistantes = gardes_ok = gardes_total = injections = 0
    prouvees = refutees = durcissements = 0
    detail_persistantes = []
    for r in rapports:
        for source, m in modules(r):
            rt = m.get("rapport_testeur") or {}
            failles = rt.get("failles") or {}
            corrigees += len(failles.get("failles_corrigees", []))
            persistantes += len(failles.get("failles_persistantes", []))
            for faille in failles.get("failles_persistantes", []):
                # Une faille persistante dans un module LIVRÉ est le cas grave.
                detail_persistantes.append({
                    "fichier": source, "module": m.get("nom_python"),
                    "decision": m.get("decision_finale"),
                    "faille": (faille.get("type") or faille.get("cwe") or str(faille))[:60]
                    if isinstance(faille, dict) else str(faille)[:60]})
            invariants = rt.get("invariants") or {}
            gardes_ok += len(invariants.get("invariants_verifies", []))
            gardes_total += len(invariants.get("invariants_verifies", [])) + \
                len(invariants.get("invariants_manquants", []))
            equivalence = m.get("equivalence") or {}
            injections += len(equivalence.get("injections_bloquees", []))
            durcissements += sum(d.get("classement") == "durcissement_securite"
                                 for d in equivalence.get("divergences", []))
            for p in (m.get("verification_formelle") or {}).get("proprietes", []):
                prouvees += p.get("statut") == "prouvee"
                refutees += p.get("statut") == "refutee"
    return {"failles_corrigees": corrigees, "failles_persistantes": persistantes,
            "taux_correction_failles": _taux(corrigees, corrigees + persistantes),
            "gardes_preservees": f"{gardes_ok}/{gardes_total}",
            "taux_gardes_preservees": _taux(gardes_ok, gardes_total),
            "injections_bloquees": injections, "durcissements_observes": durcissements,
            "proprietes_prouvees": prouvees, "proprietes_refutees": refutees,
            "failles_persistantes_detail": detail_persistantes,
            "failles_persistantes_dans_modules_livres": sum(
                d["decision"] == "LIVRER" for d in detail_persistantes)}


def par_llm(rapports: list) -> dict:
    developpeur, manager, juge, entrees = {}, {}, [], []
    hallucinations = sum(len(r.get("corrections_projet", [])) for r in rapports)
    for r in rapports:
        for _, m in modules(r):
            modele = (m.get("modele_generation") or {}).get("modele") or "inconnu (cache)"
            d = developpeur.setdefault(modele, {"modules": 0, "premier_jet": 0, "livres": 0,
                                                "bascules": 0, "tokens": []})
            d["modules"] += 1
            d["premier_jet"] += correct_premier_jet(m)
            d["livres"] += m.get("decision_finale") == "LIVRER"
            d["bascules"] += bool((m.get("modele_generation") or {}).get("bascule"))
            tokens = m.get("tokens_generation") or {}
            if tokens:
                d["tokens"].append(tokens.get("entree", 0) + tokens.get("sortie", 0))

            coordinateur = m.get("coordonne_par") or "aucun (validation humaine)"
            c = manager.setdefault(coordinateur, {"modules": 0, "sollicitations": 0,
                                                  "refus_de_phase": 0, "deja_fait": 0,
                                                  "agents_indisponibles": 0, "relais": 0})
            c["modules"] += 1
            c["relais"] += max(0, len(m.get("relais") or []) - 1)
            for entree in (m.get("etat_structure") or {}).get("journal", []):
                c["sollicitations"] += 1
                c["refus_de_phase"] += entree.get("issue") == "refus_prerequis"
                c["deja_fait"] += entree.get("issue") == "deja_fait"
                c["agents_indisponibles"] += entree.get("issue") == "indisponible"

            juge.append(m.get("jugement") or {})
            entrees.append(((m.get("equivalence") or {}).get("entrees_ia") or {},
                            (m.get("equivalence") or {}).get("mutation") or {}))

    for d in developpeur.values():
        d["pass@1"] = _taux(d.pop("premier_jet"), d["modules"])
        d["taux_livraison"] = _taux(d.pop("livres"), d["modules"])
        d["tokens_moyens"] = _moyenne(d.pop("tokens"))
    for c in manager.values():
        c["sollicitations_par_module"] = _moyenne([c["sollicitations"] / c["modules"]])
    evalues = [j for j in juge if j.get("statut") == "evalue"]
    generes = [e for e, _ in entrees if e.get("statut") == "genere"]
    gains = [len(mu.get("detectes_seulement_par_ia", [])) for _, mu in entrees
             if mu.get("statut") == "mesure"]
    return {
        "developpeur": developpeur,
        "developpeur_hallucinations_corrigees": hallucinations,
        "manager": manager,
        "juge": {"disponibilite": _taux(len(evalues), len(juge)),
                 "score_moyen": _moyenne([j.get("score") for j in evalues]),
                 "modeles": sorted({j.get("modele") for j in evalues if j.get("modele")})},
        "generateur_entrees": {"modules_avec_entrees_ia": len(generes),
                               "entrees_moyennes": _moyenne([e.get("nombre") for e in generes]),
                               "bugs_detectes_seulement_par_ia": sum(gains)},
    }


def cout(rapports: list) -> dict:
    durees, entree, sortie, appels = [], 0, 0, 0
    for r in rapports:
        for _, m in modules(r):
            if m.get("duree_s") is not None:
                durees.append(m["duree_s"])
            t = m.get("tokens_generation") or {}
            entree, sortie, appels = (entree + t.get("entree", 0), sortie + t.get("sortie", 0),
                                      appels + t.get("appels", 0))
    nombre = sum(1 for r in rapports for _ in modules(r))
    return {"duree_totale_s": round(sum(durees), 1), "duree_moyenne_s": _moyenne(durees),
            "tokens_entree": entree, "tokens_sortie": sortie, "appels_generation": appels,
            "tokens_par_module": _moyenne([(entree + sortie) / nombre]) if nombre else None}


# ═══ CodeBLEU (optionnel) ══════════════════════════════

_SCRIPT_CODEBLEU = r"""
import json, sys
from codebleu import calc_codebleu
paires = json.load(open(sys.argv[1], encoding="utf-8"))
r = calc_codebleu([p["reference"] for p in paires], [p["candidat"] for p in paires], lang="python")
print(json.dumps(r))
"""


def codebleu(dossier_candidats: str, dossier_references: str) -> dict:
    """
    CodeBLEU (Ren et al., 2020) entre chaque fichier produit et la
    traduction de référence de même nom.

    Le paquet « codebleu » exige tree-sitter < 0.23, alors que l'Analyste
    de SMAML utilise une version plus récente : on l'installe dans un
    ENVIRONNEMENT VIRTUEL SÉPARÉ, que l'on désigne par SMAML_PYTHON_CODEBLEU.
    L'environnement principal n'est jamais modifié.
    """
    paires = [{"candidat": open(os.path.join(dossier_candidats, n), encoding="utf-8").read(),
               "reference": open(os.path.join(dossier_references, n), encoding="utf-8").read()}
              for n in sorted(os.listdir(dossier_references))
              if n.endswith(".py") and os.path.exists(os.path.join(dossier_candidats, n))]
    if not paires:
        return {"statut": "aucune_paire"}
    python = os.getenv("SMAML_PYTHON_CODEBLEU")
    if not python or not os.path.exists(python):
        return {"statut": "codebleu_absent",
                "raison": "créer l'environnement : py -m venv venv_codebleu, puis "
                          "venv_codebleu\\Scripts\\pip install codebleu tree-sitter-python==0.21.0, "
                          "puis set SMAML_PYTHON_CODEBLEU=venv_codebleu\\Scripts\\python.exe"}
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as dossier:
        chemin_paires, chemin_script = os.path.join(dossier, "p.json"), os.path.join(dossier, "s.py")
        json.dump(paires, open(chemin_paires, "w", encoding="utf-8"))
        open(chemin_script, "w", encoding="utf-8").write(_SCRIPT_CODEBLEU)
        execution = subprocess.run([python, chemin_script, chemin_paires], capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", timeout=300)
    try:
        resultat = json.loads(execution.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"statut": "erreur", "raison": (execution.stderr or "")[-300:]}
    return {"statut": "mesure", "paires": len(paires),
            **{k: round(v, 3) for k, v in resultat.items()}}


# ═══ SYNTHÈSE ══════════════════════════════════════════

def calculer(chemins: list) -> dict:
    rapports = charger(chemins)
    return {"rapports": len(rapports), "fonctionnelles": fonctionnelles(rapports),
            "securite": securite(rapports), "par_llm": par_llm(rapports), "cout": cout(rapports)}


def afficher(m: dict):
    f, s, l, couts = m["fonctionnelles"], m["securite"], m["par_llm"], m["cout"]
    pct = lambda v: "—" if v is None else f"{v * 100:.1f} %"
    print(f"MÉTRIQUES — {m['rapports']} rapport(s), {f['modules']} module(s)\n")
    print("FONCTIONNELLES")
    print(f"  syntaxe valide           {pct(f['taux_syntaxe_valide'])}")
    print(f"  taux d'exécution         {pct(f['taux_execution'])} "
          f"({f['modules_executes']} module(s) exécuté(s) sur {f['modules']})")
    for raison, nombre in f["non_mesurables_par_raison"].items():
        print(f"      non exécuté ({nombre}) : {raison}")
    print(f"  computational accuracy   {pct(f['computational_accuracy'])}"
          f"   (équivalence totale : {pct(f['taux_equivalence_totale'])})")
    for cle in sorted(k for k in f if k.startswith("pass@")):
        print(f"  {cle:<24} {pct(f[cle])}")
    print(f"  taux de livraison        {pct(f['taux_livraison'])}"
          f"   (itérations moyennes : {f['iterations_moyennes']})")
    if f["mutation"]:
        print(f"  score de mutation        fixes {pct(f['mutation']['fixes'])}, "
              f"IA {pct(f['mutation']['ia'])}, hybride {pct(f['mutation']['hybride'])} "
              f"(sur les {f['mutation']['modules_compares']} module(s) où les trois sont mesurées)")
    print("\nSÉCURITÉ")
    print(f"  failles corrigées        {s['failles_corrigees']} "
          f"(persistantes : {s['failles_persistantes']}) — {pct(s['taux_correction_failles'])}")
    for d in s["failles_persistantes_detail"]:
        alerte = "   <-- MODULE LIVRÉ" if d["decision"] == "LIVRER" else ""
        print(f"      persistante : {d['faille']:<22} {d['fichier']} :: {d['module']} "
              f"({d['decision']}){alerte}")
    print(f"  gardes préservées        {s['gardes_preservees']} — {pct(s['taux_gardes_preservees'])}")
    print(f"  injections bloquées      {s['injections_bloquees']}")
    print(f"  propriétés               {s['proprietes_prouvees']} prouvée(s), "
          f"{s['proprietes_refutees']} réfutée(s)")
    print("\nPAR LLM")
    for modele, d in l["developpeur"].items():
        print(f"  Développeur {modele:<28} pass@1 {pct(d['pass@1'])}, livraison "
              f"{pct(d['taux_livraison'])}, bascules {d['bascules']}, "
              f"tokens/module {d['tokens_moyens'] or '—'}")
    print(f"  Développeur — hallucinations corrigées au niveau projet : "
          f"{l['developpeur_hallucinations_corrigees']}")
    for nom, co in l["manager"].items():
        print(f"  Coordination {nom:<24} {co['modules']} module(s), "
              f"{co['sollicitations_par_module']} sollicitation(s)/module, "
              f"{co['refus_de_phase']} refus de phase, {co['deja_fait']} redondance(s)")
    print(f"  Juge                     disponibilité {pct(l['juge']['disponibilite'])}, "
          f"score moyen {l['juge']['score_moyen']}")
    g = l["generateur_entrees"]
    print(f"  Générateur d'entrées     {g['modules_avec_entrees_ia']} module(s), "
          f"{g['entrees_moyennes']} entrée(s) en moyenne, "
          f"{g['bugs_detectes_seulement_par_ia']} bug(s) détecté(s) seulement grâce à l'IA")
    print("\nCOÛT")
    print(f"  temps                    {couts['duree_totale_s']} s au total, "
          f"{couts['duree_moyenne_s']} s par module")
    print(f"  tokens de génération     {couts['tokens_entree']} en entrée, {couts['tokens_sortie']} "
          f"en sortie ({couts['tokens_par_module']} par module)")


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if not arguments:
        print(__doc__)
        sys.exit(1)
    if arguments[0] == "--codebleu":
        print(json.dumps(codebleu(arguments[1], arguments[2]), ensure_ascii=False, indent=2))
        sys.exit(0)
    sortie_json = None
    if "--json" in arguments:
        i = arguments.index("--json")
        sortie_json = arguments[i + 1]
        arguments = arguments[:i] + arguments[i + 2:]
    resultat = calculer(arguments)
    afficher(resultat)
    if sortie_json:
        with open(sortie_json, "w", encoding="utf-8") as f:
            json.dump(resultat, f, ensure_ascii=False, indent=2)
        print(f"\nMétriques enregistrées : {sortie_json}")