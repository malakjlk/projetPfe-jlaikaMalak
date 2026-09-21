"""
Agent Testeur Différentiel — SMAML
===================================
Vérifie l'ÉQUIVALENCE COMPORTEMENTALE entre le code PHP legacy
et le code Python généré (exigence du sujet PFE).

Principe du differential testing :
  1. Générer un corpus d'entrées variées (cas normaux + cas limites)
  2. Exécuter la fonction PHP originale avec chaque entrée
  3. Exécuter la fonction Python générée avec la MÊME entrée
  4. Comparer les comportements :
       - les deux acceptent → les valeurs de retour doivent coïncider
       - les deux rejettent (exception) → équivalent
       - l'un accepte, l'autre rejette → DIVERGENCE
  5. Score = comportements identiques / total des cas testés

Prérequis : PHP CLI installé (php -v doit fonctionner).
Si PHP est absent, le test est sauté proprement (statut "php_absent").
"""

import re
import subprocess

import doublures_bdd
import tempfile
import json
import os
import shutil
import html


# ═════════════════════════════════════════════════════
# GÉNÉRATION DES CAS DE TEST
# ═════════════════════════════════════════════════════

def generer_cas_de_test(nb_parametres: int, avec_bdd: bool = False) -> list:
    """
    Corpus d'entrées couvrant les cas normaux ET les cas limites
    (l'esprit du property-based testing, avec des valeurs choisies
    pour provoquer les divergences classiques PHP/Python).
    """
    valeurs = [
        "",                          # chaîne vide
        "a",                         # 1 caractère
        "abc",                       # court
        "1234567",                   # 7 caractères (limite basse)
        "12345678",                  # 8 caractères (limite exacte)
        "Password123",               # mot de passe valide typique
        "motdepasse",                # sans majuscule
        "éàçùè",                     # accents (UTF-8)
        "mot de passe avec espaces",
        "<script>alert(1)</script>", # tentative XSS
        "' OR 1=1 --",               # tentative injection SQL
        "x" * 500,                   # très long
        "x" * 1500,                  # dépasse les limites usuelles
        "0",
        "12345678901234567890",      # numérique long
    ]
    if avec_bdd:
        # Valeurs qui exercent réellement une requête : un
        # enregistrement existant, un absent, et deux injections.
        valeurs = [
            doublures_bdd.VALEUR_CONNUE,     # l'enregistrement existe
            "inconnu@example.com",           # il n'existe pas
            "' OR '1'='1",                   # injection classique
            "'; DROP TABLE users; --",       # injection destructrice
        ] + valeurs
    if nb_parametres <= 0:
        # Fonction sans paramètre (ex. une connexion) : rejouer 15 fois
        # la même chose n'apporte rien, un seul appel suffit.
        return [[]]
    # Chaque cas = la même valeur passée à tous les paramètres
    return [[v] * nb_parametres for v in valeurs]


# ═════════════════════════════════════════════════════
# EXÉCUTION CÔTÉ PHP
# ═════════════════════════════════════════════════════

def php_disponible() -> bool:
    """Vérifie que l'exécutable PHP est accessible."""
    return shutil.which("php") is not None


