"""
Orchestration multi-agents par CrewAI — migration PHP → Python
===============================================================
CONCEPTION : aucune séquence n'est écrite dans ce fichier.

  - UNE seule tâche « mission » décrit l'OBJECTIF, pas les étapes.
  - Le Manager (processus hiérarchique) décide seul quels agents
    activer et dans quel ordre, d'après leurs descriptions.
  - Les agents ne s'appellent JAMAIS entre eux : ils déposent et
    lisent leurs résultats dans un ÉTAT PARTAGÉ (modèle du
    « tableau noir »). Il n'existe donc aucune chaîne de
    dépendances : un agent indisponible ne bloque pas le système.
  - Chaque outil porte ses PRÉCONDITIONS : appelé trop tôt, il
    répond ce qui lui manque au lieu d'échouer. L'ordre correct
    émerge du raisonnement du Manager, il n'est pas imposé.
"""

import sys
import os
import json

sys.stdout.reconfigure(encoding="utf-8")
os.environ["LITELLM_DROP_PARAMS"] = "True"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool

from agent_analyste import analyser_code_php
import cache_smaml
from agent_architecte import planifier_migration, reviser_module
from agent_developpeur import (generer_code_python, nettoyer_code,
                               extraire_metadonnees, extraire_dependances)
from agent_testeur import agent_testeur
from agent_testeur_differentiel import tester_equivalence
from agent_verification_formelle import verifier_formellement
from agent_auditeur import agent_auditeur
from agent_reviseur import agent_reviseur


# ─── LLM D'ORCHESTRATION ─────────────────────────────
# Deux fournisseurs sont disponibles pour le Manager et les agents :
#
#   gemini : gemini-3.1-flash-lite (palier gratuit : 500 requêtes/jour)
#   groq   : openai/gpt-oss-120b, via l'API compatible OpenAI de Groq
#
# Groq n'est pas un fournisseur natif de CrewAI ; son API compatible
# OpenAI l'est. Le préfixe « openai/ » plus un base_url explicite fait
# passer CrewAI par son client OpenAI natif, sans dépendre de LiteLLM.
#
#   SMAML_MANAGER=gemini|groq   modèle de départ (défaut : gemini)
#   SMAML_BASCULE=1             repli automatique sur l'autre modèle
#                               en cas de quota épuisé ou de panne
#
# Pour des MESURES, laisser SMAML_BASCULE à 0 : un seul modèle garantit
# que tous les résultats sont comparables. Chaque basculement est de
# toute façon enregistré dans le journal et le rapport.

GROQ_TOKEN_ORCHESTRATION = os.getenv("GROQ_TOKEN")
MODELE_GROQ_ORCHESTRATION = os.getenv("SMAML_MANAGER_GROQ_MODEL",
                                      "openai/gpt-oss-120b")

DESCRIPTIONS_MODELES = {
    "gemini": "gemini/gemini-3.1-flash-lite",
    "groq": f"groq/{MODELE_GROQ_ORCHESTRATION}",
}


def _creer_llm(nom: str):
    if nom == "groq":
        if not GROQ_TOKEN_ORCHESTRATION:
            return None
        return LLM(model=f"openai/{MODELE_GROQ_ORCHESTRATION}",
                   base_url="https://api.groq.com/openai/v1",
                   api_key=GROQ_TOKEN_ORCHESTRATION, temperature=0.1)
    if not GEMINI_API_KEY:
        return None
    return LLM(model="gemini/gemini-3.1-flash-lite",
               api_key=GEMINI_API_KEY, temperature=0.1)


MODELE_ACTIF = (os.getenv("SMAML_MANAGER") or "gemini").lower()
if MODELE_ACTIF not in DESCRIPTIONS_MODELES:
    MODELE_ACTIF = "gemini"
BASCULE_AUTORISEE = os.getenv("SMAML_BASCULE", "0").lower() in (
    "1", "true", "oui")

_LLMS = {}


def llm_pour(nom: str):
    if nom not in _LLMS:
        _LLMS[nom] = _creer_llm(nom)
    return _LLMS[nom]


# Modèle utilisé pour CONSTRUIRE les agents. Si la clé du modèle demandé
# manque, on en prend un autre pour que l'import réussisse — mais ce
# choix n'est jamais utilisé tel quel : chaque module réapplique le
# modèle demandé (appliquer_modele) et échoue explicitement si c'est
# impossible, au lieu de tourner en silence sur un autre modèle.
llm = llm_pour(MODELE_ACTIF) or llm_pour(
    "groq" if MODELE_ACTIF == "gemini" else "gemini")
if llm_pour(MODELE_ACTIF) is None:
    print(f"⚠️  Clé absente pour l'orchestrateur demandé ({MODELE_ACTIF}).")

# Fournisseurs en panne pendant cette exécution (coupe-circuit) : un
# fournisseur qui a échoué n'est plus retenté, ce qui évite de repayer
# deux échecs à chaque module quand les deux sont indisponibles.
FOURNISSEURS_EN_PANNE = set()


# ═══ ÉTAT PARTAGÉ (tableau noir) ══════════════════════
# Les agents n'échangent pas directement : ils écrivent et
# lisent ici. C'est ce découplage qui rend le système résilient.
ETAT = {
    "code_php": "",
    "analyse": None,
    "plan": None,
    "module": None,
    "code_python": "",
    "rapport_testeur": None,
    "rapport_differentiel": None,
    "rapport_formel": None,
    "rapport_auditeur": None,
    "decision": None,
    "iteration": 1,
    "contexte_projet": "",
    "agents_en_echec": [],
    "journal": [],
    "scores_successifs": [],
    "max_iterations": 3,
    # Fichier PHP complet d'où le module est extrait : nécessaire au
    # Comparateur quand une fonction en appelle une autre.
    "code_php_complet": "",
    # Code Python des modules déjà migrés du même fichier : résout les
    # appels d'un module à un autre lors du test d'équivalence.
    "code_python_projet": "",
    # Versions successives de chaque dépôt : rien n'est écrasé.
    "historique": {},
    # Dépôt courant de chaque type, avec son schéma complet.
    "depots": {},
    # Révision du plan demandée par le Réviseur (limite structurelle).
    "revision_plan_en_attente": False,
    "replanifications": 0,
    # Justifications des activations décidées par le Manager.
    "decisions_manager": [],
    "justifications_en_attente": {},
    # Modèle d'orchestration utilisé, et basculements éventuels.
    "modele_orchestrateur": "",
    "bascules_modele": [],
    "correction_demandee": False,
}


def reinitialiser_etat(code_php: str):
    """Remet le tableau noir à zéro pour une nouvelle migration."""
    for cle in list(ETAT.keys()):
        ETAT[cle] = None
    ETAT["code_php"] = code_php
    ETAT["code_python"] = ""
    ETAT["iteration"] = 1
    ETAT["contexte_projet"] = ""
    ETAT["agents_en_echec"] = []
    ETAT["journal"] = []
    ETAT["scores_successifs"] = []
    ETAT["max_iterations"] = 3
    ETAT["code_php_complet"] = ""
    ETAT["code_python_projet"] = ""
    ETAT["historique"] = {}
    ETAT["depots"] = {}
    ETAT["revision_plan_en_attente"] = False
    ETAT["replanifications"] = 0
    ETAT["decisions_manager"] = []
    ETAT["justifications_en_attente"] = {}
    ETAT["modele_orchestrateur"] = ""      # écrit par appliquer_modele
    ETAT["bascules_modele"] = []
    # Une correction a-t-elle été demandée par le Réviseur depuis la
    # dernière génération ? Sans elle, régénérer le code ne sert à
    # rien et invalide les vérifications déjà faites.
    ETAT["correction_demandee"] = False


# ═══ DÉPÔTS : SCHÉMA FIXE ET VERSIONNEMENT ════════════
# Chaque type de dépôt a un schéma fixe : en plus de son contenu,
# l'agent DOIT expliciter certains champs. Un dépôt incomplet est
# refusé — c'est ce qui force chaque agent à dire ce qui serait
# sinon resté implicite.
#
# Chaque écriture crée une NOUVELLE version au lieu d'effacer la
# précédente. La valeur courante reste lisible directement
# (ETAT[cle]) pour les agents ; ETAT["depots"][cle] contient le dépôt
# complet ; ETAT["historique"][cle] conserve toutes les versions.

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
    "decision":             ("points_attention",),
}


def deposer(cle: str, valeur, auteur: str, **champs):
    """
    Écrit un dépôt dans l'espace de travail : vérifie son schéma,
    le versionne et le rend courant.
    """
    import copy
    from datetime import datetime

    manquants = [c for c in SCHEMAS_DEPOT.get(cle, ()) if c not in champs]
    if manquants:
        raise ValueError(f"Dépôt « {cle} » incomplet : champ(s) "
                         f"{', '.join(manquants)} manquant(s)")

    if ETAT.get("historique") is None:
        ETAT["historique"] = {}
    if ETAT.get("depots") is None:
        ETAT["depots"] = {}
    versions = ETAT["historique"].setdefault(cle, [])
    depot = {
        "type": cle,
        "version": len(versions) + 1,
        "iteration": ETAT.get("iteration", 1),
        "auteur": auteur,
        "horodatage": datetime.now().isoformat(timespec="seconds"),
        # copie profonde : une modification ultérieure de l'objet
        # courant ne doit pas réécrire une version archivée
        "contenu": copy.deepcopy(valeur),
        **{c: list(champs[c] or []) for c in champs},
    }
    versions.append(depot)
    ETAT["depots"][cle] = depot
    ETAT[cle] = valeur


