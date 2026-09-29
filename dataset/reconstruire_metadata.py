"""
Reconstruction des métadonnées du RAG — SMAML
==============================================
    py -X utf8 reconstruire_metadata.py

Pourquoi
--------
`metadata.json` ne contenait que l'identifiant, la description et la
catégorie de chaque exemple — pas le code. Or le Développeur construit
son prompt ainsi :

    php = exemple.get("code_php", "")
    py  = exemple.get("code_python", "")
    if php and py:        # ← jamais vrai
        ...

Le bloc d'exemples envoyé au LLM était donc toujours vide : la
recherche RAG tournait sans que le modèle n'en voie jamais le résultat.

Ce script reconstruit `metadata.json` à partir de `dataset_final.json`,
en y ajoutant le code. L'index FAISS n'est PAS retouché : l'ordre des
entrées est identique (même filtre, même ordre que `indexer.py`), donc
les vecteurs déjà calculés restent valides. Aucun ré-encodage, aucune
utilisation de CodeBERT.
"""

import json
import os

DOSSIER = os.path.dirname(os.path.abspath(__file__))

# Le script peut être lancé depuis le dossier dataset/ comme depuis
# agents/ : on cherche dataset_final.json aux endroits habituels.
CANDIDATS = [
    os.path.join(DOSSIER, "dataset_final.json"),
    os.path.join(DOSSIER, "dataset", "dataset_final.json"),
    os.path.join(os.path.dirname(DOSSIER), "dataset", "dataset_final.json"),
]
DATASET = next((c for c in CANDIDATS if os.path.exists(c)), None)
if DATASET is None:
    raise SystemExit(
        "dataset_final.json introuvable. Lance le script depuis le "
        "dossier qui le contient, ou depuis agents/.")
METADATA = os.path.join(os.path.dirname(DATASET), "metadata.json")

# Longueur maximale conservée par exemple : au-delà, le prompt
# deviendrait trop lourd et coûterait des tokens pour rien.
LONGUEUR_MAX = 1200


def reconstruire():
    with open(DATASET, encoding="utf-8") as f:
        dataset = json.load(f)

    # MÊME filtre et MÊME ordre que indexer.py, sinon les vecteurs de
    # l'index ne correspondraient plus aux métadonnées.
    dataset = [p for p in dataset if p.get("code_php")]

    metadata, avec_python = [], 0
    for paire in dataset:
        code_python = paire.get("code_python")
        entree = {
            "id": paire.get("id"),
            "description": paire.get("description", ""),
            "categorie": paire.get("categorie", ""),
            "source": paire.get("source", ""),
            "cwe": paire.get("cwe"),
            "severity": paire.get("severity"),
            "avec_python": bool(code_python),
        }
        # Le code n'est conservé que pour les paires réellement
        # traduites : les autres ne peuvent pas servir d'exemple.
        if code_python:
            avec_python += 1
            entree["code_php"] = paire["code_php"][:LONGUEUR_MAX]
            entree["code_python"] = code_python[:LONGUEUR_MAX]
            entree["invariant"] = paire.get("invariant")
        metadata.append(entree)

    with open(METADATA, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"metadata.json reconstruit : {METADATA}")
    print(f"  {len(metadata)} entrées")
    print(f"  dont {avec_python} avec traduction Python "
          f"(utilisables comme exemples)")
    print(f"  {len(metadata) - avec_python} entrées PHP seules "
          f"(CodeSearchNet) : indexées, mais jamais montrées au LLM")
    taille = os.path.getsize(METADATA) / 1024
    print(f"  taille : {taille:.0f} Ko")


if __name__ == "__main__":
    reconstruire()