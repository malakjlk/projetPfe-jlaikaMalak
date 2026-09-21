import json


# ═══ POINTS D'ATTENTION — PHP LEGACY ══════════════════
# Certaines constructions PHP n'ont pas d'équivalent direct en
# Python / FastAPI. L'Architecte les signale dans son dépôt pour que
# les agents en aval (Développeur, Vérificateur, Auditeur) et le
# lecteur humain ne les manquent pas.
PATTERNS_LEGACY = [
    (r"\$_SESSION\b|\bsession_start\s*\(",
     "gère des sessions PHP natives ($_SESSION) : l'état de session "
     "doit être porté explicitement (dépendance FastAPI ou middleware)"),
    (r"\$_(GET|POST|REQUEST|COOKIE|FILES)\b",
     "lit directement les superglobales HTTP : ces entrées doivent "
     "devenir des paramètres typés et validés"),
    (r"\bglobal\s+\$",
     "utilise des variables globales : dépendance implicite à rendre "
     "explicite"),
    (r"\bmysql_\w+\s*\(",
     "utilise l'extension mysql_* obsolète : aucun équivalent direct, "
     "passage obligatoire par l'ORM"),
    (r"\beval\s*\(",
     "contient eval() : comportement dynamique non traduisible "
     "fidèlement"),
    (r"\bextract\s*\(|\$\$\w+",
     "crée des variables dynamiques (extract() ou $$nom) : noms non "
     "déterminables statiquement"),
    (r"\b(include|require)(_once)?\s*\(?\s*\$",
     "inclut un fichier dont le chemin est dynamique"),
    (r"\bheader\s*\(",
     "envoie des en-têtes HTTP via header() : à traduire en réponse "
     "FastAPI"),
    (r"\b(die|exit)\s*\(",
     "interrompt le script (die/exit) : à traduire en exception HTTP"),
    (r"@\s*\w+\s*\(",
     "masque des erreurs avec l'opérateur @ : le comportement en cas "
     "d'erreur est implicite"),
]

# Constructions dont la sémantique ne peut pas être établie
# statiquement : elles rendent la traduction incertaine.
PATTERNS_INCERTAINS = (r"\beval\s*\(", r"\bextract\s*\(", r"\$\$\w+",
                       r"\b(include|require)(_once)?\s*\(?\s*\$")


def _source_module(code_php: str, nom: str, type_module: str) -> str:
    """Extrait le corps PHP d'une fonction ou d'une classe (accolades)."""
    import re
    motif = (rf"\bclass\s+{re.escape(nom)}\b" if type_module == "classe"
             else rf"\bfunction\s+{re.escape(nom)}\s*\(")
    m = re.search(motif, code_php or "")
    if not m:
        return ""
    debut = code_php.find("{", m.end())
    if debut < 0:
        return ""
    profondeur = 0
    for i in range(debut, len(code_php)):
        if code_php[i] == "{":
            profondeur += 1
        elif code_php[i] == "}":
            profondeur -= 1
            if profondeur == 0:
                return code_php[m.start():i + 1]
    return code_php[m.start():]


def detecter_points_attention(code_php: str) -> list:
    """Points d'attention liés aux constructions PHP legacy."""
    import re
    return [message for motif, message in PATTERNS_LEGACY
            if re.search(motif, code_php or "")]


