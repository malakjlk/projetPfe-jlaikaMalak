"""
Doublures de base de données — SMAML
====================================
Permet de comparer PHP et Python sur des fonctions qui accèdent à une
base de données, alors qu'elles étaient jusqu'ici déclarées
« non testables ».

Principe
--------
Les deux langages exécutent le même SQL sur une MÊME base SQLite,
peuplée des MÊMES données initiales. Chacun reçoit sa propre copie du
fichier : les effets de bord (INSERT, UPDATE, DELETE) sont donc
mesurables séparément, puis comparés.

Côté PHP, les appels `mysqli_*`, `mysql_*` et `new PDO(...)` sont
réécrits vers des équivalents branchés sur SQLite. La réécriture porte
sur le texte du code : contrairement à une redéfinition de fonction,
elle marche même quand l'extension mysqli est réellement installée.

Côté Python, de faux modules (`mysql.connector`, `psycopg2`, `pymysql`)
sont placés dans sys.modules avant l'exécution, et `sqlite3.connect`
est redirigé vers la base de test.

Ce qui est comparé
------------------
  - la valeur retournée ;
  - l'exception levée, le cas échéant ;
  - l'état de la base après l'appel (INSERT / UPDATE / DELETE) ;
  - les requêtes émises, conservées pour l'analyse.

Le schéma est déduit du SQL présent dans le code : aucune base réelle
n'est nécessaire.
"""

import os
import re
import sqlite3

# ─── Déduction du schéma ─────────────────────────────

MOTIF_TABLES = re.compile(
    r"\b(?:FROM|INTO|UPDATE|JOIN)\s+[`\"']?(\w+)[`\"']?", re.IGNORECASE)
MOTIF_COLONNES_WHERE = re.compile(
    r"\bWHERE\s+[`\"']?(\w+)[`\"']?\s*(?:=|LIKE)", re.IGNORECASE)
MOTIF_COLONNES_INSERT = re.compile(
    r"\bINSERT\s+INTO\s+\w+\s*\(([^)]*)\)", re.IGNORECASE)
MOTIF_COLONNES_SET = re.compile(
    r"\bSET\s+[`\"']?(\w+)[`\"']?\s*=", re.IGNORECASE)

# Colonnes présentes dans presque toute table applicative héritée :
# elles rendent la base de test utilisable même quand le code n'en
# nomme qu'une seule.
COLONNES_PAR_DEFAUT = ["email", "password", "name", "role", "status"]

# Valeur connue présente dans la base : elle permet de tester le cas
# « l'enregistrement existe », le seul qui exerce vraiment la requête.
VALEUR_CONNUE = "test@example.com"


def analyser_schema(*codes: str) -> dict:
    """Tables et colonnes mentionnées dans le SQL des codes fournis."""
    tables, colonnes = set(), set()
    for code in codes:
        if not code:
            continue
        tables.update(m.lower() for m in MOTIF_TABLES.findall(code))
        colonnes.update(m.lower() for m in MOTIF_COLONNES_WHERE.findall(code))
        colonnes.update(m.lower() for m in MOTIF_COLONNES_SET.findall(code))
        for groupe in MOTIF_COLONNES_INSERT.findall(code):
            colonnes.update(c.strip(" `\"'").lower()
                            for c in groupe.split(","))
    tables.discard("")
    colonnes.discard("")
    if not tables:
        tables = {"users"}
    colonnes.update(COLONNES_PAR_DEFAUT)
    colonnes.discard("id")
    return {"tables": sorted(tables),
            "colonnes": sorted(c for c in colonnes if c.isidentifier())}


