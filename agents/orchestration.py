"""
Orchestration SMAML — conception à 4 phases
============================================
    Input (projet PHP)
       ↓
    PHASE 1  Manager — reçoit le projet entier
       ↓
    PHASE 2  Analyste (constate) · Architecte (décide)
       ↓
    PHASE 3  Développeur — module par module, dans l'ordre décidé
       ↓
    PHASE 4  Testeur · Comparateur · Vérificateur · Auditeur → Réviseur

Il n'y a plus de « couche projet » séparée : c'est le Manager qui
reçoit le projet et qui organise tout. Les tâches qu'assurait
l'ancienne couche projet sont confiées aux agents — l'Analyste
constate les dépendances et les champs attendus, l'Architecte décide
de l'ordre et du découpage, le Testeur contrôle la cohérence du
projet produit.

Tolérance aux pannes
--------------------
La phase 2 du projet, puis chaque module, sont menés sous SUPERVISION :
Manager principal → Manager de secours (autre LLM) → coordinateur fixe
(sans LLM) → validation humaine. Tout passe par l'espace partagé
persistant : une migration interrompue reprend où elle s'était arrêtée.

Modes
-----
    SMAML_MODE=orchestre  chaîne complète (Manager LLM en tête)
    SMAML_MODE=direct     coordinateur fixe seul — la référence de
                          mesure de l'étude d'ablation

Utilisation
-----------
    py -X utf8 orchestration.py application.zip [dossier_sortie]
    py -X utf8 orchestration.py --reprendre <identifiant_projet>
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import sys
import tempfile
import time
import zipfile
from datetime import datetime

import configuration                      # applique SMAML_CONFIG d'abord
import modernisation
import portee_verification
import cache_smaml
import outils_agents as oa
from espace_partage import EspaceModule, ouvrir_stockage
from supervision import Coordinateur, Superviseur

MODE_ORCHESTRE = os.getenv("SMAML_MODE", "direct").lower() == "orchestre"
SANS_BOUCLE = bool(os.getenv("SMAML_SANS_BOUCLE"))

# Avancement, lu par l'API pour l'affichage en direct.
PROGRESSION = {"fichiers": [], "statuts": {}, "fichier_courant": None,
               "modules_termines": [], "coordinateur_courant": None}

def _ident(texte: str) -> str:
    """Identifiant sûr pour un flux d'événements."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", texte)


# ═══ PHASE 1 — LE MANAGER REÇOIT LE PROJET ═════════════

def recevoir_projet(espace: EspaceModule, chemin: str) -> dict:
    """
    Le Manager reçoit le projet : ouverture de l'archive et inventaire.
    Après une panne, la réception déjà faite est réutilisée — sauf si
    le dossier temporaire a disparu, auquel cas l'archive est rouverte.
    """
    deja = espace.get("reception")
    if deja and os.path.isdir(deja.get("dossier", "")):
        return deja
    if os.path.isdir(chemin):
        dossier = chemin
    elif chemin.lower().endswith(".zip"):
        dossier = tempfile.mkdtemp(prefix="smaml_projet_")
        with zipfile.ZipFile(chemin) as archive:
            archive.extractall(dossier)
    else:
        raise ValueError(f"Entrée invalide : {chemin} (dossier ou .zip attendu)")

    from langages import adaptateur, detecter_langages
    detection = detecter_langages(dossier)
    langage = detection["principal"]
    extensions = adaptateur(langage).extensions if langage else ()
    sources, autres = [], []
    for racine, _, noms in os.walk(dossier):
        for nom in noms:
            chemin_rel = os.path.relpath(os.path.join(racine, nom), dossier)
            (sources if nom.lower().endswith(extensions) and extensions
             else autres).append(chemin_rel.replace("\\", "/"))
    attention = []
    if detection["non_pris_en_charge"]:
        attention.append("langage(s) détecté(s) sans adaptateur : "
                         + ", ".join(f"{l} ({n} fichier(s))" for l, n in
                                     detection["non_pris_en_charge"].items())
                         + " — adaptateurs disponibles : "
                         + ", ".join(detection["adaptateurs_disponibles"]))
    if not sources:
        attention.append("aucun fichier dans un langage pris en charge "
                         f"({', '.join(detection['adaptateurs_disponibles'])}) : "
                         "le projet ne peut pas être migré")
    elif autres:
        attention.append(f"{len(autres)} fichier(s) hors {adaptateur(langage).nom} "
                         f"non traité(s) : " + ", ".join(sorted(autres)[:8]))
    from frameworks import detecter_framework
    framework = detecter_framework(dossier)
    if framework and framework["pris_en_charge"]:
        attention.append(f"application {framework['nom']} détectée "
                         f"({', '.join(framework['indices'])})")
    elif framework:
        attention.append(f"framework {framework['nom']} reconnu ({', '.join(framework['indices'])}), "
                         f"sans adaptateur : l'application est migrée comme du PHP sans "
                         f"framework — routes et vues à reprendre à la main")
    reception = {"source": chemin, "dossier": dossier, "langage": langage,
                 "detection": detection, "framework": framework,
                 "fichiers_php": sorted(sources),
                 "fichiers_non_traites": sorted(autres)}
    espace.deposer("reception", reception, "Manager", points_attention=attention)
    return reception