def invalider(cle: str):
    """Retire un dépôt périmé de l'état courant (l'historique le garde)."""
    ETAT[cle] = "" if cle == "code_python" else None
    (ETAT.get("depots") or {}).pop(cle, None)


# ═══ JOURNAL DES DÉCISIONS ════════════════════════════
# L'orchestration étant dynamique, le chemin suivi n'est pas
# prévisible à l'avance. Chaque sollicitation d'agent est donc
# consignée avec l'état du module au moment où elle survient :
# le raisonnement du Manager devient ainsi auditable a posteriori.

def journaliser(agent: str, resultat: str):
    """Consigne une sollicitation d'agent et son issue."""
    from datetime import datetime
    if ETAT.get("journal") is None:
        ETAT["journal"] = []

    # Qualification de l'issue, lisible sans relire le message.
    if resultat.startswith("PRÉREQUIS MANQUANT"):
        issue = "refus_prerequis"
    elif resultat.startswith("AGENT INDISPONIBLE"):
        issue = "indisponible"
    elif "DÉJÀ disponible" in resultat:
        issue = "deja_fait"
    elif "réutilisé depuis le cache" in resultat:
        issue = "cache"
    else:
        issue = "execute"

    # Ce qui restait à faire au moment de la sollicitation : c'est
    # cela qui justifie l'activation de cet agent plutôt qu'un autre.
    restantes = [nom for cle, nom in _ETAPES if not ETAT.get(cle)]

    ETAT["journal"].append({
        "ordre": len(ETAT["journal"]) + 1,
        "horodatage": datetime.now().isoformat(timespec="seconds"),
        "agent": agent,
        # raison donnée par le Manager en activant cet agent
        "justification_manager": _prendre_justification(agent),
        "issue": issue,
        "etapes_restantes_avant": restantes,
        "iteration": ETAT.get("iteration", 1),
        "resultat": resultat[:200],
    })


# ═══ JUSTIFICATION DES ACTIVATIONS DU MANAGER ═════════
# Le Manager active un spécialiste en lui déléguant une tâche. Chaque
# délégation est interceptée sur le bus d'événements de CrewAI (qui
# couvre aussi l'appel natif d'outils, contrairement à step_callback)
# et sa justification est rattachée à l'entrée de journal de l'agent
# activé. Le raisonnement de l'orchestrateur devient ainsi auditable.

import threading
_VERROU_MANAGER = threading.Lock()
ROLE_MANAGER = "Manager de migration"
ROLE_VERS_AGENT = {}          # rempli après la définition des agents


def _agent_depuis_role(role: str) -> str:
    r = (role or "").strip().casefold()
    for role_agent, nom in ROLE_VERS_AGENT.items():
        if r == role_agent.casefold() or role_agent.casefold() in r:
            return nom
    return role or "?"


def enregistrer_delegation(agent_role, tool_name, tool_args):
    """Consigne une délégation du Manager et sa justification."""
    from datetime import datetime
    if (agent_role or "").strip() != ROLE_MANAGER:
        return
    nom_outil = (tool_name or "").casefold()
    if "coworker" not in nom_outil and "deleg" not in nom_outil:
        return

    args = tool_args
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            import ast
            try:
                args = ast.literal_eval(args)
            except (ValueError, SyntaxError):
                args = {"task": args}
    args = args if isinstance(args, dict) else {}

    tache = str(args.get("task") or args.get("question") or "")
    contexte = str(args.get("context") or "")
    justification = None
    for ligne in (contexte + "\n" + tache).splitlines():
        if ligne.strip().upper().startswith("JUSTIFICATION"):
            justification = ligne.split(":", 1)[-1].strip()
            break
    if not justification:
        justification = tache[:300]     # à défaut, la tâche confiée

    agent = _agent_depuis_role(str(args.get("coworker") or ""))
    entree = {
        "ordre": len(ETAT.get("decisions_manager") or []) + 1,
        "horodatage": datetime.now().isoformat(timespec="seconds"),
        "type": "question" if "ask" in nom_outil else "delegation",
        "agent_active": agent,
        "justification": justification,
        "tache": tache[:300],
    }
    with _VERROU_MANAGER:
        ETAT.setdefault("decisions_manager", []).append(entree)
        if entree["type"] == "delegation":
            file = ETAT.setdefault("justifications_en_attente", {})
            file.setdefault(agent, []).append(justification)


def _prendre_justification(agent: str):
    """Justification la plus ancienne en attente pour cet agent."""
    with _VERROU_MANAGER:
        file = (ETAT.get("justifications_en_attente") or {}).get(agent)
        return file.pop(0) if file else None


def _installer_ecoute_manager() -> bool:
    """Branche la capture sur le bus d'événements de CrewAI."""
    try:
        from crewai.events import crewai_event_bus, ToolUsageStartedEvent
    except ImportError:
        try:   # versions antérieures de CrewAI
            from crewai.utilities.events import (crewai_event_bus,
                                                 ToolUsageStartedEvent)
        except ImportError:
            print("⚠️  Bus d'événements CrewAI introuvable : les "
                  "justifications du Manager ne seront pas capturées.")
            return False

    @crewai_event_bus.on(ToolUsageStartedEvent)
    def _sur_utilisation_outil(source, event):
        try:
            enregistrer_delegation(getattr(event, "agent_role", None),
                                   getattr(event, "tool_name", ""),
                                   getattr(event, "tool_args", {}))
        except Exception:
            pass          # la traçabilité ne doit jamais bloquer
    return True


def _mention_cache(depuis_cache: bool) -> str:
    """Rend la réutilisation visible dans le message et le journal."""
    return " (résultat réutilisé depuis le cache)" if depuis_cache else ""


def blocage_definitif() -> str:
    """
    Message à renvoyer quand un agent BLOQUANT est indisponible.

    Sans lui, le Manager tourne en boucle : il relance le Développeur
    (qui échoue), puis les vérifications (qui réclament du code), sans
    jamais pouvoir conclure. Le Manager doit savoir que la situation
    est sans issue et clore la mission par le Réviseur.
    """
    absents = [a for a in (ETAT.get("agents_en_echec") or [])
               if a in AGENTS_BLOQUANTS]
    if not absents:
        return ""
    return ("SITUATION SANS ISSUE : " + ", ".join(absents)
            + " indisponible(s), c'est une étape non négociable. "
              "Ne relance aucun autre agent : fais intervenir le "
              "Réviseur pour clore la mission, puis rends ton bilan.")


def _echec(nom_agent: str, erreur: Exception) -> str:
    """
    Résilience : un agent qui échoue ne fait pas tomber le système.
    On enregistre l'incident et on rend la main au Manager avec un
    résultat dégradé explicite.
    """
    ETAT["agents_en_echec"].append(nom_agent)
    return (f"AGENT INDISPONIBLE — {nom_agent} a échoué "
            f"({type(erreur).__name__}: {str(erreur)[:120]}). "
            f"Cette vérification est manquante. Poursuis avec les "
            f"autres agents et signale-le dans le bilan final.")


# ═══ CRITICITÉ DES AGENTS ═════════════════════════════
# Tous les agents ne se valent pas au regard de la livraison.
#
#   BLOQUANTS     — leur vérification n'est pas négociable. Si l'un
#                   d'eux est indisponible, le module ne peut PAS
#                   être accepté : il passe en escalade humaine.
#   NON BLOQUANTS — ils apportent une garantie supplémentaire mais
#                   ne conditionnent pas la livraison. Leur absence
#                   est mentionnée explicitement dans le rapport,
#                   afin que le lecteur sache ce qui n'a pas été
#                   couvert.
AGENTS_BLOQUANTS = {"Testeur", "Auditeur", "Développeur"}
AGENTS_NON_BLOQUANTS = {"Comparateur", "Vérificateur de propriétés"}


# ═══ ÉTAT STRUCTURÉ DU MODULE ═════════════════════════
# Vue normalisée de l'avancement, dérivée de l'espace de travail.
# Elle répond à une question simple, à tout instant : qu'a-t-on
# réellement fait sur ce module, et que sait-on de sa qualité ?
#
# Cette vue est ce qui est journalisé et transmis à la couche
# projet : elle ne contient aucun rapport brut, seulement des
# faits vérifiables.

# Étapes suivies : clé de l'espace de travail → nom de l'étape
_ETAPES = [
    ("analyse", "analyse"),
    ("plan", "plan"),
    ("code_python", "code_genere"),
    ("rapport_testeur", "teste"),
    ("rapport_differentiel", "compare"),
    ("rapport_formel", "proprietes_verifiees"),
    ("rapport_auditeur", "audite"),
    ("decision", "decide"),
]


