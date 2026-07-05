import json


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


def agent_reviseur(
    rapport_testeur: dict,
    rapport_auditeur: dict,
    module_info: dict,
    iteration_actuelle: int = 1,
    max_iterations: int = 5,
    seuil_haut: float = 85.0,
    seuil_bas: float = 40.0
) -> dict:
    """
    Agent Réviseur principal — SMAML
    Décide : livrer, itérer, ou abandonner.
    """

    print(f"\nRévision du module : {module_info.get('nom_python', '')}")
    print(f"Itération actuelle : {iteration_actuelle}/{max_iterations}")

    # Calculer le score composé
    score = calculer_score_compose(rapport_testeur, rapport_auditeur)
    print(f"\nScore fonctionnel : "
          f"{rapport_testeur.get('score_fonctionnel', 0)*100:.1f}%")
    print(f"Score sécurité    : "
          f"{rapport_auditeur.get('score_securite_global', 0):.1f}%")
    print(f"Score composé (S = 0.6*F + 0.4*S) : {score:.1f}%")

    decision = {
        "module": module_info.get("nom_python", ""),
        "score_compose": score,
        "iteration": iteration_actuelle,
        "decision": None,
        "feedback": None,
        "raison": ""
    }

    # Décision selon les seuils
    if score >= seuil_haut:
        decision["decision"] = "LIVRER"
        decision["raison"] = (
            f"Score composé {score:.1f}% >= seuil haut {seuil_haut}%. "
            f"Le module respecte les critères de qualité et sécurité."
        )
        print(f"\n✅ DÉCISION : LIVRER")
        print(f"   {decision['raison']}")

    elif iteration_actuelle >= max_iterations:
        decision["decision"] = "ARRET_ECHEC"
        decision["raison"] = (
            f"Nombre maximum d'itérations atteint ({max_iterations}) "
            f"sans atteindre le seuil de qualité requis."
        )
        print(f"\n❌ DÉCISION : ARRÊT (ÉCHEC)")
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
        print(f"\n🔄 DÉCISION : RÉ-ANALYSE COMPLÈTE")
        print(f"   {decision['raison']}")
        print(f"   {len(erreurs)} erreur(s) identifiée(s)")

    else:
        erreurs = identifier_erreurs_prioritaires(
            rapport_testeur, rapport_auditeur
        )
        decision["decision"] = "ITERER"
        decision["feedback"] = generer_feedback(erreurs, module_info)
        decision["raison"] = (
            f"Score composé {score:.1f}% entre les seuils "
            f"({seuil_bas}%-{seuil_haut}%). Correction ciblée nécessaire."
        )
        print(f"\n🔁 DÉCISION : ITÉRER (feedback ciblé)")
        print(f"   {decision['raison']}")
        print(f"   {len(erreurs)} erreur(s) à corriger, "
              f"par ordre de priorité :")
        for instr in decision["feedback"]["instructions"]:
            print(f"     - {instr}")

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
    print("✅ Agent Réviseur opérationnel !")