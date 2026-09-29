import subprocess
import sys
import json
import re
import ast
from hypothesis import given, strategies as st, settings


def detecter_noms_non_resolus(code_python: str) -> list:
    """
    Détecte les noms UTILISÉS mais jamais définis ni importés
    (ex: HTTPException employé sans `from fastapi import HTTPException`).

    Pourquoi : compile() ne valide que la GRAMMAIRE. Un nom manquant
    ne se manifeste qu'à l'exécution — le module était donc déclaré
    "syntaxe valide" alors qu'il plantait sur toutes les entrées
    (cas generer_rapport du benchmark : NameError sur 15/15 cas).

    Analyse volontairement CONSERVATRICE : on collecte tous les noms
    liés n'importe où dans le module (imports, def/class, paramètres,
    affectations, boucles, with, except, compréhensions, global) sans
    tenir compte des portées. On préfère rater un vrai défaut que
    produire un faux positif.
    """
    import builtins as _builtins

    try:
        arbre = ast.parse(code_python)
    except SyntaxError:
        return []   # erreur de syntaxe : déjà signalée ailleurs

    lies = set()
    etoile = False   # `from x import *` : impossible de conclure

    def lier_cible(noeud):
        """Enregistre les noms liés par une affectation/boucle/with."""
        if isinstance(noeud, ast.Name):
            lies.add(noeud.id)
        elif isinstance(noeud, (ast.Tuple, ast.List)):
            for e in noeud.elts:
                lier_cible(e)
        elif isinstance(noeud, ast.Starred):
            lier_cible(noeud.value)

    def lier_arguments(args):
        for a in (list(getattr(args, "posonlyargs", []))
                  + list(args.args) + list(args.kwonlyargs)):
            lies.add(a.arg)
        if args.vararg:
            lies.add(args.vararg.arg)
        if args.kwarg:
            lies.add(args.kwarg.arg)

    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                lies.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(noeud, ast.ImportFrom):
            for alias in noeud.names:
                if alias.name == "*":
                    etoile = True
                lies.add(alias.asname or alias.name)
        elif isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lies.add(noeud.name)
            lier_arguments(noeud.args)
        elif isinstance(noeud, ast.Lambda):
            lier_arguments(noeud.args)
        elif isinstance(noeud, ast.ClassDef):
            lies.add(noeud.name)
        elif isinstance(noeud, ast.Assign):
            for c in noeud.targets:
                lier_cible(c)
        elif isinstance(noeud, (ast.AnnAssign, ast.AugAssign)):
            lier_cible(noeud.target)
        elif isinstance(noeud, ast.NamedExpr):
            lier_cible(noeud.target)
        elif isinstance(noeud, (ast.For, ast.AsyncFor)):
            lier_cible(noeud.target)
        elif isinstance(noeud, ast.comprehension):
            lier_cible(noeud.target)
        elif isinstance(noeud, ast.withitem):
            if noeud.optional_vars is not None:
                lier_cible(noeud.optional_vars)
        elif isinstance(noeud, ast.ExceptHandler):
            if noeud.name:
                lies.add(noeud.name)
        elif isinstance(noeud, (ast.Global, ast.Nonlocal)):
            lies.update(noeud.names)

    if etoile:
        return []

    connus = (lies | set(dir(_builtins))
              | {"self", "cls", "__name__", "__file__", "__doc__",
                 "__package__", "__spec__", "__builtins__"})

    manquants = []
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Name)
                and isinstance(noeud.ctx, ast.Load)
                and noeud.id not in connus
                and noeud.id not in manquants):
            manquants.append(noeud.id)
    return manquants


