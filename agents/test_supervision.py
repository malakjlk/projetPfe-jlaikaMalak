"""
Tests de la supervision tolérante aux pannes — sur les DEUX stockages.

    py -X utf8 test_supervision.py

Chaque scénario simule une panne différente du Manager : plantage,
blocage silencieux, échec répété. On vérifie que le système continue,
que le travail déjà fait n'est jamais refait, et qu'un Manager écarté
ne peut plus écrire.
"""

import os
import tempfile
import threading
import time
import uuid

import espace_partage as ep
from supervision import (Coordinateur, CoordinateurFixe, Disjoncteur, Etape,
                         Superviseur)

resultats = []


def verifier(nom, condition):
    resultats.append((nom, bool(condition)))
    print(f"   {'[OK]' if condition else '[ECHEC]'} {nom}")


# ── Un plan de phases minimal, à l'image de la conception ──
APPELS = []          # trace de chaque étape réellement exécutée


def etape(nom, phase, produit, prerequis=()):
    def executer(espace):
        APPELS.append(nom)
        champs = {c: [] for c in ep.SCHEMAS_DEPOT.get(produit, ("points_attention",))}
        espace.deposer(produit, f"{produit}-fait", nom, **champs)
    return Etape(nom, phase, produit, tuple(prerequis), executer)


PLAN = [
    etape("Analyste",    2, "analyse"),
    etape("Architecte",  2, "plan",                 ["analyse"]),
    etape("Développeur", 3, "code_python",          ["plan"]),
    etape("Testeur",     4, "rapport_testeur",      ["code_python"]),
    etape("Comparateur", 4, "rapport_differentiel", ["code_python"]),
    etape("Vérificateur",4, "rapport_formel",       ["code_python"]),
    etape("Auditeur",    4, "rapport_auditeur",     ["code_python"]),
    etape("Réviseur",    4, "decision",
          ["rapport_testeur", "rapport_differentiel",
           "rapport_formel", "rapport_auditeur"]),
]


class ManagerQuiReussit(Coordinateur):
    nom, niveau = "manager_principal", "llm"

    def coordonner(self, espace):
        return CoordinateurFixe(PLAN).coordonner(espace)


class ManagerQuiPlante(Coordinateur):
    """Réalise `n` étapes, puis plante (bug, quota, réseau…)."""
    niveau = "llm"

    def __init__(self, nom, n):
        self.nom, self.n = nom, n

    def coordonner(self, espace):
        for e in PLAN[:self.n]:
            if e.produit not in espace:
                e.executer(espace)
        raise RuntimeError("Error code: 429 - quota épuisé")


class ManagerQuiSeBloque(Coordinateur):
    """Réalise `n` étapes, se fige sans rien dire, puis tente d'écrire."""
    niveau = "llm"

    def __init__(self, nom, n, duree_blocage):
        self.nom, self.n, self.duree = nom, n, duree_blocage
        self.ecriture_tardive = None

    def coordonner(self, espace):
        for e in PLAN[:self.n]:
            if e.produit not in espace:
                e.executer(espace)
        time.sleep(self.duree)              # bloqué : aucun progrès
        try:                                # il se « réveille » et écrit
            espace.deposer("decision", "decision-zombie", "zombie",
                           points_attention=[])
            self.ecriture_tardive = "acceptée"
        except ep.BailPerdu:
            self.ecriture_tardive = "refusée"
        return {}


class ManagerToujoursEnPanne(Coordinateur):
    niveau = "llm"

    def __init__(self, nom):
        self.nom = nom

    def coordonner(self, espace):
        raise ConnectionError("getaddrinfo failed")


def superviseur(stockage, chaine, **options):
    reglages = dict(delai_inactivite_s=1.0, delai_total_s=20, duree_bail_ms=800,
                    periode_surveillance_s=0.1, journal=lambda *_: None)
    reglages.update(options)
    return Superviseur(stockage, chaine, **reglages)


def stockages():
    import fakeredis
    yield ep.StockageRedis(fakeredis.FakeRedis())
    yield ep.StockageSQLite(os.path.join(tempfile.mkdtemp(), "sup.db"))


