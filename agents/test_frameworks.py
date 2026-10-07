"""
Tests des frameworks : Laravel détecté, routes → FastAPI, vues → Jinja2,
et comparateur HTTP.

    py -X utf8 test_frameworks.py

Le test construit lui-même une petite application Laravel, et lance deux
serveurs HTTP locaux pour éprouver le comparateur.
"""
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

VERSIONS = {"frameworks.py": "class AdaptateurSymfony", "orchestration.py": "adaptateur_framework",
            "fichiers_annexes.py": ".twig"}
anciens = [f"[X] {n} : absent ou ancienne version" for n, m in VERSIONS.items()
           if not os.path.exists(os.path.join(ICI, n))
           or m not in open(os.path.join(ICI, n), encoding="utf-8", errors="ignore").read()]
try:
    import jinja2  # noqa: F401
except ImportError:
    anciens.append("[X] jinja2 : non installé (py -m pip install jinja2)")
if anciens:
    print("À corriger avant le test :\n  " + "\n  ".join(anciens))
    raise SystemExit(1)

import frameworks as fw

resultats = []


def verifier(nom, condition):
    resultats.append((nom, bool(condition)))
    print(f"   {'[OK]' if condition else '[ECHEC]'} {nom}")


LARAVEL = {
    "composer.json": '{"require": {"php": "^8.1", "laravel/framework": "^10.0"}}',
    "artisan": "#!/usr/bin/env php\n<?php // console Laravel",
    "routes/web.php": """<?php
use App\\Http\\Controllers\\UserController;
Route::get('/users', [UserController::class, 'index']);
Route::get('/users/{id}', [UserController::class, 'show']);
Route::post('/users', 'UserController@store');
Route::get('/about', function () { return view('about'); });
""",
    "app/Http/Controllers/UserController.php": """<?php
namespace App\\Http\\Controllers;
class UserController extends Controller {
    public function index() { return view('users.index', ['users' => User::all()]); }
    public function show($id) { return User::findOrFail($id); }
    public function store(Request $request) { $request->validate(['email' => 'required|email']); }
}
""",
    "resources/views/layouts/app.blade.php": "<html><body>@yield('content')</body></html>",
    "resources/views/users/index.blade.php": """@extends('layouts.app')
@section('content')
  <h1>{{ $titre }}</h1>
  @if(count($users) > 0)
    <ul>
    @foreach($users as $user)
      <li>{{ $user->name }} - {!! $user->bio !!}</li>
    @endforeach
    </ul>
  @else
    <p>Aucun utilisateur</p>
  @endif
  @csrf
  @can('admin') <a href="/admin">Admin</a> @endcan
@endsection
""",
}
tmp = tempfile.mkdtemp()
appli = os.path.join(tmp, "laravel")
for relatif, contenu in LARAVEL.items():
    chemin = os.path.join(appli, relatif)
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    open(chemin, "w", encoding="utf-8").write(contenu)

print("\n── Détection ──")
cadre = fw.detecter_framework(appli)
verifier("une application Laravel est détectée, sur plusieurs indices concordants",
         cadre and cadre["nom"] == "Laravel" and len(cadre["indices"]) >= 3)
verifier("un projet PHP simple n'est pas pris pour du Laravel",
         fw.detecter_framework(os.path.join(ICI, "test_php_project")) is None)

print("\n── Routes Laravel → routeur FastAPI ──")
routes = fw.lire_routes_laravel(appli)
verifier("les 4 routes sont lues : méthode, chemin, contrôleur, action, paramètres",
         [(r["methode"], r["chemin"], r["action"]) for r in routes] ==
         [("GET", "/users", "index"), ("GET", "/users/{id}", "show"),
          ("POST", "/users", "store"), ("GET", "/about", None)]
         and routes[1]["parametres"] == ["id"])
