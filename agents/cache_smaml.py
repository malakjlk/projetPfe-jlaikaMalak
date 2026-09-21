"""
Cache persistant SMAML
======================
Évite de refaire un travail déjà fait : une même analyse, une même
génération ou une même vérification portant sur exactement les mêmes
entrées est relue au lieu d'être recalculée.

Pourquoi c'est nécessaire
-------------------------
La boucle de correction et l'orchestration multiplient les
va-et-vient : un module régénéré est revérifié entièrement, et deux
modules d'un même fichier partagent la même analyse. Sans cache, ces
travaux identiques sont refaits à chaque fois — or l'appel au LLM,
l'exécution symbolique (Z3) et l'audit des dépendances sont les
étapes les plus coûteuses du pipeline.

Principe
--------
La clé est l'empreinte SHA-256 du CONTENU des entrées, pas un nom de
fichier : si une seule ligne de code change, la clé change et le
résultat est recalculé. Il n'y a donc jamais de résultat périmé.

Utilisation
-----------
    valeur, depuis_cache = avec_cache(
        "testeur", [code_python, module], lambda: agent_testeur(...))

Désactivation (mesures de performance sans cache) :
    set SMAML_CACHE=0

Emplacement de la base :
    set SMAML_CACHE_DB=C:\\chemin\\vers\\cache_smaml.db
"""

import hashlib
import json
import os
import sqlite3
import threading
import time

# Version du format : l'incrémenter invalide tout le cache existant,
# par exemple après un changement de logique d'un agent.
VERSION = "1"

DOSSIER = os.path.dirname(os.path.abspath(__file__))
CHEMIN_BD = os.getenv("SMAML_CACHE_DB",
                      os.path.join(DOSSIER, "cache_smaml.db"))
ACTIF = os.getenv("SMAML_CACHE", "1").lower() not in ("0", "false", "non")

_verrou = threading.Lock()
_statistiques = {"lectures": 0, "succes": 0, "ecritures": 0,
                 "par_categorie": {}}


def _connexion():
    cnx = sqlite3.connect(CHEMIN_BD, timeout=10)
    cnx.execute("""
        CREATE TABLE IF NOT EXISTS entrees (
            cle        TEXT PRIMARY KEY,
            categorie  TEXT NOT NULL,
            valeur     TEXT NOT NULL,
            horodatage REAL NOT NULL
        )
    """)
    return cnx


def empreinte(categorie: str, parties: list) -> str:
    """Empreinte stable du contenu des entrées."""
    serialise = json.dumps(parties, sort_keys=True, default=str,
                           ensure_ascii=False)
    brut = f"{VERSION}|{categorie}|{serialise}"
    return hashlib.sha256(brut.encode("utf-8")).hexdigest()


def lire(categorie: str, cle: str):
    """Valeur mise en cache, ou None."""
    if not ACTIF:
        return None
    _statistiques["lectures"] += 1
    try:
        with _verrou, _connexion() as cnx:
            ligne = cnx.execute(
                "SELECT valeur FROM entrees WHERE cle = ?", (cle,)
            ).fetchone()
    except sqlite3.Error:
        return None            # un cache défaillant ne bloque jamais
    if not ligne:
        return None
    try:
        valeur = json.loads(ligne[0])
    except ValueError:
        return None
    _statistiques["succes"] += 1
    stats = _statistiques["par_categorie"].setdefault(
        categorie, {"succes": 0, "calculs": 0})
    stats["succes"] += 1
    return valeur


def ecrire(categorie: str, cle: str, valeur):
    """Enregistre un résultat. Silencieux en cas d'échec."""
    if not ACTIF:
        return
    try:
        charge = json.dumps(valeur, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return                 # valeur non sérialisable : on n'en fait rien
    try:
        with _verrou, _connexion() as cnx:
            cnx.execute(
                "INSERT OR REPLACE INTO entrees "
                "(cle, categorie, valeur, horodatage) VALUES (?, ?, ?, ?)",
                (cle, categorie, charge, time.time()))
    except sqlite3.Error:
        return
    _statistiques["ecritures"] += 1


def avec_cache(categorie: str, parties: list, calcul):
    """
    Retourne (valeur, depuis_cache).
    `calcul` n'est appelé que si rien n'est en cache.
    """
    cle = empreinte(categorie, parties)
    valeur = lire(categorie, cle)
    if valeur is not None:
        return valeur, True
    valeur = calcul()
    stats = _statistiques["par_categorie"].setdefault(
        categorie, {"succes": 0, "calculs": 0})
    stats["calculs"] += 1
    ecrire(categorie, cle, valeur)
    return valeur, False


def statistiques() -> dict:
    """Bilan d'utilisation — chiffrable dans le rapport."""
    lectures = _statistiques["lectures"]
    succes = _statistiques["succes"]
    return {
        "actif": ACTIF,
        "lectures": lectures,
        "succes": succes,
        "ecritures": _statistiques["ecritures"],
        "taux_reutilisation": (succes / lectures) if lectures else 0.0,
        "par_categorie": dict(_statistiques["par_categorie"]),
    }


def resume() -> str:
    """Bilan en une ligne, à afficher en fin d'exécution."""
    s = statistiques()
    if not s["actif"]:
        return "Cache désactivé (SMAML_CACHE=0)."
    detail = ", ".join(
        f"{cat} {v['succes']}/{v['succes'] + v['calculs']}"
        for cat, v in sorted(s["par_categorie"].items()))
    return (f"Cache : {s['succes']}/{s['lectures']} réutilisation(s) "
            f"({s['taux_reutilisation'] * 100:.0f}%)"
            + (f" — {detail}" if detail else ""))


def vider(categorie: str = None) -> int:
    """Vide le cache (tout, ou une seule catégorie). Retourne le nombre."""
    try:
        with _verrou, _connexion() as cnx:
            if categorie:
                cur = cnx.execute(
                    "DELETE FROM entrees WHERE categorie = ?", (categorie,))
            else:
                cur = cnx.execute("DELETE FROM entrees")
            return cur.rowcount
    except sqlite3.Error:
        return 0


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "vider":
        print(f"{vider(sys.argv[2] if len(sys.argv) > 2 else None)} "
              f"entrée(s) supprimée(s).")
    else:
        try:
            with _connexion() as cnx:
                lignes = cnx.execute(
                    "SELECT categorie, COUNT(*), MAX(horodatage) "
                    "FROM entrees GROUP BY categorie").fetchall()
        except sqlite3.Error as e:
            print(f"Cache illisible : {e}")
            sys.exit(1)
        print(f"Base : {CHEMIN_BD}")
        if not lignes:
            print("Cache vide.")
        for categorie, nombre, dernier in lignes:
            date = time.strftime("%Y-%m-%d %H:%M",
                                 time.localtime(dernier))
            print(f"  {categorie:<14} {nombre:>4} entrée(s)  "
                  f"dernière : {date}")
        print("\nPour vider : py cache_smaml.py vider [categorie]")