for stockage in stockages():
    print(f"\n── Stockage : {stockage.nom} ──")
    fixe = CoordinateurFixe(PLAN)
    fixe.nom = "coordinateur_fixe"

    # 1. Cas normal
    APPELS.clear()
    projet = f"p-{uuid.uuid4().hex[:6]}"
    r = superviseur(stockage, [ManagerQuiReussit(), fixe]).superviser(projet, "m1")
    verifier("cas normal : le Manager principal termine seul",
             r.statut == "termine" and r.coordonne_par == "manager_principal"
             and len(r.relais) == 1)

    # 2. Le principal PLANTE après 3 étapes → le secours reprend
    APPELS.clear()
    projet = f"p-{uuid.uuid4().hex[:6]}"
    secours = ManagerQuiReussit(); secours.nom = "manager_secours"
    r = superviseur(stockage, [ManagerQuiPlante("manager_principal", 3),
                               secours, fixe]).superviser(projet, "m1")
    verifier("plantage : le Manager de secours prend le relais et termine",
             r.statut == "termine" and r.coordonne_par == "manager_secours")
    verifier("plantage : aucune étape n'a été refaite",
             len(APPELS) == len(PLAN) and len(set(APPELS)) == len(PLAN))
    verifier("plantage : la cause est consignée dans le relais",
             "429" in r.relais[0]["raison"])

    # 3. Le principal SE BLOQUE en silence → détecté par le chien de garde
    APPELS.clear()
    projet = f"p-{uuid.uuid4().hex[:6]}"
    bloque = ManagerQuiSeBloque("manager_principal", 2, duree_blocage=3.0)
    secours = ManagerQuiReussit(); secours.nom = "manager_secours"
    debut = time.monotonic()
    r = superviseur(stockage, [bloque, secours, fixe]).superviser(projet, "m1")
    verifier("blocage silencieux : détecté sans attendre la fin du blocage",
             r.coordonne_par == "manager_secours" and time.monotonic() - debut < 3.0)
    verifier("blocage silencieux : la raison est l'inactivité",
             "aucune activité" in r.relais[0]["raison"])
    time.sleep(2.5)       # le Manager bloqué se réveille et tente d'écrire
    verifier("clôture : l'écriture tardive du Manager écarté est REFUSÉE",
             bloque.ecriture_tardive == "refusée")
    vue = ep.EspaceModule(projet, "m1", stockage)
    verifier("clôture : la décision reste celle du Manager de secours",
             vue["decision"] == "decision-fait")

    # 4. Principal ET secours en panne → coordinateur fixe, sans LLM
    APPELS.clear()
    projet = f"p-{uuid.uuid4().hex[:6]}"
    r = superviseur(stockage, [ManagerQuiPlante("manager_principal", 2),
                               ManagerToujoursEnPanne("manager_secours"),
                               fixe]).superviser(projet, "m1")
    verifier("double panne : le coordinateur fixe termine le module",
             r.statut == "termine" and r.coordonne_par == "coordinateur_fixe")
    verifier("double panne : il reprend où le travail s'était arrêté",
             r.resultat["etapes_deja_faites"] == ["Analyste", "Architecte"])

    # 5. Tout échoue → validation humaine, jamais de livraison par défaut
    projet = f"p-{uuid.uuid4().hex[:6]}"
    r = superviseur(stockage, [ManagerToujoursEnPanne("manager_principal"),
                               ManagerToujoursEnPanne("manager_secours")]
                    ).superviser(projet, "m1")
    vue = ep.EspaceModule(projet, "m1", stockage)
    verifier("tout échoue : validation humaine", r.statut == "validation_humaine")
    verifier("tout échoue : aucune décision n'a été produite", vue["decision"] is None)
    verifier("tout échoue : la validation humaine est consignée dans le journal",
             any(n["nature"] == "validation_humaine" for n in vue.notes))

    # 6. Disjoncteur : après 3 échecs, le principal n'est plus sollicité
    sup = superviseur(stockage, [ManagerToujoursEnPanne("manager_principal"), fixe],
                      seuil_disjoncteur=3, delai_disjoncteur_s=60)
    for i in range(3):
        sup.superviser(f"p-{uuid.uuid4().hex[:6]}", f"m{i}")
    r = sup.superviser(f"p-{uuid.uuid4().hex[:6]}", "m4")
    verifier("disjoncteur : au 4e module, le principal est ignoré d'office",
             r.relais[0]["issue"] == "ignore" and r.coordonne_par == "coordinateur_fixe")

# 7. Disjoncteur : réouverture après le délai
d = Disjoncteur(seuil=2, delai_s=0.3)
d.echec(); d.echec()
ouvert = not d.autorise()
time.sleep(0.4)
semi = d.etat == Disjoncteur.SEMI_OUVERT and d.autorise()
d.succes()
verifier("disjoncteur : ouvert, puis semi-ouvert après délai, puis refermé",
         ouvert and semi and d.etat == Disjoncteur.FERME)

ok = sum(1 for _, r in resultats if r)
print(f"\n{ok}/{len(resultats)} vérifications réussies")
if ok != len(resultats):
    raise SystemExit(1)