"""
Réconciliation entre vérificateurs — SMAML
===========================================
La preuve formelle fait foi : quand le Vérificateur de propriétés a
PROUVÉ un invariant par exploration symbolique, une analyse moins forte
(structurelle) qui l'aurait jugé absent est corrigée en conséquence.
"""

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
    # Un invariant RÉFUTÉ PAR UN CONTRE-EXEMPLE concret ne se requalifie
    # jamais : un contre-exemple est une preuve définitive d'absence. Si
    # une preuve formelle semble dire l'inverse, c'est qu'elle portait sur
    # une autre propriété. Seuls les « manquants » de l'heuristique
    # textuelle, sans contre-exemple, peuvent être requalifiés.
    refutes = {p.get("invariant") for p in inv.get("preuves", [])
               if p.get("verdict") == "manquant"
               and "contre-exemple" in str(p.get("source", ""))}
    requalifies = [i for i in manquants
                   if i.get("type") in types_prouves
                   and i.get("description") not in refutes]
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

    print(f"  [ARBITRAGE]  Réconciliation : {len(requalifies)} invariant(s) "
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

    print(f"  [ARBITRAGE]  Réconciliation Auditeur : Dimension 1 recalculée "
          f"({dim1['score']:.0f}%), score sécurité global "
          f"{rapport_auditeur['score_securite_global']:.1f}%")


# Noms publics
types_invariants_prouves = _types_invariants_prouves
reconcilier_testeur = _reconcilier_testeur
reconcilier_auditeur = _reconcilier_auditeur