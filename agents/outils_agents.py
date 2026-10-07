"""
Outils des agents — SMAML
==========================
Chaque agent dispose d'UN outil. L'outil lit ce dont il a besoin dans
l'espace partagé, fait le travail, et y dépose son résultat selon le
schéma imposé. Aucun outil ne transmet de données directement à un
autre agent.

Les phases (conception à 4 phases)
----------------------------------
    Phase 1 — Réception          Manager
    Phase 2 — Analyse du code    Analyste, Architecte
    Phase 3 — Conversion         Développeur
    Phase 4 — Vérification       Testeur, Comparateur, Vérificateur,
                                 Auditeur, puis Réviseur en dernier

Le Manager reste libre de l'ordre des agents. Mais chaque outil
VÉRIFIE ses prérequis et REFUSE d'agir si on n'en est pas à sa phase :
le Manager ne peut donc ni sauter une étape, ni conclure sans les
quatre vérifications (option A : les phases sont imposées par les
refus des agents, sans ordre écrit dans le programme).

Les mêmes outils servent à TOUS les coordinateurs — Manager principal,
Manager de secours, coordinateur fixe : quel que soit celui qui
organise, le travail et les vérifications sont identiques.
"""

from __future__ import annotations

import copy

from espace_partage import EspaceModule

PHASES = {1: "Réception", 2: "Analyse du code", 3: "Conversion du code",
          4: "Vérification"}

VERIFICATIONS = ("rapport_testeur", "rapport_differentiel",
                 "rapport_formel", "rapport_auditeur")

# produit → (phase, agent, prérequis)
ETAPES_MODULE = {
    "code_python":          (3, "Développeur", ("module",)),
    "rapport_testeur":      (4, "Testeur", ("code_python",)),
    "rapport_differentiel": (4, "Comparateur", ("code_python",)),
    "rapport_formel":       (4, "Vérificateur de propriétés", ("code_python",)),
    "rapport_auditeur":     (4, "Auditeur", ("code_python",)),
    "decision":             (4, "Réviseur", VERIFICATIONS),
}


class PrerequisManquant(Exception):
    """L'agent refuse : on n'en est pas encore à sa phase."""


class DejaFait(Exception):
    """L'agent refuse : son travail est déjà disponible et à jour."""


def prerequis_manquants(espace: EspaceModule, produit: str) -> list:
    _, _, prerequis = ETAPES_MODULE[produit]
    return [p for p in prerequis if p not in espace]


def etapes_restantes(espace: EspaceModule) -> list:
    """Ce qui reste à faire pour ce module, dans l'ordre des phases."""
    if espace.get("correction_demandee"):
        return list(ETAPES_MODULE)
    return [p for p in ETAPES_MODULE if p not in espace]


# ═══ PRÉPARATION D'UN MODULE (fin de la phase 2) ════════

def preparer_module(espace: EspaceModule, module: dict, contexte: dict):
    """
    Dépose, au nom de l'Architecte, le module à migrer et tout ce dont
    les agents auront besoin. Sans effet si c'est déjà fait : après une
    panne, la préparation n'est jamais refaite.
    """
    if "module" in espace:
        return
    espace.deposer("module", module, "Architecte",
                   hypotheses_faites=module.get("hypotheses_faites", []),
                   points_incertains=module.get("points_incertains", []),
                   points_attention=module.get("points_attention", []))
    for cle in ("code_php_module", "code_php_fichier", "invariants",
                "failles", "contexte_projet", "code_python_projet",
                "noms_externes", "max_iterations", "sans_boucle", "dossier_python"):
        espace[cle] = contexte.get(cle)
    espace["iteration"] = 1
    espace["correction_demandee"] = False
    espace["scores_successifs"] = []


# ═══ L'OUTIL DE CHAQUE AGENT ════════════════════════════