# ═══ PHASE 2 — OUTILS DE L'ANALYSTE ET DE L'ARCHITECTE ═

def outil_analyse_projet(espace: EspaceModule) -> str:
    if "reception" not in espace:
        raise oa.PrerequisManquant("Analyste (phase 2) refuse d'agir : le "
                                   "Manager n'a pas encore reçu le projet.")
    if "analyse_projet" in espace:
        raise oa.DejaFait("L'analyse du projet est déjà disponible.")
    from agent_analyste import analyser_projet
    analyse = analyser_projet(espace["reception"]["dossier"],
                              espace["reception"].get("langage") or "php")
    espace.deposer("analyse_projet", analyse, "Analyste", points_attention=[])
    return (f"Analyse : {len(analyse['fichiers'])} fichier(s), "
            f"{analyse['failles_totales']} faille(s).")


def outil_plan_projet(espace: EspaceModule) -> str:
    if "analyse_projet" not in espace:
        raise oa.PrerequisManquant("Architecte (phase 2) refuse d'agir : "
                                   "l'analyse du projet manque.")
    if "plan_projet" in espace:
        raise oa.DejaFait("Le plan du projet est déjà disponible.")
    from agent_architecte import planifier_projet
    plan = planifier_projet(espace["analyse_projet"])
    espace.deposer("plan_projet", plan, "Architecte",
                   hypotheses_faites=[f"ordre de migration : "
                                      f"{', '.join(plan['ordre_fichiers'])}"],
                   points_incertains=[],
                   points_attention=[])
    return (f"Plan : {len(plan['ordre_modules'])} module(s) dans "
            f"{len(plan['ordre_fichiers'])} fichier(s).")


OUTILS_PROJET = {"analyse_projet": outil_analyse_projet,
                 "plan_projet": outil_plan_projet}


# ═══ COORDINATEURS FIXES (SANS LLM) ════════════════════

class CoordinateurProjetFixe(Coordinateur):
    """Phase 2 du projet : analyse, puis plan — ce qui manque seulement."""
    nom, niveau = "coordinateur_fixe", "fixe"

    def coordonner(self, espace):
        for produit in ("analyse_projet", "plan_projet"):
            try:
                OUTILS_PROJET[produit](espace)
            except oa.DejaFait:
                pass
            espace.rafraichir()
        return {"plan": "plan_projet" in espace}


class CoordinateurModuleFixe(Coordinateur):
    """
    Phases 3 et 4 d'un module, dans l'ordre des phases, avec la boucle
    de correction. Ne refait jamais une étape déjà déposée.
    """
    nom, niveau = "coordinateur_fixe", "fixe"

    def coordonner(self, espace):
        tours = 0
        while True:
            espace.rafraichir()
            restantes = oa.etapes_restantes(espace)
            if not restantes:
                break
            for produit in restantes:
                try:
                    oa.realiser(espace, produit)
                except oa.DejaFait:
                    pass
                espace.rafraichir()
            tours += 1
            if not espace.get("correction_demandee"):
                break
            if tours > (espace.get("max_iterations") or 5) + 1:
                break
        decision = espace.get("decision") or {}
        return {"decision": decision.get("decision"),
                "iterations": espace.get("iteration")}


# ═══ CHAÎNE DE COORDINATION ════════════════════════════

def chaine_coordinateurs(niveau: str) -> list:
    """
    Mode orchestré : Manager principal → Manager de secours → fixe.
    Mode direct (référence d'ablation) : coordinateur fixe seul.
    """
    fixe = CoordinateurProjetFixe() if niveau == "projet" else CoordinateurModuleFixe()
    if not MODE_ORCHESTRE:
        return [fixe]
    try:
        from manager_llm import managers_disponibles
        return managers_disponibles(niveau) + [fixe]
    except ImportError as erreur:
        print(f"  [ATTENTION]  Manager LLM indisponible ({erreur}) : coordination fixe")
        return [fixe]


def superviseur(stockage) -> Superviseur:
    return Superviseur(
        stockage, [],
        delai_inactivite_s=float(os.getenv("SMAML_DELAI_INACTIVITE", "300")),
        delai_total_s=float(os.getenv("SMAML_DELAI_TOTAL", "1800")))


def superviser(stockage, projet, flux, niveau):
    sup = superviseur(stockage)
    sup.chaine = chaine_coordinateurs(niveau)
    sup.disjoncteurs = {c.nom: d for c, d in
                        zip(sup.chaine, [_disjoncteur(c.nom) for c in sup.chaine])}
    return sup.superviser(projet, flux)


