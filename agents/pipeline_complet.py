"""
Pipeline Projet — SMAML
========================
Migre une APPLICATION PHP COMPLÈTE (ZIP ou dossier) vers Python.

Fonctionnement :
  1. Décompresse le ZIP (ou lit le dossier)
  2. Liste tous les fichiers .php
  3. Construit le graphe de dépendances (include/require)
  4. Trie les fichiers : d'abord ceux dont les autres dépendent
     (config, db, utils), puis ceux qui les utilisent
  5. Pour chaque fichier : Analyste → Architecte → Développeur
     → Testeur → Auditeur → Réviseur (avec boucle corrective)
  6. Passe le contexte des modules déjà migrés au Développeur
  7. Sauvegarde un projet Python complet dans outputs_projet/

Usage :
    python pipeline_projet.py mon_app.zip
    python pipeline_projet.py chemin/vers/dossier_php
"""

import os
import re
import sys
import json
import zipfile
import tempfile

from agent_analyste import analyser_code_php
from agent_architecte import planifier_migration
from agent_developpeur import (
    generer_code_python,
    extraire_code_module,
    extraire_code_classe,
    nettoyer_code,
)
from agent_testeur import agent_testeur
from agent_testeur_differentiel import tester_equivalence
from agent_verification_formelle import verifier_formellement
from agent_auditeur import agent_auditeur
import cache_smaml
from agent_reviseur import agent_reviseur


# ─── MODE D'ORCHESTRATION ────────────────────────────────────
# La couche projet (dépendances entre fichiers, ordonnancement,
# cohérence) reste déterministe : l'ordre des fichiers découle des
# dépendances logiques de l'application, un fichier inclus devant
# être migré avant celui qui l'inclut.
#
# En revanche la migration d'un module peut être confiée à un
# Manager multi-agents qui décide seul de l'activation des agents.
#
#   SMAML_MODE=orchestre  → migration des modules par le Manager
#   SMAML_MODE=direct     → enchaînement déterministe (par défaut)
#
# Conserver le mode direct permet des mesures reproductibles et la
# comparaison des deux approches d'orchestration.
MODE_ORCHESTRE = os.getenv("SMAML_MODE", "direct").lower() == "orchestre"


# ─── Réconciliation preuve formelle / heuristiques ───────────
# Le Testeur et l'Auditeur vérifient les invariants par PATTERNS
# TEXTUELS (rapides mais faillibles : ils ratent p.ex. un
# min_length=8 de Pydantic). La vérification formelle les vérifie
# par PREUVE MATHÉMATIQUE (Z3). Quand les deux se contredisent,
# la preuve fait foi : un invariant PROUVÉ est préservé, même si
# aucun pattern textuel ne l'a reconnu. Sans cette réconciliation,
# un module correct peut échouer en boucle sur un feedback
# impossible à satisfaire (cas hash_password du benchmark).

_LIBELLE_VERS_TYPE = {
    "longueur": "validation_longueur",
    "majuscule": "validation_format",
    "non nul": "validation_existence",
}


def _types_invariants_prouves(rapport_formel: dict) -> set:
    """Types d'invariants dont la propriété a été PROUVÉE par Z3."""
    types_prouves = set()
    for prop in rapport_formel.get("proprietes", []):
        if prop.get("statut") != "prouvee":
            continue
        libelle = prop.get("libelle", "").lower()
        for mot_cle, type_inv in _LIBELLE_VERS_TYPE.items():
            if mot_cle in libelle:
                types_prouves.add(type_inv)
    return types_prouves


def _reconcilier_testeur(rapport_testeur: dict, types_prouves: set,
                         rapport_diff: dict, rapport_formel: dict):
    """
    Requalifie comme 'vérifiés' les invariants prouvés par Z3 que
    l'heuristique textuelle avait marqués manquants, puis recalcule
    le score fonctionnel (mêmes pondérations que le flux normal).
    """
    inv = rapport_testeur.get("invariants") or {}
    manquants = inv.get("invariants_manquants", [])
    requalifies = [i for i in manquants
                   if i.get("type") in types_prouves]
    if not requalifies:
        return

    for i in requalifies:
        manquants.remove(i)
        i["requalifie_par_preuve_formelle"] = True
        inv.setdefault("invariants_verifies", []).append(i)

    total = len(inv.get("invariants_verifies", [])) + len(manquants)
    inv["score"] = (len(inv["invariants_verifies"]) / total) if total else 1.0

    # Recalcul du score fonctionnel : base (syntaxe/invariants/
    # failles) puis mêmes fusions équivalence et formel qu'avant.
    score_syntaxe = 1.0 if rapport_testeur.get(
        "syntaxe", {}).get("syntaxe_valide") else 0.0
    score_failles = rapport_testeur.get("failles", {}).get("score", 1.0)
    score = (score_syntaxe * 0.3 + inv["score"] * 0.4
             + score_failles * 0.3)
    if rapport_diff.get("statut") == "teste":
        score = score * 0.7 + rapport_diff.get("score_equivalence", 0) * 0.3
    score = score * 0.85 + rapport_formel.get("score_formel", 0) * 0.15
    rapport_testeur["score_fonctionnel"] = score

    print(f"  ⚖️  Réconciliation : {len(requalifies)} invariant(s) "
          f"non reconnu(s) par l'heuristique textuelle mais PROUVÉ(S) "
          f"par Z3 → requalifié(s) préservé(s) "
          f"(score fonctionnel recalculé : {score*100:.1f}%)")


