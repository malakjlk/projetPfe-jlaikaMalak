"""
Configurations de l'étude d'ablation — SMAML
=============================================
Une seule variable règle tous les interrupteurs, pour qu'aucune série
de mesures ne puisse être lancée avec un réglage à moitié changé :

    set SMAML_CONFIG=llm_seul        puis lancer le pipeline

Les quatre configurations comparées :

    llm_seul      LLM seul, sans RAG ni boucle de correction
    rag           LLM + RAG                  → apport des 3 060 exemples
    rag_boucle    LLM + RAG + correction     → apport de l'itération
    complet       système multi-agents       → apport de l'orchestration

Ce qui NE se désactive JAMAIS
-----------------------------
Les quatre vérifications (Testeur, Comparateur, Vérificateur de
propriétés, Auditeur) et le calcul du score de confiance tournent dans
toutes les configurations : ce sont les instruments de mesure. Couper
la boucle de correction ne veut donc pas dire « ne pas vérifier », mais
« ne pas renvoyer le code au Développeur » : on mesure le premier code
produit.

Ce module est importé AVANT les autres : il règle les variables
d'environnement que le pipeline lit ensuite.
"""

import os

CONFIGURATIONS = {
    "llm_seul": {
        "titre": "LLM seul",
        "description": "génération directe, sans exemples ni correction",
        "variables": {"SMAML_SANS_RAG": "1", "SMAML_SANS_BOUCLE": "1",
                      "SMAML_MODE": "direct"},
    },
    "rag": {
        "titre": "LLM + RAG",
        "description": "génération guidée par les exemples similaires",
        "variables": {"SMAML_SANS_RAG": "", "SMAML_SANS_BOUCLE": "1",
                      "SMAML_MODE": "direct"},
    },
    "rag_boucle": {
        "titre": "LLM + RAG + boucle de correction",
        "description": "le Réviseur peut renvoyer le code au Développeur",
        "variables": {"SMAML_SANS_RAG": "", "SMAML_SANS_BOUCLE": "",
                      "SMAML_MODE": "direct"},
    },
    "complet": {
        "titre": "Système multi-agents complet",
        "description": "orchestration dynamique par le Manager",
        "variables": {"SMAML_SANS_RAG": "", "SMAML_SANS_BOUCLE": "",
                      "SMAML_MODE": "orchestre"},
    },
    # La spécialisation du modèle ne passe pas par un affinage mais par
    # des patrons de génération propres à chaque type de faille. Cette
    # configuration les retire pour en mesurer l'apport.
    "sans_patrons": {
        "titre": "Système complet sans patrons de génération",
        "description": "mesure l'apport de la spécialisation par patrons",
        "variables": {"SMAML_SANS_RAG": "", "SMAML_SANS_BOUCLE": "",
                      "SMAML_SANS_PATRONS": "1", "SMAML_MODE": "orchestre"},
    },
}


def appliquer_configuration() -> str:
    """
    Applique SMAML_CONFIG si elle est définie. Retourne le nom de la
    configuration active, ou "" si les interrupteurs sont réglés à la
    main (cas d'un usage normal, hors mesures).
    """
    nom = (os.getenv("SMAML_CONFIG") or "").strip().lower()
    if not nom:
        return ""
    if nom not in CONFIGURATIONS:
        raise SystemExit(
            f"Configuration inconnue : « {nom} ». "
            f"Valeurs possibles : {', '.join(CONFIGURATIONS)}")
    for variable, valeur in CONFIGURATIONS[nom]["variables"].items():
        if valeur:
            os.environ[variable] = valeur
        else:
            os.environ.pop(variable, None)
    return nom


def description_active() -> dict:
    """Réglages réellement actifs — à recopier dans le rapport."""
    nom = (os.getenv("SMAML_CONFIG") or "").strip().lower()
    return {
        "configuration": nom or "réglages manuels",
        "titre": CONFIGURATIONS.get(nom, {}).get("titre", "—"),
        "rag": not os.getenv("SMAML_SANS_RAG"),
        "patrons": not os.getenv("SMAML_SANS_PATRONS"),
        "boucle_correction": not os.getenv("SMAML_SANS_BOUCLE"),
        "mode": os.getenv("SMAML_MODE", "direct"),
        "orchestrateur_demande": os.getenv("SMAML_MANAGER", "gemini"),
        "bascule_autorisee": os.getenv("SMAML_BASCULE", "0") in
                             ("1", "true", "oui"),
        "cache": os.getenv("SMAML_CACHE", "1") not in ("0", "false", "non"),
        "mode_strict": bool(os.getenv("SMAML_STRICT")),
    }


CONFIG_ACTIVE = appliquer_configuration()


if __name__ == "__main__":
    import json
    print("Configurations disponibles :\n")
    for nom, c in CONFIGURATIONS.items():
        print(f"  {nom:<12} {c['titre']}")
        print(f"  {'':<12} {c['description']}")
    print("\nRéglages actifs :")
    print(json.dumps(description_active(), indent=2, ensure_ascii=False))