import json
import os


# ═══ NIVEAU DE CONFIANCE ══════════════════════════════
# Un module n'est pas « correct » ou « incorrect » : il est vérifié
# sous quatre angles complémentaires, dont aucun ne suffit seul.
#
#   fonctionnel    — le code s'exécute, les invariants sont présents,
#                    les failles d'origine sont corrigées (Testeur)
#   securite       — aucune faille introduite, protections conservées,
#                    dépendances saines (Auditeur)
#   comportemental — le Python se comporte comme le PHP sur des
#                    entrées réelles (Comparateur)
#   proprietes     — les règles tiennent sur toutes les entrées
#                    explorées symboliquement, pas seulement 15 (Z3)
#
# Un critère non mesurable (fonction non exécutable hors base,
# CrossHair absent) ne pénalise pas le module : son poids est
# redistribué sur les critères réellement mesurés, et l'absence est
# signalée. Le score reste ainsi comparable d'un module à l'autre,
# et l'on sait toujours sur quoi il repose.

POIDS_CRITERES = {
    "fonctionnel": 0.45,
    "securite": 0.30,
    "comportemental": 0.15,
    "proprietes": 0.10,
    # Cinquième critère : la qualité jugée par le LLM juge. Son poids
    # est limité, et il est renormalisé avec les autres : à 0,15, il
    # pèse environ 13 % du score quand les cinq critères sont mesurés.
    "qualite_jugee": float(os.getenv("SMAML_POIDS_JUGE", "0.15")),
}

# Écart entre le juge et les outils au-delà duquel un module que les
# outils livreraient est confié à un humain.
SEUIL_DESACCORD = float(os.getenv("SMAML_SEUIL_DESACCORD", "40"))

# Nombre de corrections accordées au Développeur sur les remarques du juge,
# avant de demander une validation humaine.
CORRECTIONS_JUGE = int(os.getenv("SMAML_CORRECTIONS_JUGE", "2"))


def remarques_du_juge(rapport_juge: dict) -> list:
    """Les critères notés 3 ou moins deviennent des consignes de correction."""
    try:
        from agent_juge import GRILLE
    except ImportError:
        GRILLE = {}
    remarques = []
    for cle, critere in sorted((rapport_juge or {}).get("criteres", {}).items(),
                               key=lambda kv: kv[1].get("note", 5)):
        if critere.get("note", 5) <= 3 and critere.get("justification"):
            titre = GRILLE.get(cle, (cle,))[0]
            remarques.append(f"[{titre}] {critere['justification']}")
    return remarques or ["Améliore la qualité globale du code : le juge l'estime "
                         "nettement inférieure à ce qu'indiquent les tests."]


def verrous_actifs(rapport_testeur: dict, rapport_auditeur: dict,
                   rapport_formel: dict = None) -> list:
    """
    Échecs que RIEN ne peut compenser — et surtout pas le juge : un
    code inexécutable, une propriété réfutée par l'exploration
    symbolique, une faille critique.
    """
    verrous = []
    if not (rapport_testeur.get("syntaxe") or {}).get("syntaxe_valide", True):
        verrous.append("code inexécutable")
    formel = rapport_formel or rapport_testeur.get("verification_formelle") or {}
    if any(p.get("statut") == "refutee" for p in formel.get("proprietes", [])):
        verrous.append("propriété réfutée par Z3")
    if (rapport_auditeur or {}).get("niveau_alerte") == "CRITIQUE":
        verrous.append("faille critique")
    for invariant in invariants_manquants_prouves(rapport_testeur):
        verrous.append(f"garde obligatoire manquante : {invariant['description'][:90]}")
    return verrous


def invariants_manquants_prouves(rapport_testeur: dict) -> list:
    """Invariants obligatoires que le Testeur a prouvés absents par un contre-exemple."""
    invariants = (rapport_testeur or {}).get("invariants") or {}
    prouves_absents = {p.get("invariant") for p in invariants.get("preuves", [])
                       if p.get("verdict") == "manquant"}
    return [i for i in invariants.get("invariants_manquants", [])
            if i.get("obligatoire", True) and i.get("description") in prouves_absents]