def _reconcilier_auditeur(rapport_auditeur: dict, types_prouves: set):
    """
    Même principe pour la Dimension 1 de l'Auditeur, avec recalcul
    du score sécurité global et du niveau d'alerte.
    """
    dim1 = rapport_auditeur.get("dimension_1_invariants") or {}
    violes = dim1.get("invariants_violes", [])
    requalifies = [i for i in violes if i.get("type") in types_prouves]
    if not requalifies:
        return

    for i in requalifies:
        violes.remove(i)
        i["requalifie_par_preuve_formelle"] = True
        dim1.setdefault("invariants_preserves", []).append(i)

    total = len(dim1.get("invariants_preserves", [])) + len(violes)
    dim1["score"] = (len(dim1["invariants_preserves"]) / total * 100) \
        if total else 100.0

    dim2 = rapport_auditeur.get("dimension_2_bandit", {})
    dim3 = rapport_auditeur.get("dimension_3_dependances", {})
    nb_vulns = len(dim3.get("vulnerabilites", []))
    score_dim3 = 100.0 if nb_vulns == 0 else max(0, 100 - nb_vulns * 10)
    rapport_auditeur["score_securite_global"] = (
        dim1["score"] * 0.4
        + dim2.get("score_securite", 100.0) * 0.4
        + score_dim3 * 0.2
    )

    failles_high = [f for f in dim2.get("failles_detectees", [])
                    if f.get("severity") == "high"]
    if failles_high or violes:
        rapport_auditeur["niveau_alerte"] = "CRITIQUE"
    elif rapport_auditeur["score_securite_global"] < 80:
        rapport_auditeur["niveau_alerte"] = "ATTENTION"
    else:
        rapport_auditeur["niveau_alerte"] = "OK"

    print(f"  ⚖️  Réconciliation Auditeur : Dimension 1 recalculée "
          f"({dim1['score']:.0f}%), score sécurité global "
          f"{rapport_auditeur['score_securite_global']:.1f}%")


# ═════════════════════════════════════════════════════
# ÉTAPE 1 — PRÉPARATION DU PROJET
# ═════════════════════════════════════════════════════

def preparer_projet(chemin: str) -> str:
    """
    Si le chemin est un ZIP, le décompresse dans un dossier
    temporaire. Si c'est déjà un dossier, le retourne tel quel.
    """
    if os.path.isdir(chemin):
        return chemin

    if chemin.lower().endswith(".zip"):
        dossier_temp = tempfile.mkdtemp(prefix="smaml_projet_")
        with zipfile.ZipFile(chemin, "r") as zf:
            zf.extractall(dossier_temp)
        print(f"ZIP décompressé dans : {dossier_temp}")
        return dossier_temp

    raise ValueError(
        f"Chemin invalide : {chemin} "
        f"(attendu : un dossier ou un fichier .zip)"
    )


def lister_fichiers_php(dossier: str) -> list:
    """
    Parcourt récursivement le dossier et retourne
    la liste de tous les fichiers .php trouvés.
    """
    fichiers = []
    for racine, _, noms in os.walk(dossier):
        for nom in noms:
            if nom.lower().endswith(".php"):
                fichiers.append(os.path.join(racine, nom))
    return sorted(fichiers)


# ═════════════════════════════════════════════════════
# ÉTAPE 2 — GRAPHE DE DÉPENDANCES
# ═════════════════════════════════════════════════════

def extraire_includes(code_php: str) -> list:
    """
    Extrait les noms de fichiers inclus via
    include / require / include_once / require_once.

    Exemple : include('db.php');  →  ['db.php']
    Ne capture que les chemins ÉCRITS EN DUR (statiques).
    Les includes dynamiques — include($page) — ne sont pas
    résolubles sans exécuter le code.
    """
    pattern = r"(?:include|require)(?:_once)?\s*\(?\s*['\"]([^'\"]+)['\"]"
    return re.findall(pattern, code_php)


