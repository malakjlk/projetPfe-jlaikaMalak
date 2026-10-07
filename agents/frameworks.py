"""
Frameworks — SMAML
===================
Une application Laravel n'est pas une suite de fonctions isolées. Trois
couches doivent être migrées, puis vérifiées ensemble :

  1. les ROUTES, qui relient une URL et une méthode HTTP à un contrôleur
     → un routeur FastAPI, généré de façon déterministe : mêmes chemins,
       mêmes méthodes, mêmes paramètres ;
  2. les CONTRÔLEURS et les MODÈLES → traduits par le Développeur, guidé
     par la correspondance Laravel → FastAPI ;
  3. les VUES (Blade ou PHP mêlé de HTML) → des gabarits Jinja2, convertis
     de façon déterministe ; ce qui ne se convertit pas est signalé.

Vérification : le TEST DIFFÉRENTIEL HTTP. Les mêmes requêtes sont
envoyées à l'application d'origine et à l'application produite, et les
réponses comparées : code de statut et contenu.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request


# ═══ DÉTECTION ═════════════════════════════════════════

# Indices de chaque framework : paquet composer, puis fichiers ou dossiers
# caractéristiques. Il faut au moins deux indices concordants.
INDICES = {
    "Laravel":     ("laravel/framework", ["artisan", "routes/web.php", "app/Http/Controllers"]),
    "Symfony":     ("symfony/framework-bundle", ["bin/console", "symfony.lock",
                                                 "config/routes.yaml", "config/bundles.php"]),
    "CodeIgniter": ("codeigniter4/framework", ["spark", "system/core/CodeIgniter.php",
                                               "application/controllers", "app/Config/App.php"]),
    "CakePHP":     ("cakephp/cakephp", ["bin/cake", "config/app.php", "src/Application.php"]),
    "Yii":         ("yiisoft/yii2", ["yii", "config/web.php", "controllers"]),
    "Laminas":     ("laminas/laminas-mvc", ["config/application.config.php", "module"]),
    "Slim":        ("slim/slim", ["public/index.php"]),
}


def detecter_framework(dossier: str):
    """
    Le framework de l'application, s'il y en a un. « pris_en_charge »
    indique s'il a un adaptateur complet ; sinon, il est reconnu et
    signalé, et l'application est migrée comme du PHP sans framework.
    """
    exigences = {}
    composer = os.path.join(dossier, "composer.json")
    if os.path.exists(composer):
        try:
            exigences = json.load(open(composer, encoding="utf-8")).get("require", {})
        except ValueError:
            exigences = {}
    meilleur, indices_meilleur = None, []
    for nom, (paquet, chemins) in INDICES.items():
        indices = [f"composer.json : {paquet}"] if any(e.startswith(paquet) for e in exigences) else []
        indices += [c for c in chemins if os.path.exists(os.path.join(dossier, c))]
        if len(indices) > len(indices_meilleur):
            meilleur, indices_meilleur = nom, indices
    if len(indices_meilleur) < 2:
        return None
    return {"nom": meilleur, "indices": indices_meilleur,
            "pris_en_charge": meilleur in ADAPTATEURS_FRAMEWORK}


# ═══ ROUTES LARAVEL → ROUTEUR FASTAPI ══════════════════

_ROUTE = re.compile(
    r"Route::(get|post|put|patch|delete|any)\s*\(\s*['\"]([^'\"]*)['\"]\s*,\s*"
    r"(?:\[\s*([\w\\]+)::class\s*,\s*['\"](\w+)['\"]\s*\]|['\"]([\w\\]+)@(\w+)['\"]|(function))",
    re.I)


def lire_routes_laravel(dossier: str) -> list:
    routes = []
    for fichier in ("routes/web.php", "routes/api.php"):
        chemin = os.path.join(dossier, fichier)
        if not os.path.exists(chemin):
            continue
        prefixe = "/api" if fichier.endswith("api.php") else ""
        for m in _ROUTE.finditer(open(chemin, encoding="utf-8", errors="ignore").read()):
            methode, uri = m.group(1).upper(), m.group(2)
            controleur = (m.group(3) or m.group(5) or "").split("\\")[-1]
            action = m.group(4) or m.group(6)
            chemin_api = prefixe + "/" + uri.strip("/")
            parametres = re.findall(r"\{(\w+)\??\}", chemin_api)
            routes.append({"methode": methode, "chemin": re.sub(r"\{(\w+)\?\}", r"{\1}", chemin_api),
                           "controleur": controleur, "action": action,
                           "parametres": parametres, "closure": bool(m.group(7)),
                           "source": fichier})
    return routes


CONSIGNE_LARAVEL = (
    "L'APPLICATION D'ORIGINE UTILISE LE FRAMEWORK LARAVEL. Correspondances à respecter :\n"
    "- Contrôleur Laravel → classe Python aux méthodes de même rôle ; les ROUTES sont "
    "générées à part (routes.py) : n'écris pas de décorateur @app.get dans le contrôleur.\n"
    "- Request $request et $request->validate([...]) → paramètres typés et modèle Pydantic "
    "(Field avec min_length, max_length, pattern…).\n"
    "- Modèle Eloquent → modèle SQLAlchemy ; User::find($id) → session.get(User, id) ; "
    "User::where('email', $e)->first() → session.scalars(select(User).where(User.email == e)).first().\n"
    "- return view('users.index', ['users' => $u]) → renvoie les données ; le gabarit "
    "users/index.html est traduit à part.\n"
    "- response()->json($d) → renvoie le dict ; abort(404) → HTTPException(status_code=404) "
    "(autorisé ici : c'est la couche des routes).\n"
    "- Middleware auth → dépendance FastAPI (Depends) ; config('x') et env('X') → réglages "
    "lus par os.getenv.")


def generer_routeur(routes: list, modules_par_classe: dict = None) -> str:
    """
    Routeur FastAPI : mêmes chemins, mêmes méthodes, mêmes paramètres.
    modules_par_classe : le plan de l'Architecte — un contrôleur traduit en
    FONCTIONS (sans état) s'importe fonction par fonction, pas comme classe.
    """
    from agent_architecte import convertir_nom
    modules_par_classe = modules_par_classe or {}
    lignes = ['"""Routes traduites depuis Laravel, sans LLM : mêmes chemins,',
              'mêmes méthodes HTTP, mêmes paramètres."""', "",
              "from fastapi import APIRouter, HTTPException", ""]
    controleurs = sorted({r["controleur"] for r in routes if r["controleur"]})
    en_fonctions = {c for c in controleurs
                    if (modules_par_classe.get(c) or {}).get("cible_migration") == "fonctions_module"}
    for c in controleurs:
        if c in en_fonctions:
            actions = sorted({convertir_nom(r["action"]) for r in routes if r["controleur"] == c})
            lignes.append(f"from {c} import {', '.join(actions)}")
        else:
            lignes.append(f"from {c} import {c}")
    lignes += ["", "router = APIRouter()", ""]
    vus = set()
    for r in routes:
        methodes = ["get", "post", "put", "patch", "delete"] if r["methode"] == "ANY" \
            else [r["methode"].lower()]
        base = (f"{convertir_nom(r['controleur'])}_{convertir_nom(r['action'])}"
                if r["controleur"] else "route_" + re.sub(r"\W", "_", r["chemin"]).strip("_"))
        nom, i = base or "accueil", 2
        while nom in vus:
            nom, i = f"{base}_{i}", i + 1
        vus.add(nom)
        signature = ", ".join(f"{p}: str" for p in r["parametres"])
        arguments = ", ".join(r["parametres"])
        for methode in methodes:
            lignes.append(f'@router.{methode}("{r["chemin"] or "/"}")')
        lignes.append(f"def {nom}({signature}):")
        lignes.append(f'    """{r["methode"]} {r["chemin"]} — {r["source"]}"""')
        if r["closure"] or not r["controleur"]:
            lignes.append('    raise HTTPException(status_code=501, detail="route définie par '
                          'une closure Laravel : à traduire à la main")')
        elif r["controleur"] in en_fonctions:
            lignes.append(f"    return {convertir_nom(r['action'])}({arguments})")
        else:
            lignes.append(f"    return {r['controleur']}().{convertir_nom(r['action'])}({arguments})")
        lignes.append("")
    return "\n".join(lignes)