_DISJONCTEURS = {}


def _disjoncteur(nom):
    """Un disjoncteur par coordinateur, partagé par tous les modules."""
    from supervision import Disjoncteur
    return _DISJONCTEURS.setdefault(nom, Disjoncteur())


# ═══ CONTEXTE D'UN MODULE ══════════════════════════════

_INCLUSION = re.compile(r"^\s*(?:require|include)(?:_once)?\s*\(?\s*['\"][^'\"]+['\"]"
                        r"\s*\)?\s*;\s*$", re.MULTILINE | re.IGNORECASE)


def contexte_php_resolu(dossier: str, fichier: str, plan: dict) -> str:
    """
    Le fichier PHP ET tous les fichiers dont il dépend, réunis en un seul
    script, sans les require/include. Exécuté seul dans un dossier
    temporaire, login.php échouait sur « require_once 'utils.php' » : le
    Comparateur comparait alors le Python à une erreur PHP.
    """
    dependances = {f["fichier"]: f.get("depend_de", []) for f in plan["fichiers"]}
    ordre, vus = [], set()

    def visiter(nom):
        if nom in vus:
            return
        vus.add(nom)
        for dep in dependances.get(nom, []):
            visiter(dep)
        ordre.append(nom)

    visiter(fichier)
    corps = []
    for nom in ordre:
        with open(os.path.join(dossier, nom), encoding="utf-8", errors="ignore") as f:
            code = _INCLUSION.sub("", f.read())
        code = re.sub(r"^\s*<\?php", "", code.strip(), flags=re.IGNORECASE)
        code = re.sub(r"\?>\s*$", "", code)
        corps.append(f"// ── {nom} ──\n{code.strip()}")
    return "<?php\n" + "\n\n".join(corps) + "\n"

def _noms_definis(code: str) -> set:
    noms = set()
    try:
        for n in ast.walk(ast.parse(code or "")):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                noms.add(n.name)
            elif isinstance(n, ast.Assign):
                noms.update(c.id for c in n.targets if isinstance(c, ast.Name))
    except SyntaxError:
        pass
    return noms


def _signatures(module: dict) -> list:
    if module.get("type") == "classe":
        if module.get("cible_migration") == "fonctions_module":
            return [f"{m}()" for m in module.get("methodes_python", [])]
        return [f"{module['nom_python']} (classe, méthodes : "
                f"{', '.join(module.get('methodes_python', []))})"]
    params = ", ".join(p.replace("$", "") for p in module.get("parametres", []))
    return [f"{module['nom_python']}({params})"]


def contexte_module(module, fichier_plan, code_fichier, signatures_projet,
                    signatures_fichier, codes_fichier, noms_externes,
                    max_iterations, feedback_projet="", contexte_php=None):
    from agent_architecte import formater_contexte
    from langages import adaptateur
    nom_py = os.path.splitext(os.path.basename(fichier_plan["fichier"]))[0]
    texte = formater_contexte(signatures_projet)
    langage = module.get("langage_source", "php")
    from frameworks import adaptateur_framework
    cadre = adaptateur_framework(fichier_plan.get("framework") or "")
    if cadre:
        texte = cadre.consigne + "\n\n" + texte
    if langage != "php":
        # Les pièges de traduction du langage d'origine, pour le Développeur.
        texte = adaptateur(langage).consigne_traduction() + "\n\n" + texte
    if signatures_fichier:
        texte += (f"\n\nATTENTION — Les éléments suivants sont déjà définis "
                  f"PLUS HAUT DANS LE MÊME FICHIER ({nom_py}.py) :\n"
                  + "\n".join(f"- {s}" for s in signatures_fichier)
                  + f"\nUtilise-les DIRECTEMENT par leur nom. Ne les importe "
                  f"JAMAIS (from {nom_py} import ... est INTERDIT) et ne les "
                  f"redéfinis JAMAIS.")
    if module.get("champs_requis"):
        texte += (f"\nIMPORTANT — Les appelants de {module['nom_original']} "
                  f"utilisent ces champs sur son résultat : "
                  f"{', '.join(module['champs_requis'])}. Le résultat de "
                  f"{module['nom_python']} DOIT les inclure.")
    if feedback_projet:
        texte += (f"\nCORRECTION REQUISE — défauts d'intégration détectés "
                  f"dans le projet :\n{feedback_projet}")
    acceptes = {"", module.get("nom_original")} | set(module.get("methodes", []))
    return {
        "code_php_module": module.get("code_source") or code_fichier,
        "code_php_fichier": contexte_php or code_fichier,
        "invariants": [i for i in fichier_plan.get("invariants", [])
                       if i.get("fonction", "") in acceptes],
        # Les failles de CETTE fonction seulement : attribuer à chaque module
        # toutes les failles du fichier faisait juger get_user sur une
        # injection de commande située dans une autre fonction.
        "failles": [f for f in fichier_plan.get("failles", [])
                    if f.get("fonction", "") in acceptes],
        "contexte_projet": texte,
        "code_python_projet": "\n\n".join(codes_fichier),
        "noms_externes": sorted(noms_externes),
        "max_iterations": max_iterations,
        "sans_boucle": SANS_BOUCLE,
    }