code_classe = fw.generer_routeur(routes, {"UserController": {"cible_migration": "classe_python"}})
code_fonctions = fw.generer_routeur(routes, {"UserController": {"cible_migration": "fonctions_module"}})
compile(code_classe, "routes.py", "exec")
compile(code_fonctions, "routes.py", "exec")
verifier("le routeur produit est du Python valide, avec les mêmes chemins",
         '@router.get("/users/{id}")' in code_classe and '@router.post("/users")' in code_classe)
verifier("il suit le plan de l'Architecte : classe, ou fonctions si le contrôleur est sans état",
         "UserController().show(id)" in code_classe
         and "from UserController import index, show, store" in code_fonctions
         and "return show(id)" in code_fonctions)
verifier("une route en closure est signalée (501), pas inventée",
         "closure Laravel" in code_classe)

print("\n── Vues Blade → gabarits Jinja2 ──")
index, restes = fw.convertir_vue(LARAVEL["resources/views/users/index.blade.php"])
layout, _ = fw.convertir_vue(LARAVEL["resources/views/layouts/app.blade.php"])
env = jinja2.Environment(loader=jinja2.DictLoader({"layouts/app.html": layout,
                                                   "users/index.html": index}), autoescape=True)
class Utilisateur:
    def __init__(self, name, bio):
        self.name, self.bio = name, bio
html = env.get_template("users/index.html").render(
    titre="Équipe", users=[Utilisateur("Malak", "<b>PFE</b>"), Utilisateur("<script>", "x")])
verifier("le gabarit converti S'EXÉCUTE avec Jinja2 : héritage, boucle, condition",
         "<h1>Équipe</h1>" in html and "Malak" in html and "<html><body>" in html)
verifier("{{ }} reste échappé, {!! !!} reste brut — comme dans Blade",
         "&lt;script&gt;" in html and "<b>PFE</b>" in html)
vide = env.get_template("users/index.html").render(titre="x", users=[])
verifier("la branche @else est conservée", "Aucun utilisateur" in vide)
verifier("ce qui ne se convertit pas (@can) est signalé, pas perdu",
         any("@can" in r for r in restes) and "non converti" in index)
php, _ = fw.convertir_vue("<h1>Bonjour <?php echo $nom; ?></h1><?php if ($admin): ?>Admin<?php endif; ?>")
verifier("une vue PHP mêlée de HTML se convertit aussi",
         jinja2.Template(php).render(nom="Malak", admin=True) == "<h1>Bonjour Malak</h1>Admin")
verifier("nom du gabarit : resources/views/users/index.blade.php → users/index.html",
         fw.nom_gabarit("resources/views/users/index.blade.php") == "users/index.html")

print("\n── Comparateur HTTP, sur deux vrais serveurs ──")


def serveur(reponses):
    class Gestionnaire(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            statut, corps = reponses.get(self.path, (404, "introuvable"))
            self.send_response(statut)
            self.end_headers()
            self.wfile.write(corps.encode())

        def log_message(self, *args):
            pass
    s = http.server.HTTPServer(("127.0.0.1", 0), Gestionnaire)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_address[1]}"


origine, url_o = serveur({"/users/1": (200, '{"id": 1, "name": "Malak"}'),
                          "/about": (200, "<p>  À propos  </p>"),
                          "/users/2": (200, '{"id": 2}')})
migree, url_m = serveur({"/users/1": (200, '{"name":"Malak","id":1}'),
                         "/about": (200, "<p> À propos </p>"),
                         "/users/2": (500, "erreur")})
r = fw.comparer_http(url_o, url_m, [("GET", "/users/1"), ("GET", "/about"),
                                    ("GET", "/users/2"), ("GET", "/inconnue")])
verifier("même JSON dans un autre ordre, même HTML à l'espacement près : équivalents",
         r["cas_equivalents"] == 3)
verifier("une réponse différente (500 au lieu de 200) est une divergence",
         [d["requete"] for d in r["divergences"]] == ["GET /users/2"])