def verifier_syntaxe_python(code_python: str,
                            noms_externes: set = None) -> dict:
    """
    Vérifie que le code Python généré est STATIQUEMENT valide :
    grammaire correcte ET aucun nom utilisé sans être défini/importé.

    noms_externes : noms déjà définis AILLEURS dans le fichier final
    (modules du même fichier générés précédemment). Sans eux, un
    `class Admin(User)` serait signalé à tort alors que User est
    défini quelques lignes plus haut dans le fichier assemblé.
    """
    resultat = {
        "syntaxe_valide": False,
        "erreur": None,
        "noms_non_resolus": []
    }

    # Nettoyer le code (enlever les balises markdown si présentes)
    code_nettoye = code_python
    if "```python" in code_nettoye:
        code_nettoye = code_nettoye.split("```python")[1]
    if "```" in code_nettoye:
        code_nettoye = code_nettoye.split("```")[0]

    try:
        compile(code_nettoye, "<string>", "exec")
        resultat["syntaxe_valide"] = True
    except SyntaxError as e:
        resultat["erreur"] = str(e)
        return resultat

    # Grammaire correcte : on vérifie maintenant la résolution des noms
    manquants = detecter_noms_non_resolus(code_nettoye)
    if noms_externes:
        manquants = [n for n in manquants if n not in noms_externes]
    if manquants:
        resultat["noms_non_resolus"] = manquants
        resultat["syntaxe_valide"] = False
        resultat["erreur"] = (
            "Nom(s) utilisé(s) sans être défini(s) ni importé(s) : "
            + ", ".join(manquants[:5])
            + ". Ajoute les imports manquants (ex: "
            + f"from fastapi import {manquants[0]}) ou définis-les."
        )

    return resultat


# ─── INVARIANTS : TEST DYNAMIQUE PUIS STRUCTUREL ─────
# Chercher « len( » dans le texte ne prouve rien : le mot peut venir
# d'un commentaire ou d'un calcul sans rapport. On exécute donc
# réellement la fonction générée sur des entrées produites par
# Hypothesis, et on cherche un CONTRE-EXEMPLE : une entrée invalide
# que la fonction accepte quand même.
#
# Complémentarité avec le Vérificateur de propriétés : Z3 explore les
# chemins symboliquement, Hypothesis tire des entrées concrètes. L'un
# raisonne, l'autre essaie ; les deux exhibent des contre-exemples.

def _charger_module(code_python: str):
    """
    Exécute le code généré dans un espace isolé. Les bibliothèques
    absentes sont remplacées par des doublures permissives : leur
    absence ne doit pas empêcher de tester la logique métier.
    """
    code = code_python
    if "```python" in code:
        code = code.split("```python")[1]
    if "```" in code:
        code = code.split("```")[0]

    espace = {}
    for _ in range(10):
        try:
            exec(code, espace)
            return espace, None
        except ModuleNotFoundError as e:
            try:
                import doublures_bdd
                doublures_bdd.installer_module_absent(e.name)
            except Exception:
                return None, f"dépendance absente : {e.name}"
        except Exception as e:
            return None, f"{type(e).__name__} : {e}"
    return None, "trop de dépendances absentes"


def _fonction_cible(espace: dict, module_info: dict):
    """Fonction à tester, d'après le plan de migration."""
    nom = module_info.get("nom_python", "")
    cible = espace.get(nom)
    if callable(cible):
        return cible, 1
    # Classe : on teste la première méthode publique
    if isinstance(cible, type):
        for nom_methode in module_info.get("methodes_python", []) or []:
            methode = getattr(cible, nom_methode, None)
            if callable(methode):
                try:
                    return getattr(cible(), nom_methode), 1
                except Exception:
                    return methode, 2
    for valeur in espace.values():
        if callable(valeur) and getattr(valeur, "__module__", "") == "builtins":
            continue
    return None, 0


