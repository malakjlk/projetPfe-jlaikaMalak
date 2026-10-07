"""
Portée de la vérification — SMAML
==================================
« Garantir l'équivalence comportementale » ne veut rien dire sans
préciser SUR QUOI. Aucun outil ne peut vérifier toutes les entrées
possibles d'une fonction : ce serait résoudre le problème de l'arrêt.

Ce module produit, pour chaque module migré, une attestation qui
énonce exactement :
  - ce qui a été VÉRIFIÉ, et par quel moyen ;
  - ce qui n'a PAS été vérifié, et pourquoi.

C'est la différence entre « le code est équivalent » — affirmation
invérifiable — et « l'équivalence est observée sur 19 entrées, et
l'absence d'injection SQL est prouvée par exploration symbolique ».
"""


def portee_verification(module: dict) -> dict:
    """
    Attestation de vérification d'un module migré.

    module : l'entrée produite par le pipeline (équivalence,
    vérification formelle, rapports du Testeur et de l'Auditeur).
    """
    verifie, non_verifie = [], []

    # ── Équivalence comportementale ──
    equivalence = module.get("equivalence") or {}
    if equivalence.get("statut") == "teste":
        cas = equivalence.get("cas_testes", 0)
        score = (equivalence.get("score_equivalence") or 0) * 100
        verifie.append(
            f"comportement identique au PHP sur {cas} entrée(s) testée(s) "
            f"({score:.0f}% de concordance), exécution réelle des deux codes")
        if equivalence.get("injections_bloquees"):
            verifie.append(
                f"{len(equivalence['injections_bloquees'])} entrée(s) "
                f"d'injection acceptée(s) par le PHP et rejetée(s) par le "
                f"Python : écart volontaire, faille corrigée")
        non_verifie.append(
            "le comportement sur les entrées non testées : l'équivalence "
            "est observée, elle n'est pas démontrée pour toute entrée")
        non_verifie.append(
            "les particularités du moteur MySQL : la comparaison s'appuie "
            "sur une base SQLite identique pour les deux langages")
    else:
        raison = equivalence.get("raison") or equivalence.get("statut") \
            or "non testée"
        non_verifie.append(f"l'équivalence comportementale : {raison}")

    # ── Vérification formelle ──
    formel = module.get("verification_formelle") or {}
    prouvees = [p for p in (formel.get("proprietes") or [])
                if p.get("statut") == "prouvee"]
    refutees = [p for p in (formel.get("proprietes") or [])
                if p.get("statut") == "refutee"]
    for propriete in prouvees:
        verifie.append(
            f"propriété « {propriete.get('libelle', '')} » : aucun "
            f"contre-exemple trouvé par exploration symbolique")
    for propriete in refutees:
        non_verifie.append(
            f"propriété « {propriete.get('libelle', '')} » : RÉFUTÉE, "
            f"contre-exemple {propriete.get('contre_exemple', '')}")
    if prouvees:
        non_verifie.append(
            "l'exploration symbolique est bornée en temps : une propriété "
            "sans contre-exemple trouvé n'est pas une preuve absolue")
    if not formel.get("proprietes"):
        non_verifie.append(
            "aucune propriété formelle : les règles du code d'origine "
            "n'ont pas pu être traduites en contrats vérifiables")

    # ── Invariants et failles ──
    etat = module.get("etat_structure") or {}
    rapports = etat.get("rapports") or {}
    testeur = rapports.get("testeur") or module.get("rapport_testeur") or {}
    invariants = testeur.get("invariants") or {}
    verifies = len(invariants.get("invariants_verifies") or [])
    manquants = len(invariants.get("invariants_manquants") or [])
    if verifies:
        verifie.append(
            f"{verifies} invariant(s) du code d'origine préservé(s), "
            f"vérifié(s) par test dynamique ou analyse structurelle")
    if manquants:
        non_verifie.append(
            f"{manquants} invariant(s) du code d'origine NON retrouvé(s) "
            f"dans le code migré")
    if not verifies and not manquants:
        non_verifie.append(
            "aucun invariant relevé dans le code d'origine : la "
            "préservation des règles métier implicites n'est pas vérifiable")

    failles = testeur.get("failles") or {}
    corrigees = len(failles.get("failles_corrigees") or [])
    persistantes = len(failles.get("failles_persistantes") or [])
    if corrigees:
        verifie.append(f"{corrigees} faille(s) du PHP d'origine corrigée(s) "
                       f"dans le code migré")
    if persistantes:
        non_verifie.append(f"{persistantes} faille(s) encore présente(s)")

    # ── Limites permanentes, indépendantes du module ──
    non_verifie.append(
        "les effets hors périmètre mesuré : réseau, système de fichiers, "
        "courriels, horloge")

    return {
        "module": module.get("nom_python", ""),
        "decision": module.get("decision_finale", ""),
        "verifie": verifie,
        "non_verifie": non_verifie,
        "formulation": _formuler(module, verifie, non_verifie),
    }


def _formuler(module: dict, verifie: list, non_verifie: list) -> str:
    """Phrase unique, utilisable telle quelle dans un rapport."""
    if module.get("decision_finale") != "LIVRER":
        return (f"Module non livré : les vérifications n'ont pas atteint le "
                f"niveau de confiance requis ({len(verifie)} point(s) "
                f"vérifié(s), {len(non_verifie)} hors de portée).")
    return (f"Équivalence observée et propriétés vérifiées dans les limites "
            f"énoncées : {len(verifie)} point(s) établi(s), "
            f"{len(non_verifie)} point(s) hors de portée de la vérification. "
            f"Le module est livré sous ces réserves.")


def resume_portee(attestation: dict) -> str:
    """Rendu lisible pour le journal de migration."""
    lignes = [f"Portée de la vérification — {attestation['module']}"]
    for point in attestation["verifie"]:
        lignes.append(f"   {point}")
    for point in attestation["non_verifie"]:
        lignes.append(f"    non vérifié : {point}")
    lignes.append(f"    {attestation['formulation']}")
    return "\n".join(lignes)


if __name__ == "__main__":
    EXEMPLE = {
        "nom_python": "get_user_by_email",
        "decision_finale": "LIVRER",
        "equivalence": {"statut": "teste", "cas_testes": 19,
                        "score_equivalence": 1.0,
                        "injections_bloquees": ["' OR '1'='1"]},
        "verification_formelle": {"proprietes": [
            {"libelle": "le texte des requêtes SQL ne dépend pas de l'entrée",
             "statut": "prouvee", "famille": "injection_sql"}]},
        "etat_structure": {"rapports": {"testeur": {
            "invariants": {"invariants_verifies": [{"description": "email non vide"}],
                           "invariants_manquants": []},
            "failles": {"failles_corrigees": [{"type": "sql_injection"}],
                        "failles_persistantes": []}}}},
    }
    print(resume_portee(portee_verification(EXEMPLE)))