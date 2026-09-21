"""
Agent Vérification Formelle — SMAML
====================================
Couche de vérification FORMELLE par EXÉCUTION SYMBOLIQUE
(exigence explicite du sujet de PFE).

Test différentiel = EMPIRIQUE : 15 entrées concrètes comparées.
Exécution symbolique = FORMELLE : CrossHair (solveur SMT Z3)
remplace les entrées par des SYMBOLES, explore les chemins du
code et cherche mathématiquement un CONTRE-EXEMPLE violant la
propriété. Aucun contre-exemple trouvé (dans le budget) → la
propriété tient pour toutes les entrées explorées, pas 15.

Chaque invariant est traduit en CONTRAT (PEP 316, docstring
`post:`) sur un harnais appelant la fonction générée :

    def _smaml_verif_0(p: str):
        '''
        raises: Exception
        post: len(p) >= 8
        '''
        validate_password(p)   # lève une exception si invalide
        return True

Lecture : « SI validate_password(p) retourne sans exception,
ALORS len(p) >= 8 ». Vérification oubliée par le LLM →
Z3 exhibe un contre-exemple concret (ex. p = '').

Prérequis : pip install crosshair-tool
"""

import os
import re
import sys
import subprocess
import tempfile

import cache_smaml


# ─── Invariant → contrat formel ──────────────────────

def extraire_seuil_longueur(invariant: dict) -> int:
    code = invariant.get("code", "") or invariant.get("description", "")
    m = re.search(r"strlen\s*\([^)]*\)\s*<\s*(\d+)", code)
    if m:
        return int(m.group(1))
    m = re.search(r"<\s*(\d+)", code)
    return int(m.group(1)) if m else 8


def extraire_borne_numerique(invariant: dict):
    """
    Borne d'un invariant métier numérique : « solde >= 0 »,
    « quantité <= 100 ». Retourne (opérateur, valeur) ou None.

    On ne retient que les comparaisons portant sur une VALEUR
    (montant, solde, âge...), pas sur une longueur : strlen() est
    déjà traité par extraire_seuil_longueur.
    """
    code = invariant.get("code", "") or invariant.get("description", "")
    if "strlen" in code or "count(" in code:
        return None
    # PHP rejette quand la condition est vraie : « if ($solde < 0)
    # throw » signifie donc que tout appel accepté garantit solde >= 0.
    m = re.search(r"<\s*(-?\d+(?:\.\d+)?)", code)
    if m:
        return (">=", m.group(1))
    m = re.search(r">\s*(-?\d+(?:\.\d+)?)", code)
    if m:
        return ("<=", m.group(1))
    return None


def contrat_pour_invariant(invariant: dict, param: str):
    """
    (postcondition, libellé, type du paramètre) ou None si
    l'invariant n'est pas formalisable.
    """
    type_inv = invariant.get("type", "")

    if type_inv == "validation_longueur":
        seuil = extraire_seuil_longueur(invariant)
        return (f"len({param}) >= {seuil}",
                f"acceptation ⇒ longueur ≥ {seuil}", "str")

    if type_inv == "validation_format":
        desc = (invariant.get("description", "")
                + invariant.get("code", "")).lower()
        if "majuscule" in desc or "a-z" in desc:
            return (f"any(c.isupper() for c in {param})",
                    "acceptation ⇒ au moins une majuscule", "str")

    if type_inv == "validation_existence":
        return (f"{param} is not None",
                "acceptation ⇒ argument non nul", "str")

    # Invariant métier numérique : « le solde ne peut jamais être
    # négatif » est la formulation donnée en exemple par l'encadrante.
    borne = extraire_borne_numerique(invariant)
    if borne:
        operateur, valeur = borne
        # NaN est exclu : « nan < 0 » vaut False en Python, donc un
        # code correct accepte nan sans violer sa garde. Ce serait un
        # contre-exemple du langage, pas un défaut de migration.
        return (f"{param} {operateur} {valeur}",
                f"acceptation ⇒ valeur {operateur} {valeur}", "float",
                f"{param} == {param}")

    return None


# ─── Harnais ─────────────────────────────────────────