def creer_base(chemin: str, *codes: str) -> dict:
    """
    Crée la base de test et y insère des données déterministes.
    Retourne le schéma utilisé.
    """
    schema = analyser_schema(*codes)
    if os.path.exists(chemin):
        try:
            os.unlink(chemin)
        except OSError:
            # Windows refuse de supprimer un fichier encore ouvert
            # (WinError 32). On vide alors la base au lieu de la
            # recréer : le résultat est le même.
            try:
                cnx = sqlite3.connect(chemin)
                for (nom,) in cnx.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table'").fetchall():
                    cnx.execute(f"DROP TABLE IF EXISTS {nom}")
                cnx.commit()
                cnx.close()
            except sqlite3.Error:
                pass
    cnx = sqlite3.connect(chemin)
    for table in schema["tables"]:
        colonnes = ", ".join(f"{c} TEXT" for c in schema["colonnes"])
        cnx.execute(f"CREATE TABLE {table} "
                    f"(id INTEGER PRIMARY KEY, {colonnes})")
        lignes = [
            {"email": VALEUR_CONNUE, "password": "motdepasse123",
             "name": "Test", "role": "user", "status": "actif"},
            {"email": "admin@example.com", "password": "adminpass",
             "name": "Admin", "role": "admin", "status": "actif"},
        ]
        noms = ", ".join(schema["colonnes"])
        trous = ", ".join("?" * len(schema["colonnes"]))
        for ligne in lignes:
            valeurs = [ligne.get(c, f"valeur_{c}")
                       for c in schema["colonnes"]]
            cnx.execute(f"INSERT INTO {table} ({noms}) VALUES ({trous})",
                        valeurs)
    cnx.commit()
    cnx.close()
    return schema