def _developpeur(espace: EspaceModule) -> str:
    import agent_developpeur as dev

    feedback = espace.get("feedback")
    module = espace["module"]
    def generer():
        return dev.generer_code_python(
            espace["code_php_module"], module,
            espace.get("invariants") or [], espace.get("failles") or [],
            contexte_projet=espace.get("contexte_projet") or "",
            feedback=feedback)

    brut = generer()
    # Réponse vide ou tronquée : une seule nouvelle tentative.
    utiles = [l for l in dev.nettoyer_code(brut).splitlines()
              if l.strip() and not l.strip().startswith("#")]
    if len(utiles) < 2:
        brut = generer()

    meta = dev.extraire_metadonnees(brut)
    code = dev.nettoyer_code(brut)
    appel = dict(getattr(dev, "DERNIER_APPEL", {}) or {})
    espace.deposer("code_python", code, "Développeur",
                   dependances=dev.extraire_dependances(code),
                   hypotheses_faites=meta["hypotheses_faites"],
                   points_incertains=meta["points_incertains"],
                   points_attention=meta["points_attention"])
    espace["modele_generation"] = {k: appel.get(k) for k in
                                   ("fournisseur", "modele", "bascule")}
    # Le coût cumulé de toutes les générations du module (corrections comprises).
    cumul = dict(espace.get("tokens_generation") or {"entree": 0, "sortie": 0, "appels": 0})
    for cle in ("entree", "sortie"):
        cumul[cle] += (appel.get("tokens") or {}).get(cle, 0)
    cumul["appels"] += 1
    espace["tokens_generation"] = cumul
    espace["correction_demandee"] = False
    # Invalidation automatique : les vérifications portaient sur
    # l'ancien code. Elles restent consultables dans l'historique.
    for cle in VERIFICATIONS + ("rapport_juge", "decision"):
        if cle in espace:
            espace.invalider(cle, raison="nouveau code déposé")
    message = (f"Code Python déposé pour {module.get('nom_python')} "
               f"(version {espace.versions('code_python')}, "
               f"{len(code.splitlines())} lignes).")
    if meta["points_incertains"]:
        message += " Points incertains : " + " | ".join(meta["points_incertains"][:3])
    return message


def _testeur(espace: EspaceModule) -> str:
    from agent_testeur import agent_testeur
    rapport = agent_testeur(espace["code_python"], espace["module"],
                            espace.get("invariants") or [],
                            espace.get("failles") or [],
                            noms_externes=set(espace.get("noms_externes") or []))
    espace.deposer("rapport_testeur", rapport, "Testeur", points_attention=[])
    return f"Test fonctionnel : {rapport.get('score_fonctionnel', 0) * 100:.0f} %."


def _comparateur(espace: EspaceModule) -> str:
    from agent_testeur_differentiel import tester_equivalence
    module = espace["module"]
    langage = module.get("langage_source", "php")
    if langage != "php":
        from langages import adaptateur
        disponible, detail = adaptateur(langage).executeur()
        raison = (f"exécution {adaptateur(langage).nom} : "
                  + (detail if not disponible else
                     "harnais de comparaison pas encore réalisé pour ce langage"))
        espace.deposer("rapport_differentiel",
                       {"statut": "non_testable", "raison": raison,
                        "score_equivalence": None},
                       "Comparateur", points_attention=[f"équivalence non testée : {raison}"])
        return f"Équivalence non testable ({raison})."
    try:
        return _comparateur_protege(espace, module, tester_equivalence)
    except (Exception, SystemExit) as erreur:
        # Le Comparateur est un agent NON BLOQUANT : s'il plante, son
        # rapport le dit, et le module continue vers le Réviseur — au lieu
        # d'être abandonné en validation humaine.
        raison = f"le Comparateur a échoué : {type(erreur).__name__} {str(erreur)[:150]}"
        espace.deposer("rapport_differentiel",
                       {"statut": "erreur", "raison": raison, "score_equivalence": None},
                       "Comparateur", points_attention=[raison])
        return f"Équivalence non mesurée ({raison})."