STUBS = '''\
# Stubs légers : évite de tracer les bibliothèques web dans Z3
from typing import Optional, List, Dict, Any, Union, Tuple

class HTTPException(Exception):
    def __init__(self, status_code=None, detail=None):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)

class ValidationError(Exception):
    pass

# Stub de pydantic.BaseModel : accepte n'importe quels champs
class BaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

# Stub de Depends/Field (souvent importés de fastapi/pydantic)
def Depends(x=None): return x
def Field(*a, **k): return None

# ── Enregistrement des requêtes SQL ──
# Pour vérifier qu'une entrée utilisateur ne modifie pas le TEXTE de
# la requête (non-interférence), il faut observer ce qui est envoyé
# à la base. Ces doublures enregistrent les requêtes sans base réelle.
_SMAML_REQUETES = []

def _smaml_reset():
    while _SMAML_REQUETES:
        _SMAML_REQUETES.pop()

class _SMAMLCurseur:
    description = ()
    rowcount = 0
    lastrowid = 1
    def execute(self, requete, params=None, *a, **k):
        _SMAML_REQUETES.append(str(requete))
        return self
    executemany = execute
    def fetchone(self, *a, **k): return None
    def fetchall(self, *a, **k): return []
    def fetchmany(self, *a, **k): return []
    def scalar(self, *a, **k): return None
    def scalars(self, *a, **k): return self
    def first(self, *a, **k): return None
    def all(self, *a, **k): return []
    def close(self): pass
    def __iter__(self): return iter(())
    def __enter__(self): return self
    def __exit__(self, *a): return False

class _SMAMLConnexion(_SMAMLCurseur):
    def cursor(self, *a, **k): return _SMAMLCurseur()
    def commit(self): pass
    def rollback(self): pass
    def begin(self, *a, **k): return self
    def query(self, *a, **k): return _SMAMLCurseur()
    def add(self, *a, **k): pass
    def refresh(self, *a, **k): pass
    def filter(self, *a, **k): return self
    def filter_by(self, *a, **k): return self
    def is_connected(self): return True

def _smaml_connect(*a, **k): return _SMAMLConnexion()

class _SMAMLModule:
    """Remplace sqlite3, psycopg2, pymysql, mysql.connector..."""
    connect = staticmethod(_smaml_connect)
    Error = Exception
    DatabaseError = Exception
    IntegrityError = Exception
    def __init__(self, **sous_modules):
        for nom, valeur in sous_modules.items():
            setattr(self, nom, valeur)

sqlite3 = _SMAMLModule()
psycopg2 = _SMAMLModule()
pymysql = _SMAMLModule()
mysql = _SMAMLModule(connector=_SMAMLModule())

class _SMAMLTexte:
    """Résultat de sqlalchemy.text() : son str() est la requête."""
    def __init__(self, requete): self._requete = str(requete)
    def __str__(self): return self._requete
    def bindparams(self, *a, **k): return self

def text(requete, *a, **k): return _SMAMLTexte(requete)
def create_engine(*a, **k): return _SMAMLConnexion()
def sessionmaker(*a, **k): return _smaml_connect
def declarative_base(*a, **k): return object

# Noms SQLAlchemy utilisés en annotation : sans eux, la simple
# définition de la fonction échoue (NameError) et le code entier
# devient non chargeable par CrossHair.
class Engine(_SMAMLConnexion): pass
class Connection(_SMAMLConnexion): pass
class Result(_SMAMLCurseur): pass
class SQLAlchemyError(Exception): pass

# Stubs SQLAlchemy (annotations db: Session = Depends(get_db))
class Session(_SMAMLConnexion):
    pass
def get_db(): return _SMAMLConnexion()
'''

IMPORTS_A_NEUTRALISER = re.compile(
    r"^\s*(from\s+\S+\s+import\s+.*|import\s+\S+.*)$",
    re.MULTILINE,
)


def _neutraliser_imports(code: str) -> str:
    """
    Commente tous les imports SAUF ceux de la bibliothèque
    standard sûre (re, math, html, typing...), pour que
    CrossHair puisse charger le code sans dépendances externes
    (fastapi, pydantic, ni modules du projet comme 'db'/'outils').
    """
    stdlib_ok = ("import re", "import math", "import html",
                 "import json", "import typing", "from typing",
                 "from math", "from html", "import datetime")

    def remplacer(m):
        ligne = m.group(0).strip()
        if any(ligne.startswith(s) for s in stdlib_ok):
            return m.group(0)
        return "# [neutralisé pour vérif. formelle] " + ligne

    return IMPORTS_A_NEUTRALISER.sub(remplacer, code)