def planifier_migration(rapport_analyste: dict, code_php: str = "") -> dict:
    """
    Agent Architecte — SMAML
    Reçoit le rapport de l'Agent Analyste et produit
    un plan de migration structuré en JSON.

    code_php (optionnel) : source PHP, utilisé pour signaler les
    constructions legacy dans les points d'attention de chaque module.
    """

    fonctions = rapport_analyste.get("fonctions", [])
    invariants = rapport_analyste.get("invariants_securite", [])
    failles = rapport_analyste.get("failles_potentielles", [])
    metriques = rapport_analyste.get("metriques", {})

    complexite = metriques.get("complexite_estimee", "faible")
    if complexite == "elevee":
        pattern = "Strangler Fig"
        pattern_desc = "Migration progressive module par module"
    else:
        pattern = "Big Bang"
        pattern_desc = "Migration complète en une fois"

    hypotheses_plan = [
        f"complexité estimée « {complexite} » → pattern {pattern}",
        "cible FastAPI + Pydantic : les modules sont exposables en API",
    ]

    plan = {
        "pattern_migration": pattern,
        "pattern_description": pattern_desc,
        "langage_source": "PHP",
        "langage_cible": "Python",
        "framework_cible": "FastAPI + Pydantic",
        "modules": [],
        "ordre_migration": [],
        "interfaces": [],
        "priorites_securite": []
    }

    # ── Un module par FONCTION ──
    for i, fonction in enumerate(fonctions):
        module = {
            "id": i + 1,
            "type": "fonction",
            "nom_original": fonction["nom"],
            "nom_python": convertir_nom(fonction["nom"]),
            "parametres": fonction["parametres"],
            "lignes_source": fonction.get("lignes", {}),
            "priorite": "haute" if any(
                f["type"] in ["sql_injection", "command_injection"]
                for f in failles
                if fonction["nom"].lower() in f.get("code", "").lower()
            ) else "normale"
        }
        _annoter_module(module, code_php)
        plan["modules"].append(module)
        plan["ordre_migration"].append(module["nom_python"])

    # ── Un module par CLASSE (RÈGLE état/sans-état) ──
    classes = rapport_analyste.get("classes", [])
    for j, classe in enumerate(classes):
        avec_etat = len(classe.get("proprietes", [])) > 0
        parent = classe.get("classe_parente", "")
        # Une classe qui HÉRITE reste toujours une classe Python
        # (elle hérite d'un comportement qu'on ne peut pas refactorer
        # en simples fonctions sans casser la relation d'héritage).
        if parent or avec_etat:
            cible = "classe_python"
        else:
            cible = "fonctions_module"
        if parent:
            raison = f"classe héritant de {parent} → classe Python (héritage préservé)"
        elif avec_etat:
            raison = (f"classe avec état ({len(classe.get('proprietes', []))} "
                      f"propriété(s)) → classe Python fidèle")
        else:
            raison = "classe sans état → refactoring fonctionnel"
        module = {
            "id": len(fonctions) + j + 1,
            "type": "classe",
            "cible_migration": cible,
            "classe_parente": parent,
            "raison_architecturale": raison,
            "nom_original": classe["nom"],
            "nom_python": (classe["nom"] if cible == "classe_python"
                           else convertir_nom(classe["nom"])),
            "methodes": [m["nom"] for m in classe.get("methodes", [])],
            "methodes_python": [convertir_nom(m["nom"])
                                for m in classe.get("methodes", [])],
            "parametres": [],
            "lignes_source": classe.get("lignes", {}),
            "priorite": "normale"
        }
        _annoter_module(module, code_php)
        module["hypotheses_faites"].append(raison)
        noms_classes_fichier = {c["nom"] for c in classes}
        if parent and parent not in noms_classes_fichier:
            module["points_incertains"].append(
                f"classe parente {parent} absente du fichier : supposée "
                f"fournie par un autre module du projet")
        plan["modules"].append(module)
        plan["ordre_migration"].append(module["nom_python"])

    # ── Réordonner : une classe parente doit être migrée AVANT
    #    sa classe enfant (sinon class Admin(User) échoue).
    plan["modules"] = _trier_par_heritage(plan["modules"])
    plan["ordre_migration"] = [m["nom_python"] for m in plan["modules"]]

    for faille in failles:
        plan["priorites_securite"].append({
            "faille": faille["type"],
            "cwe": faille["cwe"],
            "severity": faille["severity"],
            "action": "Remplacer par équivalent Python sécurisé"
        })

    if len(fonctions) + len(classes) > 1:
        plan["interfaces"].append({
            "type": "FastAPI Router",
            "description": "Tous les modules exposés via endpoints FastAPI",
            "format": "JSON + Pydantic validation"
        })

    plan["invariants_a_preserver"] = [
        {
            "type": inv["type"],
            "description": inv["description"],
            "fonction": inv.get("fonction", ""),
            "code": inv.get("code", ""),
            "obligatoire": True
        }
        for inv in invariants
    ]

    # ── Dépôt explicite : hypothèses, incertitudes, points d'attention
    plan["hypotheses_faites"] = hypotheses_plan
    plan["points_incertains"] = [
        f"{m['nom_original']} : {p}"
        for m in plan["modules"] for p in m["points_incertains"]]
    plan["points_attention"] = [
        f"{m['nom_original']} {p}"
        for m in plan["modules"] for p in m["points_attention"]]

    return plan