# ═══ ENTRÉE DE RAPPORT D'UN MODULE ═════════════════════

def entree_module(espace: EspaceModule, supervision) -> dict:
    module = espace.get("module") or {}
    decision = espace.get("decision") or {}
    code = espace.get("code_python") or ""
    rt = espace.get("rapport_testeur") or {}
    if supervision.statut == "validation_humaine":
        verdict = "VALIDATION_HUMAINE"
    else:
        verdict = decision.get("decision") or "VALIDATION_HUMAINE"
    entree = {
        "nom_python": module.get("nom_python"),
        "nom_original": module.get("nom_original"),
        "decision_finale": verdict,
        "score_final": decision.get("score_compose", 0.0) or 0.0,
        "iterations": espace.get("iteration") or 1,
        "categorie_echec": decision.get("categorie_echec"),
        "code_python": code,
        "code_php": espace.get("code_php_module"),
        "equivalence": espace.get("rapport_differentiel"),
        "verification_formelle": espace.get("rapport_formel"),
        "jugement": espace.get("rapport_juge"),
        "confiance": decision.get("confiance"),
        "modernisation": modernisation.mesurer_modernisation(code),
        "modele_generation": espace.get("modele_generation"),
        "tokens_generation": espace.get("tokens_generation"),
        "coordonne_par": supervision.coordonne_par,
        "relais": supervision.relais,
        "rapport_testeur": {"invariants": rt.get("invariants"),
                            "failles": rt.get("failles")},
        "etat_structure": {
            "journal": espace.journal,
            "notes": espace.notes,
            "versions": {c: len(v) for c, v in espace.historique.items()},
            "derniere_decision": {"verdict": verdict,
                                  "confiance": decision.get("confiance")},
            "points_attention": sorted({p for d in espace.depots.values()
                                        for p in d.get("points_attention", [])
                                        if p}),
        },
    }
    entree["portee_verification"] = portee_verification.portee_verification(entree)
    return entree


# ═══ MIGRATION D'UN PROJET ═════════════════════════════

def migrer_projet(chemin: str, dossier_sortie: str = "outputs_projet",
                  max_iterations: int = 5, projet: str = None,
                  stockage=None) -> dict:
    stockage = stockage or ouvrir_stockage()
    projet = projet or os.getenv("SMAML_PROJET_ID") or _ident(
        f"{os.path.splitext(os.path.basename(chemin))[0]}"
        f"-{datetime.now():%Y%m%d-%H%M%S}")
    os.makedirs(dossier_sortie, exist_ok=True)
    espace_projet = EspaceModule(projet, "_projet", stockage)

    print("=" * 60)
    print(f"SMAML — projet {projet}")
    print(f"  stockage : {stockage.nom} | mode : "
          f"{'orchestré' if MODE_ORCHESTRE else 'direct'}")
    repli = getattr(stockage, "repli_depuis_redis", None)
    if repli:
        print(f"  [ATTENTION]  REDIS INJOIGNABLE — stockage de SECOURS (SQLite) utilisé")
        print(f"      cause : {repli}")
        print(f"      vérifie que Docker Desktop est lancé, puis : docker start smaml-redis")
    print("=" * 60)

    # ── Phase 1 : le Manager reçoit le projet ──
    reception = recevoir_projet(espace_projet, chemin)
    print(f"\nPHASE 1 — Réception : {len(reception['fichiers_php'])} fichier(s) PHP")
    for note in (espace_projet.depots.get("reception") or {}).get("points_attention", []):
        print(f"  [ATTENTION]  {note}")
    if not reception["fichiers_php"]:
        return _rapport(projet, espace_projet, [], {}, dossier_sortie, stockage)

    # ── Phase 2 : analyse et plan, sous supervision ──
    print("\nPHASE 2 — Analyse du code")
    sup = superviser(stockage, projet, "_projet", "projet")
    espace_projet.rafraichir()
    if "plan_projet" not in espace_projet:
        print("  [ATTENTION]  Phase 2 non menée à terme : validation humaine")
        return _rapport(projet, espace_projet, [], {}, dossier_sortie, stockage)
    plan = espace_projet["plan_projet"]
    print(f"  Ordre de migration : {' → '.join(plan['ordre_fichiers'])} "
          f"(coordonné par {sup.coordonne_par})")

    PROGRESSION.update({"fichiers": plan["ordre_fichiers"],
                        "statuts": {f: "en_attente" for f in plan["ordre_fichiers"]},
                        "modules_termines": []})

    # ── Fichiers annexes : copiés, traduits ou conservés ──
    from fichiers_annexes import traiter_annexes
    annexes = traiter_annexes(reception["dossier"], reception.get("fichiers_non_traites", []),
                              dossier_sortie)
    fichiers_migres, signatures_projet = [], {}
    if annexes["signatures_modeles"]:
        # Le Développeur saura que les modèles existent : il les importera
        # au lieu d'en inventer.
        signatures_projet["models.py"] = annexes["signatures_modeles"]
        with open(os.path.join(dossier_sortie, "models.py"), encoding="utf-8") as f:
            signatures_projet.setdefault("_codes", {})["models.py"] = f.read()
    if annexes["fichiers"]:
        comptes = {}
        for entree in annexes["fichiers"]:
            comptes[entree["categorie"]] = comptes.get(entree["categorie"], 0) + 1
        print("  Fichiers annexes : " + ", ".join(f"{n} {c}" for c, n in sorted(comptes.items())))

    framework = (reception.get("framework") or {}).get("nom")
    for fichier_plan in plan["fichiers"]:
        fichier_plan = dict(fichier_plan, framework=framework)
        fichiers_migres.append(_migrer_fichier(
            stockage, projet, reception["dossier"], fichier_plan,
            signatures_projet, max_iterations, dossier_sortie))

    # ── Vues → gabarits Jinja2 ; routes Laravel → routeur FastAPI ──
    cadre = _vues_et_routes(reception, plan, fichiers_migres, dossier_sortie)

    # ── Phase 4 au niveau du projet : cohérence, et correction ──
    coherence, corrections = _coherence_et_corrections(
        stockage, projet, reception["dossier"], plan, fichiers_migres,
        signatures_projet, max_iterations, dossier_sortie, espace_projet)
    rapport = _rapport(projet, espace_projet, fichiers_migres, coherence,
                       dossier_sortie, stockage, corrections, plan, annexes, cadre)
    return rapport