def _detecter_classe_methode(code: str, nom_methode: str):
    """
    Cherche si nom_methode est défini comme MÉTHODE d'une classe.
    Retourne le nom de la classe englobante, ou None si c'est
    une fonction de module.
    """
    import re as _re
    classe_courante = None
    for ligne in code.split("\n"):
        m_classe = _re.match(r"\s*class\s+(\w+)", ligne)
        if m_classe:
            # Une classe au niveau module (pas indentée)
            if not ligne.startswith((" ", "\t")):
                classe_courante = m_classe.group(1)
        m_def = _re.match(r"(\s*)def\s+(\w+)", ligne)
        if m_def and m_def.group(2) == nom_methode:
            # Méthode indentée → appartient à la classe courante
            if m_def.group(1):   # il y a une indentation
                return classe_courante
            return None          # def au niveau module = fonction
    return None


def _compter_params_cible(code: str, nom_cible: str) -> int:
    """
    Compte les paramètres (hors self) de la fonction/méthode
    ciblée, pour compléter l'appel du harnais avec des valeurs
    neutres sur les paramètres autres que celui vérifié.
    """
    import re as _re
    m = _re.search(rf"def\s+{_re.escape(nom_cible)}\s*\(([^)]*)\)", code)
    if not m:
        return 1
    params = [p.strip() for p in m.group(1).split(",") if p.strip()]
    params = [p for p in params if p != "self"]
    return len(params)


def _stubber_classes_manquantes(code: str) -> str:
    """
    Crée un stub pour chaque classe parente dont l'import a été
    neutralisé. Exemple : le code contient
        from utilisateurs import User   (← neutralisé)
        class Admin(User): ...
    Sans stub, Python ne peut pas charger le fichier (NameError
    sur User) et CrossHair échoue avec "Could not import your
    code". On injecte donc une classe User vide, comme pour
    HTTPException/BaseModel dans STUBS.
    """
    definis = set(re.findall(r"^\s*class\s+(\w+)", code, re.MULTILINE))
    definis |= set(re.findall(r"^\s*def\s+(\w+)", code, re.MULTILINE))
    # Noms déjà fournis par STUBS (+ object, jamais à stubber)
    definis |= {"HTTPException", "ValidationError", "BaseModel",
                "Depends", "Field", "Exception", "object"}

    stubs = ""
    for m in re.finditer(r"class\s+\w+\s*\(\s*([\w\s,]+)\)", code):
        for parent in m.group(1).split(","):
            parent = parent.strip()
            if parent and parent not in definis:
                stubs += (f"\nclass {parent}:\n"
                          f"    def __init__(self, *a, **k): pass\n")
                definis.add(parent)
    return stubs + code


def _preparer_code(code_python: str, nom_fonction: str):
    """Code neutralisé + classe englobante + appel de la cible."""
    code = _neutraliser_imports(code_python)
    code = _stubber_classes_manquantes(code)
    classe = _detecter_classe_methode(code, nom_fonction)
    return code, classe


def _appel_cible(classe, nom_fonction: str, liste_args: str,
                 indentation: str = "    ") -> str:
    if classe:
        return (f"{indentation}_instance = {classe}()\n"
                f"{indentation}_instance.{nom_fonction}({liste_args})")
    return f"{indentation}{nom_fonction}({liste_args})"


def construire_harnais(code_python: str, nom_fonction: str,
                       contrats: list, param: str) -> str:
    code = _neutraliser_imports(code_python)
    code = _stubber_classes_manquantes(code)

    # La cible est-elle une méthode de classe ou une fonction ?
    classe = _detecter_classe_methode(code, nom_fonction)

    # Combien de paramètres la cible attend-elle ? Le 1er est le
    # paramètre vérifié (symbolique) ; les autres reçoivent une
    # valeur neutre pour que l'appel soit valide.
    nb_params = _compter_params_cible(code, nom_fonction)
    args_supp = ", ".join(["1"] * (nb_params - 1)) if nb_params > 1 else ""
    liste_args = param + ((", " + args_supp) if args_supp else "")

    harnais = ""
    for i, contrat in enumerate(contrats):
        post, _lib = contrat[0], contrat[1]
        type_param = contrat[2] if len(contrat) > 2 else "str"
        pre = contrat[3] if len(contrat) > 3 else None
        appel = _appel_cible(classe, nom_fonction, liste_args)
        ligne_pre = f"    pre: {pre}\n" if pre else ""
        harnais += f'''

def _smaml_verif_{i}({param}: {type_param}):
    """
{ligne_pre}    raises: Exception
    post: {post}
    """
{appel}
    return True
'''
    return STUBS + "\n" + code + "\n" + harnais


