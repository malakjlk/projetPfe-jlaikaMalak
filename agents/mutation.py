"""
Test de mutation — SMAML
=========================
Quelles entrées détectent réellement les bugs ? On introduit
volontairement de petites erreurs dans la fonction Python — des
« mutants » — et on compte celles que chaque jeu d'entrées détecte : un
mutant est « tué » si au moins une entrée lui fait produire un résultat
différent de la fonction d'origine.

C'est la mesure de référence pour comparer des générateurs de tests :
ici, les entrées fixes du Comparateur, celles de l'IA, et les deux
ensemble.

Mutations appliquées, une à la fois :
  <  ↔  <=      >  ↔  >=      ==  ↔  !=     (bornes et égalités)
  and  ↔  or                                 (conditions composées)
  not x  →  x                                (négations)
  n  →  n + 1                                (constantes entières)
  True  ↔  False                             (constantes booléennes)
  raise …  →  pass                           (garde supprimée)

Limite connue : un mutant peut être ÉQUIVALENT à l'original (aucune
entrée ne peut le distinguer) ; il compte alors comme survivant. Le
score est donc un minorant.
"""

from __future__ import annotations

import ast
import copy
import json
import os
import subprocess
import sys
import tempfile

_ECHANGES = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
             ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}


def _cibles(fonction: ast.AST) -> list:
    """Chaque endroit mutable de la fonction : (type, nœud, détail)."""
    cibles = []
    for noeud in ast.walk(fonction):
        if isinstance(noeud, ast.Compare):
            for i, op in enumerate(noeud.ops):
                if type(op) in _ECHANGES:
                    cibles.append(("comparaison", noeud, i))
        elif isinstance(noeud, ast.BoolOp):
            cibles.append(("logique", noeud, None))
        elif isinstance(noeud, ast.UnaryOp) and isinstance(noeud.op, ast.Not):
            cibles.append(("negation", noeud, None))
        elif isinstance(noeud, ast.Constant) and type(noeud.value) is int:
            cibles.append(("constante", noeud, None))
        elif isinstance(noeud, ast.Constant) and type(noeud.value) is bool:
            cibles.append(("booleen", noeud, None))
        elif isinstance(noeud, ast.Raise):
            cibles.append(("garde", noeud, None))
    return cibles


class _Mutateur(ast.NodeTransformer):
    def __init__(self, cible_id, genre, detail):
        self.cible_id, self.genre, self.detail = cible_id, genre, detail
        self.description = ""

    def visit(self, noeud):
        if id(noeud) != self.cible_id:
            return self.generic_visit(noeud)
        if self.genre == "comparaison":
            ancien = noeud.ops[self.detail]
            noeud.ops[self.detail] = _ECHANGES[type(ancien)]()
            self.description = (f"ligne {noeud.lineno} : {type(ancien).__name__} → "
                                f"{type(noeud.ops[self.detail]).__name__}")
            return noeud
        if self.genre == "logique":
            noeud.op = ast.Or() if isinstance(noeud.op, ast.And) else ast.And()
            self.description = f"ligne {noeud.lineno} : and ↔ or"
            return noeud
        if self.genre == "negation":
            self.description = f"ligne {noeud.lineno} : not supprimé"
            return noeud.operand
        if self.genre == "constante":
            self.description = f"ligne {noeud.lineno} : {noeud.value} → {noeud.value + 1}"
            return ast.copy_location(ast.Constant(noeud.value + 1), noeud)
        if self.genre == "booleen":
            self.description = f"ligne {noeud.lineno} : {noeud.value} → {not noeud.value}"
            return ast.copy_location(ast.Constant(not noeud.value), noeud)
        if self.genre == "garde":
            self.description = f"ligne {noeud.lineno} : garde (raise) supprimée"
            return ast.copy_location(ast.Pass(), noeud)
        return noeud


def generer_mutants(code: str, nom_fonction: str, maximum: int = 40) -> list:
    """[(description, code mutant)] — uniquement dans la fonction visée."""
    arbre = ast.parse(code)
    fonction = next((n for n in ast.walk(arbre) if isinstance(n, (ast.FunctionDef,
                     ast.AsyncFunctionDef)) and n.name == nom_fonction), None)
    if fonction is None:
        return []
    mutants = []
    for genre, noeud, detail in _cibles(fonction)[:maximum]:
        copie = copy.deepcopy(arbre)
        # retrouver le même nœud dans la copie, par sa position dans le parcours
        index = [id(n) for n in ast.walk(arbre)].index(id(noeud))
        cible = list(ast.walk(copie))[index]
        mutateur = _Mutateur(id(cible), genre, detail)
        nouvel_arbre = ast.fix_missing_locations(mutateur.visit(copie))
        try:
            mutants.append((mutateur.description, ast.unparse(nouvel_arbre)))
        except Exception:
            continue
    return mutants