def _migrer_fichier(stockage, projet, dossier, fichier_plan, signatures_projet,
                    max_iterations, dossier_sortie, feedback_projet="") -> dict:
    fichier = fichier_plan["fichier"]
    nom_py = os.path.splitext(os.path.basename(fichier))[0] + ".py"
    PROGRESSION["fichier_courant"] = fichier
    PROGRESSION["statuts"][fichier] = "en_cours"
    with open(os.path.join(dossier, fichier), encoding="utf-8", errors="ignore") as f:
        code_fichier = f.read()
    espace_projet = EspaceModule(projet, "_projet", stockage)
    plan_projet = espace_projet.get("plan_projet") or {"fichiers": [fichier_plan]}
    langage = (espace_projet.get("reception") or {}).get("langage") or "php"
    contexte_php = (contexte_php_resolu(dossier, fichier, plan_projet)
                    if langage == "php" else code_fichier)

    print(f"\n{'█' * 60}\n█  FICHIER : {fichier}\n{'█' * 60}")

    # Un fichier de pures DÉFINITIONS DE DONNÉES (copybook COBOL) n'a pas
    # d'unité de code à confier au Développeur : ses structures sont
    # traduites de façon déterministe, sans LLM.
    if not fichier_plan["modules"] and langage != "php":
        from langages import adaptateur
        outil = adaptateur(langage)
        traduction, classes = (outil.traduire_donnees(code_fichier)
                               if hasattr(outil, "traduire_donnees") else (None, []))
        if traduction:
            with open(os.path.join(dossier_sortie, nom_py), "w", encoding="utf-8") as f:
                f.write(f'"""\nMigré par SMAML depuis {fichier} — données traduites '
                        f'sans LLM\n"""\n\n' + traduction)
            signatures_projet[nom_py] = [f"{c} (dataclass des données partagées, "
                                         f"à importer : from {os.path.splitext(nom_py)[0]} "
                                         f"import {c})" for c in classes]
            signatures_projet.setdefault("_codes", {})[nom_py] = traduction
            PROGRESSION["statuts"][fichier] = "livre"
            print(f"  → données traduites : {', '.join(classes)}")
            return {"source": fichier, "cible": nom_py, "statut": "livré", "modules": [],
                    "donnees": {"classes": classes,
                                "methode": "traduction déterministe des clauses PIC"}}

    if not fichier_plan["modules"] and langage == "php":
        # Une page PHP sans fonction mêle HTML et PHP : ce n'est pas du code
        # à confier au Développeur, mais une VUE, à traduire en gabarit.
        cible_vue = os.path.join(dossier_sortie, "vues", fichier)
        os.makedirs(os.path.dirname(cible_vue), exist_ok=True)
        with open(cible_vue, "w", encoding="utf-8") as f:
            f.write(code_fichier)
        PROGRESSION["statuts"][fichier] = "vue"
        print("  → vue PHP (HTML et PHP mêlés) : mise de côté pour sa traduction en gabarit")
        return {"source": fichier, "cible": f"vues/{fichier}", "statut": "vue_a_traduire",
                "modules": []}

    modules, signatures_fichier, codes_fichier = [], [], []
    noms_externes = set()
    for codes in signatures_projet.get("_codes", {}).values():
        noms_externes |= _noms_definis(codes)

    for module in fichier_plan["modules"]:
        flux = _ident(module["id"])
        espace = EspaceModule(projet, flux, stockage)
        contexte = contexte_module(module, fichier_plan, code_fichier,
                                   {k: v for k, v in signatures_projet.items()
                                    if k != "_codes"},
                                   signatures_fichier, codes_fichier,
                                   noms_externes, max_iterations, feedback_projet,
                                   contexte_php=contexte_php)
        contexte["dossier_python"] = os.path.abspath(dossier_sortie)
        oa.preparer_module(espace, module, contexte)
        if feedback_projet:
            espace["feedback"] = {"instructions": [feedback_projet],
                                  "erreurs_par_priorite": []}
            espace["correction_demandee"] = True

        print(f"\n> PHASES 3-4 — module {module['nom_python']}")
        PROGRESSION["coordinateur_courant"] = None
        debut_module = time.monotonic()
        resultat = superviser(stockage, projet, flux, "module")
        espace.rafraichir()
        entree = entree_module(espace, resultat)
        entree["duree_s"] = round(time.monotonic() - debut_module, 1)
        modules.append(entree)
        print(f"  → {entree['decision_finale']} "
              f"({entree['score_final']:.1f} %, coordonné par "
              f"{resultat.coordonne_par or 'personne'})")
        PROGRESSION["modules_termines"].append({
            "fichier": fichier, "module": entree["nom_python"],
            "decision": entree["decision_finale"], "score": entree["score_final"]})

        signatures_fichier.extend(_signatures(module))
        codes_fichier.append(entree["code_python"])
        noms_externes |= _noms_definis(entree["code_python"])

    signatures_projet[nom_py] = signatures_fichier
    signatures_projet.setdefault("_codes", {})[nom_py] = "\n\n".join(codes_fichier)

    blocs = [f"# ── {m['nom_python']} (score {m['score_final']:.1f}%, "
             f"{m['iterations']} itération(s)) ──\n{m['code_python']}"
             for m in modules]
    with open(os.path.join(dossier_sortie, nom_py), "w", encoding="utf-8") as f:
        f.write(f'"""\nMigré automatiquement par SMAML depuis {fichier}\n"""\n\n'
                + "\n\n\n".join(blocs) + "\n")
    tout_livre = all(m["decision_finale"] == "LIVRER" for m in modules)
    PROGRESSION["statuts"][fichier] = "livre" if tout_livre else "partiel"
    return {"source": fichier, "cible": nom_py,
            "statut": "livré" if tout_livre else "partiel", "modules": modules}