def etat_structure() -> dict:
    """
    Produit l'état structuré du module en cours.

    Contient : le statut, les étapes franchies, les tentatives de
    correction et leur maximum, les agents indisponibles avec leur
    criticité, la dernière activation décidée par le Manager et sa
    justification, la dernière décision du Réviseur, et les points
    d'attention destinés à la suite du traitement.
    """
    etapes = {nom: bool(ETAT[cle]) for cle, nom in _ETAPES}

    indisponibles = list(ETAT["agents_en_echec"] or [])
    bloquants_absents = [a for a in indisponibles if a in AGENTS_BLOQUANTS]

    decision = ETAT["decision"] or {}
    verdict = decision.get("decision")
    statut = {"LIVRER": "accepte",
              "ESCALADE_HUMAINE": "escalade_humaine",
              "ARRET_ECHEC": "echec"}.get(verdict, "en_cours")

    # Points d'attention : ce qu'un lecteur — humain ou agent —
    # doit savoir avant de se fier à ce module.
    #   1. ceux que chaque agent a déposés avec son travail (dépôts
    #      courants uniquement : un rapport périmé ne compte plus) ;
    #   2. ceux qui tiennent au déroulement (pannes, fragilité).
    attention = []
    for cle, _nom in _ETAPES:
        depot = (ETAT.get("depots") or {}).get(cle)
        if depot and ETAT.get(cle):
            attention += [f"[{depot['auteur']}] {p}"
                          for p in depot.get("points_attention", [])]
    if bloquants_absents:
        attention.append(
            "Vérification non négociable impossible ("
            + ", ".join(bloquants_absents)
            + ") : le module ne peut pas être accepté automatiquement.")
    for agent in indisponibles:
        if agent in AGENTS_NON_BLOQUANTS:
            attention.append(
                f"{agent} indisponible : garantie correspondante "
                f"absente, la livraison reste possible.")
    if ETAT["iteration"] > 2:
        attention.append(
            f"{ETAT['iteration'] - 1} tentative(s) de correction ont été "
            f"nécessaires : module fragile.")

    journal = list(ETAT.get("journal") or [])
    derniere = journal[-1] if journal else None

    return {
        "module": (ETAT["module"] or {}).get("nom_python", ""),
        "statut": statut,
        "etapes": etapes,
        "tentatives_correction": max(0, ETAT["iteration"] - 1),
        "max_tentatives": ETAT.get("max_iterations") or 3,
        "replanifications": ETAT.get("replanifications") or 0,
        "agents_indisponibles": [
            {"agent": a,
             "criticite": ("bloquant" if a in AGENTS_BLOQUANTS
                           else "non bloquant")}
            for a in indisponibles
        ],
        "derniere_activation": {
            "agent": derniere["agent"],
            "justification": derniere.get("justification_manager"),
        } if derniere else None,
        "derniere_decision": {
            "verdict": verdict,
            "score": decision.get("score_compose"),
            "raison": decision.get("raison"),
            "categorie_echec": decision.get("categorie_echec"),
            "confiance": decision.get("confiance"),
        } if decision else None,
        "points_attention": attention,
        "scores_successifs": list(ETAT.get("scores_successifs") or []),
        "journal": journal,
        "decisions_manager": list(ETAT.get("decisions_manager") or []),
        # nombre de versions conservées par dépôt
        "versions": {cle: len(v) for cle, v
                     in (ETAT.get("historique") or {}).items()},
        "modele_orchestrateur": ETAT.get("modele_orchestrateur"),
        "bascules_modele": list(ETAT.get("bascules_modele") or []),
    }


def resume_etat() -> str:
    """Résumé lisible de l'état structuré, destiné au Manager."""
    e = etat_structure()
    faites = [n for n, ok in e["etapes"].items() if ok]
    restantes = [n for n, ok in e["etapes"].items() if not ok]
    txt = (f"État du module {e['module']} — "
           f"étapes franchies : {', '.join(faites) or 'aucune'}"
           f" | restantes : {', '.join(restantes) or 'aucune'}"
           f" | tentatives de correction : {e['tentatives_correction']}")
    if e["agents_indisponibles"]:
        txt += (" | agents indisponibles : "
                + ", ".join(f"{a['agent']} ({a['criticite']})"
                            for a in e["agents_indisponibles"]))
    if e["points_attention"]:
        txt += " | points d'attention : " + " ".join(e["points_attention"])
    return txt



def _journalise(nom_agent):
    """
    Décorateur de traçabilité : consigne chaque sollicitation d'agent
    dans le journal, sans modifier la logique de l'outil.
    """
    def deco(fonction):
        import functools

        @functools.wraps(fonction)
        def enveloppe(*args, **kwargs):
            resultat = fonction(*args, **kwargs)
            try:
                journaliser(nom_agent, str(resultat))
            except Exception:
                pass          # la traçabilité ne doit jamais bloquer
            return resultat
        return enveloppe
    return deco


# ═══ OUTILS — chacun porte ses préconditions ══════════

@tool("Analyser le code PHP source")
@_journalise("Analyste")
def outil_analyste(note: str = "") -> str:
    """
    Analyse le code PHP source et en extrait les fonctions, les
    classes, les invariants de sécurité à préserver et les failles.
    PRÉREQUIS : aucun. C'est le point de départ de toute migration.
    """
    try:
        if not ETAT["code_php"]:
            return "IMPOSSIBLE : aucun code PHP n'a été fourni."
        # Idempotence : si l'analyse figure déjà dans l'espace de
        # travail (fournie par la couche projet), inutile de la refaire.
        if ETAT["analyse"]:
            m = ETAT["analyse"].get("metriques", {})
            return (f"L'analyse est DÉJÀ disponible dans l'espace de "
                    f"travail : {m.get('nombre_fonctions', 0)} fonction(s), "
                    f"{m.get('nombre_invariants', 0)} invariant(s), "
                    f"{m.get('nombre_failles', 0)} faille(s). "
                    f"Passe à l'étape suivante.")
        rapport, du_cache = cache_smaml.avec_cache(
            "analyse", [ETAT["code_php"]],
            lambda: analyser_code_php(ETAT["code_php"]))
        deposer("analyse", rapport, "Analyste",
                points_attention=points_attention_analyse(rapport))
        m = rapport.get("metriques", {})
        return (f"Analyse terminée{_mention_cache(du_cache)}. "
                f"{m.get('nombre_fonctions', 0)} fonction(s), "
                f"{m.get('nombre_classes', 0)} classe(s), "
                f"{m.get('nombre_invariants', 0)} invariant(s) à préserver, "
                f"{m.get('nombre_failles', 0)} faille(s) détectée(s).")
    except Exception as e:
        return _echec("Analyste", e)


def points_attention_analyse(rapport: dict) -> list:
    failles = rapport.get("failles_potentielles", []) or []
    graves = [f for f in failles
              if str(f.get("severity", "")).lower() in ("high", "critical")]
    points = []
    if graves:
        points.append(f"{len(graves)} faille(s) de sévérité élevée dans le "
                      f"PHP d'origine : "
                      + ", ".join(sorted({f.get('type', '?') for f in graves})))
    invariants = rapport.get("invariants_securite", []) or []
    if invariants:
        points.append(f"{len(invariants)} invariant(s) de sécurité à "
                      f"préserver dans le code produit")
    return points


def deposer_plan_et_module(plan: dict, module: dict, auteur: str):
    """Dépose le plan et le module courant avec leurs champs explicites."""
    deposer("plan", plan, auteur,
            hypotheses_faites=plan.get("hypotheses_faites", []),
            points_incertains=plan.get("points_incertains", []),
            points_attention=plan.get("points_attention", []))
    deposer("module", module, auteur,
            hypotheses_faites=module.get("hypotheses_faites", []),
            points_incertains=module.get("points_incertains", []),
            points_attention=module.get("points_attention", []))


@tool("Planifier la migration")
@_journalise("Architecte")
def outil_architecte(note: str = "") -> str:
    """
    Décide COMMENT migrer : quels modules créer, si une classe reste
    une classe ou devient des fonctions, et dans quel ordre traiter
    les classes qui héritent les unes des autres. Révise le plan
    quand le Réviseur le demande (échec de type limite structurelle).
    PRÉREQUIS : le code PHP doit avoir été analysé.
    """
    try:
        if not ETAT["analyse"]:
            return ("PRÉREQUIS MANQUANT : le code PHP n'a pas encore "
                    "été analysé. Fais d'abord intervenir l'Analyste.")

        # ── Révision demandée par le Réviseur ──
        # Les mêmes erreurs persistent malgré la correction : le plan
        # lui-même est en cause. L'Architecte revoit la stratégie du
        # module ; le code et ses vérifications deviennent périmés.
        if ETAT.get("revision_plan_en_attente"):
            erreurs = (ETAT["decision"] or {}).get("erreurs_persistantes", [])
            module_revise = reviser_module(ETAT["module"] or {}, erreurs)
            plan = dict(ETAT["plan"] or {})
            plan["modules"] = [
                module_revise
                if m.get("nom_original") == module_revise.get("nom_original")
                else m for m in plan.get("modules", [])] or [module_revise]
            plan["points_attention"] = list(
                plan.get("points_attention", [])) + [
                f"{module_revise.get('nom_original', '?')} : " + c
                for c in module_revise.get("changements_revision", [])]
            deposer_plan_et_module(plan, module_revise, "Architecte")
            ETAT["replanifications"] = (ETAT.get("replanifications") or 0) + 1
            ETAT["revision_plan_en_attente"] = False
            for cle in ("code_python", "rapport_testeur",
                        "rapport_differentiel", "rapport_formel",
                        "rapport_auditeur"):
                invalider(cle)
            return ("Plan révisé pour "
                    f"{module_revise.get('nom_python', '?')} : "
                    + "; ".join(module_revise.get("changements_revision", []))
                    + ". Le code précédent est périmé : réactive le "
                      "Développeur, puis fais refaire les quatre "
                      "vérifications.")

        # Idempotence : plan déjà fourni par la couche projet.
        if ETAT["plan"]:
            nom = (ETAT["module"] or {}).get("nom_python", "?")
            return (f"Le plan est DÉJÀ disponible dans l'espace de "
                    f"travail : le module à migrer est {nom}. "
                    f"Passe à l'étape suivante.")
        plan = planifier_migration(ETAT["analyse"], ETAT["code_php"])
        modules = plan.get("modules", [])
        if modules:
            deposer_plan_et_module(plan, modules[0], "Architecte")
        else:
            deposer("plan", plan, "Architecte",
                    hypotheses_faites=plan.get("hypotheses_faites", []),
                    points_incertains=plan.get("points_incertains", []),
                    points_attention=plan.get("points_attention", []))
        noms = ", ".join(m.get("nom_python", "?") for m in modules)
        reponse = (f"Plan établi : {len(modules)} module(s) à migrer "
                   f"({noms}). Pattern : {plan.get('pattern_migration', '?')}.")
        if plan.get("points_attention"):
            reponse += (" Points d'attention : "
                        + " | ".join(plan["points_attention"][:3]) + ".")
        return reponse
    except Exception as e:
        return _echec("Architecte", e)


