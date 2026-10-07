"""
Espace de travail partagé — SMAML
==================================
Event Sourcing + CQRS, sur Redis Streams (repli automatique sur SQLite).

Principe
--------
Les agents ne se parlent pas : ils DÉPOSENT leur travail dans un espace
commun. Cette version change la façon de le stocker, pas le principe.

  • Event Sourcing — on ne stocke pas l'état, on stocke la SUITE DES
    ÉVÉNEMENTS qui l'ont produit (« le Développeur a déposé le code v2 »).
    Un événement n'est jamais modifié ni effacé. L'état courant se
    reconstruit en relisant les événements dans l'ordre.

  • CQRS — l'écriture (ajouter un événement) et la lecture (consulter
    une vue de l'état) sont séparées. La vue est maintenue au fil de
    l'eau, et peut toujours être reconstruite depuis le journal.

Ce que ça apporte
-----------------
  • Reprise après panne : un programme qui redémarre relit le journal
    et retrouve l'état exact où le travail s'était arrêté.
  • Historique complet : versions, auteurs, horodatages sont natifs.
  • Notifications : un Manager peut attendre les nouveaux dépôts au
    lieu d'interroger l'espace en boucle.
  • Bail (verrou à expiration) : un seul Manager actif à la fois sur
    un même module ; si son titulaire cesse de le renouveler, le bail
    expire et un Manager de secours peut le reprendre.
  • Signe de vie : la date du dernier événement permet à un chien de
    garde de détecter un Manager qui n'avance plus, quelle qu'en soit
    la cause.

Stockage
--------
  SMAML_STOCKAGE = auto (défaut) | redis | sqlite
  SMAML_REDIS_URL = redis://localhost:6379/0
  SMAML_STOCKAGE_SQLITE = chemin du fichier de repli

En mode « auto », Redis est utilisé s'il répond, sinon SQLite : le
système fonctionne toujours, avec ou sans serveur Redis.
"""

from __future__ import annotations

import copy
import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Iterable, Optional


# ═══ SCHÉMAS DES DÉPÔTS ══════════════════════════════════
# Chaque type de dépôt impose des champs : un dépôt incomplet est
# refusé. C'est ce qui oblige chaque agent à expliciter ce qui serait
# sinon resté implicite (hypothèses, incertitudes, dépendances).

SCHEMAS_DEPOT = {
    "analyse":              ("points_attention",),
    "plan":                 ("hypotheses_faites", "points_incertains",
                             "points_attention"),
    "module":               ("hypotheses_faites", "points_incertains",
                             "points_attention"),
    "code_python":          ("dependances", "hypotheses_faites",
                             "points_incertains", "points_attention"),
    "rapport_testeur":      ("points_attention",),
    "rapport_differentiel": ("points_attention",),
    "rapport_formel":       ("points_attention",),
    "rapport_auditeur":     ("points_attention",),
    "rapport_juge":         ("points_attention",),
    "decision":             ("points_attention",),
    # Niveau projet (phases 1 et 2, puis cohérence en phase 4)
    "reception":            ("points_attention",),
    "analyse_projet":       ("points_attention",),
    "plan_projet":          ("hypotheses_faites", "points_incertains",
                             "points_attention"),
    "coherence_projet":     ("points_attention",),
}

# Types d'événements reconnus par la vue.
DEPOT = "depot"                 # un agent dépose un résultat
INVALIDATION = "invalidation"   # un résultat devient périmé
VALEUR = "valeur"               # un champ d'état change (itération, drapeau…)
SOLLICITATION = "sollicitation" # le Manager a sollicité un agent
NOTE = "note"                   # événement libre (bascule, relais, alerte…)


class DepotIncomplet(ValueError):
    """Un dépôt ne respecte pas le schéma de son type."""


class BailPerdu(RuntimeError):
    """
    Un coordinateur tente d'écrire alors qu'il ne détient plus le bail.

    C'est le cas d'un Manager déclaré défaillant mais encore en train
    de tourner : un remplaçant a pris la main, ses écritures doivent
    être refusées, sinon deux coordinateurs agiraient en même temps.
    """


def _maintenant() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


# ═══ STOCKAGE : REDIS ════════════════════════════════════

