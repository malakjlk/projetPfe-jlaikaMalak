import json
import sys

from agent_analyste import analyser_code_php
from agent_architecte import planifier_migration
from agent_developpeur import (
    generer_code_python, extraire_code_module
)
from agent_testeur import agent_testeur
from agent_auditeur import agent_auditeur
from agent_reviseur import agent_reviseur


def pipeline_smaml(code_php_complet: str, max_iterations: int = 5) -> dict:
    """
    Pipeline complet SMAML — orchestration manuelle
    avant intégration CrewAI.

    Flux : Analyste -> Architecte -> [Développeur <-> Testeur+Auditeur <-> Réviseur]
    """

    resultat_final = {
        "modules_livres": [],
        "modules_echoues": [],
        "historique_iterations": []
    }

    print("\n" + "█" * 60)
    print("█  PIPELINE SMAML — DÉMARRAGE")
    print("█" * 60)

    # ─── ÉTAPE 1 — Agent Analyste ────────────────────
    print("\n[1/3] AGENT ANALYSTE")
    print("-" * 60)
    rapport_analyste = analyser_code_php(code_php_complet)
    print(f"  {len(rapport_analyste['fonctions'])} fonction(s) détectée(s)")
    print(f"  {len(rapport_analyste['invariants_securite'])} invariant(s)")
    print(f"  {len(rapport_analyste['failles_potentielles'])} faille(s)")

    # ─── ÉTAPE 2 — Agent Architecte ──────────────────
    print("\n[2/3] AGENT ARCHITECTE")
    print("-" * 60)
    plan_architecte = planifier_migration(rapport_analyste)
    print(f"  Pattern choisi : {plan_architecte['pattern_migration']}")
    print(f"  {len(plan_architecte['modules'])} module(s) planifié(s)")

    # ─── ÉTAPE 3 — Boucle par module ──────────────────
    print("\n[3/3] BOUCLE DÉVELOPPEUR <-> TESTEUR/AUDITEUR <-> RÉVISEUR")
    print("-" * 60)

    invariants_globaux = plan_architecte.get("invariants_a_preserver", [])
    failles_globales = plan_architecte.get("priorites_securite", [])

    for module in plan_architecte["modules"]:
        nom_module = module["nom_python"]
        print(f"\n{'='*60}")
        print(f"TRAITEMENT DU MODULE : {nom_module}")
        print(f"{'='*60}")

        code_php_module = extraire_code_module(
            code_php_complet, module["nom_original"]
        )

        iteration = 1
        feedback_precedent = None
        historique_module = []

        while iteration <= max_iterations:
            print(f"\n--- Itération {iteration}/{max_iterations} ---")

            # Agent Développeur génère (ou régénère avec feedback)
            code_python = generer_code_python(
                code_php_module, module,
                invariants_globaux, failles_globales
            )

            # Agent Testeur vérifie
            rapport_testeur = agent_testeur(
                code_python, module, invariants_globaux, failles_globales
            )

            # Agent Auditeur vérifie (en "parallèle" logique)
            rapport_auditeur = agent_auditeur(
                code_python, invariants_globaux, module
            )

            # Agent Réviseur décide
            decision = agent_reviseur(
                rapport_testeur, rapport_auditeur, module,
                iteration_actuelle=iteration,
                max_iterations=max_iterations
            )

            historique_module.append({
                "iteration": iteration,
                "score_compose": decision["score_compose"],
                "decision": decision["decision"]
            })

            if decision["decision"] == "LIVRER":
                resultat_final["modules_livres"].append({
                    "nom": nom_module,
                    "code_python": code_python,
                    "score_final": decision["score_compose"],
                    "iterations_necessaires": iteration
                })
                break

            elif decision["decision"] in ["ARRET_ECHEC", "REANALYSE_COMPLETE"]:
                resultat_final["modules_echoues"].append({
                    "nom": nom_module,
                    "raison": decision["raison"],
                    "derniere_score": decision["score_compose"]
                })
                break

            else:  # ITERER
                feedback_precedent = decision.get("feedback")
                iteration += 1

        resultat_final["historique_iterations"].append({
            "module": nom_module,
            "historique": historique_module
        })

    # ─── RÉSUMÉ FINAL ──────────────────────────────────
    print("\n\n" + "█" * 60)
    print("█  PIPELINE SMAML — RÉSUMÉ FINAL")
    print("█" * 60)
    print(f"\n✅ Modules livrés  : {len(resultat_final['modules_livres'])}")
    for m in resultat_final["modules_livres"]:
        print(f"     - {m['nom']} (score: {m['score_final']:.1f}%, "
              f"{m['iterations_necessaires']} itération(s))")

    print(f"\n❌ Modules échoués : {len(resultat_final['modules_echoues'])}")
    for m in resultat_final["modules_echoues"]:
        print(f"     - {m['nom']} : {m['raison']}")

    return resultat_final


# ─── TEST END-TO-END ──────────────────────────────────
if __name__ == "__main__":

    code_php_complet = """<?php
function validatePassword($password) {
    if (strlen($password) < 8) {
        throw new Exception('Trop court');
    }
    if (!preg_match('/[A-Z]/', $password)) {
        throw new Exception('Majuscule requise');
    }
    return true;
}

function getUser($id) {
    $sql = "SELECT * FROM users WHERE id=" . $id;
    $result = mysql_query($sql);
    return mysql_fetch_array($result);
}
"""

    resultat = pipeline_smaml(code_php_complet, max_iterations=3)

    print("\n\nSauvegarde du résultat final...")
    with open("resultat_pipeline.json", "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, indent=2)
    print("✅ Sauvegardé dans resultat_pipeline.json")