def _module_a_la_ligne(chemin: str, numero: int):
    """Le module dont le bloc contient cette ligne du fichier produit."""
    courant = None
    try:
        with open(chemin, encoding="utf-8") as f:
            for i, ligne in enumerate(f, 1):
                entete = re.match(r"# ── (\w+) \(", ligne)
                if entete:
                    courant = entete.group(1)
                if i >= numero:
                    return courant
    except OSError:
        pass
    return None


def _libelle_typage(typage: dict) -> str:
    if typage.get("statut") != "teste":
        return f"non vérifié ({typage.get('statut')})"
    return "conforme" if typage.get("coherent") else \
        f"{len(typage['erreurs'])} contrat(s) rompu(s)"


def _coherence_et_corrections(stockage, projet, dossier, plan, fichiers_migres,
                              signatures_projet, max_iterations, dossier_sortie,
                              espace_projet, max_tours: int = 2):
    from agent_testeur import verifier_coherence_projet, verifier_typage_projet
    corrections = []
    for tour in range(max_tours + 1):
        coherence = verifier_coherence_projet(dossier_sortie)
        typage = verifier_typage_projet(dossier_sortie)
        coherence["typage"] = typage
        conforme = coherence.get("coherent") and typage.get("coherent", True)
        print(f"\nPHASE 4 — Cohérence du projet"
              + (f" (après correction {tour})" if tour else "")
              + f" : imports {'cohérents' if coherence.get('coherent') else 'défectueux'}"
              + f", typage {_libelle_typage(typage)}")
        for erreur in typage.get("erreurs", [])[:5]:
            print(f"  [X] {erreur['module']} — {erreur['erreur'][:140]}")
        if conforme or tour == max_tours:
            break
        # Chaque import cassé ou contrat de type rompu désigne le fichier
        # produit qui le contient.
        a_corriger = {}
        for defaut in coherence.get("imports_casses", []) + typage.get("erreurs", []):
            module_casse = os.path.splitext(str(defaut.get("module", "")))[0]
            for fm in fichiers_migres:
                if os.path.splitext(fm["cible"])[0] == module_casse:
                    a_corriger.setdefault(fm["source"], []).append(
                        defaut.get("erreur", str(defaut)))
        if not a_corriger:
            break
        for source, problemes in a_corriger.items():
            fichier_plan = next(f for f in plan["fichiers"] if f["fichier"] == source)
            feedback = "\n".join(f"- {p}" for p in problemes)
            corrections.append({"fichier": source, "defauts": problemes})
            nouvelle = _migrer_fichier(stockage, projet, dossier, fichier_plan,
                                       signatures_projet, max_iterations,
                                       dossier_sortie, feedback_projet=feedback)
            for i, fm in enumerate(fichiers_migres):
                if fm["source"] == source:
                    fichiers_migres[i] = nouvelle
    defauts = not coherence.get("coherent") or \
        not coherence.get("typage", {}).get("coherent", True)
    if defauts:
        # Un défaut d'intégration qui PERSISTE après les corrections : le
        # module concerné ne peut pas s'importer dans le projet. Il n'est
        # pas livré, quelle que soit sa décision propre.
        for defaut in coherence.get("imports_casses", []) + \
                coherence.get("typage", {}).get("erreurs", []):
            cible = os.path.splitext(str(defaut.get("module", "")))[0]
            ligne = str(defaut.get("import", ""))
            for fm in fichiers_migres:
                if os.path.splitext(fm["cible"] or "")[0] != cible:
                    continue
                # Le module concerné : celui qui contient l'import fautif, ou
                # celui dont le bloc contient la ligne de l'erreur de typage.
                # Jamais tout le fichier par défaut.
                concernes = [m for m in fm["modules"] if ligne and ligne in (m.get("code_python") or "")]
                if not concernes and defaut.get("ligne"):
                    nom = _module_a_la_ligne(os.path.join(dossier_sortie, fm["cible"]),
                                             int(defaut["ligne"]))
                    concernes = [m for m in fm["modules"] if m.get("nom_python") == nom]
                for m in concernes:
                    if m["decision_finale"] == "LIVRER":
                        m["decision_finale"] = "VALIDATION_HUMAINE"
                        m["categorie_echec"] = "integration"
                    m.setdefault("etat_structure", {}).setdefault("points_attention", []).append(
                        f"défaut d'intégration non résolu : {defaut.get('erreur', '')[:120]}")
                fm["statut"] = "partiel"
    espace_projet.deposer("coherence_projet", coherence, "Testeur",
                          points_attention=["défauts d'intégration non résolus"]
                          if defauts else [])
    return coherence, corrections