class StockageRedis:
    """
    Journal d'événements sur Redis Streams.

    Un flux par module : smaml:flux:<projet>:<module>
    Les baux sont des clés à expiration : smaml:bail:<ressource>
    """

    nom = "redis"

    # Libération et renouvellement d'un bail : opérations atomiques,
    # n'agissant que si le titulaire est bien celui qui demande.
    _LUA_RENOUVELER = """
    if redis.call('GET', KEYS[1]) == ARGV[1] then
        return redis.call('PEXPIRE', KEYS[1], ARGV[2])
    end
    return 0
    """
    _LUA_LIBERER = """
    if redis.call('GET', KEYS[1]) == ARGV[1] then
        return redis.call('DEL', KEYS[1])
    end
    return 0
    """

    def __init__(self, client):
        self.client = client

    @staticmethod
    def _cle_flux(flux: str) -> str:
        return f"smaml:flux:{flux}"

    def ajouter(self, flux: str, evenement: dict) -> str:
        ident = self.client.xadd(self._cle_flux(flux),
                                 {"e": json.dumps(evenement, ensure_ascii=False,
                                                  default=str)})
        return ident.decode() if isinstance(ident, bytes) else ident

    def lire(self, flux: str, apres: str = "0") -> list:
        debut = "(" + apres if apres not in ("0", "-") else "-"
        sortie = []
        for ident, champs in self.client.xrange(self._cle_flux(flux), min=debut):
            ident = ident.decode() if isinstance(ident, bytes) else ident
            brut = champs.get(b"e", champs.get("e"))
            brut = brut.decode() if isinstance(brut, bytes) else brut
            evenement = json.loads(brut)
            evenement["id"] = ident
            sortie.append(evenement)
        return sortie

    def attendre(self, flux: str, apres: str, delai_s: float) -> list:
        reponse = self.client.xread({self._cle_flux(flux): apres or "0"},
                                    block=int(delai_s * 1000))
        if not reponse:
            return []
        return self.lire(flux, apres)

    def dernier(self, flux: str) -> Optional[dict]:
        derniers = self.client.xrevrange(self._cle_flux(flux), count=1)
        if not derniers:
            return None
        ident, champs = derniers[0]
        ident = ident.decode() if isinstance(ident, bytes) else ident
        brut = champs.get(b"e", champs.get("e"))
        brut = brut.decode() if isinstance(brut, bytes) else brut
        evenement = json.loads(brut)
        evenement["id"] = ident
        return evenement

    def flux_existants(self, prefixe: str = "") -> list:
        motif = self._cle_flux(prefixe) + "*"
        return sorted(c.decode()[len("smaml:flux:"):] if isinstance(c, bytes)
                      else c[len("smaml:flux:"):]
                      for c in self.client.scan_iter(match=motif))

    # ── Baux ──
    def acquerir_bail(self, ressource: str, titulaire: str, duree_ms: int) -> bool:
        return bool(self.client.set(f"smaml:bail:{ressource}", titulaire,
                                    nx=True, px=duree_ms))

    def renouveler_bail(self, ressource: str, titulaire: str, duree_ms: int) -> bool:
        return bool(self.client.eval(self._LUA_RENOUVELER, 1,
                                     f"smaml:bail:{ressource}", titulaire, duree_ms))

    def liberer_bail(self, ressource: str, titulaire: str) -> bool:
        return bool(self.client.eval(self._LUA_LIBERER, 1,
                                     f"smaml:bail:{ressource}", titulaire))

    def titulaire_bail(self, ressource: str) -> Optional[str]:
        valeur = self.client.get(f"smaml:bail:{ressource}")
        if valeur is None:
            return None
        return valeur.decode() if isinstance(valeur, bytes) else valeur


# ═══ STOCKAGE : SQLITE (REPLI SANS SERVEUR) ══════════════

