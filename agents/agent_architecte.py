import json
from huggingface_hub import InferenceClient

def planifier_migration(rapport_analyste: dict) -> dict:
    """
    Agent Architecte — SMAML
    Reçoit le rapport de l'Agent Analyste et produit
    un plan de migration structuré en JSON.
    """

    # Préparer le contexte pour le LLM
    fonctions = rapport_analyste.get("fonctions", [])
    invariants = rapport_analyste.get("invariants_securite", [])
    failles = rapport_analyste.get("failles_potentielles", [])
    metriques = rapport_analyste.get("metriques", {})

    # Choisir le pattern de migration selon la complexité
    complexite = metriques.get("complexite_estimee", "faible")
    if complexite == "elevee":
        pattern = "Strangler Fig"
        pattern_desc = "Migration progressive module par module"
    else:
        pattern = "Big Bang"
        pattern_desc = "Migration complète en une fois"

    # Construire le plan de migration
    plan = {
        "pattern_migration": pattern,
        "pattern_description": pattern_desc,
        "langage_source": "PHP",
        "langage_cible": "Python",
        "framework_cible": "FastAPI + Pydantic",
        "modules": [],
        "ordre_migration": [],
        "interfaces": [],
        "priorites_securite": []
    }

    # Créer un module par fonction
    for i, fonction in enumerate(fonctions):
        module = {
            "id": i + 1,
            "nom_original": fonction["nom"],
            "nom_python": convertir_nom(fonction["nom"]),
            "parametres": fonction["parametres"],
            "lignes_source": fonction.get("lignes", {}),
            "priorite": "haute" if any(
                f["type"] in ["sql_injection", "command_injection"]
                for f in failles
                if fonction["nom"].lower() in f.get("code", "").lower()
            ) else "normale"
        }
        plan["modules"].append(module)
        plan["ordre_migration"].append(module["nom_python"])

    # Définir les priorités sécurité
    for faille in failles:
        plan["priorites_securite"].append({
            "faille": faille["type"],
            "cwe": faille["cwe"],
            "severity": faille["severity"],
            "action": f"Remplacer par équivalent Python sécurisé"
        })

    # Définir les interfaces entre modules
    if len(fonctions) > 1:
        plan["interfaces"].append({
            "type": "FastAPI Router",
            "description": "Tous les modules exposés via endpoints FastAPI",
            "format": "JSON + Pydantic validation"
        })

    # Ajouter les invariants à préserver
    plan["invariants_a_preserver"] = [
        {
            "type": inv["type"],
            "description": inv["description"],
            "obligatoire": True
        }
        for inv in invariants
    ]

    return plan


def convertir_nom(nom_php: str) -> str:
    """
    Convertit un nom camelCase PHP en snake_case Python.
    Exemple : validatePassword → validate_password
    """
    import re
    # Insérer underscore avant les majuscules
    s = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', nom_php)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s).lower()


# ─── TEST ────────────────────────────────────────────
if __name__ == "__main__":

    # Simuler le rapport de l'Agent Analyste
    rapport_analyste = {
        "langage_source": "php",
        "fonctions": [
            {
                "nom": "validatePassword",
                "parametres": ["$password"],
                "corps_resume": "if (strlen($password) < 8)...",
                "lignes": {"debut": 2, "fin": 13}
            },
            {
                "nom": "getUser",
                "parametres": ["$id"],
                "corps_resume": "mysql_query($sql)...",
                "lignes": {"debut": 15, "fin": 22}
            },
            {
                "nom": "executeCommand",
                "parametres": ["$cmd"],
                "corps_resume": "shell_exec($cmd)...",
                "lignes": {"debut": 24, "fin": 27}
            }
        ],
        "invariants_securite": [
            {
                "type": "validation_longueur",
                "description": "Vérification de longueur de champ",
                "a_preserver": True
            },
            {
                "type": "validation_format",
                "description": "Vérification de format ou pattern",
                "a_preserver": True
            }
        ],
        "failles_potentielles": [
            {
                "type": "sql_injection",
                "cwe": "CWE-89",
                "severity": "critical",
                "code": "mysql_query($sql)"
            },
            {
                "type": "command_injection",
                "cwe": "CWE-78",
                "severity": "critical",
                "code": "shell_exec($cmd)"
            }
        ],
        "metriques": {
            "nombre_fonctions": 3,
            "nombre_invariants": 2,
            "nombre_failles": 2,
            "complexite_estimee": "moyenne"
        }
    }

    print("Agent Architecte SMAML — Planification en cours...")
    print("=" * 60)

    plan = planifier_migration(rapport_analyste)

    print(json.dumps(plan, indent=2, ensure_ascii=False))

    print("\n" + "=" * 60)
    print("RÉSUMÉ DU PLAN :")
    print(f"  Pattern migration  : {plan['pattern_migration']}")
    print(f"  Modules à migrer   : {len(plan['modules'])}")
    print(f"  Priorités sécurité : {len(plan['priorites_securite'])}")
    print(f"  Invariants         : {len(plan['invariants_a_preserver'])}")
    print(f"  Ordre migration    : {plan['ordre_migration']}")
    print("\n✅ Agent Architecte opérationnel !")