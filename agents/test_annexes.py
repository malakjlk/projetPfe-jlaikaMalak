"""
Tests du traitement des fichiers annexes d'un projet.

    py -X utf8 test_annexes.py

Le test construit lui-même un projet complet : ton test_php_project,
enrichi d'un schéma SQL, de données, de CSS, de JavaScript, d'une image,
de configuration et d'une page de vue.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

VERSIONS = {"fichiers_annexes.py": "def traduire_schema_sql",
            "orchestration.py": "_vues_et_routes"}
anciens = [f"[X] {n} : absent ou ancienne version" for n, m in VERSIONS.items()
           if not os.path.exists(os.path.join(ICI, n))
           or m not in open(os.path.join(ICI, n), encoding="utf-8", errors="ignore").read()]
if anciens:
    print("Fichiers à mettre à jour avant le test :\n  " + "\n  ".join(anciens))
    raise SystemExit(1)

from fichiers_annexes import classer, traduire_schema_sql

resultats = []


def verifier(nom, condition):
    resultats.append((nom, bool(condition)))
    print(f"   {'[OK]' if condition else '[ECHEC]'} {nom}")


SCHEMA = """CREATE TABLE IF NOT EXISTS `users` (
  `id` INT(11) NOT NULL AUTO_INCREMENT,
  `email` VARCHAR(255) NOT NULL,
  `password` VARCHAR(255) NOT NULL,
  `actif` TINYINT(1) DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `email_unique` (`email`)
) ENGINE=InnoDB;
CREATE TABLE `orders` (
  `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NOT NULL,
  `montant` DECIMAL(10,2) NOT NULL DEFAULT '0.00',
  `statut` ENUM('nouveau','paye') DEFAULT 'nouveau',
  CONSTRAINT fk_user FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
);"""
IMAGE = bytes(range(256)) * 4

tmp = tempfile.mkdtemp()
projet = os.path.join(tmp, "projet")
shutil.copytree(os.path.join(ICI, "test_php_project"), projet)
fichiers = {"schema.sql": SCHEMA,
            "donnees.sql": "INSERT INTO users (email, password) VALUES ('a@b.c', 'x');",
            "static/style.css": "body { color: #333; }",
            "static/app.js": "fetch('/login').then(r => r.json());",
            "composer.json": '{"require": {"php": ">=7.4"}}',
            ".htaccess": "RewriteEngine On\nRewriteRule ^connexion$ login.php [L]",
            ".env": "DB_HOST=localhost",
            "accueil.php": "<html><body><h1>Bonjour <?php echo $nom; ?></h1></body></html>"}
for relatif, contenu in fichiers.items():
    chemin = os.path.join(projet, relatif)
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    open(chemin, "w", encoding="utf-8").write(contenu)
os.makedirs(os.path.join(projet, "static"), exist_ok=True)
open(os.path.join(projet, "static", "logo.png"), "wb").write(IMAGE)

print("\n── Classement des fichiers ──")
attendus = {"schema.sql": "schema_sql", "donnees.sql": "donnees_sql",
            "static/style.css": "statique", "static/logo.png": "statique",
            "composer.json": "configuration", ".htaccess": "configuration"}
verifier("chaque fichier reçoit la bonne catégorie",
         all(classer(os.path.join(projet, f), (".php",)) == c for f, c in attendus.items()))

print("\n── Schéma SQL → modèles SQLAlchemy, sans LLM ──")
code, classes = traduire_schema_sql(SCHEMA)
espace = {}
exec(code, espace)
Users, Orders = espace["Users"], espace["Orders"]
verifier("le code produit s'exécute réellement avec SQLAlchemy", classes == {"users": "Users", "orders": "Orders"})
verifier("clé primaire et contrainte UNIQUE (même nommée entre accents graves)",
         Users.__table__.c.id.primary_key and Users.__table__.c.email.unique
         and "UNIQUE" not in [c.name for c in Users.__table__.c])
verifier("types exacts : TINYINT(1) → booléen, DECIMAL(10,2) → Numeric(10, 2)",
         str(Users.__table__.c.actif.type) == "BOOLEAN"
         and str(Orders.__table__.c.montant.type) == "NUMERIC(10, 2)")
verifier("la clé étrangère orders.user_id → users.id est conservée",
         [str(f.column) for f in Orders.__table__.c.user_id.foreign_keys] == ["users.id"])

print("\n── Migration d'un projet complet ──")
simu = os.path.join(tmp, "simu")
os.makedirs(simu)
shutil.copy(os.path.join(ICI, "developpeur_simule.py"), os.path.join(simu, "agent_developpeur.py"))
sortie = os.path.join(tmp, "sortie")
env = dict(os.environ, PYTHONPATH=os.pathsep.join([simu, ICI]), SMAML_STOCKAGE="sqlite",
           SMAML_STOCKAGE_SQLITE=os.path.join(tmp, "e.db"), SMAML_CACHE="0",
           SMAML_MODE="direct", SMAML_JUGE="0", SMAML_ENTREES_IA="0", PYTHONIOENCODING="utf-8")
subprocess.run([sys.executable, "-X", "utf8", "-c",
                f"import orchestration; orchestration.migrer_projet({projet!r}, {sortie!r}, 2)"],
               cwd=tmp, env=env, capture_output=True, timeout=900)
rapport = json.load(open(os.path.join(sortie, "rapport_migration.json"), encoding="utf-8"))
annexes = {a["fichier"].replace("\\\\", "/"): a for a in rapport["fichiers_annexes"]}
verifier("le code PHP est toujours migré (5 modules)", rapport["statistiques"]["modules"] == 5)
verifier("les fichiers statiques sont copiés à l'identique, image comprise",
         open(os.path.join(sortie, "static", "logo.png"), "rb").read() == IMAGE
         and os.path.exists(os.path.join(sortie, "static", "style.css")))
verifier("le schéma devient models.py, les données sont conservées sans traduction",
         os.path.exists(os.path.join(sortie, "models.py"))
         and annexes["schema.sql"]["cible"] == "models.py"
         and os.path.exists(os.path.join(sortie, "donnees", "donnees.sql")))
verifier("composer.json est remplacé par requirements.txt, .htaccess est signalé",
         "cible" not in annexes["composer.json"] and "routes" in annexes[".htaccess"]["action"])
vue = next(f for f in rapport["fichiers_migres"] if f["source"] == "accueil.php")
verifier("la page de vue n'est plus un fichier Python vide : elle devient un gabarit Jinja2",
         vue["statut"] == "gabarit" and not os.path.exists(os.path.join(sortie, "accueil.py"))
         and "{{ nom }}" in open(os.path.join(sortie, "templates", "accueil.html"),
                                 encoding="utf-8").read())
verifier("le projet produit reste cohérent et bien typé, modèles compris",
         rapport["coherence_projet"]["coherent"]
         and rapport["coherence_projet"]["typage"].get("coherent", True))

ok = sum(1 for _, x in resultats if x)
print(f"\n{ok}/{len(resultats)} vérifications réussies")
shutil.rmtree(tmp, ignore_errors=True)
if ok != len(resultats):
    raise SystemExit(1)