@tool("Generer le code Python")
@_journalise("Développeur")
def outil_developpeur(note: str = "") -> str:
    """
    Traduit le module PHP en code Python moderne et sécurisé, en
    s'appuyant sur des exemples similaires et des patrons de
    correction des failles. Tient compte du feedback de révision
    et des points d'attention de l'Architecte. Déclare ses
    dépendances, ses hypothèses et ses points d'incertitude.
    PRÉREQUIS : un plan de migration doit exister.
    """
    try:
        if not ETAT["plan"] or not ETAT["module"]:
            return ("PRÉREQUIS MANQUANT : aucun plan de migration. "
                    "Fais d'abord intervenir l'Architecte.")
        if ETAT.get("revision_plan_en_attente"):
            return ("PRÉREQUIS MANQUANT : le Réviseur a demandé une "
                    "révision du plan. Fais d'abord intervenir "
                    "l'Architecte : régénérer le code avec le même plan "
                    "reproduirait les mêmes erreurs.")
        # Régénérer un code que personne n'a demandé de corriger ne
        # sert à rien : cela invalide les vérifications déjà faites et
        # peut produire un code différent. Le code n'est refait que sur
        # demande du Réviseur.
        if ETAT["code_python"] and not ETAT.get("correction_demandee"):
            nb = len((ETAT.get("historique") or {}).get("code_python", []))
            return ("Le code Python est DÉJÀ disponible (version "
                    f"{nb}) et aucune correction n'a été demandée par le "
                    "Réviseur : inutile de le régénérer. Fais faire les "
                    "vérifications qui manquent. — " + resume_etat())
        analyse = ETAT["analyse"] or {}
        feedback = None
        if ETAT["decision"]:
            feedback = ETAT["decision"].get("feedback")
        brut = generer_code_python(
            ETAT["code_php"],
            ETAT["module"],
            analyse.get("invariants_securite", []),
            analyse.get("failles_potentielles", []),
            contexte_projet=ETAT.get("contexte_projet") or "",
            feedback=feedback,
        )
        meta = extraire_metadonnees(brut)
        code = nettoyer_code(brut)
        ETAT["correction_demandee"] = False
        deposer("code_python", code, "Développeur",
                dependances=extraire_dependances(code),
                hypotheses_faites=meta["hypotheses_faites"],
                points_incertains=meta["points_incertains"],
                points_attention=meta["points_attention"])
        # nouvelle génération : les vérifications précédentes sont
        # périmées (elles restent consultables dans l'historique)
        for cle in ("rapport_testeur", "rapport_differentiel",
                    "rapport_formel", "rapport_auditeur"):
            invalider(cle)
        reponse = (f"Code Python généré pour "
                   f"{ETAT['module'].get('nom_python', '?')} "
                   f"({len(code.splitlines())} lignes). "
                   f"Il doit maintenant être vérifié.")
        if meta["points_incertains"]:
            reponse += (" Points incertains déclarés : "
                        + " | ".join(meta["points_incertains"][:3]) + ".")
        return reponse
    except Exception as e:
        return _echec("Développeur", e)


@tool("Tester le code genere")
@_journalise("Testeur")
def outil_testeur(note: str = "") -> str:
    """
    Vérifie que le code Python est exécutable, que les invariants de
    sécurité du PHP y sont préservés et que les failles sont corrigées.
    PRÉREQUIS : un code Python doit avoir été généré.
    """
    try:
        if not ETAT["code_python"]:
            return (blocage_definitif()
                    or "PRÉREQUIS MANQUANT : aucun code Python n'existe "
                       "encore. Fais d'abord intervenir le Développeur.")
        analyse = ETAT["analyse"] or {}
        rapport, du_cache = cache_smaml.avec_cache(
            "testeur",
            [ETAT["code_python"], ETAT["module"],
             analyse.get("invariants_securite", []),
             analyse.get("failles_potentielles", [])],
            lambda: agent_testeur(
                ETAT["code_python"], ETAT["module"],
                analyse.get("invariants_securite", []),
                analyse.get("failles_potentielles", []),
            ))
        points = []
        syntaxe = rapport.get("syntaxe", {}) or {}
        if not syntaxe.get("syntaxe_valide", True):
            points.append(f"code inexécutable : {syntaxe.get('erreur', '')}"[:160])
        manquants = (rapport.get("invariants", {}) or {}).get(
            "invariants_manquants", []) or []
        if manquants:
            points.append(f"{len(manquants)} invariant(s) absent(s) du code")
        persistantes = (rapport.get("failles", {}) or {}).get(
            "failles_persistantes", []) or []
        if persistantes:
            points.append(f"{len(persistantes)} faille(s) du PHP toujours "
                          f"présente(s)")
        deposer("rapport_testeur", rapport, "Testeur",
                points_attention=points)
        valide = syntaxe.get("syntaxe_valide")
        return (f"Test terminé{_mention_cache(du_cache)}. "
                f"Code exécutable : {valide}. "
                f"Score fonctionnel : "
                f"{rapport.get('score_fonctionnel', 0) * 100:.1f}%.")
    except Exception as e:
        return _echec("Testeur", e)


@tool("Comparer les comportements PHP et Python")
@_journalise("Comparateur")
def outil_differentiel(note: str = "") -> str:
    """
    Exécute réellement le code PHP d'origine et le code Python généré
    sur les mêmes entrées, et compare leurs comportements pour
    détecter les divergences.
    PRÉREQUIS : un code Python doit avoir été généré.
    """
    try:
        if not ETAT["code_python"]:
            return (blocage_definitif()
                    or "PRÉREQUIS MANQUANT : aucun code Python à comparer. "
                       "Fais d'abord intervenir le Développeur.")
        module = ETAT["module"] or {}
        rapport, du_cache = cache_smaml.avec_cache(
            "differentiel",
            [ETAT["code_php"], ETAT["code_python"],
             module.get("nom_original", ""), module.get("nom_python", ""),
             ETAT.get("code_php_complet") or "",
             ETAT.get("code_python_projet") or ""],
            lambda: tester_equivalence(
                ETAT["code_php"], ETAT["code_python"],
                module.get("nom_original", ""),
                module.get("nom_python", ""),
                len(module.get("parametres", [])) or 1,
                # fichier PHP complet : résout les appels entre
                # fonctions d'un même fichier
                contexte_php=ETAT.get("code_php_complet") or "",
                # modules déjà migrés : résout les appels entre modules
                contexte_python=ETAT.get("code_python_projet") or "",
            ))
        points = []
        divergences = rapport.get("divergences", []) or []
        if rapport.get("statut") != "teste":
            points.append(f"équivalence comportementale non testée "
                          f"({rapport.get('statut')})")
        elif divergences:
            points.append(f"{len(divergences)} divergence(s) de comportement "
                          f"entre le PHP d'origine et le Python produit")
        bloquees = rapport.get("injections_bloquees") or []
        if bloquees:
            points.append(f"{len(bloquees)} entrée(s) d'injection acceptée(s) "
                          f"par le PHP et neutralisée(s) par le Python : "
                          f"faille corrigée, écart volontaire")
        deposer("rapport_differentiel", rapport, "Comparateur",
                points_attention=points)
        if rapport.get("statut") != "teste":
            return f"Comparaison non applicable : {rapport.get('statut')}."
        base_simulee = rapport.get("base_simulee")
        mention_bdd = (" sur base de données simulée"
                       if base_simulee else "")
        return (f"Équivalence comportementale{_mention_cache(du_cache)}"
                f"{mention_bdd} : "
                f"{rapport.get('score_equivalence', 0) * 100:.0f}% "
                f"({len(divergences)} divergence(s), "
                f"{len(rapport.get('injections_bloquees') or [])} "
                f"injection(s) neutralisée(s)).")
    except Exception as e:
        return _echec("Comparateur", e)