class StockageSQLite:
    """
    Même journal, dans un fichier SQLite en mode WAL.

    Utilisé quand Redis n'est pas disponible : le système reste
    fonctionnel et persistant, sans aucun serveur à installer.
    """

    nom = "sqlite"

    _SCHEMA = (
        """CREATE TABLE IF NOT EXISTS evenements (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               flux TEXT NOT NULL,
               donnees TEXT NOT NULL)""",
        "CREATE INDEX IF NOT EXISTS idx_flux ON evenements(flux, id)",
        """CREATE TABLE IF NOT EXISTS baux (
               ressource TEXT PRIMARY KEY,
               titulaire TEXT NOT NULL,
               expire_a REAL NOT NULL)""",
    )

    def __init__(self, chemin: str):
        self.chemin = chemin
        self._verrou = threading.Lock()
        # Une connexion PAR FIL D'EXÉCUTION, réutilisée : ouvrir une
        # connexion à chaque opération sans la fermer fragilise SQLite
        # sous Windows, surtout au redémarrage après un arrêt brutal.
        self._local = threading.local()
        self._connexion()

    def _connexion(self):
        cx = getattr(self._local, "cx", None)
        if cx is None:
            cx = sqlite3.connect(self.chemin, timeout=30, isolation_level=None)
            cx.execute("PRAGMA journal_mode=WAL")
            cx.execute("PRAGMA synchronous=NORMAL")
            for instruction in self._SCHEMA:
                cx.execute(instruction)
            self._local.cx = cx
        return cx

    def _executer(self, operation):
        """
        Exécute une opération ; si le schéma paraît absent (base en cours
        de récupération après un arrêt brutal), il est réaffirmé et
        l'opération retentée une fois.
        """
        try:
            return operation(self._connexion())
        except sqlite3.OperationalError as erreur:
            if "no such table" not in str(erreur):
                raise
            cx = self._connexion()
            for instruction in self._SCHEMA:
                cx.execute(instruction)
            return operation(cx)

    def ajouter(self, flux: str, evenement: dict) -> str:
        donnees = json.dumps(evenement, ensure_ascii=False, default=str)
        with self._verrou:
            return str(self._executer(lambda cx: cx.execute(
                "INSERT INTO evenements(flux, donnees) VALUES (?, ?)",
                (flux, donnees)).lastrowid))

    def lire(self, flux: str, apres: str = "0") -> list:
        lignes = self._executer(lambda cx: cx.execute(
            "SELECT id, donnees FROM evenements WHERE flux = ? AND id > ? "
            "ORDER BY id", (flux, int(apres or 0))).fetchall())
        sortie = []
        for ident, brut in lignes:
            evenement = json.loads(brut)
            evenement["id"] = str(ident)
            sortie.append(evenement)
        return sortie

    def attendre(self, flux: str, apres: str, delai_s: float) -> list:
        limite = time.monotonic() + delai_s
        while True:
            nouveaux = self.lire(flux, apres)
            if nouveaux or time.monotonic() >= limite:
                return nouveaux
            time.sleep(0.1)

    def dernier(self, flux: str) -> Optional[dict]:
        ligne = self._executer(lambda cx: cx.execute(
            "SELECT id, donnees FROM evenements WHERE flux = ? "
            "ORDER BY id DESC LIMIT 1", (flux,)).fetchone())
        if not ligne:
            return None
        evenement = json.loads(ligne[1])
        evenement["id"] = str(ligne[0])
        return evenement

    def flux_existants(self, prefixe: str = "") -> list:
        lignes = self._executer(lambda cx: cx.execute(
            "SELECT DISTINCT flux FROM evenements WHERE flux LIKE ? "
            "ORDER BY flux", (prefixe + "%",)).fetchall())
        return [l[0] for l in lignes]

    # ── Baux ──
    def acquerir_bail(self, ressource: str, titulaire: str, duree_ms: int) -> bool:
        def operation(cx):
            maintenant = time.time()
            cx.execute("BEGIN IMMEDIATE")
            try:
                ligne = cx.execute("SELECT expire_a FROM baux WHERE ressource = ?",
                                   (ressource,)).fetchone()
                if ligne and ligne[0] > maintenant:
                    cx.execute("COMMIT")
                    return False
                cx.execute("INSERT OR REPLACE INTO baux VALUES (?, ?, ?)",
                           (ressource, titulaire, maintenant + duree_ms / 1000))
                cx.execute("COMMIT")
                return True
            except BaseException:
                cx.execute("ROLLBACK")
                raise
        with self._verrou:
            return self._executer(operation)

    def renouveler_bail(self, ressource: str, titulaire: str, duree_ms: int) -> bool:
        with self._verrou:
            return self._executer(lambda cx: cx.execute(
                "UPDATE baux SET expire_a = ? WHERE ressource = ? "
                "AND titulaire = ? AND expire_a > ?",
                (time.time() + duree_ms / 1000, ressource, titulaire,
                 time.time())).rowcount == 1)

    def liberer_bail(self, ressource: str, titulaire: str) -> bool:
        with self._verrou:
            return self._executer(lambda cx: cx.execute(
                "DELETE FROM baux WHERE ressource = ? AND titulaire = ?",
                (ressource, titulaire)).rowcount == 1)

    def titulaire_bail(self, ressource: str) -> Optional[str]:
        ligne = self._executer(lambda cx: cx.execute(
            "SELECT titulaire, expire_a FROM baux WHERE ressource = ?",
            (ressource,)).fetchone())
        if ligne and ligne[1] > time.time():
            return ligne[0]
        return None