def _comparateur_protege(espace: EspaceModule, module: dict, tester_equivalence) -> str:
    from entrees_ia import generer_entrees_ia
    nb_parametres = max(1, len(module.get("parametres") or []))
    ia = generer_entrees_ia(espace["code_php_module"], module["nom_original"], nb_parametres)
    rapport = tester_equivalence(
        espace["code_php_module"], espace["code_python"],
        module["nom_original"], module["nom_python"],
        nb_parametres=nb_parametres,
        contexte_php=espace.get("code_php_fichier") or "",
        contexte_python=espace.get("code_python_projet") or "",
        entrees_ia=ia.get("entrees"),
        dossier_python=espace.get("dossier_python"))
    rapport["entrees_ia"] = {k: v for k, v in ia.items() if k != "entrees"} | \
        {"nombre": len(ia.get("entrees") or [])}
    # Test de mutation : quelles entrées détectent réellement les bugs ?
    import os as _os
    if _os.getenv("SMAML_MUTATION", "1").lower() not in ("0", "false", "non"):
        from agent_testeur_differentiel import generer_cas_de_test
        from mutation import comparer_sources
        rapport["mutation"] = comparer_sources(
            espace["code_python"], module["nom_python"],
            {"fixes": generer_cas_de_test(nb_parametres, False),
             "ia": [e["arguments"] for e in ia.get("entrees") or []]},
            contexte=espace.get("code_python_projet") or "",
            dossier_python=espace.get("dossier_python"))
    attention = []
    if rapport.get("statut") != "teste":
        attention.append(f"équivalence non testée : "
                         f"{rapport.get('raison') or rapport.get('statut')}")
    espace.deposer("rapport_differentiel", rapport, "Comparateur",
                   points_attention=attention)
    if rapport.get("statut") == "teste":
        return f"Équivalence : {rapport.get('lecture') or rapport['score_equivalence']}."
    return f"Équivalence non testable ({rapport.get('statut')})."


def _verificateur(espace: EspaceModule) -> str:
    from agent_verification_formelle import verifier_formellement
    try:
        rapport = verifier_formellement(espace["code_python"],
                                        espace.get("invariants") or [],
                                        espace["module"])
    except (Exception, SystemExit) as erreur:
        # Agent NON BLOQUANT, comme le Comparateur : son échec est rapporté,
        # le module continue.
        rapport = {"statut": "erreur", "proprietes": [], "score_formel": None,
                   "raison": f"{type(erreur).__name__} {str(erreur)[:150]}"}
    espace.deposer("rapport_formel", rapport, "Vérificateur de propriétés",
                   points_attention=[])
    prouvees = [p for p in rapport.get("proprietes", [])
                if p.get("statut") == "prouvee"]
    return f"Propriétés : {len(prouvees)} prouvée(s) ({rapport.get('statut')})."


def _auditeur(espace: EspaceModule) -> str:
    from agent_auditeur import agent_auditeur
    rapport = agent_auditeur(espace["code_python"],
                             espace.get("invariants") or [], espace["module"],
                             rapport_formel=espace.get("rapport_formel"))
    espace.deposer("rapport_auditeur", rapport, "Auditeur", points_attention=[])
    return f"Sécurité : {rapport.get('score_securite_global', 0):.0f} %."