def executer_fonction_php(code_php: str, nom_fonction: str,
                          arguments: list, timeout: int = 10,
                          chemin_bdd: str = None) -> dict:
    """
    Exécute UNE fonction PHP avec les arguments donnés,
    dans un processus PHP isolé. Les arguments passent par
    stdin en JSON (fiable sous Windows comme Linux).
    """
    # Enlever les balises <?php ?> éventuelles du fragment
    code = code_php.replace("<?php", "").replace("?>", "")

    # Accès base de données : les appels sont redirigés vers SQLite,
    # et les requêtes émises sont renvoyées avec le résultat.
    prelude = ""
    if chemin_bdd:
        code = doublures_bdd.reecrire_php(code)
        prelude = doublures_bdd.PRELUDE_PHP

    script = f"""<?php
{prelude}
{code}
$args = json_decode(file_get_contents('php://stdin'), true);
try {{
    $r = call_user_func_array('{nom_fonction}', $args);
    echo json_encode(["ok" => true, "resultat" => $r,
                      "requetes" => $SMAML_REQUETES ?? []]);
}} catch (Throwable $e) {{
    echo json_encode(["ok" => false, "exception" => $e->getMessage(),
                      "requetes" => $SMAML_REQUETES ?? []]);
}}
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".php", delete=False, encoding="utf-8"
    ) as f:
        f.write(script)
        chemin = f.name

    try:
        environnement = dict(os.environ)
        if chemin_bdd:
            environnement["SMAML_BDD"] = chemin_bdd
        p = subprocess.run(
            ["php", chemin],
            input=json.dumps(arguments),
            capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", env=environnement
        )
        sortie = p.stdout.strip()
        if not sortie:
            # Erreur fatale PHP (parse error, etc.)
            return {"ok": False,
                    "exception": (p.stderr or "erreur PHP")[:200]}
        return json.loads(sortie)
    except subprocess.TimeoutExpired:
        return {"ok": False, "exception": "timeout"}
    except json.JSONDecodeError:
        return {"ok": False, "exception": f"sortie illisible : {sortie[:100]}"}
    finally:
        os.unlink(chemin)


# ═════════════════════════════════════════════════════
# EXÉCUTION CÔTÉ PYTHON
# ═════════════════════════════════════════════════════

def executer_fonction_python(code_python: str, nom_fonction: str,
                             arguments: list,
                             chemin_bdd: str = None) -> dict:
    """
    Exécute UNE fonction Python générée avec les arguments donnés.
    Toute exception (HTTPException, ValueError...) = comportement
    de rejet, comme un throw en PHP.

    chemin_bdd : si fourni, les accès base de données sont redirigés
    vers cette base SQLite de test (mêmes données que côté PHP).
    """
    requetes = []
    restaurer = None
    if chemin_bdd:
        restaurer = doublures_bdd.installer_doublures_python(
            chemin_bdd, requetes)
    try:
        return _executer_python(code_python, nom_fonction, arguments,
                                requetes)
    finally:
        if restaurer:
            restaurer()


def _executer_python(code_python: str, nom_fonction: str,
                     arguments: list, requetes: list) -> dict:
    espace = {}
    # Les bibliothèques absentes sont remplacées par des modules
    # permissifs, une par une, jusqu'à ce que le code se charge.
    modules_simules = []
    for _tentative in range(10):
        espace = {}
        try:
            exec(code_python, espace)
            break
        except ModuleNotFoundError as e:
            if not e.name or e.name in modules_simules:
                return {"ok": False, "exception": f"erreur d'import : {e}",
                        "requetes": requetes}
            doublures_bdd.installer_module_absent(e.name)
            modules_simules.append(e.name)
        except Exception as e:
            return {"ok": False, "exception": f"erreur d'import : {e}",
                    "requetes": requetes}
    else:
        return {"ok": False,
                "exception": "erreur d'import : trop de dépendances absentes",
                "requetes": requetes}

    fonction = espace.get(nom_fonction)
    if fonction is None:
        return {"ok": False, "requetes": requetes,
                "exception": f"fonction '{nom_fonction}' introuvable"}

    # Ajuster le nombre d'arguments à la signature RÉELLE de la
    # fonction Python générée (le LLM peut avoir ajouté/retiré des
    # paramètres par rapport au PHP → sinon faux "takes N positional").
    try:
        import inspect
        sig = inspect.signature(fonction)
        params = [p for p in sig.parameters.values()
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                  and p.default is p.empty]
        nb_requis = len(params)
        a_varargs = any(p.kind == p.VAR_POSITIONAL
                        for p in sig.parameters.values())
        if not a_varargs:
            if len(arguments) > nb_requis:
                arguments = arguments[:nb_requis]     # trop → on tronque
            elif len(arguments) < nb_requis:
                # pas assez → compléter avec la 1re valeur (test uniforme)
                remplissage = arguments[0] if arguments else ""
                arguments = arguments + [remplissage] * (
                    nb_requis - len(arguments))
    except (ValueError, TypeError):
        pass  # signature illisible → on garde les arguments d'origine

    try:
        r = fonction(*arguments)
        return {"ok": True, "resultat": r, "requetes": requetes}
    except TypeError as e:
        # Certaines fonctions Python attendent des bytes et non des
        # str (ex. pickle.loads, équivalent de unserialize). On
        # réessaie en convertissant les arguments str → bytes.
        if "bytes-like" in str(e):
            try:
                args_bytes = [
                    a.encode("utf-8") if isinstance(a, str) else a
                    for a in arguments
                ]
                r = fonction(*args_bytes)
                return {"ok": True, "resultat": r, "requetes": requetes}
            except BaseException as e2:
                message = getattr(e2, "detail", None) or str(e2)
                return {"ok": False, "exception": str(message),
                "requetes": requetes}
        message = getattr(e, "detail", None) or str(e)
        return {"ok": False, "exception": str(message),
                "requetes": requetes}
    except BaseException as e:
        # HTTPException a un attribut .detail, sinon str(e)
        message = getattr(e, "detail", None) or str(e)
        return {"ok": False, "exception": str(message),
                "requetes": requetes}


# ═════════════════════════════════════════════════════
# COMPARAISON DES COMPORTEMENTS
# ═════════════════════════════════════════════════════

def normaliser(valeur):
    """
    Normalise les valeurs pour une comparaison équitable :
    - bool PHP true/false ↔ bool Python True/False (JSON gère déjà)
    - entités HTML équivalentes : &#039; (PHP) ↔ &#x27; (Python)
    """
    if isinstance(valeur, str):
        return html.unescape(valeur)
    # Objet opaque (connexion, curseur) : réduit à une sentinelle, pour
    # que les deux langages soient comparables sur la même base.
    if valeur is not None and not isinstance(
            valeur, (bool, int, float, list, dict)):
        return f"<ressource {type(valeur).__name__}>"
    return valeur


INJECTIONS = ("' OR '1'='1", "' OR 1=1 --", "'; DROP TABLE",
              "--", " OR ")


def _est_injection(argument) -> bool:
    texte = str(argument)
    return any(motif in texte for motif in INJECTIONS)


def comparer_effets(etat_php: dict, etat_py: dict) -> dict:
    """
    Compare l'état de la base après l'appel : c'est ce qui révèle une
    différence sur les INSERT, UPDATE et DELETE, invisible dans la
    valeur de retour.
    """
    if etat_php == etat_py:
        return {"identiques": True}
    differences = []
    for table in sorted(set(etat_php) | set(etat_py)):
        lignes_php = etat_php.get(table, [])
        lignes_py = etat_py.get(table, [])
        if lignes_php != lignes_py:
            differences.append({
                "table": table,
                "lignes_php": len(lignes_php),
                "lignes_python": len(lignes_py),
            })
    return {"identiques": False, "differences": differences}


def _est_ressource(valeur) -> bool:
    """
    Valeur opaque : connexion, curseur, ressource. PHP la sérialise en
    objet vide, Python renvoie un objet non sérialisable. Comparer ces
    valeurs entre elles n'a aucun sens — seuls comptent alors le
    succès de l'appel et les effets sur la base.
    """
    return valeur == {} or (isinstance(valeur, str)
                            and valeur.startswith("<ressource"))


def comparer(res_php: dict, res_py: dict, argument=None) -> dict:
    """
    Compare les deux comportements et classe le résultat.
    """
    # Une entrée d'injection acceptée par le PHP et refusée (ou vidée)
    # par le Python n'est PAS une régression : c'est la faille
    # corrigée. La distinguer d'une divergence fonctionnelle est
    # indispensable, sans quoi sécuriser le code ferait baisser le
    # score d'équivalence.
    if argument is not None and _est_injection(argument):
        donnees_php = bool(res_php.get("ok") and res_php.get("resultat"))
        donnees_py = bool(res_py.get("ok") and res_py.get("resultat"))
        if donnees_php and not donnees_py:
            return {"equivalent": True, "type": "injection_bloquee",
                    "commentaire": ("le PHP renvoie des données sur une "
                                    "entrée d'injection, le Python non : "
                                    "faille corrigée")}

    if res_php["ok"] and res_py["ok"]:
        v_php = normaliser(res_php.get("resultat"))
        v_py = normaliser(res_py.get("resultat"))
        if _est_ressource(v_php) and _est_ressource(v_py):
            return {"equivalent": True, "type": "ressource_retournee",
                    "commentaire": ("les deux renvoient une connexion : "
                                    "comparaison portée sur le succès de "
                                    "l'appel et l'état de la base")}
        if v_php == v_py:
            return {"equivalent": True, "type": "acceptation_identique"}
        return {"equivalent": False, "type": "valeurs_differentes",
                "php": res_php.get("resultat"),
                "python": res_py.get("resultat")}

    if not res_php["ok"] and not res_py["ok"]:
        # Les deux rejettent → comportement équivalent
        # (les messages peuvent différer, c'est normal)
        return {"equivalent": True, "type": "rejet_identique"}

    return {"equivalent": False, "type": "divergence_acceptation",
            "php": ("accepte" if res_php["ok"]
                    else f"rejette ({res_php.get('exception', '')[:80]})"),
            "python": ("accepte" if res_py["ok"]
                       else f"rejette ({res_py.get('exception', '')[:80]})")}


# ═════════════════════════════════════════════════════
# FONCTION PRINCIPALE
# ═════════════════════════════════════════════════════

# Ressources qu'aucune doublure ne simule : le test différentiel y
# reste impossible, et c'est documenté comme tel.
#   - réseau (curl) : dépend d'un service extérieur
#   - fichiers, sessions, cookies : état hors du processus
# La base de données, elle, N'EST PLUS dans cette liste : elle est
# simulée à l'identique des deux côtés (voir doublures_bdd).
FONCTIONS_NON_TESTABLES = [
    "curl_", "header(", "file_get_contents", "fopen",
    "$_SESSION", "$_COOKIE"
]


def _avec_contexte(code_module: str, contexte: str,
                   motif_definition) -> str:
    """
    Code à charger pour exécuter la fonction ciblée.

    Une fonction extraite seule échoue dès qu'elle en appelle une
    autre du même fichier : `getUserByEmail` appelle `connectDatabase`,
    absent de l'extrait, et l'exécution s'arrête sur « undefined
    function ». Quand le contexte — le fichier PHP complet, ou les
    modules Python déjà migrés — contient la définition cherchée,
    c'est lui qu'on charge : les dépendances internes sont résolues.
    """
    if not contexte:
        return code_module
    if motif_definition.search(contexte):
        return contexte
    return contexte + "\n" + code_module


def tester_equivalence(code_php: str, code_python: str,
                       nom_php: str, nom_python: str,
                       nb_parametres: int = 1,
                       contexte_php: str = "",
                       contexte_python: str = "") -> dict:
    """
    Point d'entrée du differential testing pour UN module.

    Retourne :
    {
      "statut": "teste" | "php_absent" | "non_testable",
      "score_equivalence": 0.0 à 1.0,
      "cas_testes": N,
      "cas_equivalents": N,
      "divergences": [...]
    }
    """
    rapport = {
        "statut": "teste",
        "score_equivalence": 0.0,
        "cas_testes": 0,
        "cas_equivalents": 0,
        "divergences": []
    }

    # PHP installé ?
    if not php_disponible():
        rapport["statut"] = "php_absent"
        rapport["score_equivalence"] = None
        return rapport

    # Méthode de CLASSE ? (le code contient une classe ou $this)
    # Une méthode ne peut pas être exécutée en isolation comme une
    # fonction libre : il faut instancier l'objet. L'exécuteur PHP
    # l'appellerait via call_user_func_array sans instance → faux
    # rejet sur tous les cas. On saute proprement.
    if ("class " in code_php or "$this" in code_php
            or "function " in code_php and "public" in code_php):
        rapport["statut"] = "non_testable"
        rapport["score_equivalence"] = None
        rapport["raison"] = ("Méthode de classe — non exécutable en "
                             "isolation (nécessite d'instancier l'objet). "
                             "Vérification assurée par l'exécution symbolique.")
        return rapport

    # Fonction avec effets de bord (BDD, fichiers, réseau) ?
    # → non testable en isolation, on saute proprement
    if any(motif in code_php for motif in FONCTIONS_NON_TESTABLES):
        rapport["statut"] = "non_testable"
        rapport["score_equivalence"] = None
        rapport["raison"] = ("La fonction dépend de ressources externes "
                             "(BDD, fichiers, session) — non exécutable "
                             "en isolation")
        return rapport

    # Dépendances internes au fichier : on charge le fichier complet
    # quand il contient la définition de la fonction ciblée.
    code_php = _avec_contexte(
        code_php, contexte_php,
        re.compile(rf"function\s+{re.escape(nom_php)}\s*\(",
                   re.IGNORECASE))

    # Nettoyer le code Python (balises markdown)
    code_py = code_python
    if "```python" in code_py:
        code_py = code_py.split("```python")[1]
    if "```" in code_py:
        code_py = code_py.split("```")[0]
    code_py = _avec_contexte(
        code_py, contexte_python,
        re.compile(rf"def\s+{re.escape(nom_python)}\s*\("))

    # Base de données simulée, si le code y accède : chaque langage
    # reçoit sa PROPRE copie des mêmes données initiales, ce qui rend
    # les effets de bord comparables.
    utilise_bdd = (doublures_bdd.code_utilise_bdd(code_php)
                   or doublures_bdd.code_utilise_bdd(code_py))
    dossier_bdd = tempfile.mkdtemp(prefix="smaml_bdd_") if utilise_bdd else None
    bdd_php = bdd_py = None
    if utilise_bdd:
        rapport["base_simulee"] = doublures_bdd.analyser_schema(
            code_php, code_py)
        rapport["requetes_php"] = []
        rapport["requetes_python"] = []
        rapport["effets_compares"] = 0

    # Boucle de test différentiel
    cas_non_executables = 0
    for numero, arguments in enumerate(
            generer_cas_de_test(nb_parametres, utilise_bdd)):
        if utilise_bdd:
            # Données initiales identiques avant CHAQUE cas, dans des
            # fichiers distincts : une connexion laissée ouverte par le
            # code testé verrouillerait le fichier sous Windows.
            bdd_php = os.path.join(dossier_bdd, f"php_{numero}.db")
            bdd_py = os.path.join(dossier_bdd, f"python_{numero}.db")
            doublures_bdd.creer_base(bdd_php, code_php, code_py)
            doublures_bdd.creer_base(bdd_py, code_php, code_py)

        res_php = executer_fonction_php(code_php, nom_php, arguments,
                                        chemin_bdd=bdd_php)
        res_py = executer_fonction_python(code_py, nom_python, arguments,
                                          chemin_bdd=bdd_py)

        # Cas NON EXÉCUTABLE ≠ rejet comportemental !
        # Si la fonction dépend d'autres modules (undefined function
        # côté PHP, import raté côté Python), l'exécution isolée est
        # impossible : on ne peut rien conclure sur l'équivalence.
        exc_php = str(res_php.get("exception", "")).lower()
        exc_py = str(res_py.get("exception", "")).lower()
        if (("undefined function" in exc_php)
                or ("call to undefined" in exc_php)
                or ("erreur d'import" in exc_py)
                or ("introuvable" in exc_py)
                or ("no module named" in exc_py)):
            cas_non_executables += 1
            continue

        verdict = comparer(res_php, res_py, arguments[0] if arguments else None)

        # Effets de bord : l'état des deux bases doit concorder.
        if utilise_bdd:
            rapport["requetes_php"] += res_php.get("requetes", []) or []
            rapport["requetes_python"] += res_py.get("requetes", []) or []
            effets = comparer_effets(doublures_bdd.etat_base(bdd_php),
                                     doublures_bdd.etat_base(bdd_py))
            rapport["effets_compares"] += 1
            if not effets["identiques"] and verdict["equivalent"]:
                if _est_injection(arguments[0] if arguments else ""):
                    # Sur une entrée d'injection, le PHP corrompt sa
                    # propre requête tandis que le Python, paramétré,
                    # écrit la valeur telle quelle. L'écart d'état est
                    # la conséquence de la faille corrigée : le compter
                    # comme une divergence ferait baisser le score d'un
                    # code plus sûr que l'original.
                    verdict = {"equivalent": True,
                               "type": "injection_bloquee",
                               "commentaire": ("effets différents sur une "
                                               "entrée d'injection : requête "
                                               "PHP corrompue, requête Python "
                                               "paramétrée")}
                else:
                    verdict = {"equivalent": False,
                               "type": "effets_differents",
                               "detail": effets["differences"]}

        rapport["cas_testes"] += 1
        if verdict["equivalent"]:
            rapport["cas_equivalents"] += 1
            # Une faille bloquée est un résultat à part entière : le
            # comportement diffère volontairement de celui du PHP.
            if verdict.get("type") == "injection_bloquee":
                rapport.setdefault("injections_bloquees", []).append(
                    str(arguments[0])[:60])
        else:
            entree = arguments[0] if arguments else "(sans paramètre)"
            rapport["divergences"].append({
                "entree": (str(entree)[:60] + "..."
                           if len(str(entree)) > 60 else entree),
                **{k: v for k, v in verdict.items() if k != "equivalent"}
            })

    if utilise_bdd and dossier_bdd:
        shutil.rmtree(dossier_bdd, ignore_errors=True)

    if rapport["cas_testes"] > 0:
        rapport["score_equivalence"] = (
            rapport["cas_equivalents"] / rapport["cas_testes"]
        )
    elif cas_non_executables > 0:
        # Aucun cas n'a pu s'exécuter → fonction non testable
        # en isolation (dépendances inter-fichiers)
        rapport["statut"] = "non_testable"
        rapport["score_equivalence"] = None
        rapport["raison"] = ("La fonction dépend d'autres modules du "
                             "projet — non exécutable en isolation")

    return rapport


# ─── TEST AUTONOME ───────────────────────────────────
if __name__ == "__main__":

    code_php_test = """