def _annoter_module(module: dict, code_php: str):
    """Ajoute au module ses points d'attention et ses incertitudes."""
    import re
    source = _source_module(code_php, module["nom_original"],
                            module["type"])
    module["points_attention"] = detecter_points_attention(source)
    module["points_incertains"] = [
        "construction dynamique présente : la traduction ne peut pas "
        "être vérifiée statiquement"
    ] if any(re.search(m, source) for m in PATTERNS_INCERTAINS) else []
    module["hypotheses_faites"] = []


# ═══ RÉVISION DU PLAN ═════════════════════════════════
# Appelée quand le Réviseur classe un échec en « limite structurelle » :
# les mêmes erreurs persistent malgré la correction, donc relancer le
# Développeur avec le même plan ne suffit pas. L'Architecte revoit la
# stratégie du module et transforme les erreurs persistantes en
# contraintes de conception explicites.

CONTRAINTES_PAR_CATEGORIE = {
    "syntaxe_invalide":
        "produire une structure minimale : pas de routeur, pas de "
        "décorateur, pas de modèle Pydantic non indispensable",
    "securite_critique":
        "tout accès aux données passe par des paramètres liés (ORM ou "
        "requête paramétrée) ; aucune chaîne construite à partir d'une "
        "entrée",
    "faille_non_corrigee":
        "isoler l'opération vulnérable dans une fonction dédiée qui "
        "reçoit des entrées déjà validées",
    "invariant_non_preserve":
        "chaque invariant devient une garde explicite en tête de "
        "fonction, qui lève une exception si elle est violée",
}


def reviser_module(module: dict, erreurs_persistantes: list) -> dict:
    """
    Produit une nouvelle version du module avec une stratégie revue.
    Retourne le module révisé (le module d'origine n'est pas modifié).
    """
    import copy
    revise = copy.deepcopy(module)
    revise["revision"] = module.get("revision", 0) + 1
    changements = []

    # Changement de stratégie : une classe refactorée en fonctions
    # revient à une classe Python fidèle à l'original. Le refactoring
    # est la transformation la plus risquée : c'est la première
    # hypothèse à abandonner quand les corrections n'aboutissent pas.
    if (revise.get("type") == "classe"
            and revise.get("cible_migration") == "fonctions_module"):
        revise["cible_migration"] = "classe_python"
        revise["nom_python"] = revise["nom_original"]
        changements.append("refactoring en fonctions abandonné : la "
                           "classe est conservée telle quelle")

    categories = []
    for e in erreurs_persistantes or []:
        c = e.get("categorie", "")
        if c in CONTRAINTES_PAR_CATEGORIE and c not in categories:
            categories.append(c)
    contraintes = [CONTRAINTES_PAR_CATEGORIE[c] for c in categories]
    contraintes += [f"résoudre en priorité : {e.get('description', '')}"
                    for e in (erreurs_persistantes or [])[:3]]
    revise["contraintes_revision"] = contraintes
    changements.append(f"{len(contraintes)} contrainte(s) de conception "
                       f"ajoutée(s) à partir des erreurs persistantes")

    revise.setdefault("hypotheses_faites", []).append(
        f"révision {revise['revision']} : les erreurs persistantes "
        f"relèvent de la conception, pas d'un oubli ponctuel")
    revise.setdefault("points_attention", []).append(
        f"plan révisé (révision {revise['revision']}) après un échec de "
        f"type limite structurelle")
    revise["changements_revision"] = changements
    return revise