origine.shutdown(); migree.shutdown()

print("\n── Migration d'une application Laravel ──")
simu = os.path.join(tmp, "simu")
os.makedirs(simu)
shutil.copy(os.path.join(ICI, "developpeur_simule.py"), os.path.join(simu, "agent_developpeur.py"))
sortie = os.path.join(tmp, "sortie")
env_m = dict(os.environ, PYTHONPATH=os.pathsep.join([simu, ICI]), SMAML_STOCKAGE="sqlite",
             SMAML_STOCKAGE_SQLITE=os.path.join(tmp, "e.db"), SMAML_CACHE="0",
             SMAML_MODE="direct", SMAML_JUGE="0", SMAML_ENTREES_IA="0", PYTHONIOENCODING="utf-8")
subprocess.run([sys.executable, "-X", "utf8", "-c",
                f"import orchestration; orchestration.migrer_projet({appli!r}, {sortie!r}, 2)"],
               cwd=tmp, env=env_m, capture_output=True, timeout=900)
rapport = json.load(open(os.path.join(sortie, "rapport_migration.json"), encoding="utf-8"))
verifier("le framework est détecté à la réception", (rapport["reception"].get("framework") or {}).get("nom") == "Laravel")
verifier("les vues Blade deviennent des gabarits dans templates/",
         os.path.exists(os.path.join(sortie, "templates", "users", "index.html"))
         and os.path.exists(os.path.join(sortie, "templates", "layouts", "app.html")))
verifier("routes.py et main.py sont produits, en Python valide",
         all(compile(open(os.path.join(sortie, f), encoding="utf-8").read(), f, "exec")
             for f in ("routes.py", "main.py")))
verifier("le contrôleur est confié au Développeur, avec la consigne Laravel → FastAPI",
         any(m["nom_original"] == "UserController" or m["nom_python"].lower().startswith("user")
             for f in rapport["fichiers_migres"] for m in f["modules"]))

print("\n── Symfony : second adaptateur de framework ──")
SYMFONY = {
    "composer.json": '{"require": {"php": ">=8.1", "symfony/framework-bundle": "^6.4"}}',
    "bin/console": "#!/usr/bin/env php",
    "symfony.lock": "{}",
    "src/Controller/UserController.php": """<?php
namespace App\\Controller;
use Symfony\\Bundle\\FrameworkBundle\\Controller\\AbstractController;
use Symfony\\Component\\Routing\\Attribute\\Route;
#[Route('/users')]
class UserController extends AbstractController {
    #[Route('', name: 'user_list', methods: ['GET'])]
    public function list(): Response { return $this->render('user/list.html.twig', ['users' => []]); }
    #[Route('/{id}', name: 'user_show', methods: ['GET'])]
    public function show(int $id): Response { return $this->json(['id' => $id]); }
    #[Route('/{id}', name: 'user_delete', methods: ['DELETE'])]
    public function delete(int $id): Response { return $this->json(null, 204); }
}
""",
    "templates/base.html.twig": "<html><head><link href=\"{{ asset('css/app.css') }}\"></head>"
                                "<body>{% block body %}{% endblock %}</body></html>",
    "templates/user/list.html.twig": """{% extends 'base.html.twig' %}
{% block body %}
<ul>
{% for u in users %}
  <li><a href="{{ path('user_show', {id: u.id}) }}">{{ u.name|upper }}</a> {{ u.bio|raw }}</li>
{% else %}
  <li>Aucun</li>
{% endfor %}
</ul>
<p>{{ 'bienvenue'|trans }}</p>
{% endblock %}
""",
}
sym = os.path.join(tmp, "symfony")
for relatif, contenu in SYMFONY.items():
    chemin = os.path.join(sym, relatif)
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    open(chemin, "w", encoding="utf-8").write(contenu)

cadre = fw.detecter_framework(sym)
verifier("une application Symfony est détectée, et prise en charge",
         cadre and cadre["nom"] == "Symfony" and cadre["pris_en_charge"])
