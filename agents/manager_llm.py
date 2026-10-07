"""
Manager LLM — SMAML
====================
Le Manager coordonne : c'est un agent CrewAI dont les décisions —
quel spécialiste solliciter, et quand — sont prises par un LLM.

Ce qui change par rapport à la version précédente
-------------------------------------------------
  • Les outils des spécialistes travaillent sur l'ESPACE PARTAGÉ
    PERSISTANT, et refusent d'agir hors de leur phase : le Manager est
    libre de l'ordre, jamais de sauter une étape (option A).
  • Il n'y a plus de basculement de modèle à l'intérieur du Manager :
    c'est la SUPERVISION qui gère les pannes. Le Manager principal et
    le Manager de secours sont deux coordinateurs distincts, chacun avec
    son LLM, et la chaîne passe de l'un à l'autre si le premier échoue
    ou cesse d'avancer — quelle qu'en soit la cause.

Deux niveaux
------------
  • projet : phase 2 — Analyste, puis Architecte
  • module : phases 3 et 4 — Développeur, quatre vérifications, Réviseur

Réglages
--------
  SMAML_MANAGER_MODELE           Manager principal (défaut gemini/gemini-3.6-flash)
  SMAML_MANAGER_SECOURS          Manager de secours (défaut gemini/gemini-3.5-flash)
                                 forme « gemini/<modèle> » ou « groq/<modèle> »
  SMAML_RPM=4                    plafond de requêtes par minute
"""

from __future__ import annotations

import json
import os
import threading

import outils_agents as oa
from espace_partage import EspaceModule
from supervision import Coordinateur

ROLE_MANAGER = "Manager de migration"

# Chaque rôle a SON modèle, donc son propre quota. Le Manager de secours
# ne doit surtout pas utiliser gpt-oss-120b : c'est le modèle du
# Développeur, et il en épuiserait le quota journalier.
#   gpt-oss-120b (Groq)        → Développeur
#   qwen3.8-27b (Groq)         → LLM juge
#   gemini-3.8-flash           → Développeur de secours
#   gemini-3.6-flash           → Manager principal
#   gemini-3.5-flash           → Manager de secours
def modeles_manager() -> dict:
    return {
        "principal": os.getenv("SMAML_MANAGER_MODELE", "gemini/gemini-3.6-flash"),
        "secours": os.getenv("SMAML_MANAGER_SECOURS", "gemini/gemini-3.5-flash"),
    }


def _fournisseur(modele: str) -> str:
    return "groq" if modele.startswith("groq/") else "gemini"


def creer_llm(modele: str):
    """LLM du Manager (« gemini/… » ou « groq/… »), ou None si la clé manque."""
    from crewai import LLM
    if _fournisseur(modele) == "groq":
        cle = os.getenv("GROQ_TOKEN")
        if not cle:
            return None
        return LLM(model=f"openai/{modele[len('groq/'):]}",
                   base_url="https://api.groq.com/openai/v1",
                   api_key=cle, temperature=0.1)
    cle = os.getenv("GEMINI_API_KEY")
    if not cle:
        return None
    return LLM(model=modele, api_key=cle, temperature=0.1)


def managers_disponibles(niveau: str) -> list:
    """Manager principal puis Manager de secours, chacun avec son modèle."""
    import crewai  # noqa: F401 — vérifie la présence de CrewAI
    managers = []
    for rang, modele in modeles_manager().items():
        cle = os.getenv("GROQ_TOKEN") if _fournisseur(modele) == "groq" \
            else os.getenv("GEMINI_API_KEY")
        if cle:
            managers.append(ManagerLLM(niveau, modele, f"manager_{rang}"))
    return managers


# ═══ JUSTIFICATIONS DU MANAGER ═════════════════════════
# Chaque délégation du Manager est captée sur le bus d'événements de
# CrewAI ; sa justification est consignée dans le journal de l'espace
# partagé avec l'issue de la sollicitation.

_justifications = {}
_verrou = threading.Lock()
_ecoute_installee = False


def _installer_ecoute():
    global _ecoute_installee
    if _ecoute_installee:
        return
    try:
        from crewai.events import crewai_event_bus, ToolUsageStartedEvent
    except ImportError:
        try:
            from crewai.utilities.events import crewai_event_bus, ToolUsageStartedEvent
        except ImportError:
            return

    @crewai_event_bus.on(ToolUsageStartedEvent)
    def _delegation(source, event):
        if (getattr(event, "agent_role", "") or "").strip() != ROLE_MANAGER:
            return
        nom = (getattr(event, "tool_name", "") or "").casefold()
        if "coworker" not in nom and "deleg" not in nom:
            return
        args = getattr(event, "tool_args", {}) or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {"task": args}
        texte = f"{args.get('context', '')}\n{args.get('task', '')}"
        justification = next(
            (l.split(":", 1)[-1].strip() for l in texte.splitlines()
             if l.strip().upper().startswith("JUSTIFICATION")),
            str(args.get("task", ""))[:300])
        agent = str(args.get("coworker", "")).strip().casefold()
        with _verrou:
            _justifications.setdefault(agent, []).append(justification)

    _ecoute_installee = True


