"""
Tests du cache — exécutés sur les DEUX stockages (Redis simulé, SQLite).

    py -X utf8 test_cache.py
"""

import os
import tempfile
import threading
import time

import cache_smaml as cache

resultats = []


def verifier(nom, condition):
    resultats.append((nom, bool(condition)))
    print(f"   {'[OK]' if condition else '[ECHEC]'} {nom}")


def stockages():
    import fakeredis
    yield cache.CacheRedis(fakeredis.FakeRedis())
    yield cache.CacheSQLite(os.path.join(tempfile.mkdtemp(), "cache.db"))


for st in stockages():
    print(f"\n── Stockage : {st.nom} ──")
    cache.utiliser(st)
    cache.vider()

    # 1. Cache-aside : le calcul n'est fait qu'une fois
    appels = []

    def calcul():
        appels.append(1)
        return {"code": "def f(): pass"}

    v1, cache1 = cache.avec_cache("generation", ["<?php f(); ?>"], calcul)
    v2, cache2 = cache.avec_cache("generation", ["<?php f(); ?>"], calcul)
    verifier("premier appel : calculé", not cache1 and len(appels) == 1)
    verifier("second appel : relu depuis le cache", cache2 and len(appels) == 1)
    verifier("la valeur relue est identique", v1 == v2)

    # 2. Correspondance exacte : une seule différence = recalcul
    cache.avec_cache("generation", ["<?php f() ; ?>"], calcul)
    verifier("un code différent d'un seul caractère est recalculé",
             len(appels) == 2)

    # 3. Versionnement : changer le modèle invalide le résultat
    os.environ["GROQ_MODEL"] = "modele-A"
    cle_a = cache.empreinte("generation", ["x"])
    os.environ["GROQ_MODEL"] = "modele-B"
    cle_b = cache.empreinte("generation", ["x"])
    verifier("changer de modèle change la clé", cle_a != cle_b)

    # 4. Versionnement : modifier le code de l'agent invalide le résultat
    cle_avant = cache.empreinte("testeur", ["x"])
    cache._empreinte_fichier.cache_clear()
    original = cache._empreinte_fichier
    cache._empreinte_fichier = lambda nom: "code-modifie"
    cle_apres = cache.empreinte("testeur", ["x"])
    cache._empreinte_fichier = original
    verifier("modifier le code de l'agent change la clé", cle_avant != cle_apres)

    # 5. Catégories isolées
    verifier("deux catégories ne partagent pas leurs clés",
             cache.empreinte("testeur", ["x"]) != cache.empreinte("auditeur", ["x"]))

    # 6. RUÉE SUR LE CACHE : 5 traitements simultanés, un seul calcul
    cache.vider()
    calculs_lents = []

    def calcul_lent():
        calculs_lents.append(1)
        time.sleep(0.6)          # simule un appel coûteux au LLM
        return "resultat"

    sorties = []

    def traitement():
        sorties.append(cache.avec_cache("verification_formelle", ["meme-code"],
                                        calcul_lent, attente_max_s=5))

    fils = [threading.Thread(target=traitement) for _ in range(5)]
    for f in fils:
        f.start()
    for f in fils:
        f.join()
    verifier("5 traitements simultanés : un seul calcul effectué",
             len(calculs_lents) == 1)
    verifier("les 5 traitements obtiennent le résultat",
             len(sorties) == 5 and all(v == "resultat" for v, _ in sorties))

    # 7. Vidage sélectif
    cache.avec_cache("analyse", ["a"], lambda: 1)
    cache.avec_cache("auditeur", ["b"], lambda: 2)
    supprimes = cache.vider("analyse")
    _, encore = cache.avec_cache("auditeur", ["b"], lambda: 99)
    verifier("vider une catégorie n'efface que celle-ci", supprimes >= 1 and encore)

    # 8. Statistiques
    s = cache.statistiques()
    verifier("les statistiques indiquent le stockage utilisé", s["stockage"] == st.nom)

# 9. Éviction LRU (SQLite)
print("\n── Éviction des entrées les moins utilisées (SQLite) ──")
petit = cache.CacheSQLite(os.path.join(tempfile.mkdtemp(), "petit.db"))
cache.utiliser(petit)
ancien_max = cache.MAX_ENTREES
cache.MAX_ENTREES = 3
for i in range(5):
    cache.avec_cache("analyse", [f"entree-{i}"], lambda i=i: i)
    time.sleep(0.01)
verifier("au-delà de la taille maximale, les plus anciennes sont évincées",
         petit.inventaire().get("analyse") == 3)
cache.MAX_ENTREES = ancien_max

# 10. Un cache défaillant ne bloque jamais
class CachePanne:
    nom = "panne"
    def lire(self, cle): raise RuntimeError("panne")
    def ecrire(self, cle, c): raise RuntimeError("panne")
    def verrouiller(self, cle, d): raise RuntimeError("panne")
    def deverrouiller(self, cle): raise RuntimeError("panne")

cache.utiliser(CachePanne())
valeur, _ = cache.avec_cache("analyse", ["z"], lambda: "calcule quand meme")
verifier("un cache en panne laisse le calcul se faire normalement",
         valeur == "calcule quand meme")

ok = sum(1 for _, r in resultats if r)
print(f"\n{ok}/{len(resultats)} vérifications réussies")
if ok != len(resultats):
    raise SystemExit(1)