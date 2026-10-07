"""
Tests de l'espace de travail partagé — exécutés sur les DEUX stockages.

    py -X utf8 test_espace_partage.py

Redis est simulé en mémoire (fakeredis) : aucun serveur n'est requis
pour lancer les tests.
"""

import os
import tempfile
import threading
import time

import espace_partage as ep


def stockages():
    """Les deux implémentations, testées à l'identique."""
    import fakeredis
    yield ep.StockageRedis(fakeredis.FakeRedis())
    dossier = tempfile.mkdtemp()
    yield ep.StockageSQLite(os.path.join(dossier, "test.db"))


CHAMPS_CODE = dict(dependances=["sqlalchemy"], hypotheses_faites=["driver pymysql"],
                   points_incertains=[], points_attention=[])

resultats = []


def verifier(nom, condition):
    resultats.append((nom, bool(condition)))
    print(f"   {'[OK]' if condition else '[ECHEC]'} {nom}")


for stockage in stockages():
    print(f"\n── Stockage : {stockage.nom} ──")

    # 1. Dépôt et lecture
    e = ep.EspaceModule("p1", "get_user", stockage)
    e.deposer("code_python", "v1", "Développeur", **CHAMPS_CODE)
    verifier("un dépôt est lisible immédiatement", e["code_python"] == "v1")

    # 2. Schéma imposé
    try:
        e.deposer("code_python", "v2", "Développeur", dependances=[])
        verifier("un dépôt incomplet est refusé", False)
    except ep.DepotIncomplet:
        verifier("un dépôt incomplet est refusé", True)

    # 3. Versionnement : rien n'est écrasé
    e.deposer("code_python", "v2", "Développeur", **CHAMPS_CODE)
    verifier("la version courante est la dernière", e["code_python"] == "v2")
    verifier("les deux versions sont conservées", e.versions("code_python") == 2)
    verifier("la première version reste lisible",
             e.historique["code_python"][0]["contenu"] == "v1")

    # 4. Invalidation : la valeur disparaît, l'historique reste
    e.deposer("rapport_testeur", {"score": 1.0}, "Testeur", points_attention=[])
    e.invalider("rapport_testeur", raison="code régénéré")
    verifier("un rapport invalidé n'est plus courant", e["rapport_testeur"] is None)
    verifier("l'historique garde le rapport invalidé",
             e.versions("rapport_testeur") == 1)

    # 5. Champs d'état et journal
    e["iteration"] = 2
    e.journaliser({"agent": "Testeur", "issue": "execute"})
    verifier("un champ d'état est enregistré", e["iteration"] == 2)
    verifier("une sollicitation est journalisée", len(e.journal) == 1)

    # 6. REPRISE APRÈS PANNE : un nouvel objet relit le journal
    reprise = ep.EspaceModule("p1", "get_user", stockage)
    verifier("après « plantage », le code est retrouvé",
             reprise["code_python"] == "v2")
    verifier("après « plantage », l'itération est retrouvée",
             reprise["iteration"] == 2)
    verifier("après « plantage », l'historique est complet",
             reprise.versions("code_python") == 2)
    verifier("après « plantage », l'invalidation est respectée",
             reprise["rapport_testeur"] is None)

    # 7. Reconstruction complète = même vue
    avant = dict(reprise.vue["valeurs"])
    reprise.reconstruire()
    verifier("la reconstruction redonne exactement la même vue",
             reprise.vue["valeurs"] == avant)

    # 8. Isolation entre modules
    autre = ep.EspaceModule("p1", "login", stockage)
    verifier("un autre module ne voit pas ces dépôts", autre["code_python"] is None)

    # 9. Deux lecteurs d'un même module se synchronisent
    lecteur = ep.EspaceModule("p1", "get_user", stockage)
    e.deposer("code_python", "v3", "Développeur", **CHAMPS_CODE)
    lecteur.rafraichir()
    verifier("un second lecteur voit le nouveau dépôt", lecteur["code_python"] == "v3")

    # 10. Notification : un agent attend, un autre dépose
    attente = ep.EspaceModule("p1", "notif", stockage)
    recus = []

    def attendre():
        recus.extend(attente.attendre(delai_s=3))

    fil = threading.Thread(target=attendre)
    fil.start()
    time.sleep(0.3)
    depositaire = ep.EspaceModule("p1", "notif", stockage)
    depositaire.deposer("analyse", {"fonctions": 2}, "Analyste", points_attention=[])
    fil.join()
    verifier("le dépôt est notifié à celui qui attend",
             len(recus) == 1 and attente["analyse"] == {"fonctions": 2})

    # 11. Signe de vie
    secondes = e.secondes_depuis_activite()
    verifier("le temps depuis la dernière activité est mesurable",
             secondes is not None and secondes < 5)

    # 12. Bail : un seul coordinateur à la fois
    principal = ep.Bail(stockage, "p1:get_user", "manager-principal", duree_ms=400)
    secours = ep.Bail(stockage, "p1:get_user", "manager-secours", duree_ms=400)
    verifier("le Manager principal obtient le bail", principal.acquerir())
    verifier("le Manager de secours est refusé tant que le principal vit",
             not secours.acquerir())
    verifier("le principal peut renouveler son bail", principal.renouveler())
    verifier("le secours ne peut pas renouveler un bail qui n'est pas le sien",
             not secours.renouveler())
    time.sleep(0.6)   # le principal « tombe » : il ne renouvelle plus
    verifier("après expiration, le secours prend le bail", secours.acquerir())
    verifier("le principal revenu ne peut pas reprendre la main",
             not principal.renouveler())
    verifier("seul le titulaire peut libérer le bail",
             not principal.liberer() and secours.liberer())


# 13. SQLite : récupération quand le schéma paraît absent (cas observé
#     sous Windows au redémarrage après un arrêt brutal)
print("\n── SQLite : récupération du schéma ──")
import sqlite3
chemin = os.path.join(tempfile.mkdtemp(), "recup.db")
st = ep.StockageSQLite(chemin)
sqlite3.connect(chemin).execute("DROP TABLE evenements")
try:
    st.dernier("p:m")
    st.ajouter("p:m", {"type": "note"})
    verifier("une table manquante est recréée au lieu de faire planter la lecture",
             st.dernier("p:m") is not None)
except Exception as e:
    verifier(f"une table manquante est recréée ({e})", False)

ok = sum(1 for _, r in resultats if r)
print(f"\n{ok}/{len(resultats)} vérifications réussies")
if ok != len(resultats):
    raise SystemExit(1)