def generer_application(avec_gabarits: bool, avec_statique: bool) -> str:
    lignes = ['"""Point d\'entrée FastAPI de l\'application migrée.', "",
              "    uvicorn main:app --reload", '"""', "",
              "from fastapi import FastAPI"]
    if avec_statique:
        lignes.append("from fastapi.staticfiles import StaticFiles")
    lignes += ["", "from routes import router", "", 'app = FastAPI(title="Application migrée par SMAML")',
               "app.include_router(router)"]
    if avec_statique:
        lignes.append('app.mount("/static", StaticFiles(directory="static"), name="static")')
    if avec_gabarits:
        lignes += ["", "# Gabarits Jinja2 traduits des vues Blade / PHP :",
                   "#   from fastapi.templating import Jinja2Templates",
                   '#   gabarits = Jinja2Templates(directory="templates")']
    return "\n".join(lignes) + "\n"


# ═══ VUES : BLADE / PHP → JINJA2 ═══════════════════════

def _expression(php: str) -> str:
    """Une expression PHP simple en expression Jinja2."""
    e = php.strip().rstrip(";")
    e = re.sub(r"\$(\w+)", r"\1", e)                    # $nom → nom
    e = re.sub(r"->(\w+)", r".\1", e)                   # $u->nom → u.nom
    e = re.sub(r"\s*&&\s*", " and ", e)
    e = re.sub(r"\s*\|\|\s*", " or ", e)
    e = re.sub(r"!\s*(?!=)", "not ", e)
    e = re.sub(r"\bcount\((\w[\w.]*)\)", r"\1|length", e)
    e = re.sub(r"\s*\.\s*'", " ~ '", e)                 # concaténation PHP « . »
    return e