@tool("Verifier les proprietes du code")
@_journalise("Vérificateur de propriétés")
def outil_verification_formelle(note: str = "") -> str:
    """
    Traduit les invariants en propriétés logiques et les soumet à un
    solveur qui explore symboliquement les entrées pour exhiber un
    contre-exemple. Garantie bornée : l'absence de contre-exemple
    dans le budget d'exploration, non une preuve absolue.
    PRÉREQUIS : un code Python doit avoir été généré.
    """
    try:
        if not ETAT["code_python"]:
            return (blocage_definitif()
                    or "PRÉREQUIS MANQUANT : aucun code Python à vérifier. "
                       "Fais d'abord intervenir le Développeur.")
        analyse = ETAT["analyse"] or {}
        rapport = verifier_formellement(
            ETAT["code_python"],
            analyse.get("invariants_securite", []),
            ETAT["module"] or {},
        )
        props = rapport.get("proprietes", []) or []
        prouvees = sum(1 for p in props if p.get("statut") == "prouvee")
        refutees = [p for p in props if p.get("statut") == "refutee"]
        points = [f"propriété réfutée « {p.get('libelle', '?')} », "
                  f"contre-exemple : {p.get('contre_exemple')}"[:160]
                  for p in refutees]
        non_verifiees = [p for p in props
                         if p.get("statut") == "non_verifiee"]
        for p in non_verifiees:
            points.append(f"propriété non vérifiée « {p.get('libelle', '?')} » : "
                          + str(p.get("raison", ""))[:100])
        if rapport.get("statut") == "non_verifiable":
            points.append("propriétés non vérifiables sur ce code : "
                          + str(rapport.get("raison", ""))[:100])
        deposer("rapport_formel", rapport, "Vérificateur de propriétés",
                points_attention=points)
        return (f"Vérification de propriétés : {prouvees} propriété(s) "
                f"prouvée(s), {len(refutees)} réfutée(s), "
                f"{len(non_verifiees)} non vérifiable(s). Familles "
                f"couvertes : invariants métier, injection SQL, "
                f"contrôle d'accès.")
    except Exception as e:
        return _echec("Vérificateur de propriétés", e)


@tool("Auditer la securite du code")
@_journalise("Auditeur")
def outil_auditeur(note: str = "") -> str:
    """
    Audite la sécurité sous trois angles : préservation des
    protections d'origine, absence de failles nouvellement
    introduites, et vulnérabilités des dépendances.
    PRÉREQUIS : un code Python doit avoir été généré.
    """
    try:
        if not ETAT["code_python"]:
            return (blocage_definitif()
                    or "PRÉREQUIS MANQUANT : aucun code Python à auditer. "
                       "Fais d'abord intervenir le Développeur.")
        analyse = ETAT["analyse"] or {}
        rapport, du_cache = cache_smaml.avec_cache(
            "auditeur",
            [ETAT["code_python"], analyse.get("invariants_securite", []),
             ETAT["module"] or {}],
            lambda: agent_auditeur(
                ETAT["code_python"],
                analyse.get("invariants_securite", []),
                ETAT["module"] or {},
            ))
        points = []
        bandit = (rapport.get("dimension_2_bandit", {}) or {}).get(
            "failles_detectees", []) or []
        graves = [f for f in bandit
                  if str(f.get("severity", "")).lower() in ("high", "critical")]
        if graves:
            points.append(f"{len(graves)} faille(s) de sévérité élevée "
                          f"introduite(s) dans le Python")
        violes = (rapport.get("dimension_1_invariants", {}) or {}).get(
            "invariants_violes", []) or []
        if violes:
            points.append(f"{len(violes)} protection(s) d'origine perdue(s)")
        deposer("rapport_auditeur", rapport, "Auditeur",
                points_attention=points)
        return (f"Audit terminé{_mention_cache(du_cache)}. "
                f"Score sécurité : "
                f"{rapport.get('score_securite_global', 0):.1f}% — "
                f"niveau {rapport.get('niveau_alerte', '?')}.")
    except Exception as e:
        return _echec("Auditeur", e)


def _deposer_decision(decision: dict):
    """Dépose une décision ; ses indices deviennent points d'attention."""
    points = []
    if decision.get("decision") != "LIVRER":
        points = list(decision.get("indices_categorie") or [])
        if decision.get("decision") == "ESCALADE_HUMAINE":
            points.append("reprise humaine nécessaire : "
                          + str(decision.get("raison", ""))[:160])
    deposer("decision", decision, "Réviseur", points_attention=points)


def _escalader(decision: dict, raison: str, categorie=None) -> dict:
    """Transforme une décision en escalade humaine motivée."""
    escalade = dict(decision)
    escalade["decision"] = "ESCALADE_HUMAINE"
    escalade["feedback"] = None
    escalade["raison"] = raison
    if categorie:
        escalade["categorie_echec"] = categorie
    _deposer_decision(escalade)
    return escalade


@tool("Decider du sort du module")
@_journalise("Réviseur")
def outil_reviseur(note: str = "") -> str:
    """
    Consolide les vérifications en un score composé et tranche :
    livrer le module, demander une correction ciblée au Développeur,
    demander une révision du plan à l'Architecte, ou confier le
    module à un humain. Chaque échec est classé par cause.
    PRÉREQUIS : les QUATRE vérifications doivent avoir été effectuées —
    test fonctionnel, comparaison des comportements, vérification des
    propriétés et
    audit de sécurité.
    """
    try:
        # Complétude des vérifications. Un agent qui a échoué ne bloque
        # pas la décision (principe de résilience) : seule l'absence de
        # sollicitation est bloquante.
        # ── Agents bloquants indisponibles ──
        # Une vérification non négociable n'a pas pu être conduite :
        # le module ne peut pas être accepté, quel que soit son score.
        # Il est orienté vers une reprise humaine.
        bloquants_absents = [
            a for a in (ETAT["agents_en_echec"] or [])
            if a in AGENTS_BLOQUANTS
        ]
        if bloquants_absents:
            decision = {
                "decision": "ESCALADE_HUMAINE",
                "score_compose": 0.0,
                "iteration": ETAT["iteration"],
                "raison": ("Vérification non négociable impossible : "
                           + ", ".join(bloquants_absents)
                           + " indisponible(s). Le module ne peut pas "
                             "être accepté automatiquement."),
                "feedback": None,
                "categorie_echec": None,   # panne d'agent, pas du code
            }
            _deposer_decision(decision)
            return (f"Décision : ESCALADE_HUMAINE. "
                    f"{', '.join(bloquants_absents)} "
                    f"n'a pas pu se prononcer, or c'est une vérification "
                    f"non négociable. Le module ne peut pas être livré "
                    f"automatiquement : il doit être repris par un "
                    f"opérateur humain. Signale-le clairement dans le "
                    f"bilan final.")

        attendus = [
            ("rapport_testeur", "le test fonctionnel", "Testeur"),
            ("rapport_differentiel", "la comparaison des comportements",
             "Comparateur"),
            ("rapport_formel", "la vérification des propriétés",
             "Vérificateur de propriétés"),
            ("rapport_auditeur", "l'audit de sécurité", "Auditeur"),
        ]
        if ETAT.get("revision_plan_en_attente"):
            return ("PRÉREQUIS MANQUANT : une révision du plan est en "
                    "attente. Fais intervenir l'Architecte, puis le "
                    "Développeur, puis les quatre vérifications.")
        manquants = [
            libelle for cle, libelle, agent in attendus
            if not ETAT[cle] and agent not in (ETAT["agents_en_echec"] or [])
        ]
        if manquants:
            return ("PRÉREQUIS MANQUANT : je ne peux pas décider tant "
                    "que toutes les vérifications n'ont pas été faites. "
                    "Il manque encore " + ", ".join(manquants)
                    + ". Fais d'abord intervenir les agents concernés, "
                    "puis reviens vers moi. — " + resume_etat())

        # Feedback de la décision précédente : permet au Réviseur de
        # reconnaître des erreurs qui persistent malgré la correction.
        feedback_precedent = (ETAT["decision"] or {}).get("feedback")

        decision = agent_reviseur(
            ETAT["rapport_testeur"], ETAT["rapport_auditeur"],
            ETAT["module"] or {}, iteration_actuelle=ETAT["iteration"],
            max_iterations=ETAT.get("max_iterations") or 3,
            feedback_precedent=feedback_precedent,
            rapport_differentiel=ETAT["rapport_differentiel"],
            rapport_formel=ETAT["rapport_formel"],
        )
        _deposer_decision(decision)
        ETAT["iteration"] += 1
        verdict = decision.get("decision")
        categorie = decision.get("categorie_echec")
        indices = "; ".join(decision.get("indices_categorie") or [])

        # ── Suivi de progression ──
        # Une boucle de correction n'a de sens que si elle progresse.
        # Si le score n'a pas augmenté de façon significative sur deux
        # cycles consécutifs, poursuivre revient à consommer des
        # ressources sans amélioration : on arrête et l'on oriente le
        # module vers une reprise humaine.
        score = decision.get("score_compose", 0.0)
        historique = ETAT.get("scores_successifs") or []
        historique.append(score)
        ETAT["scores_successifs"] = historique

        if verdict in ("ITERER", "REANALYSE_COMPLETE") and len(historique) >= 3:
            trois_derniers = historique[-3:]
            progression = trois_derniers[-1] - trois_derniers[0]
            if progression < 1.0:      # moins d'un point sur deux cycles
                serie = " → ".join(f"{s:.1f}%" for s in trois_derniers)
                decision["indices_categorie"] = [
                    "score stagnant sur deux cycles de correction"]
                _escalader(decision,
                           f"Absence de progression : score stagnant sur "
                           f"deux cycles de correction ({serie}). Les "
                           f"corrections successives n'améliorent plus "
                           f"le module.", "limite_structurelle")
                return (f"Décision : ESCALADE_HUMAINE. Le score stagne "
                        f"({serie}) : les corrections n'apportent plus "
                        f"d'amélioration. Inutile de poursuivre la boucle, "
                        f"le module doit être repris par un opérateur "
                        f"humain. Signale-le dans le bilan final.")

        # ── Budget de tentatives épuisé → escalade humaine ──
        if verdict == "ARRET_ECHEC":
            _escalader(decision,
                       f"Nombre maximum de tentatives atteint "
                       f"({ETAT.get('max_iterations')}) sans atteindre le "
                       f"seuil de qualité. {indices}.",
                       categorie or "limite_structurelle")
            return (f"Décision : ESCALADE_HUMAINE. Le budget de "
                    f"{ETAT.get('max_iterations')} tentative(s) est épuisé "
                    f"(score {score:.1f}%) : le module doit être repris par "
                    f"un opérateur humain. Signale-le dans le bilan final.")

        # ── Réponse adaptée à la nature de l'échec ──
        #   bug simple          → le Développeur corrige
        #   limite structurelle → l'Architecte révise le plan (une fois)
        #   ambiguïté           → un humain tranche
        action = decision.get("action_recommandee")
        if verdict in ("ITERER", "REANALYSE_COMPLETE"):
            if action == "repasser_architecte":
                if (ETAT.get("replanifications") or 0) >= 1:
                    _escalader(decision,
                               f"Limite structurelle persistante après une "
                               f"révision du plan : {indices}.",
                               "limite_structurelle")
                    return ("Décision : ESCALADE_HUMAINE (limite "
                            "structurelle). Les erreurs persistent même "
                            "après la révision du plan par l'Architecte : "
                            "le module doit être repris par un opérateur "
                            "humain. Signale-le dans le bilan final.")
                replan = dict(decision)
                replan["decision"] = "REPLANIFIER"
                replan["raison"] = (f"Échec de type limite structurelle : "
                                    f"{indices}. Le plan doit être revu.")
                _deposer_decision(replan)
                ETAT["revision_plan_en_attente"] = True
                return (f"Décision : REPLANIFIER (score {score:.1f}%, échec de "
                        f"type limite structurelle : {indices}). Relancer "
                        f"le Développeur avec le même plan ne suffira pas : "
                        f"réactive l'Architecte pour réviser le plan, puis "
                        f"le Développeur, puis les quatre vérifications.")
            if action == "escalade_humaine":
                _escalader(decision,
                           f"Échec de type {categorie} : {indices}. Une "
                           f"correction automatique ne peut pas trancher.")
                return (f"Décision : ESCALADE_HUMAINE (échec de type "
                        f"{categorie}). {indices}. La spécification doit "
                        f"être clarifiée par un opérateur humain. "
                        f"Signale-le dans le bilan final.")

        # Récapitulatif honnête de ce qui a réellement été vérifié,
        # afin que le bilan du Manager ne surestime pas la couverture.
        faites, absentes = [], []
        for cle, libelle, agent in attendus:
            (faites if ETAT[cle] else absentes).append(libelle)
        recap = " Vérifications effectuées : " + ", ".join(faites) + "."
        if absentes:
            recap += (" NON EFFECTUÉES (agent non bloquant indisponible) : "
                      + ", ".join(absentes)
                      + " — la livraison reste possible, mais cette "
                        "absence doit figurer explicitement dans le "
                        "rapport de qualité final.")

        confiance = decision.get("confiance") or {}
        detail = ", ".join(
            f"{c['nom']} {c['score']:.0f}%" if c["mesure"]
            else f"{c['nom']} non mesuré"
            for c in confiance.get("criteres", []))
        base = (f"Décision : {verdict} (score de confiance "
                f"{decision.get('score_compose', 0):.1f}%, confiance "
                f"{confiance.get('niveau', '?')} — {detail}).")
        if verdict in ("ITERER", "REANALYSE_COMPLETE"):
            ETAT["correction_demandee"] = True
            instructions = (decision.get("feedback") or {}).get(
                "instructions", [])
            return (base + f" Échec de type {categorie}."
                    + " Corrections demandées : "
                    + " | ".join(instructions[:3])
                    + " → réactive le Développeur, puis fais revérifier."
                    + recap)
        return (base + " Le module est validé, la mission peut s'achever."
                + recap)
    except Exception as e:
        return _echec("Réviseur", e)


