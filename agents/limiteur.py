"""
Limiteur de débit partagé — SMAML
==================================
Plusieurs projets migrés en parallèle, ce sont plusieurs processus qui
appellent les mêmes modèles. Chacun respecterait le quota s'il était
seul ; ensemble, ils le dépasseraient en quelques minutes.

Le limiteur est un SEAU À JETONS (token bucket) PARTAGÉ entre tous les
processus, conservé dans le stockage commun (Redis, ou SQLite) :
  • chaque modèle a son seau, de capacité « appels par minute » ;
  • chaque appel prend un jeton ; le seau se remplit à vitesse constante ;
  • seau vide → l'appel attend son tour, au lieu d'être refusé par le
    fournisseur (erreur 429) et de déclencher un basculement inutile.

Réglages
--------
  SMAML_LIMITE_RPM=30          appels par minute et par modèle
  SMAML_LIMITE_RPM_<MODELE>    limite propre à un modèle, par ex.
                               SMAML_LIMITE_RPM_GEMINI_3_6_FLASH=10
  SMAML_LIMITEUR=0             désactive le limiteur

Un limiteur en panne ne bloque jamais un appel : il le laisse passer.
"""

from __future__ import annotations

import os
import re
import threading
import time

# Seau à jetons, atomique côté Redis : retourne le temps d'attente (en
# millisecondes) avant de pouvoir prendre un jeton, 0 s'il est pris.
_LUA = """
local capacite = tonumber(ARGV[1])
local debit = tonumber(ARGV[2])
local maintenant = tonumber(ARGV[3])
local etat = redis.call('HMGET', KEYS[1], 'jetons', 'instant')
local jetons = tonumber(etat[1]) or capacite
local instant = tonumber(etat[2]) or maintenant
jetons = math.min(capacite, jetons + (maintenant - instant) * debit)
local attente = 0
if jetons >= 1 then
  jetons = jetons - 1
else
  attente = math.ceil((1 - jetons) / debit * 1000)
end
redis.call('HSET', KEYS[1], 'jetons', jetons, 'instant', maintenant)
redis.call('EXPIRE', KEYS[1], 3600)
return attente
"""


def limite_rpm(cle: str) -> float:
    """Appels par minute pour ce modèle : réglage propre, sinon réglage commun."""
    propre = "SMAML_LIMITE_RPM_" + re.sub(r"[^A-Z0-9]", "_", cle.split(":", 1)[-1].upper())
    return float(os.getenv(propre) or os.getenv("SMAML_LIMITE_RPM", "30"))


class Limiteur:
    def __init__(self, stockage=None):
        self._stockage = stockage
        self._verrou = threading.Lock()

    def _stock(self):
        if self._stockage is None:
            from espace_partage import ouvrir_stockage
            self._stockage = ouvrir_stockage()
        return self._stockage

    def _prendre(self, cle: str, capacite: float, debit: float) -> float:
        """Essaie de prendre un jeton ; retourne l'attente nécessaire en secondes."""
        stock = self._stock()
        maintenant = time.time()
        if stock.nom == "redis":
            attente_ms = stock.client.eval(_LUA, 1, f"smaml:debit:{cle}",
                                           capacite, debit, maintenant)
            return int(attente_ms) / 1000
        # SQLite : la même logique, dans une transaction exclusive.
        def operation(cx):
            cx.execute("CREATE TABLE IF NOT EXISTS debit (cle TEXT PRIMARY KEY, "
                       "jetons REAL, instant REAL)")
            cx.execute("BEGIN IMMEDIATE")
            try:
                ligne = cx.execute("SELECT jetons, instant FROM debit WHERE cle = ?",
                                   (cle,)).fetchone()
                jetons, instant = ligne if ligne else (capacite, maintenant)
                jetons = min(capacite, jetons + (maintenant - instant) * debit)
                attente = 0.0
                if jetons >= 1:
                    jetons -= 1
                else:
                    attente = (1 - jetons) / debit
                cx.execute("INSERT OR REPLACE INTO debit VALUES (?, ?, ?)",
                           (cle, jetons, maintenant))
                cx.execute("COMMIT")
                return attente
            except BaseException:
                cx.execute("ROLLBACK")
                raise
        with self._verrou:
            return stock._executer(operation)

    def attendre(self, cle: str, delai_max_s: float = 300) -> float:
        """Bloque jusqu'à obtenir un jeton ; retourne le temps attendu."""
        if os.getenv("SMAML_LIMITEUR", "1").lower() in ("0", "false", "non"):
            return 0.0
        rpm = limite_rpm(cle)
        if rpm <= 0:
            return 0.0
        capacite, debit = max(1.0, rpm), rpm / 60.0
        attendu, limite = 0.0, time.monotonic() + delai_max_s
        while time.monotonic() < limite:
            try:
                attente = self._prendre(cle, capacite, debit)
            except Exception:
                return attendu          # limiteur en panne : on ne bloque jamais
            if attente <= 0:
                return attendu
            time.sleep(min(attente, 5.0))
            attendu += min(attente, 5.0)
        return attendu


LIMITEUR = Limiteur()