# Verrous qui interdisent la LIVRAISON, quel que soit le score. La faille
# critique n'en fait pas partie : l'alerte de l'Auditeur peut être levée
# par la preuve formelle (réconciliation) ; elle ne fait qu'exclure le juge.
def verrous_bloquants(verrous: list) -> list:
    return [v for v in verrous if v != "faille critique"]


def _score_fonctionnel_base(rapport_testeur: dict) -> float:
    """
    Part purement fonctionnelle : syntaxe, invariants, failles.
    On repart des sous-scores du Testeur plutôt que de son score
    global, car celui-ci peut déjà intégrer l'équivalence et la
    vérification formelle — comptées séparément ici.
    """
    syntaxe = rapport_testeur.get("syntaxe", {}) or {}
    invariants = rapport_testeur.get("invariants", {}) or {}
    failles = rapport_testeur.get("failles", {}) or {}
    if "score" not in invariants and "score" not in failles:
        return rapport_testeur.get("score_fonctionnel", 0.0) * 100
    score_syntaxe = 1.0 if syntaxe.get("syntaxe_valide", True) else 0.0
    return (score_syntaxe * 0.3
            + invariants.get("score", 1.0) * 0.4
            + failles.get("score", 1.0) * 0.3) * 100


def calculer_niveau_confiance(rapport_testeur: dict,
                              rapport_auditeur: dict,
                              rapport_differentiel: dict = None,
                              rapport_formel: dict = None,
                              rapport_juge: dict = None,
                              verrous: list = None) -> dict:
    """
    Niveau de confiance du module, détaillé par critère.
    Retourne {"score", "niveau", "criteres", "criteres_non_mesures"}.
    """
    criteres = [
        {"nom": "fonctionnel", "agent": "Testeur",
         "score": _score_fonctionnel_base(rapport_testeur),
         "mesure": True, "raison": ""},
        {"nom": "securite", "agent": "Auditeur",
         "score": (rapport_auditeur or {}).get("score_securite_global", 0.0),
         "mesure": True, "raison": ""},
    ]

    diff = rapport_differentiel or rapport_testeur.get(
        "equivalence_comportementale") or {}
    mesure_diff = diff.get("statut") == "teste"
    criteres.append({
        "nom": "comportemental", "agent": "Comparateur",
        # score_equivalence vaut None quand rien n'a pu être testé
        "score": (diff.get("score_equivalence") or 0.0) * 100,
        "mesure": mesure_diff,
        "raison": "" if mesure_diff else
                  f"équivalence non testée ({diff.get('statut', 'absente')})"})

    formel = rapport_formel or rapport_testeur.get(
        "verification_formelle") or {}
    mesure_formel = formel.get("statut") == "teste"
    criteres.append({
        "nom": "proprietes", "agent": "Vérificateur de propriétés",
        "score": (formel.get("score_formel") or 0.0) * 100,
        "mesure": mesure_formel,
        "raison": "" if mesure_formel else
                  f"aucune propriété vérifiée "
                  f"({formel.get('statut', 'absente')})"})

    # Le juge ne compte que s'il a rendu un jugement exploitable, et
    # JAMAIS en présence d'un verrou : il ne peut pas compenser un code
    # inexécutable, une propriété réfutée ou une faille critique.
    if rapport_juge is not None:
        juge_mesure = rapport_juge.get("statut") == "evalue" and not verrous
        if rapport_juge.get("statut") != "evalue":
            raison = f"juge {rapport_juge.get('statut')} : {rapport_juge.get('raison', '')}"
        elif verrous:
            raison = f"verrou actif ({', '.join(verrous)}) : le juge ne peut pas le lever"
        else:
            raison = ""
        criteres.append({"nom": "qualite_jugee", "agent": "LLM juge",
                         "score": rapport_juge.get("score") or 0.0,
                         "mesure": juge_mesure, "raison": raison})

    # Redistribution du poids des critères non mesurés.
    poids_mesures = sum(POIDS_CRITERES[c["nom"]]
                        for c in criteres if c["mesure"])
    score = 0.0
    for c in criteres:
        if c["mesure"] and poids_mesures:
            c["poids"] = POIDS_CRITERES[c["nom"]] / poids_mesures
            score += c["poids"] * c["score"]
        else:
            c["poids"] = 0.0

    non_mesures = [c["nom"] for c in criteres if not c["mesure"]]
    verifications_manquantes = [n for n in non_mesures if n != "qualite_jugee"]
    # Un critère effondré ne doit pas être noyé par la moyenne : un
    # module dont le comportement diverge massivement du PHP n'est pas
    # « de confiance élevée », même si les trois autres sont bons.
    critique = [c["nom"] for c in criteres if c["mesure"] and c["score"] < 60]

    if score >= 80 and not verifications_manquantes and not critique:
        niveau = "elevee"
    elif score >= 65 and not critique:
        niveau = "moyenne"
    else:
        niveau = "faible"

    return {"score": score, "niveau": niveau, "criteres": criteres,
            "criteres_non_mesures": non_mesures,
            "criteres_critiques": critique}