# ─── Propriété 2 : absence d'injection SQL ───────────
# Une requête paramétrée produit TOUJOURS le même texte SQL, quelle
# que soit l'entrée : seules les valeurs liées changent. Une requête
# construite par concaténation, au contraire, change de texte avec
# l'entrée — c'est exactement ce qui rend l'injection possible.
#
# La propriété vérifiée est donc une NON-INTERFÉRENCE : le texte des
# requêtes envoyées à la base ne dépend pas de l'entrée utilisateur.
# Z3 cherche une entrée qui produise un texte différent de celui
# obtenu avec une entrée de référence ; s'il en exhibe une, la
# requête est construite dynamiquement.

MOTIFS_SQL = re.compile(
    r"\b(execute|executemany|cursor|connect|session|query|text)\s*\(|"
    r"\b(SELECT|INSERT|UPDATE|DELETE)\b", re.IGNORECASE)


def code_touche_sql(code: str) -> bool:
    return bool(MOTIFS_SQL.search(code or ""))


def construire_harnais_sql(code_python: str, nom_fonction: str,
                           param: str, nb_params: int) -> str:
    code, classe = _preparer_code(code_python, nom_fonction)
    args_supp = ", ".join(["1"] * (nb_params - 1)) if nb_params > 1 else ""
    args_symbolique = param + ((", " + args_supp) if args_supp else "")
    args_reference = "\"a\"" + ((", " + args_supp) if args_supp else "")

    harnais = f'''

def _smaml_sql_0({param}: str):
    """
    post: __return__ is True
    """
    _smaml_reset()
    try:
{_appel_cible(classe, nom_fonction, args_symbolique, "        ")}
    except Exception:
        pass
    _requetes_entree = list(_SMAML_REQUETES)

    _smaml_reset()
    try:
{_appel_cible(classe, nom_fonction, args_reference, "        ")}
    except Exception:
        pass
    _requetes_reference = list(_SMAML_REQUETES)

    # Si l'un des deux appels est rejeté avant d'atteindre la base,
    # il n'y a rien à comparer : ce n'est pas une injection.
    if not _requetes_entree or not _requetes_reference:
        return True
    return _requetes_entree == _requetes_reference
'''
    return STUBS + "\n" + code + "\n" + harnais


# ─── Propriété 3 : contrôle d'accès préservé ─────────
# Quand le PHP d'origine contrôlait un droit (rôle, session, jeton),
# la fonction Python doit refuser l'appel lorsque cette autorisation
# est absente. La propriété vérifiée est : « aucun appel sans
# autorisation ne peut aboutir ». Un contre-exemple est un appel qui
# retourne normalement alors que l'autorisation vaut None.
#
# Cette propriété n'est produite QUE si l'Analyste a relevé un
# contrôle d'accès dans le PHP : sans preuve qu'il existait à
# l'origine, exiger un refus serait une invention.

MOTS_ACCES = ("role", "rôle", "permission", "droit", "admin", "auth",
              "session", "token", "jeton", "habilitation", "acces",
              "accès", "connecte", "connecté", "is_logged")

PARAMS_ACCES = ("role", "roles", "user", "utilisateur", "current_user",
                "token", "jeton", "session", "auth", "is_admin",
                "est_admin", "permission", "droits", "acl")


def invariant_de_controle_acces(invariants: list):
    """Premier invariant portant sur un contrôle d'accès, s'il existe."""
    for inv in invariants or []:
        texte = " ".join(str(inv.get(c, "")) for c in
                         ("type", "description", "code")).lower()
        if any(mot in texte for mot in MOTS_ACCES):
            return inv
    return None