def etat_base(chemin: str) -> dict:
    """Contenu de toutes les tables — sert à comparer les effets de bord."""
    if not os.path.exists(chemin):
        return {}
    etat = {}
    try:
        cnx = sqlite3.connect(chemin)
        cnx.row_factory = sqlite3.Row
        tables = [r[0] for r in cnx.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        for table in tables:
            lignes = cnx.execute(f"SELECT * FROM {table} ORDER BY id")
            etat[table] = [dict(l) for l in lignes]
        cnx.close()
    except sqlite3.Error:
        return {}
    return etat


def code_utilise_bdd(code: str) -> bool:
    """Le code accède-t-il à une base de données ?"""
    return bool(re.search(
        r"mysqli_|mysql_|new\s+PDO|new\s+mysqli|pg_|"
        r"mysql\.connector|psycopg2|pymysql|sqlite3|sqlalchemy|"
        r"\bcursor\s*\(|\bexecute\s*\(", code or "", re.IGNORECASE))


# ─── Côté PHP : réécriture vers SQLite ───────────────
# On réécrit les APPELS plutôt que de redéfinir les fonctions : PHP
# interdit de redéfinir une fonction d'extension déjà chargée, et
# mysqli est souvent installé sur la machine de développement.

REECRITURES_PHP = [
    (r"\bnew\s+mysqli\s*\(", "smaml_connexion("),
    (r"\bnew\s+PDO\s*\(", "smaml_connexion("),
    (r"\bmysqli_connect\s*\(", "smaml_connexion("),
    (r"\bmysql_connect\s*\(", "smaml_connexion("),
    (r"\bmysqli_select_db\s*\(", "smaml_vrai("),
    (r"\bmysql_select_db\s*\(", "smaml_vrai("),
    (r"\bmysqli_query\s*\(", "smaml_requete("),
    (r"\bmysql_query\s*\(", "smaml_requete_simple("),
    (r"\bmysqli_fetch_assoc\s*\(", "smaml_ligne("),
    (r"\bmysql_fetch_assoc\s*\(", "smaml_ligne("),
    (r"\bmysqli_fetch_array\s*\(", "smaml_ligne("),
    (r"\bmysqli_fetch_all\s*\(", "smaml_lignes("),
    (r"\bmysqli_num_rows\s*\(", "smaml_nombre("),
    (r"\bmysql_num_rows\s*\(", "smaml_nombre("),
    (r"\bmysqli_real_escape_string\s*\(", "smaml_echapper("),
    (r"\bmysql_real_escape_string\s*\(", "smaml_echapper_simple("),
    (r"\bmysqli_insert_id\s*\(", "smaml_dernier_id("),
    (r"\bmysqli_affected_rows\s*\(", "smaml_lignes_affectees("),
    (r"\bmysqli_error\s*\(", "smaml_erreur("),
    (r"\bmysqli_close\s*\(", "smaml_vrai("),
    (r"\bmysql_close\s*\(", "smaml_vrai("),
]


def reecrire_php(code: str) -> str:
    """Redirige les appels base de données vers les doublures."""
    for motif, remplacement in REECRITURES_PHP:
        code = re.sub(motif, remplacement, code)
    return code


PRELUDE_PHP = r"""
// ── Doublures SMAML : même base SQLite que le côté Python ──
$SMAML_REQUETES = [];

function smaml_pdo() {
    static $pdo = null;
    if ($pdo === null) {
        $pdo = new PDO("sqlite:" . getenv("SMAML_BDD"));
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    }
    return $pdo;
}
function smaml_connexion() { return smaml_pdo(); }
function smaml_vrai() { return true; }

function smaml_requete($conn, $sql = null) {
    global $SMAML_REQUETES;
    if ($sql === null) { $sql = $conn; }   // forme à un seul argument
    $SMAML_REQUETES[] = $sql;
    try {
        $st = smaml_pdo()->query($sql);
        if ($st === false) { return false; }
        // SELECT : on matérialise ; sinon on renvoie le nombre de lignes
        if (preg_match('/^\s*SELECT/i', $sql)) {
            return $st->fetchAll(PDO::FETCH_ASSOC);
        }
        return true;
    } catch (Throwable $e) {
        return false;                       // comme mysqli_query
    }
}
function smaml_requete_simple($sql, $conn = null) {
    return smaml_requete($sql);
}
function smaml_ligne(&$res) {
    if (!is_array($res) || count($res) === 0) { return null; }
    return array_shift($res);
}
function smaml_lignes($res) { return is_array($res) ? $res : []; }
function smaml_nombre($res) { return is_array($res) ? count($res) : 0; }
function smaml_echapper($conn, $valeur = null) {
    if ($valeur === null) { $valeur = $conn; }
    return str_replace("'", "''", $valeur);
}
function smaml_echapper_simple($valeur) { return str_replace("'", "''", $valeur); }
function smaml_dernier_id($conn = null) { return smaml_pdo()->lastInsertId(); }
function smaml_lignes_affectees($conn = null) { return 1; }
function smaml_erreur($conn = null) { return ""; }
"""


# ─── Côté Python : faux modules base de données ──────

def _adapter_requete(sql: str, params):
    """
    Convertit une requête et ses paramètres vers le style SQLite.

    Trois styles coexistent dans le code généré :
      - positionnel MySQL  : "... = %s"        + tuple
      - nommé SQLAlchemy   : "... = :email"    + dict
      - nommé pyformat     : "... = %(email)s" + dict
    Passer un dict comme un tuple ferait échouer silencieusement la
    requête — le code paraîtrait alors ne rien trouver.
    """
    if isinstance(params, dict):
        # %(nom)s → :nom ; les :nom sont déjà au bon format
        return re.sub(r"%\((\w+)\)s", r":\1", sql), params
    return sql.replace("%s", "?"), tuple(params) if params else ()


def installer_doublures_python(chemin_bdd: str, journal: list):
    """
    Place dans sys.modules des modules de base de données branchés sur
    la base de test, et redirige sqlite3.connect vers elle.
    Retourne une fonction de restauration.
    """
    import sys
    import types

    class _Ligne(dict):
        """
        Ligne de résultat compatible avec les deux styles de code que
        produit le LLM :
          - style dictionnaire  : ligne["email"], dict(ligne)
          - style DB-API tuple  : ligne[0], zip(colonnes, ligne)
        Un dict simple casserait le second (zip itérerait sur les noms
        de colonnes au lieu des valeurs).
        """

        def __iter__(self):
            return iter(self.values())

        def __getitem__(self, cle):
            if isinstance(cle, int):
                return list(self.values())[cle]
            return dict.__getitem__(self, cle)


    class _Curseur:
        def __init__(self, cnx):
            self._cur = cnx.cursor()
            self.lastrowid = None

        def execute(self, requete, params=None):
            journal.append(str(requete))
            sql, valeurs = _adapter_requete(str(requete), params)
            self._cur.execute(sql, valeurs)
            self.lastrowid = self._cur.lastrowid
            return self

        def executemany(self, requete, params):
            journal.append(str(requete))
            sql, _ = _adapter_requete(str(requete), None)
            self._cur.executemany(sql, params)
            return self

        @property
        def description(self):
            # Utilisé par le code généré pour reconstruire les noms de
            # colonnes : sans lui, l'appel lève AttributeError.
            return self._cur.description

        @property
        def rownumber(self):
            return 0

        def fetchone(self):
            ligne = self._cur.fetchone()
            return _Ligne(ligne) if ligne else None

        def fetchall(self):
            return [_Ligne(l) for l in self._cur.fetchall()]

        def fetchmany(self, taille=1):
            return [_Ligne(l) for l in self._cur.fetchmany(taille)]

        # Formes SQLAlchemy : result.mappings().first(), .scalar()...
        def mappings(self):
            return self

        def scalars(self):
            return self

        def first(self):
            return self.fetchone()

        def all(self):
            return self.fetchall()

        def scalar(self):
            ligne = self._cur.fetchone()
            return list(dict(ligne).values())[0] if ligne else None

        def keys(self):
            return [d[0] for d in (self._cur.description or [])]

        def __iter__(self):
            return iter(self.fetchall())

        @property
        def rowcount(self):
            return self._cur.rowcount

        def close(self):
            self._cur.close()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            self.close()
            return False

    connexions_ouvertes = []

    class _Connexion:
        def __init__(self, *a, **k):
            self._cnx = sqlite3.connect(chemin_bdd)
            self._cnx.row_factory = sqlite3.Row
            connexions_ouvertes.append(self._cnx)

        def cursor(self, *a, **k):
            return _Curseur(self._cnx)

        def execute(self, requete, params=None):
            return _Curseur(self._cnx).execute(requete, params)

        def commit(self):
            self._cnx.commit()

        def rollback(self):
            self._cnx.rollback()

        def close(self):
            # PAS de commit implicite : un pilote réel abandonne les
            # écritures non validées. C'est ce qui rend détectable
            # l'oubli d'un commit() dans le code généré.
            self._cnx.rollback()
            self._cnx.close()

        def is_connected(self):
            return True

        def __enter__(self):
            return self

        def __exit__(self, *a):
            self.close()
            return False

    def connect(*a, **k):
        return _Connexion()

    class Error(Exception):
        pass

    anciens = {}

    def _module(nom, **attributs):
        mod = types.ModuleType(nom)
        for cle, valeur in attributs.items():
            setattr(mod, cle, valeur)
        anciens[nom] = sys.modules.get(nom)
        sys.modules[nom] = mod
        return mod

    commun = {"connect": connect, "Error": Error,
              "DatabaseError": Error, "IntegrityError": Error,
              "OperationalError": Error}
    mysql = _module("mysql")
    connector = _module("mysql.connector", **commun)
    mysql.connector = connector
    _module("psycopg2", **commun)
    _module("pymysql", **commun)

    # ── SQLAlchemy ──
    # Le LLM produit souvent du SQLAlchemy plutôt qu'un pilote direct :
    # sans doublure, l'import échoue et la fonction devient
    # « non testable » alors qu'elle est parfaitement comparable.
    class _Texte:
        """Résultat de text() : son str() est la requête."""
        def __init__(self, requete):
            self._requete = str(requete)

        def __str__(self):
            return self._requete

        def bindparams(self, *a, **k):
            return self

    class _Moteur(_Connexion):
        def connect(self, *a, **k):
            return _Connexion()

        def begin(self, *a, **k):
            return _Connexion()

        def dispose(self, *a, **k):
            pass

        @property
        def url(self):
            return "sqlite:///test"

    def creer_moteur(*a, **k):
        return _Moteur()

    def texte(requete, *a, **k):
        return _Texte(requete)

    Connection = _Connexion
    Engine = _Moteur

    sqlalchemy = _module(
        "sqlalchemy", create_engine=creer_moteur, text=texte,
        Engine=_Moteur, Connection=_Connexion, MetaData=object,
        Table=object, Column=object, String=str, Integer=int)
    moteur_mod = _module("sqlalchemy.engine", Engine=_Moteur,
                         Connection=_Connexion, create_engine=creer_moteur,
                         Result=object, Row=dict)
    exc_mod = _module("sqlalchemy.exc", SQLAlchemyError=Error,
                      DatabaseError=Error, OperationalError=Error,
                      IntegrityError=Error)
    orm_mod = _module(
        "sqlalchemy.orm", Session=_Connexion,
        sessionmaker=lambda *a, **k: (lambda *b, **c: _Connexion()),
        declarative_base=lambda *a, **k: object)
    sqlalchemy.engine = moteur_mod
    sqlalchemy.exc = exc_mod
    sqlalchemy.orm = orm_mod

    # sqlite3.connect redirigé vers la base de test
    connect_origine = sqlite3.connect
    sqlite3.connect = lambda *a, **k: connect_origine(chemin_bdd)

    def restaurer():
        # Toute connexion laissée ouverte par le code testé garderait
        # le fichier verrouillé sous Windows.
        for cnx in connexions_ouvertes:
            try:
                cnx.rollback()      # jamais de commit implicite
                cnx.close()
            except sqlite3.Error:
                pass
        connexions_ouvertes.clear()
        sqlite3.connect = connect_origine
        for nom, ancien in anciens.items():
            if ancien is None:
                sys.modules.pop(nom, None)
            else:
                sys.modules[nom] = ancien

    return restaurer


# ─── Modules tiers absents ───────────────────────────
# Le code généré importe souvent des bibliothèques qui ne sont pas
# installées (fastapi, pydantic, sqlalchemy...). Sans elles, la
# fonction ne peut pas être chargée et le test différentiel est
# abandonné — alors que ces dépendances ne changent rien au
# comportement comparé. On fournit donc un module permissif, créé à la
# demande, qui laisse le code se charger.

class _ObjetPermissif(Exception):
    """
    Remplace n'importe quel objet importé : instanciable, appelable,
    levable comme une exception, et transparent comme décorateur.
    Hérite d'Exception pour que `raise HTTPException(...)` fonctionne.
    """

    def __init__(self, *a, **k):
        super().__init__(*[str(x) for x in a][:1])

    def __call__(self, *a, **k):
        # Décorateur : @app.get("/x") doit rendre la fonction intacte
        if len(a) == 1 and callable(a[0]) and not k:
            return a[0]
        return self

    def __getattr__(self, nom):
        return type(nom, (_ObjetPermissif,), {})()

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return True


class _ModulePermissif(types_module_base := type(os)):
    """Module dont tout attribut existe, créé à la volée."""

    def __getattr__(self, nom):
        if nom.startswith("__"):
            raise AttributeError(nom)
        return type(nom, (_ObjetPermissif,), {})


def installer_module_absent(nom: str):
    """Crée un module permissif pour `nom` (et ses parents)."""
    import sys
    parties = nom.split(".")
    for i in range(len(parties)):
        chemin = ".".join(parties[:i + 1])
        if chemin not in sys.modules:
            module = _ModulePermissif(chemin)
            module.__path__ = []          # autorise les sous-modules
            sys.modules[chemin] = module
            if i:
                setattr(sys.modules[".".join(parties[:i])],
                        parties[i], module)
    return sys.modules[nom]


if __name__ == "__main__":
    import json
    import tempfile

    code = """
    $sql = "SELECT * FROM users WHERE email='" . $email . "'";
    mysqli_query($conn, $sql);
    """
    print("Schéma déduit :", json.dumps(analyser_schema(code),
                                        ensure_ascii=False))
    chemin = os.path.join(tempfile.gettempdir(), "smaml_demo.db")
    creer_base(chemin, code)
    etat = etat_base(chemin)
    print(f"Table users : {len(etat['users'])} ligne(s)")
    print("Première ligne :", etat["users"][0])
    os.unlink(chemin)