# ═══ CHOIX DU STOCKAGE ═══════════════════════════════════

def ouvrir_stockage(mode: str = None):
    """
    Ouvre le stockage demandé. En mode « auto », Redis s'il répond,
    sinon SQLite — le système n'a jamais besoin d'un serveur pour
    fonctionner.
    """
    mode = (mode or os.getenv("SMAML_STOCKAGE", "auto")).lower()
    chemin_sqlite = os.getenv(
        "SMAML_STOCKAGE_SQLITE",
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "espace_partage.db"))

    if mode in ("auto", "redis"):
        try:
            import redis
            client = redis.Redis.from_url(
                os.getenv("SMAML_REDIS_URL", "redis://localhost:6379/0"),
                socket_connect_timeout=1)
            client.ping()
            return StockageRedis(client)
        except Exception as erreur:
            if mode == "redis":
                raise RuntimeError(f"Redis demandé mais injoignable : {erreur}")
            # Repli sur le secours : il doit se voir, pas passer inaperçu.
            stockage = StockageSQLite(chemin_sqlite)
            stockage.repli_depuis_redis = f"{type(erreur).__name__} : {str(erreur)[:150]}"
            return stockage
    return StockageSQLite(chemin_sqlite)


# ═══ LA VUE (CÔTÉ LECTURE DU CQRS) ═══════════════════════

def vue_initiale() -> dict:
    """État de départ d'un module, avant tout événement."""
    return {
        "valeurs": {},       # valeur courante de chaque clé
        "depots": {},        # dépôt courant complet de chaque type
        "historique": {},    # toutes les versions, par type
        "journal": [],       # sollicitations du Manager
        "notes": [],         # bascules, relais, alertes
        "dernier_id": "0",
        "derniere_activite": None,
    }


def appliquer(vue: dict, evenement: dict) -> dict:
    """
    Fait évoluer la vue d'UN événement. La vue entière n'est jamais
    que l'application, dans l'ordre, de tous les événements du flux.
    """
    genre = evenement.get("type")
    cle = evenement.get("cle")

    if genre == DEPOT:
        depot = evenement["depot"]
        vue["historique"].setdefault(cle, []).append(depot)
        vue["depots"][cle] = depot
        vue["valeurs"][cle] = depot.get("contenu")
    elif genre == INVALIDATION:
        vue["depots"].pop(cle, None)
        vue["valeurs"][cle] = "" if cle == "code_python" else None
    elif genre == VALEUR:
        vue["valeurs"][cle] = evenement.get("valeur")
    elif genre == SOLLICITATION:
        vue["journal"].append(evenement.get("entree"))
    elif genre == NOTE:
        vue["notes"].append({k: v for k, v in evenement.items() if k != "id"})

    vue["dernier_id"] = evenement.get("id", vue["dernier_id"])
    vue["derniere_activite"] = evenement.get("horodatage",
                                             vue["derniere_activite"])
    return vue


# ═══ L'ESPACE DE TRAVAIL D'UN MODULE ═════════════════════

