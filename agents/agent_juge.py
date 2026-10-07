"""
LLM juge — SMAML
=================
Un modèle de langage évalue la qualité du code migré, selon une grille,
comme un enseignant note un travail. Sa note compte dans la décision du
Réviseur — dans des limites strictes.

Ce que le juge apporte
----------------------
Les vérifications déterministes mesurent l'exécution, l'équivalence,
les failles et les propriétés. Elles ne savent pas juger si le code
traduit FIDÈLEMENT L'INTENTION du PHP, s'il est lisible, idiomatique,
bien structuré, bien documenté. C'est ce que mesure le juge.

Les garde-fous
--------------
  1. Une autre famille de modèle que le générateur : le code est produit
     par gpt-oss (OpenAI) ; il est jugé par Kimi (Moonshot AI). Un juge
     de la même famille favoriserait ses propres productions.
  2. Une grille : cinq critères notés de 1 à 5, chaque niveau décrit.
     La justification est écrite AVANT la note.
  3. Le juge ne voit QUE le PHP et le Python, jamais les rapports des
     outils — sinon il les recopierait au lieu de juger.
  4. Température nulle : à code identique, jugement identique.
  5. Dans le Réviseur, sa note a un poids limité, et il ne peut JAMAIS
     lever un verrou : code inexécutable, propriété réfutée par Z3,
     faille critique. Un désaccord fort avec les outils déclenche une
     validation humaine.
  6. Il doit être ÉTALONNÉ sur des jugements humains avant que ses notes
     aient une valeur (voir etalonnage_juge.py).

Réglages
--------
  SMAML_MODELE_JUGE      modèle du juge chez Groq
                         (défaut : moonshotai/kimi-k2-instruct-0905)
  SMAML_CHAINE_JUGE      fournisseurs du juge (défaut : groq)
  SMAML_JUGE=0           désactive le juge

    py -X utf8 agent_juge.py --modeles    modèles Kimi proposés par Groq
    py -X utf8 agent_juge.py --essai      jugement réel d'un exemple
"""

from __future__ import annotations

import json
import os
import re

import cache_smaml
import fournisseurs_llm

VERSION_GRILLE = "1"

GRILLE = {
    "fidelite_intention": (
        "Fidélité à l'intention du code d'origine",
        "1 : le code Python fait autre chose que le PHP · "
        "3 : l'essentiel est préservé, des cas sont perdus · "
        "5 : toute l'intention du PHP est préservée, y compris les cas limites"),
    "lisibilite": (
        "Lisibilité et style Python idiomatique",
        "1 : illisible ou calqué mot à mot sur le PHP · "
        "3 : lisible, quelques tournures non idiomatiques · "
        "5 : clair, idiomatique, nommage explicite"),
    "architecture": (
        "Qualité de l'architecture",
        "1 : tout mélangé, état global, dépendances cachées · "
        "3 : structure correcte, quelques couplages évitables · "
        "5 : responsabilités séparées, dépendances injectées, typage"),
    "gestion_erreurs": (
        "Gestion des erreurs",
        "1 : erreurs ignorées ou masquées · "
        "3 : erreurs traitées mais génériques · "
        "5 : exceptions typées, messages utiles, aucune information sensible exposée"),
    "documentation": (
        "Documentation",
        "1 : aucune · 3 : présente mais incomplète · "
        "5 : docstrings précises sur le rôle, les paramètres et les erreurs"),
}


def modele_juge() -> str:
    """Modèle du juge chez Groq."""
    return os.getenv("SMAML_MODELE_JUGE", "moonshotai/kimi-k2-instruct-0905")


def modele_juge_gemini() -> str:
    """Modèle du juge chez Gemini, si la chaîne du juge passe par Gemini."""
    return os.getenv("SMAML_MODELE_JUGE_GEMINI", "gemini-3.1-pro-preview")