def calculer_score_compose(
    rapport_testeur: dict,
    rapport_auditeur: dict,
    alpha: float = 0.6,
    beta: float = 0.4
) -> float:
    """
    Calcule le score composé S = alpha * fonctionnel + beta * securite
    """
    score_fonctionnel = rapport_testeur.get("score_fonctionnel", 0.0) * 100
    score_securite = rapport_auditeur.get("score_securite_global", 0.0)

    score_compose = alpha * score_fonctionnel + beta * score_securite
    return score_compose


def identifier_erreurs_prioritaires(
    rapport_testeur: dict,
    rapport_auditeur: dict
) -> list:
    """
    Identifie les erreurs à corriger, classées par priorité.
    Les failles de sécurité CRITICAL/HIGH passent toujours
    avant les erreurs fonctionnelles.
    """
    erreurs = []

    # Priorité 1 — Failles Bandit HIGH/CRITICAL
    failles_bandit = rapport_auditeur.get(
        "dimension_2_bandit", {}
    ).get("failles_detectees", [])
    for f in failles_bandit:
        if f.get("severity") in ["high", "critical"]:
            erreurs.append({
                "priorite": 1,
                "categorie": "securite_critique",
                "description": f.get("description", ""),
                "ligne": f.get("ligne", 0),
                "action": f"Corriger la faille {f.get('type', '')} "
                          f"détectée par Bandit"
            })

    # Priorité 2 — Invariants violés
    invariants_violes = rapport_auditeur.get(
        "dimension_1_invariants", {}
    ).get("invariants_violes", [])
    for inv in invariants_violes:
        erreurs.append({
            "priorite": 2,
            "categorie": "invariant_non_preserve",
            "description": inv.get("description", ""),
            "action": f"Ajouter la vérification : "
                       f"{inv.get('description', '')}"
        })

    # Priorité 3 — Failles fonctionnelles persistantes
    failles_persistantes = rapport_testeur.get(
        "failles", {}
    ).get("failles_persistantes", [])
    for f in failles_persistantes:
        erreurs.append({
            "priorite": 3,
            "categorie": "faille_non_corrigee",
            "description": f"Faille {f.get('faille', '')} "
                            f"({f.get('cwe', '')}) non corrigée",
            "action": "Reformuler le code pour éliminer la faille"
        })

    # Priorité 4 — Erreur de syntaxe
    if not rapport_testeur.get("syntaxe", {}).get("syntaxe_valide", True):
        erreurs.append({
            "priorite": 0,  # Bloquant absolu
            "categorie": "syntaxe_invalide",
            "description": rapport_testeur.get("syntaxe", {}).get("erreur", ""),
            "action": "Corriger l'erreur de syntaxe avant toute autre chose"
        })

    # Trier par priorité (0 = le plus urgent)
    erreurs.sort(key=lambda e: e["priorite"])

    return erreurs


def generer_feedback(erreurs: list, module_info: dict) -> dict:
    """
    Génère un feedback structuré et actionnable
    pour l'Agent Développeur.
    """
    feedback = {
        "module": module_info.get("nom_python", ""),
        "nombre_erreurs": len(erreurs),
        "erreurs_par_priorite": erreurs,
        "instructions": []
    }

    for erreur in erreurs:
        feedback["instructions"].append(
            f"[Priorité {erreur['priorite']}] "
            f"{erreur['categorie']} : {erreur['action']}"
        )

    return feedback