class EspaceModule:
    """
    Espace de travail d'un module : écriture par événements, lecture
    par la vue.

    S'utilise comme le dictionnaire ETAT d'avant pour la lecture
    (espace["code_python"]), mais toute écriture devient un événement
    durable — aucune donnée n'est jamais perdue ni écrasée.
    """

    def __init__(self, projet: str, module: str, stockage=None, bail=None):
        self.projet = projet
        self.module = module
        self.flux = f"{projet}:{module}"
        self.stockage = stockage or ouvrir_stockage()
        # Clôture (fencing) : si un bail est fourni, toute écriture
        # exige d'en être encore le titulaire.
        self.bail = bail
        self._verrou = threading.RLock()
        self.vue = vue_initiale()
        self.rafraichir()

    # ── Lecture ──────────────────────────────────────────
    def rafraichir(self) -> int:
        """Intègre à la vue les événements qu'elle n'a pas encore vus."""
        with self._verrou:
            nouveaux = self.stockage.lire(self.flux, self.vue["dernier_id"])
            for evenement in nouveaux:
                appliquer(self.vue, evenement)
            return len(nouveaux)

    def __getitem__(self, cle: str):
        return self.vue["valeurs"].get(cle)

    def get(self, cle: str, defaut=None):
        valeur = self.vue["valeurs"].get(cle)
        return defaut if valeur is None else valeur

    def __contains__(self, cle: str) -> bool:
        return self.vue["valeurs"].get(cle) not in (None, "")

    @property
    def depots(self) -> dict:
        return self.vue["depots"]

    @property
    def historique(self) -> dict:
        return self.vue["historique"]

    @property
    def journal(self) -> list:
        return self.vue["journal"]

    @property
    def notes(self) -> list:
        return self.vue["notes"]

    def versions(self, cle: str) -> int:
        return len(self.vue["historique"].get(cle, []))

    # ── Écriture : chaque appel ajoute un événement ──────
    def _emettre(self, evenement: dict) -> dict:
        if self.bail is not None and \
                self.bail.detenteur() != self.bail.titulaire:
            raise BailPerdu(f"{self.bail.titulaire} ne détient plus le bail "
                            f"« {self.bail.ressource} » : écriture refusée")
        if self.bail is not None:
            evenement.setdefault("coordinateur", self.bail.titulaire)
        evenement.setdefault("horodatage", _maintenant())
        evenement["module"] = self.module
        evenement["projet"] = self.projet
        with self._verrou:
            # On intègre d'abord ce que d'autres ont pu écrire, pour
            # que la version attribuée tienne compte de leurs dépôts.
            self.rafraichir()
            ident = self.stockage.ajouter(self.flux, evenement)
            evenement["id"] = ident
            appliquer(self.vue, evenement)
        return evenement

    def deposer(self, cle: str, valeur: Any, auteur: str, **champs) -> dict:
        """
        Dépose le résultat d'un agent. Le schéma du type est vérifié :
        un dépôt incomplet est refusé.
        """
        manquants = [c for c in SCHEMAS_DEPOT.get(cle, ()) if c not in champs]
        if manquants:
            raise DepotIncomplet(f"Dépôt « {cle} » incomplet : champ(s) "
                                 f"{', '.join(manquants)} manquant(s)")
        with self._verrou:
            self.rafraichir()
            depot = {
                "type": cle,
                "version": self.versions(cle) + 1,
                "iteration": self.get("iteration", 1),
                "auteur": auteur,
                "horodatage": _maintenant(),
                "contenu": copy.deepcopy(valeur),
                **{c: list(champs[c] or []) for c in champs},
            }
            self._emettre({"type": DEPOT, "cle": cle, "depot": depot})
        return depot

    def invalider(self, cle: str, raison: str = ""):
        """Rend un dépôt périmé ; l'historique, lui, le conserve."""
        self._emettre({"type": INVALIDATION, "cle": cle, "raison": raison})

    def definir(self, cle: str, valeur: Any):
        """Change un champ d'état (itération, drapeau, compteur…)."""
        self._emettre({"type": VALEUR, "cle": cle, "valeur": valeur})

    def __setitem__(self, cle: str, valeur: Any):
        self.definir(cle, valeur)

    def journaliser(self, entree: dict):
        """Consigne une sollicitation d'agent par le Manager."""
        entree = dict(entree)
        entree.setdefault("ordre", len(self.vue["journal"]) + 1)
        entree.setdefault("horodatage", _maintenant())
        self._emettre({"type": SOLLICITATION, "entree": entree})

    def noter(self, nature: str, **details):
        """Événement libre : bascule de modèle, relais de Manager, alerte."""
        self._emettre({"type": NOTE, "nature": nature, **details})

    # ── Notifications ────────────────────────────────────
    def attendre(self, delai_s: float = 5.0) -> list:
        """
        Attend de nouveaux événements, au plus `delai_s` secondes, et
        les intègre à la vue. Un Manager l'utilise pour savoir qu'un
        agent vient de déposer son travail, sans interroger en boucle.
        """
        nouveaux = self.stockage.attendre(self.flux, self.vue["dernier_id"],
                                          delai_s)
        with self._verrou:
            for evenement in nouveaux:
                if evenement["id"] != self.vue["dernier_id"]:
                    appliquer(self.vue, evenement)
        return nouveaux

    # ── Signe de vie ─────────────────────────────────────
    def secondes_depuis_activite(self) -> Optional[float]:
        """
        Temps écoulé depuis le dernier événement de ce module. Un chien
        de garde s'en sert pour détecter un coordinateur qui n'avance
        plus — quelle que soit la cause.
        """
        dernier = self.stockage.dernier(self.flux)
        if not dernier or not dernier.get("horodatage"):
            return None
        instant = datetime.fromisoformat(dernier["horodatage"])
        return (datetime.now() - instant).total_seconds()

    # ── Reconstruction ───────────────────────────────────
    def reconstruire(self) -> dict:
        """Reconstruit la vue depuis zéro, par relecture du journal."""
        with self._verrou:
            self.vue = vue_initiale()
            self.rafraichir()
            return self.vue

    def resume(self) -> dict:
        """Résumé lisible : ce qui est fait, ce qui ne l'est pas."""
        return {
            "module": self.module,
            "evenements": self.vue["dernier_id"],
            "depots": {cle: d["version"] for cle, d in self.depots.items()},
            "sollicitations": len(self.journal),
            "derniere_activite": self.vue["derniere_activite"],
        }