# Famille de chaque modèle, d'après son identifiant. Le juge doit venir
# d'une AUTRE famille que le générateur (gpt-oss, famille OpenAI).
FAMILLES = (("openai/", "OpenAI"), ("gpt", "OpenAI"), ("moonshot", "Moonshot AI"),
            ("kimi", "Moonshot AI"), ("qwen", "Alibaba"), ("llama", "Meta"),
            ("meta-", "Meta"), ("deepseek", "DeepSeek"), ("gemini", "Google"),
            ("gemma", "Google"), ("mistral", "Mistral"), ("mixtral", "Mistral"),
            ("claude", "Anthropic"), ("allam", "SDAIA"), ("compound", "Groq"))
# Modèles qui ne sont pas des modèles de conversation : inutilisables.
NON_CONVERSATION = ("whisper", "tts", "guard", "embedding", "embed", "aqa",
                    "imagen", "veo", "orpheus", "distil")


def famille(identifiant: str) -> str:
    bas = identifiant.lower()
    return next((nom for motif, nom in FAMILLES if motif in bas), "inconnue")


def chaine_juge() -> list:
    return [f.strip() for f in os.getenv("SMAML_CHAINE_JUGE", "groq").split(",")
            if f.strip()]


def construire_prompt(code_php: str, code_python: str) -> str:
    criteres = "\n".join(f"- {cle} — {titre}\n  Échelle : {echelle}"
                         for cle, (titre, echelle) in GRILLE.items())
    gabarit = ",\n".join(f'    "{cle}": {{"justification": "...", "note": 1}}'
                         for cle in GRILLE)
    return f"""Tu es un évaluateur expert en migration de code PHP vers Python.
Évalue la qualité de la migration ci-dessous selon la grille, critère par critère.
Pour chaque critère, écris d'abord ta justification en une ou deux phrases,
PUIS donne une note entière de 1 à 5. Sois exigeant et précis.

GRILLE
{criteres}

CODE PHP D'ORIGINE
```php
{code_php}
```

CODE PYTHON MIGRÉ
```python
{code_python}
```

Réponds UNIQUEMENT par un objet JSON de cette forme, sans aucun texte autour :
{{
  "criteres": {{
{gabarit}
  }},
  "synthese": "une phrase"
}}"""


def analyser_reponse(texte: str) -> dict:
    """Extrait et valide le jugement. Lève ValueError s'il est inexploitable."""
    # Certains modèles (Qwen, DeepSeek) écrivent leur réflexion entre
    # balises <think> avant de répondre : seul le jugement compte.
    texte = re.sub(r"<think>.*?</think>", "", texte or "", flags=re.S)
    texte = re.sub(r"```(?:json)?", "", texte)
    debut, fin = texte.find("{"), texte.rfind("}")
    if debut < 0 or fin <= debut:
        raise ValueError("aucun objet JSON dans la réponse")
    donnees = json.loads(texte[debut:fin + 1])
    criteres = donnees.get("criteres") or {}
    resultat = {}
    for cle in GRILLE:
        entree = criteres.get(cle) or {}
        try:
            note = int(entree.get("note"))
        except (TypeError, ValueError):
            raise ValueError(f"note absente ou invalide pour « {cle} »")
        if not 1 <= note <= 5:
            raise ValueError(f"note hors échelle pour « {cle} » : {note}")
        resultat[cle] = {"note": note,
                         "justification": str(entree.get("justification", ""))[:400]}
    return {"criteres": resultat, "synthese": str(donnees.get("synthese", ""))[:400]}


def score_sur_100(criteres: dict) -> float:
    """Moyenne des notes, ramenée de l'échelle 1-5 à 0-100."""
    moyenne = sum(c["note"] for c in criteres.values()) / len(criteres)
    return round((moyenne - 1) / 4 * 100, 1)


