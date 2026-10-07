"""
Cache SMAML — patron cache-aside, sur Redis (repli automatique sur SQLite)
==========================================================================
Évite de refaire un travail déjà fait : une même analyse, une même
génération ou une même vérification portant exactement sur les mêmes
entrées est relue au lieu d'être recalculée.

Patron : cache-aside
--------------------
L'application gère le cache elle-même :
    1. chercher le résultat dans le cache ;
    2. s'il est absent, le calculer (LLM, Z3, audit…) ;
    3. le ranger dans le cache, puis le renvoyer.
C'est le patron adapté ici, parce que les résultats mis en cache sont
DÉRIVÉS et IMMUABLES pour une entrée donnée : on ne les modifie jamais,
on les recalcule si l'entrée change. Les patrons write-through et
write-behind, conçus pour garder un cache cohérent avec une base que
l'on modifie, n'ont donc pas d'objet.

Les deux faiblesses connues du cache-aside, et leur traitement
-------------------------------------------------------------
  1. Données périmées — si l'on modifie un agent, un prompt ou le
     modèle, un ancien résultat ne doit plus être resservi. La clé
     contient donc, en plus du contenu des entrées :
       • l'empreinte du CODE SOURCE de l'agent concerné,
       • le nom du modèle utilisé,
       • une version globale, modifiable à la main.
     Toute modification de l'un d'eux change la clé : le résultat est
     recalculé, sans avoir à vider le cache.

  2. Ruée sur le cache (cache stampede) — si plusieurs traitements
     parallèles cherchent le même résultat absent, un seul le calcule
     (verrou par clé) ; les autres attendent et relisent son résultat.

Correspondance EXACTE uniquement
--------------------------------
Un cache « sémantique », qui réutiliserait le résultat d'un code
ressemblant, est volontairement écarté : dans un système de
vérification, deux PHP presque identiques peuvent différer sur une
garde de sécurité. Seule une entrée strictement identique est
réutilisée.

Réglages
--------
  SMAML_CACHE=0              désactive le cache (mesures du benchmark)
  SMAML_STOCKAGE=auto        auto | redis | sqlite (partagé avec l'espace)
  SMAML_REDIS_URL            redis://localhost:6379/0
  SMAML_CACHE_DB             fichier SQLite de repli
  SMAML_CACHE_TTL_JOURS=30   durée de vie d'une entrée
  SMAML_CACHE_MAX=5000       nombre maximal d'entrées (repli SQLite)
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import sqlite3
import threading
import time

# Version globale : l'incrémenter invalide tout le cache existant.
VERSION = "2"

DOSSIER = os.path.dirname(os.path.abspath(__file__))
CHEMIN_BD = os.getenv("SMAML_CACHE_DB", os.path.join(DOSSIER, "cache_smaml.db"))
ACTIF = os.getenv("SMAML_CACHE", "1").lower() not in ("0", "false", "non")
TTL_S = int(float(os.getenv("SMAML_CACHE_TTL_JOURS", "30")) * 86400)
MAX_ENTREES = int(os.getenv("SMAML_CACHE_MAX", "5000"))

# Fichiers source dont dépend chaque catégorie : une modification de
# l'un d'eux invalide automatiquement les résultats correspondants.
SOURCES_PAR_CATEGORIE = {
    "analyse":               ["agent_analyste.py"],
    "generation":            ["agent_developpeur.py"],
    "testeur":               ["agent_testeur.py"],
    "differentiel":          ["agent_testeur_differentiel.py", "doublures_bdd.py"],
    "verification_formelle": ["agent_verification_formelle.py"],
    "auditeur":              ["agent_auditeur.py"],
    "juge":                  ["agent_juge.py"],
    "entrees_ia":            ["entrees_ia.py"],
}

# Variables désignant le modèle utilisé par chaque catégorie.
MODELES_PAR_CATEGORIE = {
    "generation": ["GROQ_MODEL", "SMAML_MODELE_SECOURS"],
    "juge":       ["SMAML_MODELE_JUGE"],
    "entrees_ia": ["SMAML_MODELE_ENTREES", "SMAML_MODELE_JUGE"],
}

_statistiques = {"lectures": 0, "succes": 0, "ecritures": 0,
                 "attentes": 0, "par_categorie": {}}
_verrou_stats = threading.Lock()


# ═══ VERSIONNEMENT DES CLÉS ══════════════════════════════

@functools.lru_cache(maxsize=None)
def _empreinte_fichier(nom: str) -> str:
    chemin = os.path.join(DOSSIER, nom)
    try:
        with open(chemin, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except OSError:
        return "absent"


def contexte_version(categorie: str) -> dict:
    """Tout ce qui, en changeant, doit rendre un résultat périmé."""
    return {
        "version": VERSION,
        "sources": {nom: _empreinte_fichier(nom)
                    for nom in SOURCES_PAR_CATEGORIE.get(categorie, [])},
        "modeles": {var: os.getenv(var, "")
                    for var in MODELES_PAR_CATEGORIE.get(categorie, [])},
    }


def empreinte(categorie: str, parties: list) -> str:
    """
    Clé du cache : empreinte du contenu des entrées ET du contexte de
    version (code de l'agent, modèle, version globale).
    """
    serialise = json.dumps({"entrees": parties,
                            "contexte": contexte_version(categorie)},
                           sort_keys=True, default=str, ensure_ascii=False)
    brut = f"{categorie}|{serialise}"
    return f"{categorie}:{hashlib.sha256(brut.encode('utf-8')).hexdigest()}"


# ═══ STOCKAGE : REDIS ════════════════════════════════════

class CacheRedis:
    """
    Entrées à durée de vie (SETEX). Quand la mémoire est pleine, c'est
    Redis lui-même qui évince les entrées les moins utilisées.

    Politique d'éviction : volatile-lru, et surtout PAS allkeys-lru.
    Le journal d'événements de l'espace partagé vit dans le même
    Redis, sans durée de vie : volatile-lru n'évince que les clés qui
    en ont une — les entrées du cache —, et ne touche jamais au
    journal. allkeys-lru pourrait, elle, effacer de l'historique.
    """

    nom = "redis"
    PREFIXE = "smaml:cache:"

    def __init__(self, client):
        self.client = client

    def lire(self, cle: str):
        brut = self.client.get(self.PREFIXE + cle)
        if brut is None:
            return None
        return brut.decode() if isinstance(brut, bytes) else brut

    def ecrire(self, cle: str, charge: str):
        self.client.setex(self.PREFIXE + cle, TTL_S, charge)

    def verrouiller(self, cle: str, duree_ms: int) -> bool:
        return bool(self.client.set(self.PREFIXE + "verrou:" + cle, "1",
                                    nx=True, px=duree_ms))

    def deverrouiller(self, cle: str):
        self.client.delete(self.PREFIXE + "verrou:" + cle)

    def vider(self, categorie: str = None) -> int:
        motif = self.PREFIXE + (f"{categorie}:*" if categorie else "*")
        cles = [c for c in self.client.scan_iter(match=motif)
                if b":verrou:" not in (c if isinstance(c, bytes) else c.encode())]
        return self.client.delete(*cles) if cles else 0

    def inventaire(self) -> dict:
        compte = {}
        for c in self.client.scan_iter(match=self.PREFIXE + "*"):
            c = c.decode() if isinstance(c, bytes) else c
            if ":verrou:" in c:
                continue
            categorie = c[len(self.PREFIXE):].split(":", 1)[0]
            compte[categorie] = compte.get(categorie, 0) + 1
        return compte


# ═══ STOCKAGE : SQLITE (REPLI SANS SERVEUR) ══════════════

class CacheSQLite:
    """
    Même cache dans un fichier SQLite : durée de vie, et éviction des
    entrées les moins récemment utilisées au-delà d'une taille maximale.
    """

    nom = "sqlite"

    def __init__(self, chemin: str):
        self.chemin = chemin
        self._verrou = threading.Lock()
        self._verrous_cles = {}
        with self._connexion() as cx:
            cx.execute("""CREATE TABLE IF NOT EXISTS cache (
                            cle TEXT PRIMARY KEY,
                            categorie TEXT,
                            valeur TEXT,
                            cree_a REAL,
                            expire_a REAL,
                            utilise_a REAL)""")
            cx.execute("CREATE INDEX IF NOT EXISTS idx_utilise ON cache(utilise_a)")
            cx.execute("""CREATE TABLE IF NOT EXISTS verrous (
                            cle TEXT PRIMARY KEY, expire_a REAL)""")

    def _connexion(self):
        cx = sqlite3.connect(self.chemin, timeout=30, isolation_level=None)
        cx.execute("PRAGMA journal_mode=WAL")
        return cx

    def lire(self, cle: str):
        maintenant = time.time()
        with self._verrou, self._connexion() as cx:
            ligne = cx.execute("SELECT valeur, expire_a FROM cache WHERE cle = ?",
                               (cle,)).fetchone()
            if not ligne:
                return None
            if ligne[1] < maintenant:
                cx.execute("DELETE FROM cache WHERE cle = ?", (cle,))
                return None
            cx.execute("UPDATE cache SET utilise_a = ? WHERE cle = ?",
                       (maintenant, cle))
            return ligne[0]

    def ecrire(self, cle: str, charge: str):
        maintenant = time.time()
        categorie = cle.split(":", 1)[0]
        with self._verrou, self._connexion() as cx:
            cx.execute("INSERT OR REPLACE INTO cache VALUES (?, ?, ?, ?, ?, ?)",
                       (cle, categorie, charge, maintenant,
                        maintenant + TTL_S, maintenant))
            # Éviction LRU : au-delà de la taille maximale, on retire
            # les entrées les moins récemment utilisées.
            total = cx.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            if total > MAX_ENTREES:
                cx.execute("DELETE FROM cache WHERE cle IN (SELECT cle FROM cache "
                           "ORDER BY utilise_a LIMIT ?)", (total - MAX_ENTREES,))

    def verrouiller(self, cle: str, duree_ms: int) -> bool:
        maintenant = time.time()
        with self._verrou, self._connexion() as cx:
            cx.execute("BEGIN IMMEDIATE")
            ligne = cx.execute("SELECT expire_a FROM verrous WHERE cle = ?",
                               (cle,)).fetchone()
            if ligne and ligne[0] > maintenant:
                cx.execute("COMMIT")
                return False
            cx.execute("INSERT OR REPLACE INTO verrous VALUES (?, ?)",
                       (cle, maintenant + duree_ms / 1000))
            cx.execute("COMMIT")
            return True

    def deverrouiller(self, cle: str):
        with self._verrou, self._connexion() as cx:
            cx.execute("DELETE FROM verrous WHERE cle = ?", (cle,))

    def vider(self, categorie: str = None) -> int:
        with self._verrou, self._connexion() as cx:
            if categorie:
                curseur = cx.execute("DELETE FROM cache WHERE categorie = ?",
                                     (categorie,))
            else:
                curseur = cx.execute("DELETE FROM cache")
            return curseur.rowcount

    def inventaire(self) -> dict:
        with self._connexion() as cx:
            lignes = cx.execute("SELECT categorie, COUNT(*) FROM cache "
                                "GROUP BY categorie").fetchall()
        return {c: n for c, n in lignes}


# ═══ CHOIX DU STOCKAGE ═══════════════════════════════════

_stockage = None
_verrou_init = threading.Lock()


def stockage():
    """Redis s'il répond, sinon SQLite — le cache ne bloque jamais."""
    global _stockage
    if _stockage is not None:
        return _stockage
    with _verrou_init:
        if _stockage is not None:
            return _stockage
        mode = os.getenv("SMAML_STOCKAGE", "auto").lower()
        if mode in ("auto", "redis"):
            try:
                import redis
                client = redis.Redis.from_url(
                    os.getenv("SMAML_REDIS_URL", "redis://localhost:6379/0"),
                    socket_connect_timeout=1)
                client.ping()
                _stockage = CacheRedis(client)
                return _stockage
            except Exception:
                if mode == "redis":
                    raise
        _stockage = CacheSQLite(CHEMIN_BD)
        return _stockage


def utiliser(stockage_force):
    """Impose un stockage (tests)."""
    global _stockage
    _stockage = stockage_force


# ═══ INTERFACE (identique à la version précédente) ═══════

def _compter(categorie: str, champ: str):
    with _verrou_stats:
        stats = _statistiques["par_categorie"].setdefault(
            categorie, {"succes": 0, "calculs": 0})
        stats[champ] += 1


def lire(categorie: str, cle: str):
    """Valeur mise en cache, ou None. Un cache défaillant ne bloque jamais."""
    if not ACTIF:
        return None
    with _verrou_stats:
        _statistiques["lectures"] += 1
    try:
        brut = stockage().lire(cle)
    except Exception:
        return None
    if brut is None:
        return None
    try:
        valeur = json.loads(brut)
    except ValueError:
        return None
    with _verrou_stats:
        _statistiques["succes"] += 1
    _compter(categorie, "succes")
    return valeur


def ecrire(categorie: str, cle: str, valeur):
    """Enregistre un résultat. Silencieux en cas d'échec."""
    if not ACTIF:
        return
    try:
        charge = json.dumps(valeur, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return
    try:
        stockage().ecrire(cle, charge)
    except Exception:
        return
    with _verrou_stats:
        _statistiques["ecritures"] += 1


def avec_cache(categorie: str, parties: list, calcul,
               attente_max_s: float = 600.0):
    """
    Cache-aside protégé contre la ruée. Retourne (valeur, depuis_cache).

    Si le résultat est absent, UN SEUL appelant le calcule (verrou par
    clé). Les autres attendent qu'il apparaisse dans le cache, au lieu
    de relancer chacun le même appel coûteux au LLM.
    """
    cle = empreinte(categorie, parties)
    valeur = lire(categorie, cle)
    if valeur is not None:
        return valeur, True
    if not ACTIF:
        return calcul(), False

    duree_verrou_ms = int(attente_max_s * 1000)
    try:
        obtenu = stockage().verrouiller(cle, duree_verrou_ms)
    except Exception:
        obtenu = True        # cache défaillant : on calcule, simplement

    if not obtenu:
        # Un autre traitement calcule déjà ce résultat : on l'attend.
        with _verrou_stats:
            _statistiques["attentes"] += 1
        limite = time.monotonic() + attente_max_s
        while time.monotonic() < limite:
            time.sleep(0.2)
            valeur = lire(categorie, cle)
            if valeur is not None:
                return valeur, True
        # Le calculateur a échoué ou disparu : on calcule soi-même.

    try:
        valeur = calcul()
        _compter(categorie, "calculs")
        ecrire(categorie, cle, valeur)
        return valeur, False
    finally:
        try:
            stockage().deverrouiller(cle)
        except Exception:
            pass


def statistiques() -> dict:
    """Bilan d'utilisation — chiffrable dans le rapport."""
    with _verrou_stats:
        lectures = _statistiques["lectures"]
        succes = _statistiques["succes"]
        par_categorie = {k: dict(v) for k, v in
                         _statistiques["par_categorie"].items()}
        attentes = _statistiques["attentes"]
        ecritures = _statistiques["ecritures"]
    try:
        nom_stockage = stockage().nom
    except Exception:
        nom_stockage = "indisponible"
    return {
        "actif": ACTIF,
        "stockage": nom_stockage,
        "lectures": lectures,
        "succes": succes,
        "ecritures": ecritures,
        "ruees_evitees": attentes,
        "taux_reutilisation": (succes / lectures) if lectures else 0.0,
        "par_categorie": par_categorie,
    }


def resume() -> str:
    """Bilan en une ligne, à afficher en fin d'exécution."""
    s = statistiques()
    if not s["actif"]:
        return "Cache désactivé (SMAML_CACHE=0)."
    detail = ", ".join(f"{cat} {v['succes']}/{v['succes'] + v['calculs']}"
                       for cat, v in sorted(s["par_categorie"].items()))
    return (f"Cache ({s['stockage']}) : {s['succes']}/{s['lectures']} "
            f"réutilisation(s) ({s['taux_reutilisation'] * 100:.0f}%)"
            + (f" — {detail}" if detail else ""))


def vider(categorie: str = None) -> int:
    """Vide le cache (tout, ou une seule catégorie)."""
    try:
        return stockage().vider(categorie)
    except Exception:
        return 0


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "vider":
        print(f"{vider(sys.argv[2] if len(sys.argv) > 2 else None)} "
              f"entrée(s) supprimée(s).")
    else:
        print(f"Stockage : {stockage().nom}")
        inventaire = stockage().inventaire()
        if not inventaire:
            print("Cache vide.")
        for categorie, nombre in sorted(inventaire.items()):
            print(f"  {categorie:<22} {nombre:>5} entrée(s)")
        print("\nPour vider : py cache_smaml.py vider [categorie]")