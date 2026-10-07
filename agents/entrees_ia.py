"""
Entrées de test produites par l'IA — SMAML
===========================================
Le Comparateur exécute le PHP et le Python sur les mêmes entrées. Ses
entrées fixes (chaîne vide, accents, injection…) sont les mêmes pour
toutes les fonctions : elles ne savent pas qu'une fonction attend un
e-mail, un mot de passe ou un montant. Un pourcentage d'équivalence
obtenu sur ces seules entrées est difficile à interpréter.

L'IA lit la fonction PHP et propose des entrées QUI ONT DU SENS pour
elle, chacune avec sa catégorie et son intention :

    nominal              un usage normal
    limite               une borne : longueur minimale, zéro, maximum…
    caracteres_speciaux  accents, emojis, espaces — pièges d'encodage
    attaque              injection SQL, balise HTML, chemin ../
    invalide             une entrée hors du domaine prévu

Ces entrées S'AJOUTENT aux entrées fixes, qui sont gardées.

Réglages
--------
  SMAML_ENTREES_IA=0          désactive l'IA (entrées fixes seules)
  SMAML_CHAINE_ENTREES        fournisseurs (défaut : celui du juge)
  SMAML_MODELE_ENTREES        modèle (défaut : celui du juge)
"""

from __future__ import annotations

import json
import os
import re

import cache_smaml
import fournisseurs_llm

CATEGORIES = ("nominal", "limite", "caracteres_speciaux", "attaque", "invalide")
VERSION = "1"
MAXIMUM = 16


def _modele() -> str:
    return os.getenv("SMAML_MODELE_ENTREES") or os.getenv("SMAML_MODELE_JUGE", "qwen/qwen3.8-27b")


def _chaine() -> list:
    return [f.strip() for f in (os.getenv("SMAML_CHAINE_ENTREES") or
                                os.getenv("SMAML_CHAINE_JUGE", "groq")).split(",") if f.strip()]


def construire_prompt(code_php: str, nom_fonction: str, nb_parametres: int) -> str:
    return f"""Tu prépares des entrées de test pour comparer une fonction PHP à sa traduction
en Python. Lis la fonction et propose entre 8 et 12 entrées qui ONT DU SENS pour
elle, réparties dans ces catégories :
- nominal : un usage normal
- limite : une borne (longueur minimale ou maximale exacte, zéro, négatif…)
- caracteres_speciaux : accents, emojis, espaces — les pièges d'encodage
- attaque : injection SQL, balise HTML, chemin ../
- invalide : une entrée hors du domaine prévu (mauvais format, mauvais type)

Pour une limite, donne la valeur JUSTE AVANT et JUSTE APRÈS la borne.

FONCTION PHP ({nom_fonction}, {nb_parametres} paramètre(s))
```php
{code_php}
```

Réponds UNIQUEMENT par un objet JSON, sans texte autour. Chaque entrée donne
EXACTEMENT {nb_parametres} argument(s), des valeurs simples (texte, nombre,
booléen ou null) :
{{"entrees": [{{"arguments": [...], "categorie": "limite", "intention": "7 caractères : juste sous le minimum"}}]}}"""


def valider(donnees: dict, nb_parametres: int) -> list:
    """Garde les entrées bien formées ; écarte les autres sans échouer."""
    entrees, vues = [], set()
    for e in (donnees or {}).get("entrees", []):
        arguments = e.get("arguments")
        if not isinstance(arguments, list) or len(arguments) != nb_parametres:
            continue
        if not all(isinstance(a, (str, int, float, bool)) or a is None for a in arguments):
            continue
        cle = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
        if cle in vues:
            continue
        vues.add(cle)
        categorie = e.get("categorie") if e.get("categorie") in CATEGORIES else "nominal"
        entrees.append({"arguments": arguments, "categorie": categorie,
                        "intention": str(e.get("intention", ""))[:120], "origine": "ia"})
    return entrees[:MAXIMUM]


def generer_entrees_ia(code_php: str, nom_fonction: str, nb_parametres: int,
                       transport=None) -> dict:
    """
    Retourne {"statut", "entrees": [...], "raison"?}. En cas d'échec, la
    liste est vide : le Comparateur continue avec ses entrées fixes.
    """
    if os.getenv("SMAML_ENTREES_IA", "1").lower() in ("0", "false", "non"):
        return {"statut": "desactive", "entrees": []}
    if nb_parametres <= 0:
        return {"statut": "sans_objet", "entrees": [],
                "raison": "fonction sans paramètre : un seul appel suffit"}

    cle = cache_smaml.empreinte("entrees_ia", [code_php, nom_fonction, nb_parametres,
                                               VERSION, _modele()])
    deja = cache_smaml.lire("entrees_ia", cle)
    if deja:
        return deja
    try:
        reponse = fournisseurs_llm.generer(
            construire_prompt(code_php, nom_fonction, nb_parametres), temperature=0.3,
            max_tokens=6000, transport=transport, chaine=_chaine(),
            modeles={"groq": _modele()}, journal=lambda *_: None)
    except Exception as e:
        return {"statut": "indisponible", "entrees": [],
                "raison": f"{type(e).__name__} : {str(e)[:150]}"}
    texte = re.sub(r"<think>.*?</think>|```(?:json)?", "", reponse.texte or "", flags=re.S)
    debut, fin = texte.find("{"), texte.rfind("}")
    try:
        entrees = valider(json.loads(texte[debut:fin + 1]), nb_parametres)
    except (ValueError, TypeError):
        entrees = []
    if not entrees:
        return {"statut": "invalide", "entrees": [], "raison": "réponse inexploitable"}
    resultat = {"statut": "genere", "entrees": entrees, "modele": reponse.modele}
    cache_smaml.ecrire("entrees_ia", cle, resultat)
    return resultat