def _trier_par_heritage(modules: list) -> list:
    """
    Réordonne les modules pour qu'une classe parente soit
    toujours placée AVANT ses classes enfants (tri topologique
    sur la relation d'héritage). Les fonctions gardent leur
    ordre. Évite qu'une classe enfant soit migrée avant son
    parent (class Admin(User) échouerait sinon).
    """
    noms_classes = {m["nom_original"] for m in modules
                    if m.get("type") == "classe"}
    ordonnes = []
    restants = list(modules)
    securite = 0

    while restants and securite < 1000:
        securite += 1
        for m in list(restants):
            parent = m.get("classe_parente", "")
            # Prêt si : pas de parent, OU parent hors projet,
            # OU parent déjà placé
            parent_dans_projet = parent in noms_classes
            parent_deja_place = any(
                o["nom_original"] == parent for o in ordonnes
            )
            if (not parent) or (not parent_dans_projet) or parent_deja_place:
                ordonnes.append(m)
                restants.remove(m)

    # Sécurité : cycle d'héritage (ne devrait jamais arriver en PHP)
    ordonnes.extend(restants)
    return ordonnes


def convertir_nom(nom_php: str) -> str:
    """camelCase → snake_case (validatePassword → validate_password)."""
    import re
    s = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', nom_php)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s).lower()


if __name__ == "__main__":
    rapport = {
        "fonctions": [],
        "classes": [
            {"nom": "OutilsTexte", "proprietes": [],
             "methodes": [{"nom": "formaterPrix", "parametres": ["$m"]},
                          {"nom": "genererRapport", "parametres": ["$c"]}]},
            {"nom": "PanierAchat", "proprietes": ["$articles", "$total"],
             "methodes": [{"nom": "ajouterArticle", "parametres": ["$n", "$p"]}]},
        ],
        "invariants_securite": [],
        "failles_potentielles": [],
        "metriques": {"complexite_estimee": "faible"},
    }
    plan = planifier_migration(rapport)
    print(f"Modules créés : {len(plan['modules'])}")
    for m in plan["modules"]:
        print(f"  - {m['nom_original']} (type={m['type']}, "
              f"cible={m.get('cible_migration','—')})")
    assert len(plan["modules"]) == 2
    assert plan["modules"][0]["cible_migration"] == "fonctions_module"
    assert plan["modules"][1]["cible_migration"] == "classe_python"
    print("\n✅ Architecte gère les classes")

    code = """<?php
class OutilsTexte { function formaterPrix($m) { return @number_format($m); } }
function login($u) { session_start(); $_SESSION['u'] = $_POST['u']; eval($u); }
?>"""
    plan2 = planifier_migration({
        "fonctions": [{"nom": "login", "parametres": ["$u"]}],
        "classes": [{"nom": "OutilsTexte", "proprietes": [],
                     "methodes": [{"nom": "formaterPrix"}]}],
        "invariants_securite": [], "failles_potentielles": [],
        "metriques": {}}, code)
    login = [m for m in plan2["modules"] if m["nom_original"] == "login"][0]
    print("Points d'attention (login) :")
    for p in login["points_attention"]:
        print(f"  - {p}")
    assert len(login["points_attention"]) == 3 and login["points_incertains"]
    outils = [m for m in plan2["modules"] if m["type"] == "classe"][0]
    assert any("opérateur @" in p for p in outils["points_attention"])
    rev = reviser_module(outils, [{"categorie": "syntaxe_invalide",
                                   "description": "NameError"}])
    print("Révision :", rev["changements_revision"])
    assert rev["cible_migration"] == "classe_python" and rev["revision"] == 1
    assert outils["cible_migration"] == "fonctions_module"
    print("✅ Points d'attention et révision du plan opérationnels")