def _parametres_cible(code: str, nom_cible: str) -> list:
    m = re.search(rf"def\s+{re.escape(nom_cible)}\s*\(([^)]*)\)", code)
    if not m:
        return []
    params = []
    for brut in m.group(1).split(","):
        nom = brut.split(":")[0].split("=")[0].strip()
        if nom and nom != "self":
            params.append(nom)
    return params


def parametre_autorisation(code: str, nom_cible: str):
    """Paramètre portant l'autorisation, d'après son nom."""
    for nom in _parametres_cible(code, nom_cible):
        court = nom.lower()
        if any(mot in court for mot in PARAMS_ACCES):
            return nom
    return None


def construire_harnais_acces(code_python: str, nom_fonction: str,
                             param: str, params_cible: list,
                             param_autorisation: str) -> str:
    code, classe = _preparer_code(code_python, nom_fonction)
    # L'autorisation est absente (None) ; les autres paramètres sont
    # laissés libres, donc explorés symboliquement par le solveur.
    args = ", ".join("None" if nom == param_autorisation else param
                     for nom in params_cible) or "None"

    harnais = f'''

def _smaml_acces_0({param}: str):
    """
    raises: Exception
    post: False
    """
{_appel_cible(classe, nom_fonction, args, "    ")}
    return True
'''
    return STUBS + "\n" + code + "\n" + harnais


# ─── CrossHair ───────────────────────────────────────

def lancer_crosshair(chemin: str, timeout: int = 120) -> dict:
    try:
        p = subprocess.run(
            [sys.executable, "-m", "crosshair", "check", chemin,
             "--per_condition_timeout", "15"],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "raison": "timeout global"}

    sortie = (p.stdout or "") + (p.stderr or "")
    # Contre-exemples : "... false when calling _smaml_verif_0('') ..."
    refutations = {}
    for m in re.finditer(
        r"false when calling\s+(_smaml_\w+)\s*(\(.*?\))", sortie
    ):
        refutations[m.group(1)] = m.group(2)[:120]

    if p.returncode != 0 and not refutations and sortie.strip():
        return {"ok": False, "raison": sortie.strip()[:200]}
    return {"ok": True, "refutations": refutations}


# ─── Point d'entrée (interface pipeline) ─────────────

def _executer_harnais(contenu: str, proprietes: list) -> list:
    """
    Lance CrossHair sur un harnais et convertit son verdict.
    Le résultat est mis en cache : l'exécution symbolique est lente,
    et le même harnais revient à chaque revérification d'un code
    inchangé.
    proprietes : [(nom_fonction_harnais, libellé)].
    Un harnais qui ne se charge pas ne fait échouer QUE ses propres
    propriétés : les autres familles restent vérifiables.
    """
    def _lancer():
        with tempfile.NamedTemporaryFile(
            mode="w", suffix="_smaml_verif.py", delete=False,
            encoding="utf-8"
        ) as f:
            f.write(contenu)
            chemin = f.name
        try:
            return lancer_crosshair(chemin)
        finally:
            os.unlink(chemin)

    res, _depuis_cache = cache_smaml.avec_cache(
        "verification_formelle", [contenu], _lancer)

    if not res["ok"]:
        return [{"libelle": libelle, "statut": "non_verifiee",
                 "contre_exemple": None,
                 "raison": res.get("raison", "")[:200]}
                for _nom, libelle in proprietes]

    refutations = res["refutations"]
    resultats = []
    for nom, libelle in proprietes:
        if nom in refutations:
            resultats.append({"libelle": libelle, "statut": "refutee",
                              "contre_exemple": refutations[nom]})
        else:
            resultats.append({"libelle": libelle, "statut": "prouvee",
                              "contre_exemple": None})
    return resultats


def _snake(nom: str) -> str:
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', nom)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def _cibles_module(module_info: dict) -> list:
    """Fonctions à vérifier pour ce module (méthodes si c'est une classe)."""
    methodes = module_info.get("methodes_python") or []
    if methodes:
        return list(methodes)
    nom = module_info.get("nom_python", "")
    return [nom] if nom else []