def _proprietes_testables(invariants: list) -> list:
    """
    Traduit chaque invariant en propriété vérifiable :
    « si la fonction ACCEPTE l'entrée, alors la règle est respectée ».
    """
    import re as _re
    proprietes = []
    for inv in invariants:
        type_inv = (inv.get("type") or "").lower()
        texte = f"{inv.get('code', '')} {inv.get('description', '')}"
        nombres = _re.findall(r"\d+", texte)
        seuil = int(nombres[0]) if nombres else 8

        if type_inv == "validation_longueur":
            proprietes.append({
                "invariant": inv, "libelle": f"longueur ≥ {seuil}",
                "strategie": "texte",
                "regle": lambda v, s=seuil: isinstance(v, str) and len(v) >= s})
        elif type_inv == "validation_format":
            description = (inv.get("description", "") + inv.get("code", "")).lower()
            if "majuscule" in description or "a-z" in description:
                proprietes.append({
                    "invariant": inv, "libelle": "au moins une majuscule",
                    "strategie": "texte",
                    "regle": lambda v: isinstance(v, str)
                                       and any(c.isupper() for c in v)})
        elif type_inv == "validation_existence":
            proprietes.append({
                "invariant": inv, "libelle": "argument non vide",
                "strategie": "texte_ou_none",
                "regle": lambda v: v is not None and v != ""})
        elif type_inv == "validation_type":
            def numerique(v):
                try:
                    float(v)
                    return True
                except (TypeError, ValueError):
                    return False
            proprietes.append({
                "invariant": inv, "libelle": "valeur numérique",
                "strategie": "texte",
                "regle": numerique})
        elif type_inv == "validation_intervalle":
            borne = _re.search(r"([<>]=?)\s*(-?\d+(?:\.\d+)?)", texte)
            if borne:
                operateur, valeur = borne.group(1), float(borne.group(2))

                def dans_intervalle(v, operateur=operateur, valeur=valeur):
                    try:
                        nombre = float(v)
                    except (TypeError, ValueError):
                        return True        # entrée non numérique : hors sujet
                    # Le PHP rejette quand la condition est vraie :
                    # « if ($x < 0) throw » garantit donc x >= 0.
                    if operateur.startswith("<"):
                        return nombre >= valeur
                    return nombre <= valeur
                proprietes.append({
                    "invariant": inv,
                    "libelle": f"valeur bornée ({operateur} {valeur:g} rejeté)",
                    # Une borne porte sur des NOMBRES : envoyer du texte
                    # ferait rejeter toutes les entrées, et le test ne
                    # prouverait rien.
                    "strategie": "nombre", "regle": dans_intervalle})
        elif type_inv == "assainissement_sortie":
            # Propriété sur la SORTIE : si l'entrée contient du HTML,
            # la sortie ne doit plus contenir de balise brute.
            def sortie_echappee(entree, sortie):
                if not isinstance(entree, str) or not isinstance(sortie, str):
                    return True
                if not any(c in entree for c in "<>"):
                    return True
                return "<" not in sortie and ">" not in sortie
            proprietes.append({
                "invariant": inv, "libelle": "sortie échappée",
                "strategie": "html", "regle_sortie": sortie_echappee})
    return proprietes


def tester_property_based(code_python: str, module_info: dict,
                          invariants: list, max_exemples: int = 60) -> dict:
    """
    Exécute la fonction générée sur des entrées produites par Hypothesis
    et cherche une entrée invalide qu'elle accepterait.
    """
    resultat = {"tests_executes": 0, "tests_reussis": 0,
                "details": [], "verdicts": {}, "raison": None}

    proprietes = _proprietes_testables(invariants)
    if not proprietes:
        resultat["raison"] = "aucun invariant traduisible en propriété"
        return resultat

    espace, erreur = _charger_module(code_python)
    if espace is None:
        resultat["raison"] = f"code non exécutable ({erreur})"
        return resultat

    fonction, nb_args = _fonction_cible(espace, module_info)
    if fonction is None:
        resultat["raison"] = "fonction cible introuvable dans le code généré"
        return resultat

    # Fonction asynchrone : l'appeler sans l'attendre renverrait une
    # coroutine sans jamais lever d'exception — toute entrée paraîtrait
    # acceptée, ce qui produirait de faux contre-exemples.
    import asyncio
    import inspect
    if inspect.iscoroutinefunction(fonction):
        fonction_brute = fonction

        def appeler(*arguments):
            return asyncio.run(fonction_brute(*arguments))
    else:
        appeler = fonction

    for propriete in proprietes:
        contre_exemple = []
        acceptations = []

        if propriete["strategie"] == "texte_ou_none":
            strategie = st.one_of(st.none(), st.text(max_size=25))
        elif propriete["strategie"] == "nombre":
            strategie = st.one_of(
                st.integers(min_value=-10000, max_value=10000),
                st.floats(allow_nan=False, allow_infinity=False,
                          min_value=-10000, max_value=10000))
        elif propriete["strategie"] == "html":
            # Du texte au hasard ne contient presque jamais de balise :
            # on injecte des charges utiles réalistes.
            strategie = st.one_of(
                st.sampled_from(["<script>alert(1)</script>", "<b>gras</b>",
                                 "a & b", "<img src=x onerror=1>", "'\""]),
                st.text(max_size=25))
        else:
            strategie = st.text(max_size=25)

        def construire(regle=propriete.get("regle"),
                       regle_sortie=propriete.get("regle_sortie"),
                       trace=contre_exemple, acceptees=acceptations):
            # Hypothesis refuse une fonction de test ayant des valeurs
            # par défaut : la fermeture les porte à sa place.
            @settings(max_examples=max_exemples, deadline=None)
            @given(strategie)
            def verifier(valeur):
                try:
                    resultat_appel = appeler(valeur, *([1] * (nb_args - 1)))
                except Exception:
                    return      # entrée rejetée : comportement attendu
                # La fonction a ACCEPTÉ l'entrée : la règle doit tenir.
                acceptees.append(valeur)
                if regle_sortie is not None:
                    if not regle_sortie(valeur, resultat_appel):
                        trace.append((valeur, resultat_appel))
                        raise AssertionError(
                            f"sortie non conforme pour {valeur!r}")
                elif not regle(valeur):
                    trace.append(valeur)
                    raise AssertionError(f"entrée acceptée : {valeur!r}")
            return verifier

        resultat["tests_executes"] += 1
        try:
            construire()()
            resultat["tests_reussis"] += 1
            if acceptations:
                verdict = "respecte"
                detail = (f"aucun contre-exemple sur {max_exemples} entrées "
                          f"(la fonction en a accepté certaines)")
            else:
                # La fonction a rejeté TOUTES les entrées : souvent un
                # code qui plante. On ne peut rien conclure.
                verdict = "non_teste"
                detail = "la fonction rejette toutes les entrées testées"
        except AssertionError:
            verdict = "refute"
            detail = f"entrée acceptée alors qu'elle viole la règle : {contre_exemple[-1]!r}" if contre_exemple else "contre-exemple trouvé"
        except Exception as e:
            verdict, detail = "non_teste", f"{type(e).__name__} : {e}"

        resultat["verdicts"][propriete["libelle"]] = verdict
        resultat["details"].append({
            "propriete": propriete["libelle"], "verdict": verdict,
            "detail": detail,
            "invariant": propriete["invariant"].get("description", "")})
    return resultat