def _prendre_justification(role: str):
    with _verrou:
        for cle, file in _justifications.items():
            if file and (cle == role.casefold() or role.casefold() in cle):
                return file.pop(0)
    return None


# ═══ OUTILS CREWAI, LIÉS À L'ESPACE DU MODULE ══════════

def _outil(nom_outil, role, description, action, espace):
    """
    Enveloppe une action en outil CrewAI : refus de phase et travail
    déjà fait deviennent des réponses claires pour le Manager, et chaque
    sollicitation est consignée dans le journal de l'espace partagé.
    """
    from crewai.tools import tool

    def executer(note: str = "") -> str:
        try:
            resultat, issue = action(), "execute"
        except oa.PrerequisManquant as e:
            resultat, issue = f"PRÉREQUIS MANQUANT : {e}", "refus_prerequis"
        except oa.DejaFait as e:
            resultat, issue = f"DÉJÀ FAIT : {e}", "deja_fait"
        except Exception as e:                       # agent en panne
            resultat, issue = (f"AGENT INDISPONIBLE : {type(e).__name__} — "
                               f"{str(e)[:200]}"), "indisponible"
            espace.noter("agent_indisponible", agent=role, erreur=str(e)[:200])
        espace.journaliser({"agent": role, "issue": issue,
                            "justification_manager": _prendre_justification(role),
                            "resultat": resultat[:200]})
        espace.rafraichir()
        return f"{resultat} — Prochaine étape : {_prochaine_etape(espace)}."

    executer.__doc__ = description
    executer.__name__ = nom_outil.replace(" ", "_")
    return tool(nom_outil)(executer)


def _prochaine_etape(espace) -> str:
    """
    Ce qu'il reste à faire, exprimé en AGENTS à solliciter. Lui dire
    « reste : rapport_differentiel » faisait tourner le Manager en rond :
    il ne savait pas que c'est le travail du Comparateur.
    """
    if "module" in espace:
        if espace.get("correction_demandee"):
            return ("solliciter le Développeur : le Réviseur a demandé une "
                    "correction")
        agents = [oa.ETAPES_MODULE[p][1] for p in oa.etapes_restantes(espace)]
    else:
        agents = [nom for produit, nom in (("analyse_projet", "Analyste"),
                                           ("plan_projet", "Architecte"))
                  if produit not in espace]
    if not agents:
        return "aucune — tout est fait, rédige ton bilan final et termine"
    return "solliciter " + ", puis ".join(agents)


SPECIALISTES_MODULE = [
    ("Développeur", "code_python", "Produire le code Python",
     "Traduit le module PHP en Python moderne et sécurisé. Phase 3."),
    ("Testeur", "rapport_testeur", "Tester le code",
     "Vérifie la syntaxe, les invariants et les failles du code. Phase 4."),
    ("Comparateur", "rapport_differentiel", "Comparer PHP et Python",
     "Exécute les deux codes sur les mêmes entrées et compare. Phase 4."),
    ("Vérificateur de propriétés", "rapport_formel", "Vérifier les propriétés",
     "Exploration symbolique des propriétés par Z3. Phase 4."),
    ("Auditeur", "rapport_auditeur", "Auditer la sécurité",
     "Failles, invariants préservés, dépendances vulnérables. Phase 4."),
    ("Réviseur", "decision", "Décider",
     "Calcule le score de confiance et décide. Exige les 4 vérifications."),
]


# ═══ LE COORDINATEUR ═══════════════════════════════════