# ═══ AGENTS — leurs descriptions déclarent les prérequis ══
# C'est sur ces descriptions que le Manager raisonne pour décider
# qui activer. Aucun ordre n'est écrit : il est déduit des besoins.

analyste = Agent(
    role="Analyste de code legacy",
    goal="Comprendre le code PHP source et en extraire les invariants "
         "de sécurité à préserver ainsi que les failles à corriger",
    backstory="Tu es le point d'entrée de toute migration : personne "
              "ne peut travailler avant que le code source soit compris. "
              "Tu n'as besoin de rien d'autre que le code PHP."
              "RÈGLE ABSOLUE : appelle ton outil UNE seule fois, "
              "puis réponds en reprenant EXACTEMENT le texte "
              "retourné par l'outil, rien de plus. N'écris ni "
              "analyse, ni code, ni explication : ton travail "
              "réel est déjà enregistré dans l'espace de "
              "travail partagé.",
    tools=[outil_analyste], llm=llm,
    allow_delegation=False, verbose=True,
)

architecte = Agent(
    role="Architecte de migration",
    goal="Décider comment le code doit être restructuré en Python",
    backstory="Tu interviens APRÈS l'Analyste : tu as besoin de son "
              "rapport pour planifier. Sans analyse, tu ne peux rien "
              "décider et tu le signales. Tu signales les points "
              "d'attention du code legacy. Tu peux être réactivé si le "
              "Réviseur demande une révision du plan."
              "RÈGLE ABSOLUE : appelle ton outil UNE seule fois, "
              "puis réponds en reprenant EXACTEMENT le texte "
              "retourné par l'outil, rien de plus. N'écris ni "
              "analyse, ni code, ni explication : ton travail "
              "réel est déjà enregistré dans l'espace de "
              "travail partagé.",
    tools=[outil_architecte], llm=llm,
    allow_delegation=False, verbose=True,
)

developpeur = Agent(
    role="Développeur de migration",
    goal="Produire un code Python moderne, sûr et fidèle au PHP",
    backstory="Tu as besoin d'un plan de migration pour travailler. "
              "Tu peux être réactivé plusieurs fois : si le Réviseur "
              "demande des corrections, tu régénères le code en tenant "
              "compte de son retour."
              "RÈGLE ABSOLUE : appelle ton outil UNE seule fois, "
              "puis réponds en reprenant EXACTEMENT le texte "
              "retourné par l'outil, rien de plus. N'écris ni "
              "analyse, ni code, ni explication : ton travail "
              "réel est déjà enregistré dans l'espace de "
              "travail partagé.",
    tools=[outil_developpeur], llm=llm,
    allow_delegation=False, verbose=True,
)

testeur = Agent(
    role="Testeur fonctionnel",
    goal="Vérifier qu'un code Python généré est valide et n'a rien "
         "perdu du comportement d'origine",
    backstory="Tu n'interviens que sur un code Python DÉJÀ généré. "
              "S'il n'en existe aucun, tu le signales au lieu de "
              "travailler dans le vide. Tu es un agent BLOQUANT : sans "
              "ton verdict, aucun module ne peut être livré."
              "RÈGLE ABSOLUE : appelle ton outil UNE seule fois, "
              "puis réponds en reprenant EXACTEMENT le texte "
              "retourné par l'outil, rien de plus. N'écris ni "
              "analyse, ni code, ni explication : ton travail "
              "réel est déjà enregistré dans l'espace de "
              "travail partagé.",
    tools=[outil_testeur], llm=llm,
    allow_delegation=False, verbose=True,
)

differentiel = Agent(
    role="Comparateur",
    goal="Comparer empiriquement les comportements du PHP et du Python",
    backstory="Tu exécutes les deux versions côte à côte. Il te faut "
              "donc un code Python généré. Ton travail est indépendant "
              "des autres vérifications. Tu es un agent NON BLOQUANT : "
              "ton indisponibilité n'empêche pas la livraison, mais "
              "doit être signalée."
              "RÈGLE ABSOLUE : appelle ton outil UNE seule fois, "
              "puis réponds en reprenant EXACTEMENT le texte "
              "retourné par l'outil, rien de plus. N'écris ni "
              "analyse, ni code, ni explication : ton travail "
              "réel est déjà enregistré dans l'espace de "
              "travail partagé.",
    tools=[outil_differentiel], llm=llm,
    allow_delegation=False, verbose=True,
)

verificateur_formel = Agent(
    role="Vérificateur de propriétés",
    goal="Établir que les propriétés de sécurité identifiées sont "
         "préservées par le code produit",
    backstory="Tu vérifies des propriétés précises — validations "
              "d'entrée, invariants métier, contrôles conservés — en "
              "raisonnant sur les entrées possibles plutôt qu'en "
              "testant des exemples. Ta garantie est bornée par un "
              "budget d'exploration : tu établis l'absence de "
              "contre-exemple, non une preuve absolue. Il te faut un "
              "code Python généré. Tu es un agent NON BLOQUANT : ton "
              "indisponibilité n'empêche pas la livraison, mais doit "
              "être signalée."
              "RÈGLE ABSOLUE : appelle ton outil UNE seule fois, "
              "puis réponds en reprenant EXACTEMENT le texte "
              "retourné par l'outil, rien de plus. N'écris ni "
              "analyse, ni code, ni explication : ton travail "
              "réel est déjà enregistré dans l'espace de "
              "travail partagé.",
    tools=[outil_verification_formelle], llm=llm,
    allow_delegation=False, verbose=True,
)