def verifier_invariants_presents(code_python: str, invariants: list,
                                 tests_dynamiques: dict = None) -> dict:
    """
    Un invariant est considéré préservé si la fonction générée REFUSE
    les entrées qui le violent.

    Deux niveaux de preuve :
      1. test dynamique (Hypothesis) : un contre-exemple prouve
         que l'invariant n'est pas appliqué ;
      2. à défaut (code non exécutable), analyse structurelle : existe-
         t-il une garde qui lève une exception ?
    """
    resultat = {"invariants_verifies": [], "invariants_manquants": [],
                "invariants_douteux": [], "preuves": [], "score": 0.0}

    # Verdicts dynamiques, indexés par description d'invariant
    dynamiques = {}
    for detail in (tests_dynamiques or {}).get("details", []):
        dynamiques[detail.get("invariant", "")] = detail

    from agent_auditeur import (_extraire_gardes, _garde_correspondante,
                                _seuil_invariant, _appel_correspondant)
    gardes = _extraire_gardes(code_python)

    for inv in invariants:
        description = inv.get("description", "")
        detail = dynamiques.get(description)

        if detail and detail["verdict"] == "respecte":
            resultat["invariants_verifies"].append(inv)
            resultat["preuves"].append({
                "invariant": description, "verdict": "vérifié",
                "source": f"test dynamique : {detail['detail']}"})
            continue
        if detail and detail["verdict"] == "refute":
            # La fonction testée accepte une entrée invalide. Mais la
            # règle peut être appliquée AILLEURS dans le module (modèle
            # Pydantic, validation en amont) : le verdict est alors
            # douteux plutôt que négatif.
            garde, _ = _garde_correspondante(inv, gardes,
                                             _seuil_invariant(inv))
            if garde:
                resultat["invariants_douteux"].append(inv)
                resultat["preuves"].append({
                    "invariant": description, "verdict": "douteux",
                    "source": (f"contre-exemple sur la fonction migrée, mais "
                               f"une garde existe ligne {garde['ligne']} : "
                               f"{garde['texte'][:45]}")})
            else:
                resultat["invariants_manquants"].append(inv)
                resultat["preuves"].append({
                    "invariant": description, "verdict": "manquant",
                    "source": f"contre-exemple : {detail['detail']}"})
            continue

        # Certains invariants sont des APPELS (échappement, hachage,
        # comparaison de secret), pas des gardes : les chercher parmi
        # les conditions reviendrait à les déclarer tous manquants.
        appel = _appel_correspondant(inv, code_python)
        if appel:
            resultat["invariants_verifies"].append(inv)
            resultat["preuves"].append({
                "invariant": description, "verdict": "vérifié",
                "source": f"appel attendu présent : {appel}"})
            continue

        garde, reserve = _garde_correspondante(inv, gardes,
                                               _seuil_invariant(inv))
        if garde and not reserve:
            resultat["invariants_verifies"].append(inv)
            resultat["preuves"].append({
                "invariant": description, "verdict": "vérifié",
                "source": f"garde ligne {garde['ligne']} : {garde['texte'][:60]}"})
        else:
            resultat["invariants_manquants"].append(inv)
            resultat["preuves"].append({
                "invariant": description, "verdict": "manquant",
                "source": reserve or "aucune garde ne rejette l'entrée invalide"})

    total = len(invariants)
    # un invariant douteux compte pour la moitié
    valeur = (len(resultat["invariants_verifies"])
              + 0.5 * len(resultat["invariants_douteux"]))
    resultat["score"] = (valeur / total) if total > 0 else 1.0
    return resultat