# ═══ RAPPORT ═══════════════════════════════════════════

def _vues_et_routes(reception, plan, fichiers_migres, dossier_sortie) -> dict:
    """
    Les vues mises de côté deviennent des gabarits Jinja2 ; pour une
    application Laravel, les routes deviennent un routeur FastAPI.
    """
    from frameworks import (AdaptateurFramework, adaptateur_framework,
                            generer_application, generer_routeur)
    framework = reception.get("framework") or {}
    cadre_fw = adaptateur_framework(framework.get("nom", "")) or AdaptateurFramework()
    # Les vues : pages PHP mises de côté, et gabarits propres au framework
    # (Twig pour Symfony), qui ne sont pas des fichiers PHP.
    for relatif in reception.get("fichiers_non_traites", []):
        if cadre_fw.extensions_vues and relatif.lower().endswith(cadre_fw.extensions_vues) \
                and not relatif.lower().endswith(".php"):
            fichiers_migres.append({"source": relatif, "cible": None,
                                    "statut": "vue_a_traduire", "modules": []})
    gabarits, non_convertis = [], []
    for entree in fichiers_migres:
        if entree.get("statut") != "vue_a_traduire":
            continue
        source = open(os.path.join(reception["dossier"], entree["source"]),
                      encoding="utf-8", errors="ignore").read()
        gabarit, restes = cadre_fw.convertir_vue(source)
        cible = os.path.join("templates", cadre_fw.nom_gabarit(entree["source"])).replace("\\", "/")
        os.makedirs(os.path.dirname(os.path.join(dossier_sortie, cible)), exist_ok=True)
        with open(os.path.join(dossier_sortie, cible), "w", encoding="utf-8") as f:
            f.write(gabarit)
        entree.update({"statut": "gabarit" if not restes else "gabarit_partiel",
                       "cible": cible, "non_convertis": restes})
        gabarits.append(cible)
        non_convertis += [f"{entree['source']} : {r[:80]}" for r in restes]
    if gabarits:
        shutil.rmtree(os.path.join(dossier_sortie, "vues"), ignore_errors=True)
        print(f"  Vues → {len(gabarits)} gabarit(s) Jinja2"
              + (f", {len(non_convertis)} élément(s) à reprendre" if non_convertis else ""))

    cadre = {"gabarits": gabarits, "non_convertis": non_convertis}
    if framework.get("pris_en_charge"):
        routes = cadre_fw.lire_routes(reception["dossier"])
        modules_par_classe = {m.get("nom_original"): m for f in plan["fichiers"]
                              for m in f["modules"]}
        if routes:
            with open(os.path.join(dossier_sortie, "routes.py"), "w", encoding="utf-8") as f:
                f.write(generer_routeur(routes, modules_par_classe))
            with open(os.path.join(dossier_sortie, "main.py"), "w", encoding="utf-8") as f:
                f.write(generer_application(bool(gabarits),
                                            os.path.isdir(os.path.join(dossier_sortie, "static"))))
            print(f"  Routes {framework['nom']} → routes.py ({len(routes)} route(s)) et main.py")
        cadre.update({"framework": framework, "routes": routes})
    return cadre