auditeur = Agent(
    role="Auditeur de sécurité",
    goal="Garantir qu'aucune protection n'a été perdue et qu'aucune "
         "faille n'a été introduite",
    backstory="Tu audites un code Python déjà généré. Ton travail est "
              "indépendant des autres vérifications. Tu es un agent "
              "BLOQUANT : la sécurité n'étant pas négociable, aucun "
              "module ne peut être livré sans ton verdict."
              "RÈGLE ABSOLUE : appelle ton outil UNE seule fois, "
              "puis réponds en reprenant EXACTEMENT le texte "
              "retourné par l'outil, rien de plus. N'écris ni "
              "analyse, ni code, ni explication : ton travail "
              "réel est déjà enregistré dans l'espace de "
              "travail partagé.",
    tools=[outil_auditeur], llm=llm,
    allow_delegation=False, verbose=True,
)

reviseur = Agent(
    role="Réviseur",
    goal="Trancher : livrer le module, le faire corriger, ou signaler "
         "un échec",
    backstory="Tu interviens en dernier, quand les QUATRE vérifications "
              "ont été faites : test fonctionnel, comparaison des "
              "comportements, vérification des propriétés et audit de "
              "sécurité. S'il "
              "en manque une, tu refuses de décider et tu dis laquelle. "
              "Tu classes chaque échec par cause : un bug simple fait "
              "réactiver le Développeur, une limite structurelle fait "
              "réactiver l'Architecte, une ambiguïté est confiée à un "
              "humain."
              "RÈGLE ABSOLUE : appelle ton outil UNE seule fois, "
              "puis réponds en reprenant EXACTEMENT le texte "
              "retourné par l'outil, rien de plus. N'écris ni "
              "analyse, ni code, ni explication : ton travail "
              "réel est déjà enregistré dans l'espace de "
              "travail partagé.",
    tools=[outil_reviseur], llm=llm,
    allow_delegation=False, verbose=True,
)

# Le Manager n'est PAS dans la liste des agents : il les coordonne
# depuis l'extérieur.
manager = Agent(
    role="Manager de migration",
    goal="Obtenir un module Python validé à partir du code PHP fourni, "
         "en sollicitant les spécialistes appropriés",
    backstory=(
        "Tu diriges une équipe de spécialistes de la migration de code. "
        "Aucun ordre d'exécution ne t'est imposé : tu décides toi-même "
        "qui solliciter, à quel moment, en fonction de ce qui a déjà "
        "été produit et de ce que rapportent les spécialistes.\n"
        "RÈGLE ABSOLUE : ne sollicite JAMAIS deux fois un spécialiste "
        "pour un travail déjà accompli. Chaque résultat est conservé "
        "dans l'espace de travail partagé : dès qu'un spécialiste t'a "
        "rendu son compte rendu, considère son travail comme acquis et "
        "passe au suivant. Répéter une étape est une erreur grave qui "
        "gaspille les ressources.\n"
        "Chaque spécialiste connaît ses prérequis : s'il te répond "
        "qu'il lui manque quelque chose, sollicite d'abord celui qui "
        "peut le produire, puis reviens vers lui.\n"
        "Si un spécialiste est indisponible, ne bloque pas : poursuis "
        "avec les autres et mentionne la vérification manquante dans "
        "ton bilan.\n"
        "Si le Réviseur demande des corrections, refais intervenir le "
        "Développeur puis fais revérifier le nouveau code. S'il demande "
        "une révision du plan, refais intervenir l'Architecte, puis le "
        "Développeur, puis les vérifications : c'est un travail nouveau, "
        "pas une répétition.\n"
        "JUSTIFIE chaque activation : le champ context de chaque "
        "délégation commence par une ligne « JUSTIFICATION : j'active "
        "<spécialiste> parce que <raison tirée de l'état du module> ».\n"
        "Chaque spécialiste te rappelle, dans sa réponse, ce qui a "
        "déjà été accompli : appuie-toi sur ces retours plutôt que de "
        "solliciter quelqu'un inutilement.\n"
        "Ton bilan final doit être bref : quelques lignes suffisent."
    ),
    llm=llm, allow_delegation=True, verbose=True,
    # Une mission complète (génération, 4 vérifications, décision,
    # corrections, révision du plan) dépasse largement les 25 étapes
    # par défaut de CrewAI : sans marge, le Manager s'arrête avant la
    # décision finale du Réviseur.
    max_iter=80,
)


# Correspondance rôle CrewAI → nom de l'agent dans le journal
ROLE_VERS_AGENT.update({
    analyste.role: "Analyste",
    architecte.role: "Architecte",
    developpeur.role: "Développeur",
    testeur.role: "Testeur",
    differentiel.role: "Comparateur",
    verificateur_formel.role: "Vérificateur de propriétés",
    auditeur.role: "Auditeur",
    reviseur.role: "Réviseur",
})
ROLE_MANAGER = manager.role
_installer_ecoute_manager()


# ═══ LA MISSION — un objectif, pas une séquence ═══════
mission = Task(
    description=(
        "Migrer le code PHP suivant vers du Python moderne et sécurisé.\n\n"
        "CODE PHP :\n```php\n{code_php}\n```\n\n"
        "Le résultat attendu est un module Python analysé, planifié, "
        "généré, vérifié, audité et validé. Détermine toi-même quels "
        "spécialistes solliciter et dans quel ordre, selon ce que tu "
        "découvres à chaque étape."
    ),
    expected_output=(
        "Un bilan de la migration indiquant : le module traité, la "
        "décision finale du Réviseur avec son score, les vérifications "
        "réalisées, et le cas échéant les vérifications manquantes."
    ),
    # Volontairement PAS de agent= : c'est le Manager qui attribue.
)


# ═══ BASCULEMENT DU MODÈLE D'ORCHESTRATION ════════════

import re as _re_panne

# Erreurs qui relèvent du FOURNISSEUR, pas du code : un autre modèle a
# une chance de réussir. Un bug (KeyError, TypeError...) n'en fait pas
# partie : changer de modèle ne le réparerait pas.
MOTIF_PANNE_FOURNISSEUR = _re_panne.compile(
    r"\b(429|500|502|503|504)\b"            # codes HTTP de surcharge/panne
    r"|resource_exhausted|quota|rate.?limit"
    r"|unavailable|overloaded"
    r"|time.?out|timed out"                  # réseau
    r"|connection(error| error| reset| refused| aborted)"
    r"|apiconnectionerror|internal server error",
    _re_panne.IGNORECASE)


def est_panne_fournisseur(erreur: Exception) -> bool:
    """Quota, surcharge, panne ou réseau : l'autre modèle peut aider."""
    return bool(MOTIF_PANNE_FOURNISSEUR.search(
        f"{type(erreur).__name__} {erreur}"))


def appliquer_modele(nom: str) -> bool:
    """Affecte le modèle `nom` au Manager et à tous les agents."""
    global MODELE_ACTIF
    nouveau = llm_pour(nom)
    if nouveau is None:
        return False
    for agent in (manager, analyste, architecte, developpeur, testeur,
                  differentiel, verificateur_formel, auditeur, reviseur):
        agent.llm = nouveau
    MODELE_ACTIF = nom
    ETAT["modele_orchestrateur"] = DESCRIPTIONS_MODELES[nom]
    return True


def _basculer(erreur: Exception) -> bool:
    """
    Passe sur l'autre fournisseur et consigne le basculement.
    Le basculement reste actif pour les modules suivants : un quota
    journalier épuisé ne reviendra pas dans l'heure.
    """
    from datetime import datetime
    depart = MODELE_ACTIF
    FOURNISSEURS_EN_PANNE.add(depart)
    cible = "groq" if depart == "gemini" else "gemini"
    if cible in FOURNISSEURS_EN_PANNE or not appliquer_modele(cible):
        return False
    ETAT.setdefault("bascules_modele", []).append({
        "horodatage": datetime.now().isoformat(timespec="seconds"),
        "de": DESCRIPTIONS_MODELES[depart],
        "vers": DESCRIPTIONS_MODELES[cible],
        "raison": f"{type(erreur).__name__} : {str(erreur)[:160]}",
    })
    print(f"\n  ↪  Basculement de l'orchestrateur : "
          f"{DESCRIPTIONS_MODELES[depart]} → {DESCRIPTIONS_MODELES[cible]}")
    return True