def verifier_failles_corrigees(
    code_python: str,
    failles: list
) -> dict:
    """
    Vérifie par analyse textuelle si les failles détectées
    par l'Analyste ont été corrigées dans le code Python.
    """
    resultat = {
        "failles_corrigees": [],
        "failles_persistantes": [],
        "score": 0.0
    }

    code_lower = code_python.lower()

    # Patterns qui indiquent qu'une faille a été corrigée
    indicateurs_correction = {
        "sql_injection": ["sqlalchemy", ".query(", "orm", ".filter(",
                          "text(", "bindparam", "session.execute"],
        "command_injection": ["subprocess.run", "shlex", "shell=false",
                              "subprocess.check_output", "shell = false"],
        "file_inclusion": ["whitelist", "allowed_pages", "in allowed",
                           "pathlib", "os.path.basename", "allowlist"],
        "insecure_deserialization": ["json.loads", "pydantic", "basemodel",
                                     "json.load", ".model_validate"]
    }

    # Patterns qui indiquent que la faille est toujours présente
    indicateurs_faille_presente = {
        "sql_injection": ["mysql_query", "execute(f\"", "execute(f'",
                         "+ id", ". $id", "% (id", "format(sql"],
        "command_injection": ["shell_exec", "os.system(", "os.popen(",
                             "shell=true", "shell = true", "eval("],
        "file_inclusion": ["include($", "require($"],
        "insecure_deserialization": ["pickle.loads", "pickle.load",
                                     "unserialize", "yaml.load("]
    }

    for faille in failles:
        type_faille = faille.get("faille") or faille.get("type", "")

        a_corrige = any(
            p in code_lower
            for p in indicateurs_correction.get(type_faille, [])
        )
        a_faille_residuelle = any(
            p in code_lower
            for p in indicateurs_faille_presente.get(type_faille, [])
        )

        if a_corrige and not a_faille_residuelle:
            resultat["failles_corrigees"].append(faille)
        else:
            resultat["failles_persistantes"].append(faille)

    total = len(failles)
    corrigees = len(resultat["failles_corrigees"])
    resultat["score"] = (corrigees / total) if total > 0 else 1.0

    return resultat