class ManagerLLM(Coordinateur):
    """Coordinateur dont les décisions sont prises par un LLM."""

    def __init__(self, niveau: str, modele: str, nom: str):
        self.niveau_coordination = niveau
        self.modele = modele
        self.fournisseur = _fournisseur(modele)
        self.nom = nom
        self.niveau = f"llm:{modele}"

    def _manager(self, llm):
        from crewai import Agent
        return Agent(
            role=ROLE_MANAGER,
            goal="Mener le travail à terme en sollicitant les spécialistes appropriés",
            backstory=(
                "Tu diriges une équipe de spécialistes. Aucun ordre d'exécution ne "
                "t'est imposé : tu décides qui solliciter et quand, d'après ce qui "
                "est déjà produit.\n"
                "Le travail suit des phases : analyse, puis conversion, puis "
                "vérification, puis décision. Un spécialiste sollicité hors de sa "
                "phase te répond PRÉREQUIS MANQUANT : sollicite alors celui qui peut "
                "produire ce qui manque.\n"
                "Ne sollicite JAMAIS deux fois un spécialiste pour un travail déjà "
                "fait (réponse DÉJÀ FAIT). Chaque réponse t'indique ce qui reste à "
                "faire : appuie-toi dessus.\n"
                "Si le Réviseur demande une correction, refais intervenir le "
                "Développeur, puis les vérifications, puis le Réviseur.\n"
                "Si un spécialiste est INDISPONIBLE, poursuis avec les autres.\n"
                "JUSTIFIE chaque activation : le champ context de chaque délégation "
                "commence par « JUSTIFICATION : j'active <spécialiste> parce que "
                "<raison> ».\n"
                "Tes consignes tiennent en deux phrases et ne contiennent JAMAIS de "
                "code : chaque spécialiste lit lui-même l'espace de travail partagé.\n"
                "Ton bilan final est bref."),
            llm=llm, allow_delegation=True, verbose=True)

    def _specialistes(self, espace, llm):
        from crewai import Agent
        if self.niveau_coordination == "projet":
            import orchestration
            definitions = [
                ("Analyste", lambda: orchestration.outil_analyse_projet(espace),
                 "Analyser le projet", "Constate les fichiers, failles, dépendances "
                 "et champs attendus. Phase 2."),
                ("Architecte", lambda: orchestration.outil_plan_projet(espace),
                 "Planifier la migration", "Décide l'ordre de migration, les modules "
                 "et le découpage en services. Phase 2, après l'Analyste."),
            ]
        else:
            definitions = [(role, (lambda p=produit: oa.realiser(espace, p)),
                            outil, desc)
                           for role, produit, outil, desc in SPECIALISTES_MODULE]
        return [Agent(role=role, goal=desc, backstory=desc,
                      tools=[_outil(outil, role, desc, action, espace)],
                      llm=llm, allow_delegation=False, verbose=False)
                for role, action, outil, desc in definitions]

    def _mission(self, espace):
        from crewai import Task
        if self.niveau_coordination == "projet":
            texte = ("Le projet PHP a été reçu (phase 1). Fais réaliser la phase 2 : "
                     "l'analyse du code par l'Analyste, puis le plan de migration "
                     "par l'Architecte.")
            attendu = "Le plan de migration est déposé."
        else:
            module = espace.get("module") or {}
            texte = (f"Obtenir le module Python « {module.get('nom_python')} » validé : "
                     "fais-le produire (phase 3), fais-le vérifier par les quatre "
                     "vérificateurs (phase 4), puis obtiens la décision du Réviseur. "
                     "Les analyses et le plan sont déjà dans l'espace partagé.")
            attendu = "La décision du Réviseur et les vérifications effectuées."
        return Task(description=texte, expected_output=attendu)

    def coordonner(self, espace: EspaceModule) -> dict:
        from crewai import Crew, Process
        llm = creer_llm(self.modele)
        if llm is None:
            raise RuntimeError(f"clé absente pour {self.modele}")
        _installer_ecoute()
        espace.noter("coordination_demarree", coordinateur=self.nom,
                     modele=self.modele)
        Crew(agents=self._specialistes(espace, llm), tasks=[self._mission(espace)],
             process=Process.hierarchical, manager_agent=self._manager(llm),
             max_rpm=int(os.getenv("SMAML_RPM", "4")), verbose=True).kickoff()

        # La mission n'est réussie que si l'espace partagé le prouve :
        # le bilan textuel du Manager ne compte pas.
        espace.rafraichir()
        if self.niveau_coordination == "projet":
            if "plan_projet" not in espace:
                raise RuntimeError("mission inachevée : aucun plan déposé")
        elif "decision" not in espace or espace.get("correction_demandee"):
            raise RuntimeError("mission inachevée : aucune décision finale déposée")
        return {"coordonne_par": self.nom, "modele": self.modele}


if __name__ == "__main__":
    # Vérification en direct des modèles du Manager :
    #   py -X utf8 manager_llm.py --essai                      modèles configurés
    #   py -X utf8 manager_llm.py --essai gemini/<m> groq/<m>  candidats à tester
    import sys
    if "--essai" not in sys.argv:
        print(__doc__)
        sys.exit(0)
    candidats = [a for a in sys.argv[1:] if a != "--essai"]
    a_tester = ([(f"candidat {i + 1}", m) for i, m in enumerate(candidats)]
                if candidats else list(modeles_manager().items()))
    print("Vérification des modèles du Manager\n")
    for rang, modele in a_tester:
        try:
            llm = creer_llm(modele)
            if llm is None:
                print(f"  {rang:<12} {modele:<38} [ECHEC] clé absente")
                continue
            reponse = llm.call("Réponds uniquement par le mot : OK")
            print(f"  {rang:<12} {modele:<38} [OK] répond ({str(reponse).strip()[:30]})")
        except Exception as erreur:
            print(f"  {rang:<12} {modele:<38} [ECHEC] {type(erreur).__name__} : "
                  f"{str(erreur)[:110]}")