def verifier_formellement(code_python: str, invariants: list,
                          module_info: dict) -> dict:
    """
    Vérifie formellement UN module généré, sur trois familles de
    propriétés :

      1. invariants métier explicites relevés par l'Analyste
         (longueur, format, argument non nul, borne numérique) ;
      2. absence d'injection SQL, formalisée comme une
         non-interférence : le texte des requêtes ne dépend pas de
         l'entrée utilisateur ;
      3. contrôle d'accès préservé : aucun appel sans autorisation
         n'aboutit — vérifié uniquement si le PHP d'origine
         contrôlait bien un droit.

    Retourne :
    {
      "statut": "teste" | "crosshair_absent" | "aucune_propriete"
                | "non_verifiable",
      "proprietes": [ { "libelle", "famille",
                        "statut": "prouvee"|"refutee"|"non_verifiee",
                        "contre_exemple": str|None } ],
      "score_formel": proportion de propriétés prouvées parmi celles
                      réellement vérifiées (0..1),
      "raison": détail éventuel
    }

    Honnêteté scientifique : « prouvée » = « aucun contre-exemple
    trouvé par exploration symbolique dans le budget de temps »
    (vérification bornée) — formulation à employer dans le rapport.
    """
    rapport = {"statut": "aucune_propriete",
               "proprietes": [], "score_formel": 0.0}

    try:
        import crosshair  # noqa: F401
    except ImportError:
        rapport["statut"] = "crosshair_absent"
        return rapport

    code = code_python
    if "```python" in code:
        code = code.split("```python")[1]
    if "```" in code:
        code = code.split("```")[0]

    params = module_info.get("parametres", [])
    param = (params[0].replace("$", "").strip() if params else "x") or "x"
    if not param.isidentifier():
        param = "x"

    proprietes = []

    # ── Famille 1 : invariants métier ──
    # Chaque invariant est vérifié sur SA fonction d'origine, pas sur
    # le nom du module (crucial pour les classes).
    from collections import defaultdict
    invariants_par_cible = defaultdict(list)
    for inv in invariants or []:
        fonction_origine = inv.get("fonction", "")
        cible = (_snake(fonction_origine) if fonction_origine
                 else module_info.get("nom_python", ""))
        contrat = contrat_pour_invariant(inv, param)
        if contrat and cible:
            invariants_par_cible[cible].append(contrat)

    for cible, contrats in invariants_par_cible.items():
        contenu = construire_harnais(code, cible, contrats, param)
        noms = [(f"_smaml_verif_{i}", f"{cible} : {c[1]}")
                for i, c in enumerate(contrats)]
        for r in _executer_harnais(contenu, noms):
            r["famille"] = "invariant_metier"
            proprietes.append(r)

    # ── Famille 2 : absence d'injection SQL ──
    if code_touche_sql(code):
        for cible in _cibles_module(module_info):
            if not re.search(rf"def\s+{re.escape(cible)}\s*\(", code):
                continue
            nb = _compter_params_cible(code, cible)
            contenu = construire_harnais_sql(code, cible, param, nb)
            noms = [("_smaml_sql_0",
                     f"{cible} : le texte des requêtes SQL ne dépend pas "
                     f"de l'entrée (requête paramétrée)")]
            for r in _executer_harnais(contenu, noms):
                r["famille"] = "injection_sql"
                proprietes.append(r)

    # ── Famille 3 : contrôle d'accès ──
    invariant_acces = invariant_de_controle_acces(invariants)
    if invariant_acces:
        for cible in _cibles_module(module_info):
            if not re.search(rf"def\s+{re.escape(cible)}\s*\(", code):
                continue
            params_cible = _parametres_cible(code, cible)
            autorisation = parametre_autorisation(code, cible)
            if not autorisation:
                proprietes.append({
                    "libelle": f"{cible} : contrôle d'accès préservé",
                    "famille": "controle_acces",
                    "statut": "non_verifiee", "contre_exemple": None,
                    "raison": ("le PHP contrôlait un droit mais le code "
                               "Python n'expose aucun paramètre "
                               "d'autorisation")})
                continue
            contenu = construire_harnais_acces(code, cible, param,
                                               params_cible, autorisation)
            noms = [("_smaml_acces_0",
                     f"{cible} : aucun appel sans autorisation "
                     f"({autorisation}) n'aboutit")]
            for r in _executer_harnais(contenu, noms):
                r["famille"] = "controle_acces"
                proprietes.append(r)

    if not proprietes:
        return rapport

    rapport["proprietes"] = proprietes
    verifiees = [p for p in proprietes if p["statut"] != "non_verifiee"]
    prouvees = sum(1 for p in verifiees if p["statut"] == "prouvee")
    rapport["score_formel"] = (prouvees / len(verifiees)
                               if verifiees else 0.0)
    if verifiees:
        rapport["statut"] = "teste"
    else:
        rapport["statut"] = "non_verifiable"
        rapport["raison"] = proprietes[0].get("raison", "")
    return rapport