def agent_testeur(
    code_python: str,
    module_info: dict,
    invariants: list,
    failles: list,
    noms_externes: set = None
) -> dict:
    """
    Agent Testeur principal — SMAML
    Vérifie l'équivalence fonctionnelle et la qualité
    du code Python généré.
    """

    print(f"\nVérification du module : "
          f"{module_info.get('nom_python', '')}")

    rapport = {
        "module": module_info.get("nom_python", ""),
        "syntaxe": None,
        "invariants": None,
        "failles": None,
        "tests_property_based": None,
        "score_fonctionnel": 0.0
    }

    # Étape 1 — Validité statique (grammaire + résolution des noms)
    print("  1. Vérification syntaxique et résolution des noms...")
    rapport["syntaxe"] = verifier_syntaxe_python(code_python, noms_externes)
    statut_syntaxe = "✅" if rapport["syntaxe"]["syntaxe_valide"] else "❌"
    print(f"     {statut_syntaxe} Code statiquement valide : "
          f"{rapport['syntaxe']['syntaxe_valide']}")
    if rapport["syntaxe"].get("noms_non_resolus"):
        print(f"     ⚠️  Nom(s) non défini(s) ni importé(s) : "
              f"{', '.join(rapport['syntaxe']['noms_non_resolus'][:5])}")

    # Étape 2 — Tests dynamiques : on EXÉCUTE la fonction générée sur
    # des entrées produites par Hypothesis, et on cherche une entrée
    # invalide qu'elle accepterait.
    print("  2. Tests property-based (Hypothesis)...")
    rapport["tests_property_based"] = tester_property_based(
        code_python, module_info, invariants
    )
    tests = rapport["tests_property_based"]
    if tests["tests_executes"]:
        print(f"     {tests['tests_reussis']}/{tests['tests_executes']} "
              f"propriété(s) sans contre-exemple")
        for detail in tests["details"]:
            if detail["verdict"] != "respecte":
                print(f"     ⚠️  {detail['propriete']} : {detail['detail'][:70]}")
    else:
        print(f"     non applicable ({tests['raison']})")

    # Étape 3 — Invariants : verdict dynamique, sinon analyse structurelle
    print("  3. Vérification des invariants de sécurité...")
    rapport["invariants"] = verifier_invariants_presents(
        code_python, invariants, rapport["tests_property_based"]
    )
    for preuve in rapport["invariants"]["preuves"]:
        print(f"       {preuve['verdict']:<9} {preuve['invariant'][:36]:<38}"
              f" {preuve['source'][:58]}")
    print(f"     Score invariants : "
          f"{rapport['invariants']['score']*100:.0f}% "
          f"({len(rapport['invariants']['invariants_verifies'])}"
          f"/{len(invariants)})")

    # Étape 4 — Vérification des failles corrigées
    print("  4. Vérification de la correction des failles...")
    rapport["failles"] = verifier_failles_corrigees(
        code_python, failles
    )
    print(f"     Score failles corrigées : "
          f"{rapport['failles']['score']*100:.0f}% "
          f"({len(rapport['failles']['failles_corrigees'])}"
          f"/{len(failles)})")

    # Score fonctionnel composé
    score_syntaxe = 1.0 if rapport["syntaxe"]["syntaxe_valide"] else 0.0
    score_invariants = rapport["invariants"]["score"]
    score_failles = rapport["failles"]["score"]

    rapport["score_fonctionnel"] = (
        score_syntaxe * 0.3 +
        score_invariants * 0.4 +
        score_failles * 0.3
    )

    print(f"\n  📊 Score fonctionnel global : "
          f"{rapport['score_fonctionnel']*100:.1f}%")

    return rapport


# ─── TEST ────────────────────────────────────────────
if __name__ == "__main__":

    # Code Python simulé (résultat de l'Agent Développeur)
    code_python_test = """
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, validator
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker

class UserRequest(BaseModel):
    id: int
    username: str
    password: str

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Le mot de passe doit avoir au moins 8 caracteres")
        if not any(char.isupper() for char in v):
            raise ValueError("Majuscule requise")
        return v

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur non trouve")
    return user.__dict__
"""

    invariants_test = [
        {"type": "validation_longueur",
         "description": "len >= 8"},
        {"type": "validation_format",
         "description": "majuscule requise"}
    ]

    failles_test = [
        {"faille": "sql_injection",
         "cwe": "CWE-89",
         "severity": "critical"}
    ]

    module_test = {
        "nom_python": "get_user",
        "nom_original": "getUser"
    }

    print("=" * 60)
    print("Agent Testeur SMAML — Vérification en cours...")
    print("=" * 60)

    rapport = agent_testeur(
        code_python_test,
        module_test,
        invariants_test,
        failles_test
    )

    print("\n" + "=" * 60)
    print("RAPPORT COMPLET (JSON) :")
    print("=" * 60)
    print(json.dumps(rapport, indent=2, ensure_ascii=False))

    print("\n✅ Agent Testeur opérationnel !")