# ═══ CATÉGORISATION DES ÉCHECS ════════════════════════
# Un module non livrable n'échoue pas toujours pour la même raison,
# et la bonne réponse dépend de la nature de l'échec :
#
#   BUG_SIMPLE          — erreurs concrètes et localisées (syntaxe,
#                         faille Bandit, invariant oublié). Le
#                         Développeur sait quoi corriger : on itère.
#   AMBIGUITE           — le code n'est pas livrable mais aucune règle
#                         ne désigne l'erreur : comportement divergent
#                         du PHP sans défaut statique, ou aucune erreur
#                         identifiable. La spécification elle-même est
#                         en cause : un humain doit trancher.
#   LIMITE_STRUCTURELLE — la boucle de correction ne peut plus
#                         progresser : mêmes erreurs d'une itération à
#                         l'autre, ou budget d'itérations épuisé. Le
#                         problème dépasse ce que le feedback résout :
#                         on repasse par l'Architecte pour revoir la
#                         conception ; si le budget est épuisé, il n'y
#                         a plus de marge et un humain reprend.

BUG_SIMPLE = "bug_simple"
AMBIGUITE = "ambiguite"
LIMITE_STRUCTURELLE = "limite_structurelle"

ACTION_PAR_CATEGORIE = {
    BUG_SIMPLE: "iterer",                        # relancer le Développeur
    AMBIGUITE: "validation_humaine",               # la spec doit être tranchée
    LIMITE_STRUCTURELLE: "repasser_architecte",  # revoir la conception
}


def _signature_erreurs(erreurs: list) -> set:
    """Identité d'une erreur, indépendante de sa formulation."""
    return {(e.get("categorie", ""), e.get("description", ""))
            for e in (erreurs or [])}


def categoriser_echec(
    erreurs: list,
    rapport_testeur: dict,
    iteration_actuelle: int,
    max_iterations: int,
    feedback_precedent: dict = None,
    rapport_differentiel: dict = None,
) -> dict:
    """
    Détermine la nature d'un échec et l'action qui en découle.

    Retourne {"categorie", "action_recommandee", "indices"} : les
    indices sont les faits observés qui justifient la catégorie,
    afin que le choix reste explicable a posteriori.
    """
    indices = []

    # ── Limite structurelle ──
    budget_epuise = iteration_actuelle >= max_iterations
    if budget_epuise:
        indices.append(f"budget d'itérations épuisé "
                       f"({iteration_actuelle}/{max_iterations})")

    precedentes = _signature_erreurs(
        (feedback_precedent or {}).get("erreurs_par_priorite"))
    persistantes = _signature_erreurs(erreurs) & precedentes
    erreurs_persistantes = []
    if persistantes and persistantes == _signature_erreurs(erreurs):
        indices.append(f"{len(persistantes)} erreur(s) inchangée(s) "
                       f"malgré la correction précédente")
        erreurs_persistantes = list(erreurs)

    if indices:
        return {"categorie": LIMITE_STRUCTURELLE,
                "action_recommandee": ("validation_humaine" if budget_epuise
                                       else ACTION_PAR_CATEGORIE[LIMITE_STRUCTURELLE]),
                "indices": indices,
                "erreurs_persistantes": erreurs_persistantes}

    # ── Ambiguïté ──
    # Toutes les erreurs que sait produire le Réviseur sont concrètes
    # (syntaxe, faille, invariant). Si le module n'est pas livrable
    # sans qu'aucune ne soit relevée, le défaut n'est désigné par
    # aucune règle : c'est la spécification qui est en question.
    if not erreurs:
        indices.append("score insuffisant sans aucune erreur "
                       "identifiable par les vérifications")
        diff = (rapport_differentiel
                or rapport_testeur.get("equivalence_comportementale") or {})
        divergences = diff.get("divergences", []) if diff else []
        if divergences:
            indices.append(f"{len(divergences)} divergence(s) de "
                           f"comportement PHP/Python non expliquée(s)")
        return {"categorie": AMBIGUITE,
                "action_recommandee": ACTION_PAR_CATEGORIE[AMBIGUITE],
                "indices": indices}

    # ── Bug simple ──
    return {"categorie": BUG_SIMPLE,
            "action_recommandee": ACTION_PAR_CATEGORIE[BUG_SIMPLE],
            "indices": [f"{len(erreurs)} erreur(s) localisée(s) avec "
                        f"correction identifiée"]}