def _rapport(projet, espace_projet, fichiers_migres, coherence, dossier_sortie,
             stockage, corrections=None, plan=None, annexes=None, cadre=None) -> dict:
    modules = [m for f in fichiers_migres for m in f["modules"]]
    rapport = {
        "projet": projet,
        "stockage": stockage.nom,
        "stockage_repli": getattr(stockage, "repli_depuis_redis", None),
        "mode": "orchestré" if MODE_ORCHESTRE else "direct",
        "reception": espace_projet.get("reception"),
        "fichiers_migres": fichiers_migres,
        "statistiques": {
            "total_fichiers": len(fichiers_migres),
            "fichiers_livres": sum(1 for f in fichiers_migres if f["statut"] == "livré"),
            "modules": len(modules),
            "modules_livres": sum(1 for m in modules if m["decision_finale"] == "LIVRER"),
            "relais_de_coordination": sum(len(m.get("relais") or []) - 1
                                          for m in modules if m.get("relais")),
        },
        "coherence_projet": coherence,
        "corrections_projet": corrections or [],
        "decoupage_services": (plan or {}).get("decoupage_services"),
        "fichiers_annexes": (annexes or {}).get("fichiers", []),
        "framework": cadre or {},
        "reglages": configuration.description_active(),
        "cache": cache_smaml.statistiques(),
    }
    with open(os.path.join(dossier_sortie, "rapport_migration.json"), "w",
              encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2, default=str)

    dependances = set()
    for depot in (m.get("code_python") or "" for m in modules):
        for ligne in depot.splitlines():
            trouve = re.match(r"\s*(?:from|import)\s+([A-Za-z_]\w*)", ligne)
            if trouve and trouve.group(1) not in sys.stdlib_module_names:
                dependances.add(trouve.group(1))
    # Pilotes cités seulement dans une adresse de connexion (mysql+pymysql://).
    for depot in (m.get("code_python") or "" for m in modules):
        for pilote in re.findall(r"[a-z]+\+([a-z0-9_]+)://", depot):
            dependances.add(pilote)
    internes = {os.path.splitext(f["cible"])[0] for f in fichiers_migres}
    # Un module local supposé par le LLM (models…) n'est pas une dépendance.
    from agent_testeur import NOMS_LOCAUX_TYPIQUES
    internes |= NOMS_LOCAUX_TYPIQUES
    with open(os.path.join(dossier_sortie, "requirements.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(sorted(dependances - internes)) + "\n")

    s = rapport["statistiques"]
    print("\n" + "=" * 60)
    print(f"MIGRATION TERMINÉE — {s['modules_livres']}/{s['modules']} module(s) "
          f"livré(s), {s['fichiers_livres']}/{s['total_fichiers']} fichier(s)")
    print(f"  {cache_smaml.resume()}")
    print(f"  Résultats : {dossier_sortie}/")
    return rapport


def principal(arguments: list):
    """Point d'entrée en ligne de commande."""
    if not arguments:
        print(__doc__)
        sys.exit(1)
    if arguments[0] == "--reprendre":
        identifiant = arguments[1]
        espace = EspaceModule(identifiant, "_projet")
        source = (espace.get("reception") or {}).get("source")
        if not source:
            sys.exit(f"Projet {identifiant} introuvable dans l'espace partagé.")
        print(f"Reprise du projet {identifiant}")
        return migrer_projet(source, arguments[2] if len(arguments) > 2
                             else "outputs_projet", projet=identifiant)
    return migrer_projet(arguments[0],
                         arguments[1] if len(arguments) > 1 else "outputs_projet")


if __name__ == "__main__":
    principal(sys.argv[1:])