# ─── Test autonome ───────────────────────────────────
if __name__ == "__main__":
    import json

    invariants = [{
        "type": "validation_longueur",
        "description": "Vérification de longueur de champ",
        "code": "if (strlen($password) < 8) { throw ... }",
    }]
    module = {"nom_python": "validate_password",
              "parametres": ["$password"]}

    code_correct = """
from fastapi import HTTPException

def validate_password(password: str) -> bool:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Trop court")
    return True
"""
    code_casse = """
from fastapi import HTTPException

def validate_password(password: str) -> bool:
    return True
"""

    print("=" * 60)
    print("Vérification formelle SMAML — exécution symbolique (Z3)")
    print("=" * 60)

    print("\nCAS 1 — Code correct (invariant présent) :")
    r1 = verifier_formellement(code_correct, invariants, module)
    print(json.dumps(r1, indent=2, ensure_ascii=False))

    print("\nCAS 2 — Code défectueux (invariant oublié) :")
    r2 = verifier_formellement(code_casse, invariants, module)
    print(json.dumps(r2, indent=2, ensure_ascii=False))

    assert r1["statut"] == "teste" and r1["score_formel"] == 1.0
    assert r2["statut"] == "teste" and r2["score_formel"] == 0.0
    assert r2["proprietes"][0]["contre_exemple"]
    print("\n✅ Invariants métier : preuve ET réfutation démontrées.")

    # ── Famille 2 : injection SQL (non-interférence) ──
    sql_sur = """
import sqlite3
def get_user(email):
    conn = sqlite3.connect("app.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    return cur.fetchone()
"""
    sql_vulnerable = """
import sqlite3
def get_user(email):
    conn = sqlite3.connect("app.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = '" + email + "'")
    return cur.fetchone()
"""
    inv_sql = [{"type": "requete_sql", "fonction": "getUser"}]
    mod_sql = {"nom_python": "get_user", "parametres": ["$email"]}

    print("\nCAS 3 — Requête paramétrée :")
    r3 = verifier_formellement(sql_sur, inv_sql, mod_sql)
    print(f"   {r3['proprietes'][0]['statut']}")
    print("CAS 4 — Requête concaténée :")
    r4 = verifier_formellement(sql_vulnerable, inv_sql, mod_sql)
    print(f"   {r4['proprietes'][0]['statut']} — contre-exemple "
          f"{r4['proprietes'][0]['contre_exemple']}")
    assert r3["proprietes"][0]["statut"] == "prouvee"
    assert r4["proprietes"][0]["statut"] == "refutee"

    # ── Famille 3 : contrôle d'accès ──
    acces_ok = """
from fastapi import HTTPException
def supprimer_article(article_id, role):
    if role != "admin":
        raise HTTPException(status_code=403, detail="Interdit")
    return True
"""
    acces_ko = """
def supprimer_article(article_id, role):
    return True
"""
    inv_acces = [{"type": "controle_acces", "fonction": "supprimerArticle",
                  "description": "verification du role admin",
                  "code": "if ($role != 'admin') { throw ... }"}]
    mod_acces = {"nom_python": "supprimer_article",
                 "parametres": ["$article_id"]}

    print("\nCAS 5 — Contrôle d'accès présent :")
    r5 = verifier_formellement(acces_ok, inv_acces, mod_acces)
    print(f"   {r5['proprietes'][0]['statut']}")
    print("CAS 6 — Contrôle d'accès oublié :")
    r6 = verifier_formellement(acces_ko, inv_acces, mod_acces)
    print(f"   {r6['proprietes'][0]['statut']} — contre-exemple "
          f"{r6['proprietes'][0]['contre_exemple']}")
    assert r5["proprietes"][0]["statut"] == "prouvee"
    assert r6["proprietes"][0]["statut"] == "refutee"

    print("\n✅ Trois familles de propriétés opérationnelles : "
          "invariants métier, injection SQL, contrôle d'accès.")