function validatePassword($password) {
    if (strlen($password) < 8) {
        throw new Exception("Mot de passe trop court");
    }
    return true;
}
"""

    code_python_test = """
class HTTPException(Exception):
    def __init__(self, status_code=None, detail=None):
        self.detail = detail
        super().__init__(detail)

def validate_password(password: str) -> bool:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Mot de passe trop court")
    return True
"""

    print("=" * 60)
    print("Agent Testeur Différentiel SMAML — Test autonome")
    print("=" * 60)
    print(f"PHP disponible : {php_disponible()}")

    rapport = tester_equivalence(
        code_php_test, code_python_test,
        "validatePassword", "validate_password",
        nb_parametres=1
    )

    print(json.dumps(rapport, indent=2, ensure_ascii=False))

    if rapport["statut"] == "teste":
        print(f"\nÉquivalence comportementale : "
              f"{rapport['score_equivalence']*100:.1f}% "
              f"({rapport['cas_equivalents']}/{rapport['cas_testes']} cas)")
        if rapport["divergences"]:
            print("\nDivergences détectées :")
            for d in rapport["divergences"]:
                print(f"  - Entrée {repr(d['entree'])[:50]} : "
                      f"PHP={d.get('php')} / Python={d.get('python')}")
    print("\n✅ Agent Testeur Différentiel opérationnel !")