def convertir_vue(source: str) -> tuple:
    """
    Vue Blade ou PHP → gabarit Jinja2. Retourne (gabarit, non_convertis) :
    tout ce qui ne se convertit pas est signalé dans le gabarit et listé.
    """
    t = source
    t = re.sub(r"\{\{--(.*?)--\}\}", r"{#\1#}", t, flags=re.S)
    t = re.sub(r"\{!!\s*(.+?)\s*!!\}", lambda m: "{{ " + _expression(m.group(1)) + " | safe }}", t)
    t = re.sub(r"\{\{\s*(.+?)\s*\}\}", lambda m: "{{ " + _expression(m.group(1)) + " }}", t)

    blade = [
        (r"@extends\(\s*['\"]([\w.\-/]+)['\"]\s*\)",
         lambda m: '{% extends "' + m.group(1).replace(".", "/") + '.html" %}'),
        (r"@section\(\s*['\"](\w+)['\"]\s*,\s*['\"]([^'\"]*)['\"]\s*\)",
         lambda m: "{% block " + m.group(1) + " %}" + m.group(2) + "{% endblock %}"),
        (r"@section\(\s*['\"](\w+)['\"]\s*\)", lambda m: "{% block " + m.group(1) + " %}"),
        (r"@(?:endsection|stop|show)\b", lambda m: "{% endblock %}"),
        (r"@yield\(\s*['\"](\w+)['\"]\s*\)", lambda m: "{% block " + m.group(1) + " %}{% endblock %}"),
        (r"@include\(\s*['\"]([\w.\-/]+)['\"]\s*\)",
         lambda m: '{% include "' + m.group(1).replace(".", "/") + '.html" %}'),
        (r"@foreach\s*\(\s*\$(\w+)\s+as\s+\$(\w+)\s*=>\s*\$(\w+)\s*\)",
         lambda m: "{% for " + m.group(2) + ", " + m.group(3) + " in " + m.group(1) + ".items() %}"),
        (r"@foreach\s*\(\s*(.+?)\s+as\s+\$(\w+)\s*\)",
         lambda m: "{% for " + m.group(2) + " in " + _expression(m.group(1)) + " %}"),
        (r"@endforeach\b", lambda m: "{% endfor %}"),
        (r"@if\s*\((.+?)\)\s*$", lambda m: "{% if " + _expression(m.group(1)) + " %}"),
        (r"@elseif\s*\((.+?)\)\s*$", lambda m: "{% elif " + _expression(m.group(1)) + " %}"),
        (r"@else\b", lambda m: "{% else %}"),
        (r"@endif\b", lambda m: "{% endif %}"),
        (r"@csrf\b", lambda m: "{# protection CSRF : à assurer côté FastAPI #}"),
    ]
    for motif, remplacement in blade:
        t = re.sub(motif, remplacement, t, flags=re.M)

    php = [
        (r"<\?(?:php\s+echo|=)\s*(.+?)\s*;?\s*\?>", lambda m: "{{ " + _expression(m.group(1)) + " }}"),
        (r"<\?php\s+if\s*\((.+?)\)\s*:\s*\?>", lambda m: "{% if " + _expression(m.group(1)) + " %}"),
        (r"<\?php\s+elseif\s*\((.+?)\)\s*:\s*\?>", lambda m: "{% elif " + _expression(m.group(1)) + " %}"),
        (r"<\?php\s+else\s*:\s*\?>", lambda m: "{% else %}"),
        (r"<\?php\s+endif\s*;?\s*\?>", lambda m: "{% endif %}"),
        (r"<\?php\s+foreach\s*\(\s*\$(\w+)\s+as\s+\$(\w+)\s*\)\s*:\s*\?>",
         lambda m: "{% for " + m.group(2) + " in " + m.group(1) + " %}"),
        (r"<\?php\s+endforeach\s*;?\s*\?>", lambda m: "{% endfor %}"),
    ]
    for motif, remplacement in php:
        t = re.sub(motif, remplacement, t, flags=re.S)

    non_convertis = re.findall(r"<\?(?:php)?.*?\?>|@\w+(?:\(.*?\))?", t, flags=re.S)
    non_convertis = [n for n in non_convertis if not n.startswith("@media")
                     and not re.match(r"@\w+\.\w+", n)]          # adresses e-mail, CSS
    for bloc in non_convertis:
        t = t.replace(bloc, "{# SMAML — non converti, à traduire à la main : "
                      + bloc.replace("#}", "# }")[:120] + " #}")
    return t, non_convertis