def juger(code_php: str, code_python: str, transport=None) -> dict:
    """
    Jugement du code migré. Retourne toujours un rapport : en cas
    d'indisponibilité ou de réponse inexploitable, le statut le dit et
    le critère ne sera pas compté (son poids est redistribué).
    """
    if os.getenv("SMAML_JUGE", "1").lower() in ("0", "false", "non"):
        return {"statut": "desactive", "raison": "juge désactivé (SMAML_JUGE=0)"}

    cle_cache = cache_smaml.empreinte("juge", [code_php, code_python,
                                               VERSION_GRILLE, modele_juge()])
    deja = cache_smaml.lire("juge", cle_cache)
    if deja:
        return deja

    try:
        reponse = fournisseurs_llm.generer(
            construire_prompt(code_php, code_python), temperature=0.0,
            # budget large : un modèle qui réfléchit avant de répondre
            # consomme des tokens avant d'écrire son jugement
            max_tokens=8000, transport=transport, chaine=chaine_juge(),
            modeles={"groq": modele_juge(), "gemini": modele_juge_gemini()},
            journal=lambda *_: None)
    except Exception as e:
        return {"statut": "indisponible",
                "raison": f"{type(e).__name__} : {str(e)[:200]}"}

    try:
        jugement = analyser_reponse(reponse.texte)
    except (ValueError, json.JSONDecodeError) as e:
        return {"statut": "invalide", "raison": f"réponse inexploitable : {e}",
                "modele": reponse.modele}

    rapport = {"statut": "evalue",
               "score": score_sur_100(jugement["criteres"]),
               "criteres": jugement["criteres"],
               "synthese": jugement["synthese"],
               "modele": reponse.modele,
               "fournisseur": reponse.fournisseur,
               "version_grille": VERSION_GRILLE}
    cache_smaml.ecrire("juge", cle_cache, rapport)
    return rapport


if __name__ == "__main__":
    import sys
    import urllib.request

    if "--modeles" in sys.argv:
        def lister(url, cle):
            requete = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {cle}",
                "User-Agent": "SMAML/2.0 (python; migration-legacy)"})
            with urllib.request.urlopen(requete, timeout=30) as r:
                return sorted(m["id"].replace("models/", "") for m in json.load(r)["data"])

        sources = [("groq", "https://api.groq.com/openai/v1/models",
                    os.getenv("GROQ_TOKEN"), modele_juge()),
                   ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai/models",
                    os.getenv("GEMINI_API_KEY"), modele_juge_gemini())]
        print("Modèles accessibles avec tes clés — candidats pour le juge\n"
              "(le générateur est gpt-oss, famille OpenAI : cette famille est exclue)\n")
        for fournisseur, url, cle, configure in sources:
            if not cle:
                print(f"{fournisseur} : clé absente\n")
                continue
            try:
                modeles = lister(url, cle)
            except Exception as e:
                print(f"{fournisseur} : liste indisponible ({e})\n")
                continue
            print(f"{fournisseur.upper()}")
            for m in modeles:
                if any(x in m.lower() for x in NON_CONVERSATION):
                    continue
                fam = famille(m)
                if fam == "OpenAI":
                    etat = "exclu (même famille que le générateur)"
                else:
                    etat = "candidat"
                marque = "   ← configuré" if m == configure else ""
                print(f"  {m:<48} {fam:<12} {etat}{marque}")
            print()
        print("Pour choisir un modèle Groq   : set SMAML_MODELE_JUGE=<identifiant>")
        print("Pour choisir un modèle Gemini : set SMAML_CHAINE_JUGE=gemini")
        print("                                set SMAML_MODELE_JUGE_GEMINI=<identifiant>")
    elif "--essai" in sys.argv:
        php = ('<?php function validatePassword($p) {\n'
               '  if (strlen($p) < 8) { throw new Exception("court"); }\n'
               '  return true; } ?>')
        python = ('def validate_password(password: str) -> bool:\n'
                  '    """Vérifie la longueur minimale du mot de passe."""\n'
                  '    if len(password) < 8:\n'
                  '        raise ValueError("Mot de passe trop court")\n'
                  '    return True\n')
        rapport = juger(php, python)
        print(json.dumps(rapport, ensure_ascii=False, indent=2))
    else:
        print(__doc__)