"""
Supervision tolérante aux pannes — SMAML
=========================================
Le Manager coordonne tout. S'il tombe en panne — LLM injoignable, bug,
blocage, boucle sans fin, plantage —, le système ne doit pas s'arrêter.

Cinq mécanismes, indépendants de la CAUSE de la panne
-----------------------------------------------------
  1. DÉTECTER — un chien de garde surveille le PROGRÈS du coordinateur
     dans l'espace partagé. Aucun nouvel événement pendant un délai
     donné : il est déclaré défaillant. On ne cherche pas pourquoi.

  2. ISOLER — un coordinateur n'agit qu'en détenant le BAIL du module.
     Déclaré défaillant, il le perd : ses écritures sont refusées
     (clôture), même s'il continue de tourner.

  3. REPRENDRE — l'espace partagé est un journal d'événements
     persistant. Le remplaçant relit l'état exact et ne refait que ce
     qui manque.

  4. RELAYER — une chaîne de coordinateurs, du plus capable au plus
     sûr : Manager principal → Manager de secours (autre LLM) →
     coordinateur fixe (sans LLM) → validation humaine.

  5. NE PAS S'ACHARNER — un disjoncteur cesse de solliciter un
     coordinateur qui échoue à répétition, et passe directement au
     suivant pendant un temps.

Ce qui ne change jamais
-----------------------
Quel que soit le coordinateur, les agents, les vérifications et le
Réviseur sont les mêmes. Seul change QUI organise le travail ; le
rapport indique lequel.
"""

from __future__ import annotations

import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Callable, Optional

from espace_partage import Bail, BailPerdu, EspaceModule


# ═══ DISJONCTEUR ═════════════════════════════════════════

class Disjoncteur:
    """
    Après `seuil` échecs consécutifs, le disjoncteur s'ouvre : le
    coordinateur n'est plus sollicité pendant `delai_s`. Ensuite, un
    essai est autorisé (semi-ouvert) : réussi, il se referme ; raté,
    il se rouvre.
    """

    FERME, OUVERT, SEMI_OUVERT = "fermé", "ouvert", "semi-ouvert"

    def __init__(self, seuil: int = 3, delai_s: float = 600.0):
        self.seuil = seuil
        self.delai_s = delai_s
        self.echecs_consecutifs = 0
        self.ouvert_depuis: Optional[float] = None
        self._verrou = threading.Lock()

    @property
    def etat(self) -> str:
        with self._verrou:
            if self.ouvert_depuis is None:
                return self.FERME
            if time.monotonic() - self.ouvert_depuis >= self.delai_s:
                return self.SEMI_OUVERT
            return self.OUVERT

    def autorise(self) -> bool:
        return self.etat != self.OUVERT

    def succes(self):
        with self._verrou:
            self.echecs_consecutifs = 0
            self.ouvert_depuis = None

    def echec(self):
        with self._verrou:
            self.echecs_consecutifs += 1
            if self.echecs_consecutifs >= self.seuil:
                self.ouvert_depuis = time.monotonic()


# ═══ COORDINATEURS ═══════════════════════════════════════

class Coordinateur:
    """
    Un coordinateur organise le travail d'un module. Il reçoit
    l'espace partagé du module — lié à son bail — et doit le mener
    jusqu'à une décision.

    À surcharger : `coordonner(espace)`.
    """

    nom = "coordinateur"
    niveau = "inconnu"

    def coordonner(self, espace: EspaceModule) -> dict:
        raise NotImplementedError


@dataclass
class Etape:
    """
    Étape d'un plan de phases : ce qu'elle produit, ce qu'elle exige,
    et la fonction qui la réalise.

    `executer(espace)` doit déposer `produit` dans l'espace.
    """
    nom: str
    phase: int
    produit: str
    prerequis: tuple = ()
    executer: Callable = None