routes_s = fw.lire_routes_symfony(sym)
verifier("routes par attributs, avec le PRÉFIXE de la classe et les méthodes HTTP",
         sorted((r["methode"], r["chemin"], r["action"]) for r in routes_s) ==
         [("DELETE", "/users/{id}", "delete"), ("GET", "/users", "list"),
          ("GET", "/users/{id}", "show")])
liste, restes_s = fw.convertir_twig(SYMFONY["templates/user/list.html.twig"])
base, _ = fw.convertir_twig(SYMFONY["templates/base.html.twig"])
env_s = jinja2.Environment(loader=jinja2.DictLoader({"base.html": base, "user/list.html": liste}),
                           autoescape=True)
env_s.globals["url_for"] = lambda nom, **kw: f"/{nom}/" + "/".join(str(v) for v in kw.values())
rendu = env_s.get_template("user/list.html").render(
    users=[{"id": 7, "name": "malak", "bio": "<i>PFE</i>"}])
verifier("le gabarit Twig converti S'EXÉCUTE avec Jinja2 : héritage, filtres, liens",
         all(attendu in rendu for attendu in
             ("MALAK", "<i>PFE</i>", 'href="/user_show/7"', 'href="/static/css/app.css"')))
verifier("la branche {% else %} de la boucle est conservée",
         "Aucun" in env_s.get_template("user/list.html").render(users=[]))
verifier("ce qui est propre à Symfony (|trans) est signalé, pas perdu",
         any("trans" in r for r in restes_s) and "non converti" in liste)

print("\n── Frameworks reconnus sans adaptateur ──")
ci = os.path.join(tmp, "codeigniter")
os.makedirs(os.path.join(ci, "app", "Config"))
open(os.path.join(ci, "composer.json"), "w").write('{"require": {"codeigniter4/framework": "^4"}}')
open(os.path.join(ci, "spark"), "w").write("#!/usr/bin/env php")
cadre = fw.detecter_framework(ci)
verifier("CodeIgniter est reconnu et nommé, mais signalé comme sans adaptateur",
         cadre and cadre["nom"] == "CodeIgniter" and not cadre["pris_en_charge"])

print("\n── Migration d'une application Symfony ──")
sortie_s = os.path.join(tmp, "sortie_symfony")
env_m["SMAML_STOCKAGE_SQLITE"] = os.path.join(tmp, "s.db")
subprocess.run([sys.executable, "-X", "utf8", "-c",
                f"import orchestration; orchestration.migrer_projet({sym!r}, {sortie_s!r}, 2)"],
               cwd=tmp, env=env_m, capture_output=True, timeout=900)
rapport_s = json.load(open(os.path.join(sortie_s, "rapport_migration.json"), encoding="utf-8"))
verifier("Symfony détecté à la réception", (rapport_s["reception"].get("framework") or {}).get("nom") == "Symfony")
verifier("les gabarits Twig deviennent des gabarits Jinja2, et ne sont pas copiés comme fichiers ordinaires",
         os.path.exists(os.path.join(sortie_s, "templates", "user", "list.html"))
         and os.path.exists(os.path.join(sortie_s, "templates", "base.html"))
         and not os.path.exists(os.path.join(sortie_s, "autres", "templates")))
routes_py = open(os.path.join(sortie_s, "routes.py"), encoding="utf-8").read()
compile(routes_py, "routes.py", "exec")
verifier("routes.py reprend les routes Symfony, préfixe compris, en Python valide",
         '@router.get("/users/{id}")' in routes_py and '@router.delete("/users/{id}")' in routes_py)

ok = sum(1 for _, x in resultats if x)
print(f"\n{ok}/{len(resultats)} vérifications réussies")
shutil.rmtree(tmp, ignore_errors=True)
if ok != len(resultats):
    raise SystemExit(1)