def construire_graphe(fichiers: list) -> dict:
    """
    Construit le graphe de dépendances du projet.
    graphe[fichier] = liste des fichiers dont il dépend.
    """
    ensemble_fichiers = set(fichiers)
    graphe = {}

    for fichier in fichiers:
        with open(fichier, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()

        dependances = []
        for inclus in extraire_includes(code):
            # Résoudre le chemin relatif au fichier courant
            candidat = os.path.normpath(
                os.path.join(os.path.dirname(fichier), inclus)
            )
            if candidat in ensemble_fichiers:
                dependances.append(candidat)

        graphe[fichier] = dependances

    return graphe


def tri_topologique(graphe: dict) -> list:
    """
    Trie les fichiers pour que chaque fichier soit migré
    APRÈS les fichiers dont il dépend.

    Exemple : si login.php inclut db.php,
    alors db.php sera migré en premier.

    Algorithme de Kahn simplifié. En cas de cycle
    (a inclut b qui inclut a), les fichiers restants
    sont ajoutés à la fin dans l'ordre alphabétique.
    """
    ordre = []
    restants = dict(graphe)  # copie

    while restants:
        # Fichiers dont toutes les dépendances sont déjà migrées
        prets = [
            f for f, deps in restants.items()
            if all(d in ordre for d in deps)
        ]

        if not prets:
            # Cycle détecté → on force l'ordre alphabétique
            print("⚠️  Cycle de dépendances détecté, "
                  "ordre alphabétique appliqué aux fichiers restants")
            ordre.extend(sorted(restants.keys()))
            break

        for f in sorted(prets):
            ordre.append(f)
            del restants[f]

    return ordre


# ═════════════════════════════════════════════════════
# ÉTAPE 2bis — ANALYSE DES USAGES INTER-FICHIERS
# ═════════════════════════════════════════════════════

def analyser_usages_champs(fichiers: list) -> dict:
    """
    Passe d'analyse PRÉALABLE sur tout le projet :
    pour chaque fonction, recense les CHAMPS que ses appelants
    utilisent sur son résultat.

    Exemple : si login.php contient
        $user = getUserByEmail($email);
        if ($user["password"] == ...)
    alors le résultat contiendra :
        {"getUserByEmail": {"password"}}

    Cette info est injectée dans le prompt du Développeur pour
    que les modèles de données générés incluent TOUS les champs
    dont les appelants auront besoin — sans elle, le Développeur
    génère db.py avant de savoir ce que login.py utilisera.
    """
    # 1. Recenser toutes les fonctions définies dans le projet
    noms_fonctions = set()
    contenus = {}
    for fichier in fichiers:
        with open(fichier, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
        contenus[fichier] = code
        noms_fonctions.update(re.findall(r"function\s+(\w+)\s*\(", code))

    # 2. Pour chaque fonction, chercher dans TOUS les fichiers :
    #    $variable = nomFonction(...) puis $variable["champ"]
    #    ou $variable->champ
    usages = {}
    for nom in noms_fonctions:
        champs = set()
        for code in contenus.values():
            # Variables qui reçoivent le résultat de la fonction
            variables = re.findall(
                rf"\$(\w+)\s*=\s*{re.escape(nom)}\s*\(", code
            )
            for var in variables:
                # Accès tableau : $user["password"] ou $user['password']
                champs.update(re.findall(
                    rf"\${re.escape(var)}\s*\[\s*[\"'](\w+)[\"']\s*\]",
                    code
                ))
                # Accès objet : $user->password
                champs.update(re.findall(
                    rf"\${re.escape(var)}->(\w+)", code
                ))
        if champs:
            usages[nom] = champs

    return usages



# ═════════════════════════════════════════════════════
# ÉTAPE 3 — CONTEXTE PARTAGÉ ENTRE FICHIERS
# ═════════════════════════════════════════════════════

def formater_contexte(contexte_projet: dict) -> str:
    """
    Transforme le dictionnaire des modules déjà migrés
    en texte lisible pour le prompt du LLM.

    contexte_projet = {
        "db.py": ["get_connection(host, user)"],
        "utils.py": ["hash_password(pwd)", "send_email(to)"]
    }
    """
    if not contexte_projet:
        return ""

    lignes = []
    for module, fonctions in contexte_projet.items():
        lignes.append(f"- {module} : {', '.join(fonctions)}")
    return "\n".join(lignes)


# ═════════════════════════════════════════════════════
# ÉTAPE 4 — MIGRATION D'UN SEUL FICHIER
# (ton pipeline existant, transformé en fonction)
# ═════════════════════════════════════════════════════

def migrer_fichier(
    chemin_php: str,
    contexte_projet: dict,
    max_iterations: int = 5,
    usages_champs: dict = None,
    feedback_projet: str = ""
) -> dict:
    """
    Migre UN fichier PHP en passant par les 6 agents,
    avec la boucle corrective du Réviseur.
    Retourne le code Python final + les rapports.

    usages_champs : résultat de analyser_usages_champs() —
    indique quels champs les appelants utilisent sur le
    résultat de chaque fonction (analyse projet préalable).

    feedback_projet : diagnostic de la vérification de
    cohérence (boucle corrective NIVEAU PROJET) — quand le
    fichier généré précédemment était incohérent (fonction
    dupliquée, import cassé...), ce texte est injecté dans
    le prompt pour que la régénération corrige le problème.
    """
    usages_champs = usages_champs or {}
    nom_fichier = os.path.basename(chemin_php)
    print("\n" + "█" * 60)
    print(f"█  FICHIER : {nom_fichier}")
    print("█" * 60)

    with open(chemin_php, "r", encoding="utf-8", errors="ignore") as f:
        code_php = f.read()

    # ── Agent Analyste ──
    rapport_analyste = analyser_code_php(code_php)
    print(f"  Analyste : {rapport_analyste['metriques']['nombre_fonctions']} "
          f"fonction(s), "
          f"{rapport_analyste['metriques'].get('nombre_classes', 0)} "
          f"classe(s), "
          f"{rapport_analyste['metriques']['nombre_failles']} faille(s)")

    # ── Agent Architecte ──
    plan = planifier_migration(rapport_analyste, code_php)
    invariants = plan.get("invariants_a_preserver", [])
    failles = plan.get("priorites_securite", [])

    contexte_txt = formater_contexte(contexte_projet)

    resultat_fichier = {
        "fichier_source": nom_fichier,
        "modules": [],
        "fonctions_migrees": []
    }

    # ── Contexte INTRA-FICHIER ──
    # Les modules d'un même fichier .php sont assemblés dans le
    # MÊME fichier .py final. Un module généré après un autre
    # (ex: Admin après User) doit donc utiliser ses prédécesseurs
    # DIRECTEMENT — ni les importer (auto-import circulaire), ni
    # les redéfinir (définition dupliquée). On tient à jour la
    # liste des modules déjà générés dans CE fichier et on
    # l'injecte dans le prompt avec la consigne adaptée.
    modules_meme_fichier = []   # ex: ["User (classe, méthodes : obtenir_nom)"]
    # Noms Python réellement définis par les modules déjà générés de ce
    # fichier : ils sont légitimement utilisables par les suivants
    # (class Admin(User)) et ne doivent pas être signalés "non résolus".
    noms_definis_fichier = set()
    # Code Python des modules déjà migrés de ce fichier : un module
    # peut appeler une fonction migrée avant lui (get_user_by_email
    # appelle connect_database). Sans ce contexte, le test
    # d'équivalence échoue sur un NameError qui n'existe pas dans le
    # projet assemblé.
    codes_python_precedents = []
    nom_py = os.path.splitext(nom_fichier)[0]

    # ── Boucle sur les modules du fichier ──
    for module in plan.get("modules", []):
        if module.get("type") == "classe":
            code_php_module = extraire_code_classe(
                code_php, module["nom_original"]
            )
        else:
            code_php_module = extraire_code_module(
                code_php, module["nom_original"]
            )

        # Injection des champs requis par les appelants (analyse
        # projet préalable) — corrige les modèles incomplets :
        # ex. login.php lit $user["password"] → le modèle retourné
        # par get_user_by_email DOIT contenir le champ password.
        contexte_module = contexte_txt

        # Bloc intra-fichier : prioritaire sur la consigne d'import
        # générale (qui ne vaut que pour les AUTRES fichiers).
        if modules_meme_fichier:
            contexte_module += (
                f"\n\nATTENTION — Les éléments suivants sont déjà "
                f"définis PLUS HAUT DANS LE MÊME FICHIER ({nom_py}.py) "
                f"que le code que tu vas générer :\n"
                + "\n".join(f"- {m}" for m in modules_meme_fichier)
                + f"\nUtilise-les DIRECTEMENT par leur nom "
                f"(ex: class Enfant(Parent)). Ne les importe JAMAIS "
                f"(from {nom_py} import ... est INTERDIT : c'est le "
                f"fichier lui-même) et ne les redéfinis JAMAIS."
            )

        if feedback_projet:
            contexte_module += (
                f"\nCORRECTION REQUISE — La version précédente de ce "
                f"fichier présentait des défauts d'intégration détectés "
                f"par l'analyse du projet. Corrige impérativement :\n"
                f"{feedback_projet}"
            )
        # ✅ Invariants rattachés à CE module uniquement.
        # (Un invariant de validatePassword ne doit pas être exigé
        # de sanitizeInput, son voisin de fichier — c'était la cause
        # des fausses alertes en vérification formelle et des
        # dérives comportementales introduites par la boucle
        # corrective.) Les invariants sans fonction identifiée
        # (code hors fonction) restent globaux.
        noms_acceptes = {"", module["nom_original"]}
        noms_acceptes.update(module.get("methodes", []))
        invariants_module = [
            inv for inv in invariants
            if inv.get("fonction", "") in noms_acceptes
        ]

        champs = usages_champs.get(module["nom_original"])
        if champs:
            contexte_module += (
                f"\nIMPORTANT — Les appelants de "
                f"{module['nom_original']} utilisent ces champs "
                f"sur son résultat : {', '.join(sorted(champs))}. "
                f"Le modèle/objet retourné par "
                f"{module['nom_python']} DOIT inclure ces champs."
            )
            print(f"  Champs requis par les appelants de "
                  f"{module['nom_original']} : {sorted(champs)}")

        feedback = None
        code_python = None
        decision = None

        # ── Boucle corrective (Réviseur) ──
        etat_module = None
        for iteration in range(1, max_iterations + 1):
            # Mode orchestré : la migration du module est confiée au
            # Manager multi-agents, qui décide lui-même de l'ordre
            # d'activation des agents et gère ses propres itérations.
            # La couche projet ne conserve que ce qui relève du projet :
            # dépendances entre fichiers, contexte partagé, cohérence.
            if MODE_ORCHESTRE:
                from crewai_pipeline import migrer_module_orchestre
                print(f"\n  [orchestration multi-agents] "
                      f"module {module['nom_python']} confié au Manager")
                res = migrer_module_orchestre(
                    code_php_module, module, rapport_analyste,
                    contexte_projet=contexte_module,
                    max_iterations=max_iterations,
                    code_php_complet=code_php,
                    code_python_projet="\n\n".join(codes_python_precedents),
                )
                code_python = res["code_python"]
                decision = res["decision"]
                rapport_testeur = res["rapport_testeur"]
                rapport_auditeur = res["rapport_auditeur"] or {}
                etat_module = res.get("etat_structure")
                journal = res.get("journal") or []
                if journal:
                    print(f"  📖 Journal : {len(journal)} sollicitation(s) "
                          f"d'agent consignée(s)")
                if etat_module:
                    print(f"  📋 Étapes franchies : "
                          + ", ".join(n for n, ok
                                      in etat_module["etapes"].items() if ok))
                    for pa in etat_module.get("points_attention", []):
                        print(f"  ⚠️  {pa}")
                if res["agents_en_echec"]:
                    print(f"  ⚠️  Agents indisponibles : "
                          f"{', '.join(res['agents_en_echec'])}")
                break

            code_python = generer_code_python(
                code_php_module,
                module,
                invariants_module,
                failles,
                contexte_projet=contexte_module,
                feedback=feedback
            )

            # Protection : si le LLM renvoie un code vide ou trivial
            # (réponse tronquée, rate limit sur le dernier appel...),
            # on réessaie une fois avant de continuer. Évite d'écrire
            # un fichier .py vide dans le projet final.
            code_utile = nettoyer_code(code_python)
            lignes_code = [l for l in code_utile.split("\n")
                           if l.strip() and not l.strip().startswith("#")]
            if len(lignes_code) < 2:
                print(f"  ⚠️ Code généré vide/trivial "
                      f"({len(lignes_code)} ligne utile) — nouvelle tentative")
                code_python = generer_code_python(
                    code_php_module, module, invariants_module, failles,
                    contexte_projet=contexte_module, feedback=feedback
                )

            rapport_testeur = agent_testeur(
                code_python, module, invariants_module, failles,
                noms_externes=noms_definis_fichier
            )

            # ── Équivalence comportementale (differential testing)
            # Exécute le PHP original ET le Python généré avec les
            # mêmes entrées, puis compare les comportements.
            rapport_diff = tester_equivalence(
                code_php_module, code_python,
                module["nom_original"], module["nom_python"],
                nb_parametres=max(1, len(module.get("parametres", []))),
                # fichier PHP complet : une fonction qui en appelle une
                # autre du même fichier reste exécutable
                contexte_php=code_php,
                contexte_python="\n\n".join(codes_python_precedents),
            )
            if rapport_diff["statut"] == "teste":
                print(f"  Équivalence comportementale : "
                      f"{rapport_diff['score_equivalence']*100:.0f}% "
                      f"({rapport_diff['cas_equivalents']}"
                      f"/{rapport_diff['cas_testes']} cas)")
                for div in rapport_diff["divergences"]:
                    print(f"    ⚠️ Divergence sur "
                          f"{repr(div['entree'])[:40]} : "
                          f"PHP={str(div.get('php'))[:40]} / "
                          f"Python={str(div.get('python'))[:40]}")
                # Le score d'équivalence pèse 30% du score fonctionnel
                rapport_testeur["score_fonctionnel"] = (
                    rapport_testeur["score_fonctionnel"] * 0.7
                    + rapport_diff["score_equivalence"] * 0.3
                )
                rapport_testeur["equivalence_comportementale"] = rapport_diff
            elif rapport_diff["statut"] == "php_absent":
                print("  Équivalence comportementale : sautée "
                      "(PHP non installé)")
            else:
                print("  Équivalence comportementale : non testable "
                      "(fonction avec effets de bord — BDD, fichiers...)")

            # ── Vérification FORMELLE par exécution symbolique
            # (CrossHair + Z3) : les invariants sont traduits en
            # propriétés logiques prouvées pour TOUTES les entrées.
            rapport_formel = verifier_formellement(
                code_python, invariants_module, module
            )
            if rapport_formel["statut"] == "teste":
                for prop in rapport_formel["proprietes"]:
                    symbole = "✅ PROUVÉE" if prop["statut"] == "prouvee" \
                        else "❌ RÉFUTÉE"
                    print(f"  Vérification formelle : {symbole} — "
                          f"{prop['libelle']}")
                    if prop["contre_exemple"]:
                        print(f"     Contre-exemple Z3 : "
                              f"{prop['contre_exemple'][:80]}")
                # Une propriété réfutée pèse sur le score fonctionnel
                rapport_testeur["score_fonctionnel"] = (
                    rapport_testeur["score_fonctionnel"] * 0.85
                    + rapport_formel["score_formel"] * 0.15
                )
                rapport_testeur["verification_formelle"] = rapport_formel
            elif rapport_formel["statut"] == "crosshair_absent":
                print("  Vérification formelle : sautée "
                      "(CrossHair non installé — pip install crosshair-tool)")
            elif rapport_formel["statut"] == "aucune_propriete":
                print("  Vérification formelle : aucun invariant "
                      "traduisible en propriété pour ce module")
            else:
                print(f"  Vérification formelle : "
                      f"{rapport_formel['statut']} "
                      f"({rapport_formel.get('raison', '')})")

            # ── Réconciliation : la preuve formelle fait foi
            types_prouves = set()
            if rapport_formel.get("statut") == "teste":
                types_prouves = _types_invariants_prouves(rapport_formel)
                if types_prouves:
                    _reconcilier_testeur(rapport_testeur, types_prouves,
                                         rapport_diff, rapport_formel)

            rapport_auditeur = agent_auditeur(
                code_python, invariants_module, module
            )
            if types_prouves:
                _reconcilier_auditeur(rapport_auditeur, types_prouves)
            decision = agent_reviseur(
                rapport_testeur,
                rapport_auditeur,
                module,
                iteration_actuelle=iteration,
                max_iterations=max_iterations,
                feedback_precedent=feedback,
                rapport_differentiel=rapport_diff,
                rapport_formel=rapport_formel,
            )

            if decision["decision"] == "LIVRER":
                break
            if decision["decision"] == "ARRET_ECHEC":
                break
            # ITERER ou REANALYSE_COMPLETE → on récupère
            # le feedback et on régénère
            feedback = decision.get("feedback")

        codes_python_precedents.append(nettoyer_code(code_python))

        resultat_fichier["modules"].append({
            "nom_python": module["nom_python"],
            "code_python": nettoyer_code(code_python),
            "decision_finale": decision["decision"],
            "score_final": decision["score_compose"],
            "iterations": decision["iteration"],
            "categorie_echec": decision.get("categorie_echec"),
            "equivalence": rapport_testeur.get(
                "equivalence_comportementale"
            ),
            "verification_formelle": rapport_testeur.get(
                "verification_formelle"
            ),
            # État structuré du module : étapes franchies, tentatives,
            # agents indisponibles et points d'attention. Présent
            # uniquement en mode orchestré.
            "etat_structure": etat_module,
        })

        # Signature pour le contexte des fichiers suivants
        # ET pour les modules suivants de CE MÊME fichier
        signatures_module = []
        if module.get("type") == "classe":
            if module.get("cible_migration") == "fonctions_module":
                # Classe refactorée en FONCTIONS : annoncer chaque
                # fonction individuellement (il n'existe AUCUN objet
                # portant le nom de la classe). Sinon les fichiers
                # suivants tentent d'importer un nom inexistant.
                for meth in module.get("methodes_python", []):
                    signatures_module.append(f"{meth}()")
            else:
                # Classe Python fidèle : annoncer la classe + méthodes
                methodes = ", ".join(module.get("methodes_python", []))
                signatures_module.append(
                    f"{module['nom_python']} (classe, méthodes : {methodes})"
                )
        else:
            params = ", ".join(
                p.replace("$", "") for p in module.get("parametres", [])
            )
            signatures_module.append(
                f"{module['nom_python']}({params})"
            )

        resultat_fichier["fonctions_migrees"].extend(signatures_module)
        modules_meme_fichier.extend(signatures_module)

        # Mémoriser les noms Python définis au niveau module par ce
        # code, pour que les modules suivants du même fichier puissent
        # les utiliser sans être accusés d'utiliser un nom inconnu.
        try:
            import ast as _ast
            for _n in _ast.walk(_ast.parse(nettoyer_code(code_python))):
                if isinstance(_n, (_ast.FunctionDef, _ast.AsyncFunctionDef,
                                   _ast.ClassDef)):
                    noms_definis_fichier.add(_n.name)
                elif isinstance(_n, _ast.Assign):
                    for _c in _n.targets:
                        if isinstance(_c, _ast.Name):
                            noms_definis_fichier.add(_c.id)
        except SyntaxError:
            pass

    return resultat_fichier


# ═════════════════════════════════════════════════════
# ÉTAPE 6 — VÉRIFICATION DE COHÉRENCE DU PROJET
# ═════════════════════════════════════════════════════

def verifier_coherence_projet(dossier_sortie: str) -> dict:
    """
    Vérifie que le projet Python généré est cohérent :
    chaque `from module import nom` doit correspondre à un
    nom réellement défini dans le module généré.

    C'est la vérification d'INTÉGRATION : les fichiers ne sont
    pas seulement corrects individuellement, ils fonctionnent
    ENSEMBLE.
    """
    import ast

    resultat = {
        "imports_valides": [],
        "imports_casses": [],
        "coherent": True
    }

    # 1. Recenser ce que chaque module définit réellement
    definitions = {}   # {"db": {"get_user", "User", ...}}
    signatures = {}    # {"db": {"get_user": (min_args, max_args)}}
    arbres = {}
    for nom in os.listdir(dossier_sortie):
        if not nom.endswith(".py"):
            continue
        module = nom[:-3]
        chemin = os.path.join(dossier_sortie, nom)
        with open(chemin, "r", encoding="utf-8") as f:
            code = f.read()
        try:
            arbre = ast.parse(code)
        except SyntaxError as e:
            resultat["imports_casses"].append({
                "module": module,
                "erreur": f"Erreur de syntaxe : {e}"
            })
            resultat["coherent"] = False
            continue
        arbres[module] = arbre
        noms = set()
        doublons = set()
        sigs = {}
        for noeud in arbre.body:   # définitions au niveau module
            if isinstance(noeud, (ast.FunctionDef,
                                  ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                if noeud.name in noms:
                    doublons.add(noeud.name)   # ← définie 2 fois !
                noms.add(noeud.name)
                # Signature : nb d'arguments min et max
                if isinstance(noeud, (ast.FunctionDef,
                                      ast.AsyncFunctionDef)):
                    args = noeud.args
                    positionnels = (len(args.posonlyargs)
                                    + len(args.args))
                    minimum = positionnels - len(args.defaults)
                    maximum = (None if args.vararg
                               else positionnels)
                    sigs[noeud.name] = (minimum, maximum)
            elif isinstance(noeud, ast.Assign):
                for cible in noeud.targets:
                    if isinstance(cible, ast.Name):
                        noms.add(cible.id)
        definitions[module] = noms
        signatures[module] = sigs

        # Signaler les définitions dupliquées (la 2ème écrase
        # la 1ère silencieusement en Python !)
        for nom_double in doublons:
            resultat["imports_casses"].append({
                "module": f"{module}.py",
                "import": f"définition dupliquée : {nom_double}",
                "erreur": f"'{nom_double}' est défini plusieurs fois "
                          f"dans {module}.py — garde UNE SEULE définition. "
                          f"S'il est déjà défini plus haut dans ce même "
                          f"fichier, utilise-le directement (sans "
                          f"l'importer ni le redéfinir)"
            })
            resultat["coherent"] = False

    # 2. Vérifier les imports internes au projet
    for module, arbre in arbres.items():
        imports_locaux = {}   # {nom_utilisé: (module_source, nom)}
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.ImportFrom):
                source = noeud.module

                # AUTO-IMPORT : un fichier qui s'importe LUI-MÊME
                # (from utilisateurs import User DANS utilisateurs.py).
                # L'élément est défini dans ce même fichier : l'import
                # est circulaire et inutile → défaut d'intégration.
                if source == module:
                    for alias in noeud.names:
                        resultat["imports_casses"].append({
                            "module": f"{module}.py",
                            "import": f"from {source} import {alias.name}",
                            "erreur": f"auto-import : '{alias.name}' est "
                                      f"défini dans {module}.py lui-même — "
                                      f"utilise-le directement, sans "
                                      f"l'importer ni le redéfinir"
                        })
                    resultat["coherent"] = False
                    continue

                # Import RELATIF (from .models import ...) :
                # le module doit exister dans le projet généré,
                # sinon c'est une hallucination du LLM !
                if noeud.level and noeud.level > 0:
                    if source not in definitions:
                        for alias in noeud.names:
                            resultat["imports_casses"].append({
                                "module": f"{module}.py",
                                "import": f"from .{source} "
                                          f"import {alias.name}",
                                "erreur": f"Le module '.{source}' "
                                          f"n'existe pas dans le projet "
                                          f"(import halluciné par le LLM)"
                            })
                        resultat["coherent"] = False
                        continue

                if source not in definitions:
                    # Import depuis un module au nom manifestement
                    # inventé par le LLM (placeholder). Ces noms ne
                    # correspondent ni au projet ni à une bibliothèque
                    # réelle → import cassé à l'exécution.
                    noms_fantomes = {
                        "votre_module", "your_module", "module",
                        "mon_module", "nom_du_module", "module_name",
                        "the_module", "some_module"
                    }
                    if source in noms_fantomes:
                        for alias in noeud.names:
                            resultat["imports_casses"].append({
                                "module": f"{module}.py",
                                "import": f"from {source} import {alias.name}",
                                "erreur": f"Le module '{source}' est un nom "
                                          f"placeholder inventé par le LLM — "
                                          f"import invalide"
                            })
                        resultat["coherent"] = False
                    continue   # sinon import externe (fastapi...) → ignoré
                for alias in noeud.names:
                    if alias.name in definitions[source]:
                        resultat["imports_valides"].append(
                            f"{module}.py : from {source} "
                            f"import {alias.name}"
                        )
                        imports_locaux[alias.asname or alias.name] = (
                            source, alias.name
                        )
                    else:
                        resultat["imports_casses"].append({
                            "module": f"{module}.py",
                            "import": f"from {source} import {alias.name}",
                            "erreur": f"'{alias.name}' n'est pas défini "
                                      f"dans {source}.py",
                            "definitions_disponibles":
                                sorted(definitions[source])[:10]
                        })
                        resultat["coherent"] = False

        # 3. Vérifier les SIGNATURES : chaque appel à une fonction
        # importée doit fournir le bon nombre d'arguments
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Call)
                    and isinstance(noeud.func, ast.Name)
                    and noeud.func.id in imports_locaux):
                source, nom_fonction = imports_locaux[noeud.func.id]
                sig = signatures.get(source, {}).get(nom_fonction)
                if sig is None:
                    continue
                minimum, maximum = sig
                fournis = (len(noeud.args)
                           + len([k for k in noeud.keywords if k.arg]))
                if fournis < minimum or (
                        maximum is not None and fournis > maximum):
                    attendu = (f"{minimum}" if minimum == maximum
                               else f"{minimum} à "
                                    f"{maximum if maximum else '∞'}")
                    resultat["imports_casses"].append({
                        "module": f"{module}.py",
                        "import": f"appel {nom_fonction}(...) "
                                  f"avec {fournis} argument(s)",
                        "erreur": f"{nom_fonction}() défini dans "
                                  f"{source}.py attend {attendu} "
                                  f"argument(s), mais l'appel en "
                                  f"fournit {fournis}"
                    })
                    resultat["coherent"] = False

    return resultat



def migrer_projet(
    chemin_projet: str,
    dossier_sortie: str = "outputs_projet",
    max_iterations: int = 5
) -> dict:
    """
    Point d'entrée principal : migre une application
    PHP complète vers un projet Python.
    """
    print("=" * 60)
    print("SMAML — MIGRATION D'APPLICATION COMPLÈTE")
    print("=" * 60)

    # 1. Préparer (ZIP → dossier)
    dossier = preparer_projet(chemin_projet)

    # 2. Lister les fichiers PHP
    fichiers = lister_fichiers_php(dossier)
    print(f"\n{len(fichiers)} fichier(s) PHP trouvé(s) :")
    for f in fichiers:
        print(f"  - {os.path.relpath(f, dossier)}")

    if not fichiers:
        raise ValueError("Aucun fichier PHP dans ce projet !")

    # 3. Graphe de dépendances + ordre de migration
    graphe = construire_graphe(fichiers)
    ordre = tri_topologique(graphe)

    # 3bis. Analyse préalable des usages inter-fichiers :
    # quels champs chaque appelant utilise sur le résultat
    # de chaque fonction du projet
    usages_champs = analyser_usages_champs(fichiers)
    if usages_champs:
        print(f"\nUsages de champs détectés (analyse projet) :")
        for fonction, champs in usages_champs.items():
            print(f"  - {fonction} → champs utilisés par les "
                  f"appelants : {sorted(champs)}")

    print(f"\nOrdre de migration (dépendances d'abord) :")
    for i, f in enumerate(ordre, 1):
        deps = [os.path.basename(d) for d in graphe[f]]
        deps_txt = f" (dépend de : {', '.join(deps)})" if deps else ""
        print(f"  {i}. {os.path.basename(f)}{deps_txt}")

    # 4. Migrer fichier par fichier
    # Nettoyer le dossier de sortie AVANT de migrer : sinon des
    # fichiers .py d'un run précédent (ex. login.py d'un autre
    # projet) restent et faussent la vérification de cohérence
    # (imports vers des modules qui n'appartiennent pas à CE projet).
    if os.path.isdir(dossier_sortie):
        for ancien in os.listdir(dossier_sortie):
            if ancien.endswith((".py", ".json", ".txt")):
                try:
                    os.remove(os.path.join(dossier_sortie, ancien))
                except OSError:
                    pass
    os.makedirs(dossier_sortie, exist_ok=True)
    contexte_projet = {}   # {nom_module.py: [signatures]}
    rapport_global = {
        "fichiers_migres": [],
        "statistiques": {
            "total_fichiers": len(fichiers),
            "fichiers_livres": 0,
            "fichiers_en_echec": 0
        }
    }

    def traiter_fichier(chemin_php: str, feedback_projet: str = "") -> dict:
        """
        Traite UN fichier : migration + assemblage + écriture
        sur disque. Retourne l'entrée de rapport correspondante.
        Réutilisée par la boucle principale ET par la boucle
        corrective au niveau projet.
        """
        resultat = migrer_fichier(
            chemin_php, contexte_projet, max_iterations,
            usages_champs=usages_champs,
            feedback_projet=feedback_projet
        )

        nom_py = os.path.splitext(
            os.path.basename(chemin_php)
        )[0] + ".py"

        blocs = []
        tout_livre = True
        for m in resultat["modules"]:
            blocs.append(
                f"# ── {m['nom_python']} "
                f"(score {m['score_final']:.1f}%, "
                f"{m['iterations']} itération(s)) ──\n"
                f"{m['code_python']}"
            )
            if m["decision_finale"] != "LIVRER":
                tout_livre = False

        contenu = (
            f'"""\nMigré automatiquement par SMAML depuis '
            f'{resultat["fichier_source"]}\n"""\n\n'
            + "\n\n\n".join(blocs) + "\n"
        )

        with open(
            os.path.join(dossier_sortie, nom_py),
            "w", encoding="utf-8"
        ) as f:
            f.write(contenu)

        # Mettre à jour le contexte pour les fichiers suivants
        contexte_projet[nom_py] = resultat["fonctions_migrees"]

        return {
            "source": resultat["fichier_source"],
            "cible": nom_py,
            "statut": "livré" if tout_livre else "partiel",
            "modules": [
                {k: v for k, v in m.items() if k != "code_python"}
                for m in resultat["modules"]
            ]
        }

    for chemin_php in ordre:
        entree = traiter_fichier(chemin_php)
        rapport_global["fichiers_migres"].append(entree)
        if entree["statut"] == "livré":
            rapport_global["statistiques"]["fichiers_livres"] += 1
        else:
            rapport_global["statistiques"]["fichiers_en_echec"] += 1

    # 5. Vérification de cohérence inter-fichiers
    #    AVEC BOUCLE CORRECTIVE AU NIVEAU PROJET :
    #    si un défaut d'intégration est détecté (fonction
    #    dupliquée, import cassé, signature incompatible...),
    #    le fichier fautif est RÉGÉNÉRÉ avec le diagnostic
    #    injecté dans le prompt, puis on re-vérifie.
    def afficher_coherence(coherence):
        for imp in coherence["imports_valides"]:
            print(f"  ✅ {imp}")
        for casse in coherence["imports_casses"]:
            print(f"  ❌ {casse.get('module', '')} : "
                  f"{casse.get('import', casse.get('erreur', ''))}")
            if "definitions_disponibles" in casse:
                print(f"     → {casse['erreur']}")
                print(f"     → Définitions disponibles : "
                      f"{casse['definitions_disponibles']}")

    correspondance = {   # db.py → chemin de db.php
        os.path.splitext(os.path.basename(c))[0] + ".py": c
        for c in ordre
    }
    rapport_global["corrections_projet"] = []
    max_corrections_projet = 2

    for tentative in range(max_corrections_projet + 1):
        print("\n" + "=" * 60)
        print("VÉRIFICATION DE COHÉRENCE DU PROJET"
              + (f" — après correction {tentative}" if tentative else ""))
        print("=" * 60)
        coherence = verifier_coherence_projet(dossier_sortie)
        afficher_coherence(coherence)

        if coherence["coherent"]:
            print("  ✅ Projet cohérent : tous les imports internes "
                  "sont valides")
            break

        if tentative == max_corrections_projet:
            print("  ⚠️  Projet toujours incohérent après "
                  f"{max_corrections_projet} correction(s) — "
                  "défauts documentés dans le rapport")
            break

        # ── Boucle corrective projet : régénérer les fichiers fautifs
        print("\n  🔁 BOUCLE CORRECTIVE PROJET — régénération des "
              "fichiers présentant des défauts d'intégration...")

        # Grouper les défauts par fichier fautif
        defauts_par_fichier = {}
        for casse in coherence["imports_casses"]:
            cible = casse.get("module", "")
            if not cible.endswith(".py"):
                continue
            defauts_par_fichier.setdefault(cible, []).append(
                f"- {casse.get('import', '')} : {casse.get('erreur', '')}"
            )

        for cible, defauts in defauts_par_fichier.items():
            chemin_php = correspondance.get(cible)
            if not chemin_php:
                continue
            feedback = "\n".join(defauts)
            print(f"\n  Régénération de {cible} "
                  f"(depuis {os.path.basename(chemin_php)}) avec "
                  f"{len(defauts)} défaut(s) à corriger :")
            for d in defauts:
                print(f"    {d}")

            nouvelle_entree = traiter_fichier(
                chemin_php, feedback_projet=feedback
            )

            # Remplacer l'entrée du rapport pour ce fichier
            for i, e in enumerate(rapport_global["fichiers_migres"]):
                if e["cible"] == cible:
                    rapport_global["fichiers_migres"][i] = nouvelle_entree
                    break

            rapport_global["corrections_projet"].append({
                "tentative": tentative + 1,
                "fichier": cible,
                "defauts_corriges": defauts
            })

    rapport_global["coherence_projet"] = coherence

    # 6. Générer requirements.txt
    with open(
        os.path.join(dossier_sortie, "requirements.txt"),
        "w", encoding="utf-8"
    ) as f:
        f.write("fastapi\nuvicorn\npydantic\nsqlalchemy\n")

    # 6. Sauvegarder le rapport global
    with open(
        os.path.join(dossier_sortie, "rapport_migration.json"),
        "w", encoding="utf-8"
    ) as f:
        # default=str : le code généré peut produire des valeurs non
        # sérialisables (ex: bytes de bcrypt) qui remontent dans les
        # divergences du rapport — on les convertit en texte plutôt
        # que de faire échouer tout le projet.
        json.dump(rapport_global, f, indent=2, ensure_ascii=False,
                  default=str)

    # Résumé final
    stats = rapport_global["statistiques"]
    print("\n" + "=" * 60)
    print("MIGRATION DU PROJET TERMINÉE")
    print("=" * 60)
    print(f"  Fichiers migrés  : {stats['fichiers_livres']}"
          f"/{stats['total_fichiers']}")
    print(f"  {cache_smaml.resume()}")
    print(f"  Résultats dans   : {dossier_sortie}/")

    rapport_global["cache"] = cache_smaml.statistiques()

    # Orchestrateurs réellement utilisés : pour un benchmark, il ne doit
    # y en avoir qu'un. Un mélange est signalé au lieu de passer inaperçu.
    modeles, bascules = set(), 0
    for fichier in rapport_global.get("fichiers_migres", []):
        for module in fichier.get("modules", []):
            etat = module.get("etat_structure") or {}
            if etat.get("modele_orchestrateur"):
                modeles.add(etat["modele_orchestrateur"])
            bascules += len(etat.get("bascules_modele") or [])
    rapport_global["orchestrateurs_utilises"] = sorted(modeles)
    rapport_global["basculements_orchestrateur"] = bascules
    if len(modeles) > 1:
        print(f"  ⚠️  Plusieurs orchestrateurs utilisés : {sorted(modeles)} "
              f"— résultats non comparables pour une mesure.")
    elif modeles:
        print(f"  Orchestrateur    : {next(iter(modeles))}")

    return rapport_global


# ─── LANCEMENT EN LIGNE DE COMMANDE ──────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python pipeline_projet.py <app.zip | dossier>")
        sys.exit(1)

    migrer_projet(sys.argv[1])