def nom_gabarit(chemin_vue: str) -> str:
    """resources/views/users/index.blade.php → users/index.html"""
    relatif = chemin_vue.replace("\\", "/")
    relatif = re.sub(r"^(?:.*?/)?resources/views/", "", relatif)
    return re.sub(r"(\.blade)?\.php$", ".html", relatif)


# ═══ TEST DIFFÉRENTIEL HTTP ════════════════════════════

def _envoyer(base: str, methode: str, chemin: str, delai_s: float = 10):
    requete = urllib.request.Request(base.rstrip("/") + chemin, method=methode,
                                     headers={"Accept": "application/json, text/html"})
    try:
        with urllib.request.urlopen(requete, timeout=delai_s) as reponse:
            return reponse.status, reponse.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b"").decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as e:
        return 0, f"injoignable : {e}"


def _normaliser(corps: str):
    """JSON comparé comme données ; HTML et texte sans écarts d'espacement."""
    try:
        return json.loads(corps)
    except (ValueError, TypeError):
        return re.sub(r"\s+", " ", re.sub(r">\s+<", "><", corps or "")).strip()


def comparer_http(base_origine: str, base_migree: str, requetes: list) -> dict:
    """
    Envoie les mêmes requêtes aux deux applications et compare les
    réponses : code de statut, puis contenu normalisé.
    requetes : [(méthode, chemin)]
    """
    cas = []
    for methode, chemin in requetes:
        statut_o, corps_o = _envoyer(base_origine, methode, chemin)
        statut_m, corps_m = _envoyer(base_migree, methode, chemin)
        equivalent = statut_o == statut_m and _normaliser(corps_o) == _normaliser(corps_m)
        cas.append({"requete": f"{methode} {chemin}", "equivalent": equivalent,
                    "origine": {"statut": statut_o, "extrait": corps_o[:120]},
                    "migree": {"statut": statut_m, "extrait": corps_m[:120]}})
    equivalents = sum(c["equivalent"] for c in cas)
    return {"statut": "teste", "cas_testes": len(cas), "cas_equivalents": equivalents,
            "score_equivalence": equivalents / len(cas) if cas else None,
            "divergences": [c for c in cas if not c["equivalent"]]}