def agent_reviseur(
    rapport_testeur: dict,
    rapport_auditeur: dict,
    module_info: dict,
    iteration_actuelle: int = 1,
    max_iterations: int = 5,
    seuil_haut: float = 65.0,
    seuil_bas: float = 30.0,
    feedback_precedent: dict = None,
    rapport_differentiel: dict = None,
    rapport_formel: dict = None,
    rapport_juge: dict = None,
) -> dict:
    """
    Agent Réviseur principal — SMAML
    Décide : livrer, itérer, ou abandonner.
    """

    print(f"\nRévision du module : {module_info.get('nom_python', '')}")
    print(f"Itération actuelle : {iteration_actuelle}/{max_iterations}")

    # Niveau de confiance : quatre critères, poids redistribué sur
    # ceux qui ont réellement pu être mesurés.
    verrous = verrous_actifs(rapport_testeur, rapport_auditeur, rapport_formel)
    confiance = calculer_niveau_confiance(
        rapport_testeur, rapport_auditeur,
        rapport_differentiel, rapport_formel,
        rapport_juge=rapport_juge, verrous=verrous)
    score = confiance["score"]
    # Le même score SANS le juge : il sert à mesurer le désaccord.
    score_outils = calculer_niveau_confiance(
        rapport_testeur, rapport_auditeur,
        rapport_differentiel, rapport_formel)["score"]

    print("\nNiveau de confiance — détail par critère :")
    for c in confiance["criteres"]:
        if c["mesure"]:
            print(f"  {c['nom']:<15} {c['score']:>6.1f}%  "
                  f"(poids {c['poids']*100:.0f}%)  — {c['agent']}")
        else:
            print(f"  {c['nom']:<15}     —     non mesuré : {c['raison']}")
    print(f"Score de confiance : {score:.1f}% "
          f"(confiance {confiance['niveau']})")

    decision = {
        "module": module_info.get("nom_python", ""),
        "score_compose": score,
        "confiance": confiance,
        "iteration": iteration_actuelle,
        "decision": None,
        "feedback": None,
        "raison": "",
        "categorie_echec": None,
    }

    # ── VERROU BLOQUANT ──
    # Un module statiquement invalide (erreur de syntaxe OU nom utilisé
    # sans être défini/importé) est INEXÉCUTABLE : il ne doit jamais
    # être livré, quel que soit le score composé. Sans ce verrou, un
    # module levant NameError sur toutes les entrées pouvait passer le
    # seuil grâce aux autres dimensions (cas generer_rapport, 71,6 %).
    syntaxe = rapport_testeur.get("syntaxe", {})
    code_inexecutable = not syntaxe.get("syntaxe_valide", True)

    # Décision selon les seuils
    if score >= seuil_haut and not code_inexecutable:
        decision["decision"] = "LIVRER"
        decision["raison"] = (
            f"Score composé {score:.1f}% >= seuil haut {seuil_haut}%. "
            f"Le module respecte les critères de qualité et sécurité."
        )
        print(f"\n[OK] DÉCISION : LIVRER")
        print(f"   {decision['raison']}")

    elif iteration_actuelle >= max_iterations:
        decision["decision"] = "ARRET_ECHEC"
        decision["raison"] = (
            f"Nombre maximum d'itérations atteint ({max_iterations}) "
            f"sans atteindre le seuil de qualité requis."
            + (" Le code reste statiquement invalide (inexécutable) : "
               "livraison refusée quel que soit le score."
               if code_inexecutable else "")
        )
        print(f"\n[ECHEC] DÉCISION : ARRÊT (ÉCHEC)")
        print(f"   {decision['raison']}")

    elif score < seuil_bas:
        erreurs = identifier_erreurs_prioritaires(
            rapport_testeur, rapport_auditeur
        )
        decision["decision"] = "REANALYSE_COMPLETE"
        decision["feedback"] = generer_feedback(erreurs, module_info)
        decision["raison"] = (
            f"Score composé {score:.1f}% < seuil bas {seuil_bas}%. "
            f"Trop d'erreurs critiques, ré-analyse complète nécessaire."
        )
        print(f"\n[BASCULE] DÉCISION : RÉ-ANALYSE COMPLÈTE")
        print(f"   {decision['raison']}")
        print(f"   {len(erreurs)} erreur(s) identifiée(s)")

    else:
        erreurs = identifier_erreurs_prioritaires(
            rapport_testeur, rapport_auditeur
        )
        decision["decision"] = "ITERER"
        decision["feedback"] = generer_feedback(erreurs, module_info)
        decision["raison"] = (
            (f"Code statiquement invalide (inexécutable) malgré un score "
             f"composé de {score:.1f}% : livraison bloquée, correction "
             f"obligatoire."
             if code_inexecutable else
             f"Score composé {score:.1f}% entre les seuils "
             f"({seuil_bas}%-{seuil_haut}%). Correction ciblée nécessaire.")
        )
        print(f"\n[ITERATION] DÉCISION : ITÉRER (feedback ciblé)")
        print(f"   {decision['raison']}")
        print(f"   {len(erreurs)} erreur(s) à corriger, "
              f"par ordre de priorité :")
        for instr in decision["feedback"]["instructions"]:
            print(f"     - {instr}")

    # ── Catégorisation de l'échec (tout verdict autre que LIVRER) ──
    if decision["decision"] != "LIVRER":
        erreurs = (decision["feedback"] or {}).get("erreurs_par_priorite")
        if erreurs is None:
            erreurs = identifier_erreurs_prioritaires(
                rapport_testeur, rapport_auditeur)
        cat = categoriser_echec(
            erreurs, rapport_testeur, iteration_actuelle, max_iterations,
            feedback_precedent=feedback_precedent,
            rapport_differentiel=rapport_differentiel,
        )
        decision["categorie_echec"] = cat["categorie"]
        decision["action_recommandee"] = cat["action_recommandee"]
        decision["indices_categorie"] = cat["indices"]
        decision["erreurs_persistantes"] = cat.get("erreurs_persistantes", [])
        print(f"   Catégorie d'échec : {cat['categorie']} "
              f"→ {cat['action_recommandee']}")
        for ind in cat["indices"]:
            print(f"     · {ind}")

    # ── Verrous : aucun score ne compense ces échecs ──
    bloquants = verrous_bloquants(verrous)
    if decision["decision"] == "LIVRER" and bloquants:
        instructions = [f"Rétablis la garde du code d'origine, qui a disparu : "
                        f"{i['description']} (code d'origine : {i.get('code', '')})"
                        for i in invariants_manquants_prouves(rapport_testeur)]
        if iteration_actuelle < max_iterations:
            decision["decision"] = "ITERER"
            decision["action_recommandee"] = "iterer"
            decision["feedback"] = {
                "instructions": instructions or [f"Corrige : {v}" for v in bloquants],
                "erreurs_par_priorite": [{"type": "verrou", "priorite": 1, "message": v,
                                          "action": "corriger avant toute livraison"}
                                         for v in bloquants]}
        else:
            decision["decision"] = "ARRET_ECHEC"
        decision["categorie_echec"] = "verrou"
        decision["raison"] = (f"Score {score:.1f} %, mais livraison impossible : "
                              + " ; ".join(bloquants))
        print(f"\n[VERROU] DÉCISION : {decision['decision']} — {decision['raison']}")

    # ── Désaccord entre le juge et les outils ──
    # Les outils livreraient, mais le juge estime la qualité très
    # inférieure. Comme un relecteur qui trouve un défaut, le juge renvoie
    # le travail à son auteur : ses remarques deviennent la consigne de
    # correction du Développeur. Une validation humaine n'intervient que
    # si le désaccord PERSISTE après plusieurs corrections.
    juge = next((c for c in confiance["criteres"]
                 if c["nom"] == "qualite_jugee" and c["mesure"]), None)
    decision["score_outils"] = score_outils
    if juge is not None:
        ecart = score_outils - juge["score"]
        decision["desaccord_juge"] = round(ecart, 1)
        if decision["decision"] == "LIVRER" and ecart >= SEUIL_DESACCORD:
            remarques = remarques_du_juge(rapport_juge)
            if iteration_actuelle <= CORRECTIONS_JUGE and \
                    iteration_actuelle < max_iterations:
                decision["decision"] = "ITERER"
                decision["categorie_echec"] = "desaccord_juge"
                decision["action_recommandee"] = "iterer"
                decision["feedback"] = {
                    "instructions": remarques,
                    "erreurs_par_priorite": [
                        {"type": "qualite_jugee", "priorite": 2,
                         "message": r, "action": "corriger selon la remarque"}
                        for r in remarques]}
                decision["raison"] = (
                    f"Désaccord entre évaluations (outils {score_outils:.1f} %, "
                    f"juge {juge['score']:.1f} %) : le module est renvoyé au "
                    f"Développeur avec les {len(remarques)} remarque(s) du juge.")
                print(f"\n[ITERATION] DÉCISION : ITÉRER — {decision['raison']}")
            else:
                decision["decision"] = "VALIDATION_HUMAINE"
                decision["categorie_echec"] = "desaccord_juge"
                decision["action_recommandee"] = "validation_humaine"
                decision["remarques_juge"] = remarques
                decision["raison"] = (
                    f"Désaccord persistant après {iteration_actuelle - 1} "
                    f"correction(s) : outils {score_outils:.1f} %, juge "
                    f"{juge['score']:.1f} %. Validation humaine demandée, "
                    f"avec les remarques du juge.")
                print(f"\n[ARBITRAGE]  DÉCISION : VALIDATION HUMAINE — {decision['raison']}")
    return decision