# ═══ BAIL : UN SEUL COORDINATEUR ACTIF ═══════════════════

class Bail:
    """
    Verrou à expiration sur une ressource (un module, un projet).

    Un coordinateur doit détenir le bail pour agir, et le renouveler
    régulièrement. S'il cesse — panne, plantage, blocage —, le bail
    expire seul, et un coordinateur de secours peut le prendre. Deux
    coordinateurs ne peuvent donc jamais agir en même temps.
    """

    def __init__(self, stockage, ressource: str, titulaire: str = None,
                 duree_ms: int = 30_000):
        self.stockage = stockage
        self.ressource = ressource
        self.titulaire = titulaire or f"coord-{uuid.uuid4().hex[:8]}"
        self.duree_ms = duree_ms

    def acquerir(self) -> bool:
        return self.stockage.acquerir_bail(self.ressource, self.titulaire,
                                           self.duree_ms)

    def renouveler(self) -> bool:
        return self.stockage.renouveler_bail(self.ressource, self.titulaire,
                                             self.duree_ms)

    def liberer(self) -> bool:
        return self.stockage.liberer_bail(self.ressource, self.titulaire)

    def detenteur(self) -> Optional[str]:
        return self.stockage.titulaire_bail(self.ressource)

    def __enter__(self):
        if not self.acquerir():
            raise RuntimeError(f"Bail « {self.ressource} » déjà détenu par "
                               f"{self.detenteur()}")
        return self

    def __exit__(self, *exc):
        self.liberer()
        return False


if __name__ == "__main__":
    stockage = ouvrir_stockage()
    print(f"Stockage actif : {stockage.nom}")
    espace = EspaceModule("demo", f"module-{uuid.uuid4().hex[:6]}", stockage)
    espace.deposer("code_python", "def f(x):\n    return x\n", "Développeur",
                   dependances=[], hypotheses_faites=["entrée entière"],
                   points_incertains=[], points_attention=[])
    espace["iteration"] = 2
    print("Vue :", espace.resume())