def _reviseur(espace: EspaceModule) -> str:
    from agent_reviseur import agent_reviseur
    from reconciliation import (types_invariants_prouves, reconcilier_testeur,
                                reconcilier_auditeur)

    rt = copy.deepcopy(espace["rapport_testeur"])
    ra = copy.deepcopy(espace["rapport_auditeur"])
    rd = espace["rapport_differentiel"]
    rf = espace["rapport_formel"]

    # Combinaison des mesures, identique à la version précédente :
    # l'équivalence pèse 30 % du fonctionnel, la preuve formelle 15 %.
    if rd.get("statut") == "teste":
        rt["score_fonctionnel"] = (rt["score_fonctionnel"] * 0.7
                                   + rd["score_equivalence"] * 0.3)
        rt["equivalence_comportementale"] = rd
    if rf.get("statut") == "teste":
        rt["score_fonctionnel"] = (rt["score_fonctionnel"] * 0.85
                                   + rf["score_formel"] * 0.15)
        rt["verification_formelle"] = rf
        prouves = types_invariants_prouves(rf)
        if prouves:                       # la preuve formelle fait foi
            reconcilier_testeur(rt, prouves, rd, rf)
            reconcilier_auditeur(ra, prouves)

    # Le Réviseur consulte le LLM juge sur la qualité du code. Le juge
    # ne voit que le PHP et le Python, jamais les rapports des outils.
    from agent_juge import juger
    rapport_juge = juger(espace.get("code_php_module") or "",
                         espace["code_python"])
    espace.deposer("rapport_juge", rapport_juge, "LLM juge",
                   points_attention=[] if rapport_juge.get("statut") == "evalue"
                   else [f"juge non pris en compte : "
                         f"{rapport_juge.get('raison', rapport_juge.get('statut'))}"])

    iteration = espace.get("iteration", 1)
    maximum = espace.get("max_iterations") or 5
    decision = agent_reviseur(rt, ra, espace["module"],
                              iteration_actuelle=iteration,
                              max_iterations=maximum,
                              feedback_precedent=espace.get("feedback"),
                              rapport_differentiel=rd, rapport_formel=rf,
                              rapport_juge=rapport_juge)

    # Détection de stagnation : deux cycles sans progrès → arrêt.
    scores = list(espace.get("scores_successifs") or [])
    scores.append(decision.get("score_compose", 0.0))
    espace["scores_successifs"] = scores
    if decision["decision"] in ("ITERER", "REANALYSE_COMPLETE") \
            and len(scores) >= 3 and scores[-1] - scores[-3] < 1.0:
        decision["decision"] = "ARRET_ECHEC"
        decision["categorie_echec"] = "limite_structurelle"
        decision["raison"] = ("Absence de progression sur deux cycles : "
                              + " → ".join(f"{s:.1f}%" for s in scores[-3:]))

    espace.deposer("decision", decision, "Réviseur",
                   points_attention=[decision.get("raison", "")]
                   if decision["decision"] != "LIVRER" else [])

    verdict = decision["decision"]
    if verdict in ("LIVRER", "ARRET_ECHEC", "VALIDATION_HUMAINE") \
            or espace.get("sans_boucle"):
        return f"Décision : {verdict} ({decision.get('score_compose', 0):.1f} %)."

    if decision.get("action_recommandee") == "validation_humaine":
        return f"Décision : {verdict} — validation humaine recommandée."

    # Retour en arrière : la correction est demandée au Développeur,
    # ou, sur une limite structurelle, le plan est revu par l'Architecte.
    if decision.get("action_recommandee") == "repasser_architecte":
        from agent_architecte import reviser_module
        erreurs = (decision.get("feedback") or {}).get("erreurs_par_priorite") or []
        nouveau = reviser_module(espace["module"], erreurs)
        espace.deposer("module", nouveau, "Architecte",
                       hypotheses_faites=nouveau.get("hypotheses_faites", []),
                       points_incertains=nouveau.get("points_incertains", []),
                       points_attention=["plan révisé après une limite structurelle"])
    espace["feedback"] = decision.get("feedback")
    espace["iteration"] = iteration + 1
    espace["correction_demandee"] = True
    return (f"Décision : {verdict} — correction demandée "
            f"(itération {iteration + 1}/{maximum}).")


OUTILS = {
    "code_python": _developpeur,
    "rapport_testeur": _testeur,
    "rapport_differentiel": _comparateur,
    "rapport_formel": _verificateur,
    "rapport_auditeur": _auditeur,
    "decision": _reviseur,
}


def realiser(espace: EspaceModule, produit: str) -> str:
    """
    Fait réaliser une étape par son agent, après contrôle de la phase.

    Lève PrerequisManquant si la phase de l'agent n'est pas atteinte,
    DejaFait si son travail est déjà disponible et à jour.
    """
    espace.rafraichir()
    phase, agent, _ = ETAPES_MODULE[produit]
    manquants = prerequis_manquants(espace, produit)
    if manquants:
        raise PrerequisManquant(
            f"{agent} (phase {phase} — {PHASES[phase]}) refuse d'agir : "
            f"il manque {', '.join(manquants)}.")
    correction = espace.get("correction_demandee")
    if produit == "code_python":
        # Régénérer sans demande du Réviseur ne servirait à rien, et
        # invaliderait des vérifications encore valables.
        if "code_python" in espace and not correction:
            raise DejaFait("Le code est déjà disponible et aucune correction "
                           "n'a été demandée par le Réviseur.")
    else:
        # Une correction est en attente : vérifier l'ancien code n'a
        # plus de sens, le Développeur doit d'abord produire le nouveau.
        if correction:
            raise PrerequisManquant(
                f"{agent} refuse d'agir : une correction a été demandée, le "
                f"Développeur doit d'abord produire le nouveau code.")
        if produit in espace:
            raise DejaFait(f"{agent} a déjà déposé un résultat à jour.")
    return OUTILS[produit](espace)