import re
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

    # ── Choix du pattern de migration ──
    # Le nombre de failles ne dit rien de la stratégie : un fichier
    # d'une fonction vulnérable se migre d'un coup, un fichier de
    # vingt fonctions entrelacées non. Les critères retenus sont
    # structurels : la taille, l'état partagé et les dépendances.
    nb_modules = len(fonctions) + len(rapport_analyste.get("classes", []))
    etat_partage = [v for v in rapport_analyste.get("variables_globales", [])
                    if v in ("$_SESSION", "$_COOKIE")]
    appels_internes = _appels_internes(code_php, [f["nom"] for f in fonctions])
    nb_liens = sum(len(d) for d in appels_internes.values())

    raisons = []
    if nb_modules > 8:
        raisons.append(f"{nb_modules} modules")
    if etat_partage:
        raisons.append(f"état partagé ({', '.join(etat_partage)})")
    if nb_liens > 5:
        raisons.append(f"{nb_liens} appels entre modules")

    if raisons:
        pattern = "Strangler Fig"
        pattern_desc = ("Migration progressive : les modules sont "
                        "remplacés un à un, l'ancien et le nouveau code "
                        "coexistant pendant la transition")
    else:
        pattern = "Big Bang"
        pattern_desc = ("Migration complète en une fois : le fichier est "
                        "assez petit et peu couplé pour être remplacé "
                        "d'un bloc")

    hypotheses_plan = [
        (f"pattern {pattern} — " + (", ".join(raisons) if raisons
         else f"{nb_modules} module(s), pas d'état partagé, "
              f"{nb_liens} appel(s) interne(s)")),
        f"complexité estimée « {complexite} » (nombre de failles)",
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
            # L'Analyste rattache chaque faille à sa fonction : on
            # s'appuie dessus. Chercher le nom de la fonction dans le
            # code de la faille ne marchait jamais, puisqu'un appel
            # « mysqli_query($conn, $sql) » ne contient pas le nom de
            # la fonction qui l'entoure.
            "priorite": "haute" if any(
                f.get("fonction") == fonction["nom"]
                and f["type"] in ("sql_injection", "command_injection",
                                  "insecure_deserialization",
                                  "file_inclusion")
                for f in failles
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

    # ── Réordonner : une fonction appelée doit être migrée AVANT
    #    celle qui l'appelle, sinon le Développeur n'a pas son
    #    contexte et le Testeur la déclare inexécutable.
    for module in plan["modules"]:
        _completer_pour_services(module, code_php, appels_internes)

    plan["modules"] = _trier_par_appels(plan["modules"], appels_internes)

    # ── Puis : une classe parente avant sa classe enfant
    #    (sinon class Admin(User) échoue).
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


def _completer_pour_services(module: dict, code_php: str, appels: dict):
    """
    Ajoute au module ce dont le découpage en services a besoin : son
    code d'origine (pour en déduire les tables) et les modules qu'il
    appelle (pour mesurer la cohésion).
    """
    module["code_source"] = _source_module(
        code_php, module["nom_original"], module.get("type", "fonction"))
    module["appelle"] = sorted(appels.get(module["nom_original"], set()))


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


def _appels_internes(code_php: str, noms_fonctions: list) -> dict:
    """
    Qui appelle qui, à l'intérieur du fichier.

    Sert à deux choses : choisir le pattern de migration (un fichier
    très entrelacé se migre progressivement) et ordonner les modules.
    """
    appels = {nom: set() for nom in noms_fonctions}
    if not code_php:
        return appels
    for nom in noms_fonctions:
        source = _source_module(code_php, nom, "fonction")
        for autre in noms_fonctions:
            if autre == nom:
                continue
            if re.search(rf"\b{re.escape(autre)}\s*\(", source):
                appels[nom].add(autre)
    return appels


def _trier_par_appels(modules: list, appels: dict) -> list:
    """Une fonction appelée passe avant celle qui l'appelle."""
    if not appels:
        return modules
    restants = list(modules)
    ordonnes, places = [], set()
    # Tri topologique simple ; en cas de cycle (récursivité croisée),
    # l'ordre d'origine est conservé pour les modules restants.
    for _ in range(len(restants)):
        progres = False
        for module in list(restants):
            requis = appels.get(module["nom_original"], set())
            if all(r in places or r not in
                   {m["nom_original"] for m in modules} for r in requis):
                ordonnes.append(module)
                places.add(module["nom_original"])
                restants.remove(module)
                progres = True
        if not progres:
            break
    return ordonnes + restants


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
    print("\n[OK] Architecte gère les classes")

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
    print("[OK] Points d'attention et révision du plan opérationnels")

# ═══ DÉCOUPAGE EN SERVICES ════════════════════════════
# Le sujet demande un refactoring vers une architecture moderne, dont
# les microservices. Ce découpage est une PROPOSITION d'architecture,
# pas un déploiement : le système ne génère ni conteneurs, ni API
# inter-services, ni bases séparées. Il indique où passent les
# frontières, et ce qui s'oppose à les tracer.
#
# Critère retenu : la cohésion par les DONNÉES d'abord (un service
# possède ses tables), puis par les APPELS. C'est la règle classique
# du découpage par domaine : ce qui change ensemble reste ensemble.

MOTIF_TABLE = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+[`\"']?([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE)


def tables_utilisees(code: str) -> set:
    """Tables lues ou écrites par un code PHP."""
    exclus = {"if", "select", "where", "set", "values", "exists"}
    return {t.lower() for t in MOTIF_TABLE.findall(code or "")
            if t.lower() not in exclus}


def decouper_en_services(modules: list, graine: int = 42,
                         resolution: float = 1.0) -> dict:
    """
    Découpage du projet en services candidats, par partitionnement de
    graphe.

    Méthode
    -------
      1. Contrainte métier (dure) : un service POSSÈDE ses tables. Les
         modules qui touchent une même table sont fusionnés d'office.
      2. Bibliothèques partagées : un module sans données, appelé depuis
         plusieurs domaines, n'est pas un service — il est dupliqué.
      3. Graphe pondéré des domaines, arêtes = appels entre modules.
      4. Détection de communautés par l'algorithme de LOUVAIN, qui
         maximise la MODULARITÉ : beaucoup de liens à l'intérieur des
         groupes, peu entre eux. Graine fixée : le résultat est
         reproductible.
      5. Modularité, cohésion et couplage mesurés ; obstacles signalés.

    modules : [{"nom", "fichier", "code", "appelle": set(noms)}]
    """
    import networkx as nx
    from networkx.algorithms.community import louvain_communities, modularity

    if not modules:
        return {"services": [], "obstacles": [], "metriques": {},
                "bibliotheques_partagees": []}

    noms = [m["nom"] for m in modules]
    tables = {m["nom"]: tables_utilisees(m.get("code", "")) for m in modules}
    appels = {m["nom"]: {a for a in (m.get("appelle") or set()) if a in noms}
              for m in modules}

    # ── 1. Contrainte dure : fusion des modules partageant une table ──
    parent = {n: n for n in noms}

    def racine(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    for i, a in enumerate(noms):
        for b in noms[i + 1:]:
            if tables[a] & tables[b]:
                parent[racine(b)] = racine(a)

    # Identifiant canonique de chaque groupe de tables : indépendant de
    # l'ordre des modules, pour un résultat reproductible.
    membres_groupe = {}
    for n in noms:
        if tables[n]:
            membres_groupe.setdefault(racine(n), []).append(n)
    canonique = {r: min(m) for r, m in membres_groupe.items()}
    domaine = {n: canonique[racine(n)] for n in noms if tables[n]}

    # ── Domaine effectif des modules sans données ──
    # Un module sans table rejoint le domaine dont il LIT les données :
    # login, qui appelle getUserByEmail, relève des utilisateurs.
    for _ in range(len(noms)):
        change = False
        for n in sorted(noms):
            if n in domaine:
                continue
            lus = {domaine[a] for a in appels[n] if a in domaine}
            if len(lus) == 1:
                domaine[n] = lus.pop()
                change = True
        if not change:
            break

    # ── 2. Bibliothèques partagées ──
    # Sans données propres, appelé depuis plusieurs domaines : c'est un
    # utilitaire commun, à dupliquer plutôt qu'à exposer en service.
    appele_par = {n: {a for a in noms if n in appels[a]} for n in noms}
    bibliotheques = sorted(
        n for n in noms if not tables[n]
        and len({domaine[a] for a in appele_par[n] if a in domaine}) > 1)
    for b in bibliotheques:
        domaine.pop(b, None)

    # ── 3. Graphe pondéré des domaines, construit dans un ordre canonique ──
    graphe = nx.Graph()
    noeud = {n: domaine.get(n, n) for n in sorted(noms) if n not in bibliotheques}
    graphe.add_nodes_from(sorted(set(noeud.values())))
    aretes = {}
    for a in sorted(noeud):
        for b in sorted(appels[a]):
            if b in noeud and noeud[a] != noeud[b]:
                cle = tuple(sorted((noeud[a], noeud[b])))
                aretes[cle] = aretes.get(cle, 0) + 1
    for (u, v), poids in sorted(aretes.items()):
        graphe.add_edge(u, v, weight=poids)

    # ── 4. Louvain ──
    communautes = louvain_communities(graphe, weight="weight", seed=graine,
                                      resolution=resolution)
    communaute_de = {}
    for indice, groupe in enumerate(sorted(communautes, key=lambda g: min(g))):
        for d in groupe:
            communaute_de[d] = indice

    groupes = {}
    for n, d in noeud.items():
        groupes.setdefault(communaute_de[d], []).append(n)

    services = []
    for membres in sorted(groupes.values(), key=lambda g: sorted(g)):
        compte = {}
        for m in membres:
            for t in tables[m]:
                compte[t] = compte.get(t, 0) + 1
        tables_service = sorted(compte)
        # nom du service : la table la plus utilisée par ses modules
        principale = (sorted(compte, key=lambda t: (-compte[t], t))[0]
                      if compte else None)
        services.append({
            "nom": f"service_{principale}" if principale
                   else f"service_{sorted(membres)[0].lower()}",
            "modules": sorted(membres),
            "tables": tables_service,
            "fichiers": sorted({m["fichier"] for m in modules
                                if m["nom"] in membres}),
        })

    # Modularité mesurée sur le graphe des MODULES (appels et tables
    # partagées), plus significative que sur le graphe contracté.
    graphe_modules = nx.Graph()
    graphe_modules.add_nodes_from(sorted(noeud))
    for a in sorted(noeud):
        for b in sorted(appels[a]):
            if b in noeud and a != b:
                graphe_modules.add_edge(a, b, weight=1)
    for i, a in enumerate(sorted(noeud)):
        for b in sorted(noeud)[i + 1:]:
            if tables[a] & tables[b]:
                graphe_modules.add_edge(a, b, weight=2)
    modularite = None
    if graphe_modules.number_of_edges() > 0 and len(services) > 1:
        modularite = round(modularity(
            graphe_modules, [set(s["modules"]) for s in services],
            weight="weight"), 3)

    # ── 5. Mesures ──
    service_de = {m: s["nom"] for s in services for m in s["modules"]}
    internes = externes = 0
    for service in services:
        dependances = set()
        for membre in service["modules"]:
            for appele in appels[membre]:
                if appele in bibliotheques:
                    continue            # appel local : la bibliothèque est dupliquée
                if service_de[appele] == service["nom"]:
                    internes += 1
                else:
                    externes += 1
                    dependances.add(service_de[appele])
        service["depend_de"] = sorted(dependances)

    total = internes + externes
    metriques = {
        "methode": "louvain",
        "services": len(services),
        "modularite": modularite,
        "cohesion": round(100 * internes / total, 1) if total else 100.0,
        "couplage": round(100 * externes / total, 1) if total else 0.0,
        "appels_internes": internes,
        "appels_inter_services": externes,
    }

    obstacles = []
    for module in modules:
        code = module.get("code", "")
        if "$_SESSION" in code:
            obstacles.append(f"« {module['nom']} » dépend de l'état de session "
                             f"PHP : à porter en jeton ou en service de session")
        if re.search(r"\bglobal\s+\$", code):
            obstacles.append(f"« {module['nom']} » utilise une variable globale : "
                             f"l'état doit devenir explicite avant tout découpage")
    if externes:
        obstacles.append(f"{externes} appel(s) deviendraient des appels réseau : "
                         f"prévoir la gestion des pannes et des délais")
    if len(services) == 1:
        obstacles.append("un seul service se dégage : le projet est trop couplé ou "
                         "trop petit pour être découpé, un monolithe modulaire est "
                         "préférable")
    elif modularite is not None and modularite < 0.3:
        obstacles.append(f"modularité faible ({modularite}) : les frontières entre "
                         f"services sont peu nettes, un monolithe modulaire est "
                         f"probablement préférable")

    return {"services": services, "metriques": metriques,
            "bibliotheques_partagees": bibliotheques,
            "obstacles": sorted(set(obstacles))}


def resume_services(decoupage: dict) -> str:
    """Rendu lisible, pour le journal et le rapport."""
    if not decoupage.get("services"):
        return "découpage en services non applicable"
    lignes = []
    m = decoupage["metriques"]
    lignes.append(f"{m['services']} service(s) candidat(s) — "
                  f"cohésion {m['cohesion']}%, couplage {m['couplage']}%"
                  + (f", modularité {m['modularite']}" if m.get("modularite")
                     is not None else "")
                  + f" (méthode : {m.get('methode', 'règles')})")
    if decoupage.get("bibliotheques_partagees"):
        lignes.append("  • bibliothèque partagée (à dupliquer dans chaque "
                      "service plutôt qu'à exposer) : "
                      + ", ".join(decoupage["bibliotheques_partagees"]))
    for service in decoupage["services"]:
        dependances = (" → dépend de " + ", ".join(service["depend_de"])
                       if service["depend_de"] else "")
        lignes.append(f"  • {service['nom']} : "
                      f"{', '.join(service['modules'])}"
                      + (f" [tables : {', '.join(service['tables'])}]"
                         if service["tables"] else "")
                      + dependances)
    for obstacle in decoupage["obstacles"]:
        lignes.append(f"  [ATTENTION]  {obstacle}")
    return "\n".join(lignes)



# ═══ PLAN DU PROJET ENTIER ══════════════════════════════
# L'Architecte DÉCIDE à partir de ce que l'Analyste a constaté : dans
# quel ordre migrer les fichiers, comment découper chacun en modules,
# et quel découpage en services proposer.

import os as _os
import os


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
            print("[ATTENTION]  Cycle de dépendances détecté, "
                  "ordre alphabétique appliqué aux fichiers restants")
            ordre.extend(sorted(restants.keys()))
            break

        for f in sorted(prets):
            ordre.append(f)
            del restants[f]

    return ordre


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


def planifier_projet(analyse_projet: dict) -> dict:
    """
    Plan de migration du projet : ordre des fichiers (dépendances
    d'abord), modules de chaque fichier dans leur ordre, découpage en
    services proposé.
    """
    dossier = analyse_projet["dossier"]
    ordre_fichiers = tri_topologique(
        {f: list(d) for f, d in analyse_projet["dependances"].items()})

    fichiers, modules_projet = [], []
    for fichier in ordre_fichiers:
        chemin = _os.path.join(dossier, fichier)
        with open(chemin, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
        plan = planifier_migration(analyse_projet["analyses"][fichier], code)
        langage = analyse_projet.get("langage", "php")
        modules = []
        for module in plan.get("modules", []):
            module = dict(module)
            module["langage_source"] = langage
            if langage != "php":
                # L'unité est extraite par l'adaptateur du langage, et son
                # nom (VERIFIER-MOT-DE-PASSE) devient un nom Python valide.
                from langages import adaptateur
                module["code_source"] = adaptateur(langage).extraire_unite(
                    code, module.get("nom_original", ""))
                module["nom_python"] = re.sub(
                    r"[^a-z0-9_]", "_", str(module.get("nom_original", "")).lower()).strip("_")
            module["fichier"] = fichier
            module["champs_requis"] = analyse_projet["usages_champs"].get(
                module.get("nom_original"), [])
            module["id"] = f"{fichier}::{module.get('nom_python')}"
            modules.append(module)
            modules_projet.append({
                "nom": module.get("nom_original") or module.get("nom_python"),
                "fichier": fichier,
                "code": module.get("code_source", ""),
                "appelle": set(module.get("appelle") or []),
            })
        fichiers.append({"fichier": fichier,
                         "depend_de": analyse_projet["dependances"][fichier],
                         "pattern": plan.get("pattern_migration"),
                         "modules": modules,
                         "invariants": plan.get("invariants_a_preserver", []),
                         # Les failles TELLES QUE L'ANALYSTE LES A CONSTATÉES,
                         # avec leur fonction : les priorités du plan perdaient
                         # ce champ, et chaque module était jugé sur les failles
                         # de toutes les fonctions du fichier.
                         "failles": analyse_projet["analyses"][fichier].get(
                             "failles_potentielles", [])})

    # Appels ENTRE fichiers : nécessaires pour juger la cohésion des services.
    noms = {m["nom"] for m in modules_projet}
    for m in modules_projet:
        for autre in noms - {m["nom"]}:
            if re.search(rf"\b{re.escape(autre)}\s*\(", m["code"] or ""):
                m["appelle"].add(autre)

    return {
        "ordre_fichiers": ordre_fichiers,
        "fichiers": fichiers,
        "ordre_modules": [m["id"] for f in fichiers for m in f["modules"]],
        "decoupage_services": decouper_en_services(modules_projet)
        if modules_projet else None,
    }