_HARNAIS = r'''
import json, sys
espace = {"__name__": "module_migre", "__file__": sys.argv[1]}
exec(open(sys.argv[1], encoding="utf-8").read(), espace)
fonction = espace[sys.argv[2]]
resultats = []
for arguments in json.load(open(sys.argv[3], encoding="utf-8")):
    try:
        resultats.append({"ok": True, "valeur": repr(fonction(*arguments))[:300]})
    except BaseException as e:
        resultats.append({"ok": False, "valeur": type(e).__name__})
print(json.dumps(resultats))
'''


def executer(code: str, nom_fonction: str, cas: list, delai_s: float = 20,
             dossier_python: str = None):
    """Résultats de la fonction sur chaque cas, ou None si elle ne s'exécute pas."""
    with tempfile.TemporaryDirectory() as dossier:
        chemins = {n: f"{dossier}/{n}" for n in ("code.py", "harnais.py", "cas.json")}
        open(chemins["code.py"], "w", encoding="utf-8").write(code)
        open(chemins["harnais.py"], "w", encoding="utf-8").write(_HARNAIS)
        json.dump(cas, open(chemins["cas.json"], "w", encoding="utf-8"), default=str)
        try:
            env = dict(os.environ)
            if dossier_python:      # les autres fichiers du projet, importables
                env["PYTHONPATH"] = os.pathsep.join(filter(None, [dossier_python,
                                                                  env.get("PYTHONPATH")]))
            sortie = subprocess.run([sys.executable, chemins["harnais.py"], chemins["code.py"],
                                     nom_fonction, chemins["cas.json"]], capture_output=True,
                                    text=True, encoding="utf-8", errors="replace",
                                    timeout=delai_s, env=env)
            return json.loads(sortie.stdout.strip().splitlines()[-1])
        except (subprocess.TimeoutExpired, ValueError, IndexError):
            return None


def comparer_sources(code: str, nom_fonction: str, sources: dict, contexte: str = "",
                     dossier_python: str = None) -> dict:
    """
    Score de mutation de chaque source d'entrées.
    sources : {"fixes": [arguments…], "ia": [arguments…]} ; « hybride » est
    calculé d'office comme leur réunion.
    """
    sources = {k: [list(a) for a in v] for k, v in sources.items() if v}
    # UNE SEULE clé pour dédoublonner et pour retrouver une entrée : [10, 0]
    # et [10, 0.0] sont égaux pour Python, mais pas en texte.
    cle = lambda a: json.dumps(a, default=str, sort_keys=True)
    uniques = {}
    for liste in sources.values():
        for a in liste:
            uniques.setdefault(cle(a), a)
    tous = list(uniques.values())
    if not tous:
        return {"statut": "sans_entrees"}
    complet = (contexte + "\n\n" + code) if contexte else code
    origine = executer(complet, nom_fonction, tous, dossier_python=dossier_python)
    if origine is None:
        return {"statut": "non_executable",
                "raison": "la fonction ne s'exécute pas seule (dépendances, base de données)"}
    # Si la fonction échoue sur TOUTES les entrées (base de données absente,
    # par exemple), aucun mutant ne peut être distingué : le score serait
    # faussement bas. Le cas est signalé et exclu des moyennes.
    if all(not r["ok"] for r in origine) and len({r["valeur"] for r in origine}) == 1:
        return {"statut": "non_observable",
                "raison": f"la fonction échoue sur toutes les entrées ({origine[0]['valeur']}) : "
                          f"son comportement n'est pas observable hors de son environnement"}
    mutants = generer_mutants(code, nom_fonction)
    if not mutants:
        return {"statut": "sans_mutant"}

    tues_par_cas = []                       # pour chaque mutant : indices des cas qui le tuent
    for description, mutant in mutants:
        resultats = executer((contexte + "\n\n" + mutant) if contexte else mutant,
                             nom_fonction, tous, dossier_python=dossier_python)
        if resultats is None:               # mutant qui plante ou boucle : tué par tous
            tues_par_cas.append((description, set(range(len(tous)))))
            continue
        tues_par_cas.append((description, {i for i, (o, m) in enumerate(zip(origine, resultats))
                                           if o != m}))

    position = {k: i for i, k in enumerate(uniques)}
    indices = {k: {position[cle(a)] for a in v} for k, v in sources.items()}
    indices["hybride"] = set(range(len(tous)))
    scores = {}
    for source, ensemble in indices.items():
        tues = [d for d, cas in tues_par_cas if cas & ensemble]
        scores[source] = {"entrees": len(ensemble), "tues": len(tues),
                          "score": round(len(tues) / len(mutants), 3)}
    seulement_ia = [d for d, cas in tues_par_cas
                    if cas & indices.get("ia", set()) and not cas & indices.get("fixes", set())]
    return {"statut": "mesure", "mutants": len(mutants), "scores": scores,
            "detectes_seulement_par_ia": seulement_ia,
            "survivants": [d for d, cas in tues_par_cas if not cas]}