class CoordinateurFixe(Coordinateur):
    """
    Coordinateur de dernier recours, sans LLM.

    Il suit simplement l'ordre des phases, et ne réalise que les
    étapes dont le produit manque encore dans l'espace partagé. Il
    reprend donc exactement où le coordinateur précédent s'est arrêté,
    sans refaire le travail déjà déposé.
    """

    nom = "coordinateur_fixe"
    niveau = "fixe"

    def __init__(self, plan: list):
        self.plan = sorted(plan, key=lambda e: e.phase)

    def coordonner(self, espace: EspaceModule) -> dict:
        espace.rafraichir()
        realisees, sautees = [], []
        for etape in self.plan:
            if etape.produit in espace:
                sautees.append(etape.nom)        # déjà fait avant la panne
                continue
            manquants = [p for p in etape.prerequis if p not in espace]
            if manquants:
                raise RuntimeError(f"étape « {etape.nom} » impossible : "
                                   f"prérequis manquant(s) {manquants}")
            etape.executer(espace)
            espace.rafraichir()
            realisees.append(etape.nom)
        return {"etapes_realisees": realisees, "etapes_deja_faites": sautees}


# ═══ RÉSULTAT DE LA SUPERVISION ══════════════════════════

@dataclass
class ResultatSupervision:
    statut: str                          # « termine » ou « validation_humaine »
    coordonne_par: Optional[str] = None
    niveau: Optional[str] = None
    resultat: Optional[dict] = None
    relais: list = field(default_factory=list)

    def en_dict(self) -> dict:
        return {"statut": self.statut, "coordonne_par": self.coordonne_par,
                "niveau": self.niveau, "resultat": self.resultat,
                "relais": self.relais}


# ═══ LE SUPERVISEUR ══════════════════════════════════════