# ─── TEST ────────────────────────────────────────────
if __name__ == "__main__":

    # Cas 1 — Bon score, doit livrer
    print("=" * 60)
    print("CAS 1 — Score élevé (résultat réel de nos tests)")
    print("=" * 60)

    rapport_testeur_bon = {
        "score_fonctionnel": 1.0,
        "syntaxe": {"syntaxe_valide": True, "erreur": None},
        "failles": {"failles_persistantes": []}
    }

    rapport_auditeur_bon = {
        "score_securite_global": 80.0,
        "dimension_1_invariants": {"invariants_violes": []},
        "dimension_2_bandit": {"failles_detectees": []}
    }

    module_test = {"nom_python": "get_user", "nom_original": "getUser"}

    decision1 = agent_reviseur(
        rapport_testeur_bon, rapport_auditeur_bon, module_test,
        iteration_actuelle=1
    )

    # Cas 2 — Score moyen, doit itérer
    print("\n\n" + "=" * 60)
    print("CAS 2 — Score moyen (simulation d'un module avec erreurs)")
    print("=" * 60)

    rapport_testeur_moyen = {
        "score_fonctionnel": 0.6,
        "syntaxe": {"syntaxe_valide": True, "erreur": None},
        "failles": {
            "failles_persistantes": [
                {"faille": "sql_injection", "cwe": "CWE-89"}
            ]
        }
    }

    rapport_auditeur_moyen = {
        "score_securite_global": 55.0,
        "dimension_1_invariants": {
            "invariants_violes": [
                {"type": "validation_longueur", "description": "len >= 8"}
            ]
        },
        "dimension_2_bandit": {
            "failles_detectees": [
                {"type": "hardcoded_password", "severity": "high",
                 "description": "Mot de passe en dur détecté",
                 "ligne": 12}
            ]
        }
    }

    decision2 = agent_reviseur(
        rapport_testeur_moyen, rapport_auditeur_moyen, module_test,
        iteration_actuelle=2
    )

    print("\n\n" + "=" * 60)
    print("[OK] Agent Réviseur opérationnel !")