def migrer_module_orchestre(code_php_module: str, module: dict,
                            analyse: dict, contexte_projet: str = "",
                            max_iterations: int = 3,
                            code_php_complet: str = "",
                            code_python_projet: str = "") -> dict:
    """
    Point d'entrée utilisé par la couche projet.

    L'analyse et le plan ont déjà été établis au niveau du projet
    (ordonnancement des fichiers, dépendances). Ils sont déposés
    directement dans l'espace de travail partagé : les agents
    Analyste et Architecte le constateront et n'auront pas à
    refaire ce travail.

    Le Manager orchestre alors la génération, les quatre
    vérifications et la décision, sans qu'aucun ordre ne lui soit
    imposé.

    Retourne le code produit, la décision, et les rapports de
    vérification dans le format attendu par la couche projet.
    """
    reinitialiser_etat(code_php_module)
    ETAT["max_iterations"] = max_iterations
    ETAT["code_php_complet"] = code_php_complet or code_php_module
    ETAT["code_python_projet"] = code_python_projet
    deposer("analyse", analyse, "couche projet",
            points_attention=points_attention_analyse(analyse))
    deposer_plan_et_module({
        "modules": [module],
        "hypotheses_faites": module.get("hypotheses_faites", []),
        "points_incertains": module.get("points_incertains", []),
        "points_attention": module.get("points_attention", []),
    }, module, "couche projet")
    ETAT["contexte_projet"] = contexte_projet

    description_mission = (
            "Obtenir un module Python validé à partir du code PHP "
            "suivant.\n\n"
            f"CODE PHP :\n```php\n{code_php_module}\n```\n\n"
            f"Le module à produire est « {module.get('nom_python', '?')} ». "
            "L'analyse du code et le plan de migration sont DÉJÀ "
            "disponibles dans l'espace de travail partagé : ne les fais "
            "pas refaire.\n"
            "Ta mission consiste à faire produire le code Python, à le "
            "faire vérifier, et à obtenir la décision du Réviseur. "
            "Détermine toi-même quels spécialistes solliciter et dans "
            "quel ordre."
    )
    mission_module = Task(
        description=description_mission,
        expected_output=(
            "La décision finale du Réviseur avec son score, et la liste "
            "des vérifications effectuées."
        ),
    )

    def _equipe():
        return Crew(
            agents=[analyste, architecte, developpeur, testeur,
                    differentiel, verificateur_formel, auditeur, reviseur],
            tasks=[mission_module],
            process=Process.hierarchical,
            manager_agent=manager,
            max_rpm=int(os.getenv("SMAML_RPM", "4")),
            verbose=True,
        )

    # ── Choix de l'orchestrateur pour ce module ──
    # Jamais de substitution silencieuse : si le modèle demandé ne peut
    # pas servir (clé absente, fournisseur déjà en panne), on bascule
    # seulement si c'est autorisé — et le basculement est consigné.
    # Sinon le module part en reprise humaine, sans appel inutile.
    orchestrateur_pret = (MODELE_ACTIF not in FOURNISSEURS_EN_PANNE
                          and appliquer_modele(MODELE_ACTIF))
    if not orchestrateur_pret and BASCULE_AUTORISEE:
        orchestrateur_pret = _basculer(RuntimeError(
            f"orchestrateur {MODELE_ACTIF} indisponible "
            f"(clé absente ou fournisseur en panne)"))
    if not orchestrateur_pret:
        ETAT["agents_en_echec"] = list(
            set((ETAT.get("agents_en_echec") or []) + ["Manager"]))
        print(f"\n  ⚠️  Aucun orchestrateur utilisable pour ce module "
              f"(demandé : {MODELE_ACTIF}, en panne : "
              f"{sorted(FOURNISSEURS_EN_PANNE) or 'aucun'}).")

    # Une panne du LLM orchestrateur (quota épuisé, service
    # indisponible) ne doit pas détruire la migration du projet : les
    # modules déjà traités seraient perdus.
    #   - si le basculement est autorisé, la mission REPREND sur
    #     l'autre modèle : l'espace de travail a gardé tous les dépôts
    #     déjà faits, le nouveau Manager repart de là ;
    #   - sinon, le module est confié à un humain et la couche projet
    #     poursuit avec le module suivant.
    try:
        if orchestrateur_pret:
            _equipe().kickoff()
    except Exception as e:
        reprise_reussie = False
        if est_panne_fournisseur(e):
            FOURNISSEURS_EN_PANNE.add(MODELE_ACTIF)
        if (BASCULE_AUTORISEE and est_panne_fournisseur(e)
                and _basculer(e)):
            try:
                # Le nouveau Manager ne partage pas la mémoire du
                # précédent : on lui dit explicitement qu'il REPREND,
                # et où en est le module.
                mission_module.description = (
                    description_mission
                    + "\n\nREPRISE : un premier orchestrateur a été "
                      "interrompu. Le travail déjà fait est conservé dans "
                      "l'espace de travail — ne le fais pas refaire. "
                    + resume_etat())
                _equipe().kickoff()
                reprise_reussie = True
            except Exception as e2:
                if est_panne_fournisseur(e2):
                    FOURNISSEURS_EN_PANNE.add(MODELE_ACTIF)
                e = e2
        if not reprise_reussie:
            ETAT["agents_en_echec"] = list(
                set((ETAT.get("agents_en_echec") or []) + ["Manager"]))
            print(f"\n  ⚠️  Orchestration interrompue : "
                  f"{type(e).__name__} — {str(e)[:200]}")

    # Reconstitution du rapport attendu par la couche projet :
    # l'équivalence et la vérification des propriétés y sont rattachées
    # au rapport du Testeur, comme dans le mode direct.
    rapport_testeur = ETAT["rapport_testeur"] or {
        "score_fonctionnel": 0.0,
        "syntaxe": {"syntaxe_valide": False,
                    "erreur": "Testeur non sollicité"},
        "invariants": {"invariants_verifies": [],
                       "invariants_manquants": [], "score": 0.0},
        "failles": {"score": 0.0, "failles_persistantes": []},
    }
    rapport_testeur["equivalence_comportementale"] = \
        ETAT["rapport_differentiel"]
    rapport_testeur["verification_formelle"] = ETAT["rapport_formel"]

    # ── Mission interrompue avant une décision finale ──
    # Le Manager peut s'arrêter (limite d'étapes, erreur LLM) alors que
    # la dernière décision n'est qu'intermédiaire (ITERER, REPLANIFIER)
    # ou absente. Son bilan textuel peut alors inventer un verdict : on
    # ne s'y fie pas, et le module est confié à un humain.
    decision = ETAT["decision"]
    if not decision or decision.get("decision") not in (
            "LIVRER", "ESCALADE_HUMAINE", "ARRET_ECHEC"):
        derniere = (decision or {}).get("decision") or "aucune"
        panne_manager = "Manager" in (ETAT.get("agents_en_echec") or [])
        _escalader(decision or {"score_compose": 0.0,
                                "iteration": ETAT["iteration"]},
                   ("Orchestrateur indisponible (quota ou service) : le "
                    "module doit être repris."
                    if panne_manager else
                    f"Orchestration interrompue avant la décision finale "
                    f"du Réviseur (dernière décision : {derniere}). Le "
                    f"module n'a pas été validé."))
        decision = ETAT["decision"]
    decision.setdefault("iteration", ETAT["iteration"])

    return {
        "code_python": ETAT["code_python"],
        "decision": decision,
        "rapport_testeur": rapport_testeur,
        "rapport_auditeur": ETAT["rapport_auditeur"],
        "agents_en_echec": list(ETAT["agents_en_echec"] or []),
        "etat_structure": etat_structure(),
        "journal": list(ETAT.get("journal") or []),
        "historique": ETAT.get("historique") or {},
        "decisions_manager": list(ETAT.get("decisions_manager") or []),
        "cache": cache_smaml.statistiques(),
    }


def lancer_migration(code_php: str) -> dict:
    """Lance la migration orchestrée d'un code PHP."""
    reinitialiser_etat(code_php)

    # Même garantie que pour la migration de projet : le modèle
    # demandé, ou un échec explicite — jamais un autre en silence.
    if not appliquer_modele(MODELE_ACTIF):
        raise RuntimeError(
            f"Orchestrateur demandé indisponible : {MODELE_ACTIF} "
            f"(clé absente). Fournis la clé, ou choisis l'autre modèle "
            f"avec SMAML_MANAGER.")

    equipe = Crew(
        agents=[analyste, architecte, developpeur, testeur,
                differentiel, verificateur_formel, auditeur, reviseur],
        tasks=[mission],                 # UNE seule tâche
        process=Process.hierarchical,    # le Manager orchestre
        manager_agent=manager,           # hors de la liste agents
        # Le palier gratuit limite le nombre de requêtes par minute. Le
        # mode hiérarchique en consomme plusieurs par étape (le Manager
        # délibère, l'agent répond) : on plafonne le débit pour que
        # CrewAI attende de lui-même au lieu d'échouer.
        max_rpm=int(os.getenv("SMAML_RPM", "4")),
        verbose=True,
    )

    resultat = equipe.kickoff(inputs={"code_php": code_php})

    return {
        "bilan": str(resultat),
        "code_python": ETAT["code_python"],
        "decision": ETAT["decision"],
        "agents_en_echec": ETAT["agents_en_echec"],
    }


# ═══ LANCEMENT ════════════════════════════════════════
# Usage : py crewai_pipeline.py [fichier.php]
if __name__ == "__main__":

    EXEMPLE = """<?php
function validatePassword($password) {
    if (strlen($password) < 8) {
        throw new Exception('Trop court');
    }
    return true;
}
?>"""

    if len(sys.argv) > 1:
        chemin = sys.argv[1]
        if not os.path.isfile(chemin):
            print(f"Fichier introuvable : {chemin}")
            sys.exit(1)
        with open(chemin, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
        print(f"Code PHP chargé depuis : {chemin}")
    else:
        code = EXEMPLE
        print("Aucun fichier fourni — exemple intégré utilisé.")

    resultat = lancer_migration(code)

    print("\n" + "=" * 60)
    print("BILAN DE LA MIGRATION")
    print("=" * 60)
    print(resultat["bilan"])
    if resultat["agents_en_echec"]:
        print(f"\nAgents indisponibles pendant la migration : "
              f"{', '.join(resultat['agents_en_echec'])}")
    if resultat["code_python"]:
        print("\n--- CODE PYTHON PRODUIT ---")
        print(resultat["code_python"])