class Superviseur:
    """
    Fait coordonner un module par une chaîne de coordinateurs, sous la
    surveillance d'un chien de garde.

      delai_inactivite_s : sans nouvel événement pendant ce délai, le
                           coordinateur est déclaré défaillant
      delai_total_s      : durée maximale accordée à un coordinateur
      duree_bail_ms      : durée du bail, renouvelé en continu tant que
                           le coordinateur est jugé vivant
    """

    def __init__(self, stockage, chaine: list,
                 delai_inactivite_s: float = 300.0,
                 delai_total_s: float = 1800.0,
                 duree_bail_ms: int = 30_000,
                 periode_surveillance_s: float = 1.0,
                 seuil_disjoncteur: int = 3,
                 delai_disjoncteur_s: float = 600.0,
                 journal: Callable = print):
        self.stockage = stockage
        self.chaine = chaine
        self.delai_inactivite_s = delai_inactivite_s
        self.delai_total_s = delai_total_s
        self.duree_bail_ms = duree_bail_ms
        self.periode = periode_surveillance_s
        self.journal = journal
        self.disjoncteurs = {c.nom: Disjoncteur(seuil_disjoncteur,
                                                delai_disjoncteur_s)
                             for c in chaine}

    # ─────────────────────────────────────────────────────
    def superviser(self, projet: str, module: str) -> ResultatSupervision:
        ressource = f"{projet}:{module}"
        relais = []
        observateur = EspaceModule(projet, module, self.stockage)

        for rang, coordinateur in enumerate(self.chaine):
            disjoncteur = self.disjoncteurs[coordinateur.nom]
            dernier_recours = rang == len(self.chaine) - 1
            # Le dernier coordinateur de la chaîne est toujours essayé :
            # le sauter reviendrait à escalader sans avoir rien tenté.
            if not dernier_recours and not disjoncteur.autorise():
                relais.append({"coordinateur": coordinateur.nom,
                               "issue": "ignore",
                               "raison": "disjoncteur ouvert après des "
                                         "échecs répétés"})
                continue

            issue = self._essayer(coordinateur, projet, module, ressource)
            relais.append(issue)

            if issue["issue"] == "termine":
                disjoncteur.succes()
                observateur.noter("coordination_terminee",
                                  coordinateur=coordinateur.nom,
                                  niveau=coordinateur.niveau)
                return ResultatSupervision("termine", coordinateur.nom,
                                           coordinateur.niveau,
                                           issue.get("resultat"), relais)

            disjoncteur.echec()
            observateur.noter("relais", depuis=coordinateur.nom,
                              raison=issue["raison"])
            self.journal(f"  -> Relais : {coordinateur.nom} défaillant "
                         f"({issue['raison']})")

        observateur.noter("validation_humaine",
                          raison="tous les coordinateurs ont échoué")
        self.journal("  [ATTENTION]  Validation humaine : aucun coordinateur n'a pu "
                     "mener le module à terme.")
        return ResultatSupervision("validation_humaine", relais=relais)

    # ─────────────────────────────────────────────────────
    def _essayer(self, coordinateur, projet, module, ressource) -> dict:
        bail = Bail(self.stockage, ressource,
                    f"{coordinateur.nom}-{int(time.time() * 1000) % 100000}",
                    self.duree_bail_ms)

        # Attendre que le bail se libère : un coordinateur précédent,
        # déclaré défaillant, a pu le garder jusqu'à son expiration.
        limite_bail = time.monotonic() + self.duree_bail_ms / 1000 + 5
        while not bail.acquerir():
            if time.monotonic() > limite_bail:
                return {"coordinateur": coordinateur.nom, "issue": "echec",
                        "raison": "bail impossible à obtenir"}
            time.sleep(min(0.2, self.periode))

        espace = EspaceModule(projet, module, self.stockage, bail=bail)
        sortie = {}

        def travailler():
            try:
                sortie["resultat"] = coordinateur.coordonner(espace)
            except BailPerdu as e:
                sortie["erreur"] = f"bail perdu : {e}"
            except BaseException as e:
                # BaseException, et pas seulement Exception : un fil qui
                # meurt d'une erreur grave ne doit jamais passer pour une
                # coordination réussie.
                sortie["erreur"] = f"{type(e).__name__} : {str(e)[:200]}"
                sortie["trace"] = traceback.format_exc()[-1500:]

        ouvrier = threading.Thread(target=travailler, daemon=True,
                                   name=f"coord-{coordinateur.nom}")
        debut = time.monotonic()
        ouvrier.start()

        raison = None
        # Le chien de garde : tant que le coordinateur progresse, on
        # renouvelle son bail ; dès qu'il cesse, on le retire.
        while ouvrier.is_alive():
            ouvrier.join(self.periode)
            if not ouvrier.is_alive():
                break
            ecoule = time.monotonic() - debut
            # Inactivité mesurée depuis le plus récent entre le
            # démarrage de CE coordinateur et son dernier dépôt : les
            # événements de ses prédécesseurs ne comptent pas contre lui.
            depuis_evenement = espace.secondes_depuis_activite()
            inactif = ecoule if depuis_evenement is None \
                else min(depuis_evenement, ecoule)
            if inactif > self.delai_inactivite_s:
                raison = f"aucune activité depuis {inactif:.0f} s"
                break
            if ecoule > self.delai_total_s:
                raison = f"durée maximale dépassée ({ecoule:.0f} s)"
                break
            bail.renouveler()

        if raison is not None:
            # Déclaré défaillant : on libère son bail. S'il continue
            # de tourner, ses écritures seront refusées (clôture).
            bail.liberer()
            return {"coordinateur": coordinateur.nom, "issue": "echec",
                    "raison": raison}

        bail.liberer()
        if "erreur" not in sortie and "resultat" not in sortie:
            sortie["erreur"] = "le coordinateur s'est arrêté sans résultat"
        if "erreur" in sortie:
            return {"coordinateur": coordinateur.nom, "issue": "echec",
                    "raison": sortie["erreur"]}
        return {"coordinateur": coordinateur.nom, "issue": "termine",
                "resultat": sortie.get("resultat")}