def requetes_depuis_routes(routes: list, valeurs=("1",)) -> list:
    """Une requête par route, les paramètres remplis par des valeurs d'essai."""
    requetes = []
    for r in routes:
        for valeur in valeurs:
            chemin = re.sub(r"\{\w+\}", valeur, r["chemin"] or "/")
            methode = "GET" if r["methode"] == "ANY" else r["methode"]
            requetes.append((methode, chemin))
    return sorted(set(requetes))


def demarrer_serveur(commande: list, dossier: str, url: str, delai_s: float = 30):
    """Lance un serveur (php -S, uvicorn) et attend qu'il réponde."""
    processus = subprocess.Popen(commande, cwd=dossier, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
    limite = time.monotonic() + delai_s
    while time.monotonic() < limite:
        if _envoyer(url, "GET", "/", delai_s=2)[0] != 0:
            return processus
        time.sleep(0.5)
    processus.terminate()
    raise RuntimeError(f"le serveur {' '.join(commande)} ne répond pas sur {url}")


def outils_http_disponibles() -> dict:
    return {"php": shutil.which("php") is not None,
            "uvicorn": shutil.which("uvicorn") is not None}


# ═══ SYMFONY ═══════════════════════════════════════════

CONSIGNE_SYMFONY = (
    "L'APPLICATION D'ORIGINE UTILISE LE FRAMEWORK SYMFONY. Correspondances à respecter :\n"
    "- Contrôleur (AbstractController) → classe Python aux méthodes de même rôle ; les "
    "ROUTES sont générées à part (routes.py) : n'écris pas de décorateur @app.get.\n"
    "- $this->render('x.html.twig', [...]) → renvoie les données ; le gabarit est traduit à part.\n"
    "- $this->json($d) → renvoie le dict ; throw $this->createNotFoundException() → "
    "HTTPException(status_code=404).\n"
    "- Entité et dépôt Doctrine → modèle SQLAlchemy ; $repo->find($id) → session.get(Entite, id) ; "
    "$repo->findOneBy(['email' => $e]) → session.scalars(select(Entite).where(Entite.email == e)).first().\n"
    "- Formulaires et contraintes de validation → modèle Pydantic (Field).\n"
    "- Sécurité (IsGranted, voters) → dépendance FastAPI (Depends).")

_ROUTE_ATTRIBUT = re.compile(
    r"#\[Route\(\s*['\"]([^'\"]*)['\"](?P<options>.*?)\)\]"
    r"|@Route\(\s*\"([^\"]*)\"(?P<options2>[^)]*)\)", re.S)


def _methodes_route(options: str) -> list:
    trouve = re.search(r"methods\s*[:=]\s*[\[{]([^\]}]*)[\]}]", options or "")
    return [m.strip(" '\"").upper() for m in trouve.group(1).split(",")] if trouve else ["GET"]


def lire_routes_symfony(dossier: str) -> list:
    """Routes déclarées par attributs #[Route] (ou annotations @Route) dans les contrôleurs."""
    routes = []
    for racine, _, noms in os.walk(os.path.join(dossier, "src", "Controller")):
        for nom in noms:
            if not nom.endswith(".php"):
                continue
            code = open(os.path.join(racine, nom), encoding="utf-8", errors="ignore").read()
            classe = re.search(r"class\s+(\w+)", code)
            if not classe:
                continue
            # Préfixe : une route posée sur la CLASSE s'ajoute à celles des méthodes.
            avant_classe = code[:classe.start()]
            prefixe_m = list(_ROUTE_ATTRIBUT.finditer(avant_classe))
            prefixe = (prefixe_m[-1].group(1) or prefixe_m[-1].group(3) or "") if prefixe_m else ""
            corps = code[classe.end():]
            for m in _ROUTE_ATTRIBUT.finditer(corps):
                methode_php = re.search(r"function\s+(\w+)", corps[m.end():])
                if not methode_php:
                    continue
                chemin = "/" + (prefixe.strip("/") + "/" + (m.group(1) or m.group(3) or "")
                                .strip("/")).strip("/")
                parametres = re.findall(r"\{(\w+)\}", chemin)
                for verbe in _methodes_route(m.group("options") or m.group("options2")):
                    routes.append({"methode": verbe, "chemin": chemin, "controleur": classe.group(1),
                                   "action": methode_php.group(1), "parametres": parametres,
                                   "closure": False, "source": os.path.relpath(
                                       os.path.join(racine, nom), dossier).replace("\\", "/")})
    return routes


def convertir_twig(source: str) -> tuple:
    """
    Twig → Jinja2. Les deux langages de gabarits sont très proches ; seules
    quelques fonctions et filtres propres à Symfony diffèrent.
    """
    t = source
    t = re.sub(r"(['\"])([\w./-]+)\.html\.twig\1", r'"\2.html"', t)
    t = re.sub(r"\|\s*raw\b", "| safe", t)
    t = re.sub(r"\|\s*json_encode\b", "| tojson", t)
    t = re.sub(r"\basset\(\s*(['\"])([^'\"]+)\1\s*\)", r"url_for('static', path='\2')", t)
    t = re.sub(r"\bpath\(\s*(['\"])(\w+)\1\s*(?:,\s*\{([^}]*)\})?\s*\)",
               lambda m: "url_for('" + m.group(2) + "'" + "".join(
                   f", {k.strip()}={v.strip()}" for k, v in
                   (p.split(":", 1) for p in (m.group(3) or "").split(",") if ":" in p)) + ")", t)
    # Ce qui est propre à Symfony : filtres sans équivalent direct, et la
    # variable globale « app » (app.user, app.request…) — mais pas un nom
    # de fichier comme 'css/app.css', d'où le contexte exigé avant « app ».
    restes = re.findall(r"\{[{%][^}]*?(?:\|\s*(?:trans|date|format|nl2br|number_format)\b|"
                        r"(?<![\w/.'\"-])app\.(?:user|request|session|flashes|environment|debug|token)\b|"
                        r"\bdump\(|\{%\s*trans\b)[^}]*?[}%]\}", t)
    for bloc in restes:
        t = t.replace(bloc, "{# SMAML — non converti, à traduire à la main : "
                      + bloc.replace("#}", "# }")[:120] + " #}")
    return t, restes


# ═══ ADAPTATEURS DE FRAMEWORK ══════════════════════════

class AdaptateurFramework:
    """Ce qui est propre à un framework : routes, vues, consigne."""
    nom = "inconnu"
    extensions_vues: tuple = ()
    consigne = ""

    def lire_routes(self, dossier: str) -> list:
        return []

    def convertir_vue(self, source: str) -> tuple:
        return convertir_vue(source)

    def nom_gabarit(self, chemin: str) -> str:
        return nom_gabarit(chemin)


class AdaptateurLaravel(AdaptateurFramework):
    nom = "Laravel"
    extensions_vues = (".blade.php",)
    consigne = CONSIGNE_LARAVEL

    def lire_routes(self, dossier):
        return lire_routes_laravel(dossier)


class AdaptateurSymfony(AdaptateurFramework):
    nom = "Symfony"
    extensions_vues = (".twig",)
    consigne = CONSIGNE_SYMFONY

    def lire_routes(self, dossier):
        return lire_routes_symfony(dossier)

    def convertir_vue(self, source):
        return convertir_twig(source)

    def nom_gabarit(self, chemin):
        relatif = re.sub(r"^(?:.*?/)?templates/", "", chemin.replace("\\", "/"))
        return re.sub(r"\.html\.twig$|\.twig$", ".html", relatif)


ADAPTATEURS_FRAMEWORK = {"Laravel": AdaptateurLaravel(), "Symfony": AdaptateurSymfony()}


def adaptateur_framework(nom: str):
    return ADAPTATEURS_FRAMEWORK.get(nom)