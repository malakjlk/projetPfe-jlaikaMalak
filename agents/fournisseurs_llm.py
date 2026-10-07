"""
Fournisseurs de LLM et basculement — SMAML
===========================================
Le Développeur dépend d'un service externe. Si ce service tombe —
quota épuisé, surcharge, réseau, clé refusée —, la génération passe
sur un AUTRE fournisseur au lieu de s'arrêter.

Chaîne par défaut :  Groq (gpt-oss-120b)  →  Gemini (gemini-3.8-flash)

Le secours doit être chez un AUTRE fournisseur : si Groq est en panne
ou à court de quota, un second modèle hébergé chez Groq tomberait en
même temps.

Toutes les erreurs ne justifient pas un basculement
---------------------------------------------------
  quota journalier épuisé   → basculer tout de suite, et ne plus
                              solliciter ce fournisseur pendant l'exécution
  limite par minute (429)   → attendre un peu, réessayer, puis basculer
  surcharge (5xx), réseau   → réessayer une fois, puis basculer
  clé refusée (401, 403)    → basculer, le fournisseur est inutilisable
  requête invalide (400)    → NE PAS basculer : le même prompt échouerait
                              ailleurs — c'est une erreur à corriger

Mode strict (benchmark)
-----------------------
SMAML_STRICT=1 interdit tout basculement : une mesure doit être faite
avec un seul modèle du début à la fin. Une panne interrompt alors la
mesure, plutôt que de la contaminer.

Réglages
--------
  GROQ_TOKEN, GROQ_MODEL                     fournisseur principal
  GEMINI_API_KEY, SMAML_MODELE_SECOURS       fournisseur de secours
  SMAML_CHAINE_GENERATION=groq,gemini        ordre de la chaîne
  SMAML_BASCULE_DEV=0                        désactive le basculement

Aucune dépendance : appels HTTP directs aux interfaces compatibles
OpenAI des deux fournisseurs.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Optional


FOURNISSEURS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "cles": ("GROQ_TOKEN", "GROQ_API_KEY"),
        "modele_var": "GROQ_MODEL",
        "modele_defaut": "openai/gpt-oss-120b",
    },
    "gemini": {
        "url": ("https://generativelanguage.googleapis.com/v1beta/openai/"
                "chat/completions"),
        "cles": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "modele_var": "SMAML_MODELE_SECOURS",
        # plusieurs modèles, essayés dans l'ordre : un secours ne doit pas
        # dépendre d'un seul modèle, lui-même parfois surchargé
        "modele_defaut": "gemini-3.8-flash,gemini-3.5-flash",
    },
}

# Coupe-circuit, pendant l'exécution :
#   • clé refusée, client bloqué → tout le FOURNISSEUR est écarté ;
#   • quota journalier épuisé    → seul ce MODÈLE est écarté : chez Groq,
#     chaque modèle a son propre quota, et l'épuisement de gpt-oss ne
#     doit pas priver le juge de Qwen.
EN_PANNE: dict = {}

# Tokens de la dernière réponse réussie (relevés pour mesurer le coût).
DERNIERS_TOKENS: dict = {}


class ErreurRequete(RuntimeError):
    """La requête elle-même est fautive : basculer ne servirait à rien."""


class ErreurFournisseurs(RuntimeError):
    """Aucun fournisseur de la chaîne n'a pu répondre."""

    def __init__(self, message: str, essais: list):
        super().__init__(message)
        self.essais = essais


@dataclass
class Reponse:
    texte: str
    fournisseur: str
    modele: str
    bascule: bool = False
    essais: list = field(default_factory=list)
    tokens: dict = field(default_factory=dict)   # {"entree": n, "sortie": n}


def modele_de(fournisseur: str) -> str:
    conf = FOURNISSEURS[fournisseur]
    return os.getenv(conf["modele_var"], conf["modele_defaut"])


def cle_de(fournisseur: str) -> Optional[str]:
    for nom in FOURNISSEURS[fournisseur]["cles"]:
        if os.getenv(nom):
            return os.getenv(nom)
    return None


def chaine_active() -> list:
    chaine = [f.strip() for f in
              os.getenv("SMAML_CHAINE_GENERATION", "groq,gemini").split(",")
              if f.strip() in FOURNISSEURS]
    strict = os.getenv("SMAML_STRICT", "").lower() in ("1", "true", "oui")
    coupe = os.getenv("SMAML_BASCULE_DEV", "1").lower() in ("0", "false", "non")
    return chaine[:1] if (strict or coupe) else chaine


# ═══ TRANSPORT HTTP ══════════════════════════════════════

def transport_http(url: str, cle: str, charge: dict, delai_s: float = 120):
    """Envoie la requête ; retourne (statut, corps, en-têtes)."""
    requete = urllib.request.Request(
        url, data=json.dumps(charge).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json",
                 "Accept": "application/json",
                 # Signature explicite du client : le pare-feu Cloudflare
                 # placé devant certaines API (dont Groq) rejette la
                 # signature par défaut de Python (« Python-urllib »),
                 # avec l'erreur 403 / code 1010.
                 "User-Agent": "SMAML/2.0 (python; migration-legacy)",
                 "Authorization": f"Bearer {cle}"})
    try:
        with urllib.request.urlopen(requete, timeout=delai_s) as reponse:
            return reponse.status, reponse.read().decode("utf-8"), \
                dict(reponse.headers)
    except urllib.error.HTTPError as e:
        corps = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, corps, dict(e.headers or {})
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, f"réseau : {e}", {}


# ═══ CLASSIFICATION DES ÉCHECS ═══════════════════════════

QUOTA_JOURNALIER = "quota_journalier"
LIMITE_MINUTE = "limite_minute"
SURCHARGE = "surcharge"
RESEAU = "reseau"
CLE_REFUSEE = "cle_refusee"
CLIENT_BLOQUE = "client_bloque_par_pare_feu"
MODELE_INTROUVABLE = "modele_introuvable"
REQUETE_INVALIDE = "requete_invalide"


def classer(statut: int, corps: str) -> str:
    texte = (corps or "").lower()
    if statut == 429:
        if any(m in texte for m in ("per day", "tokens per day", "(tpd)",
                                    "requests per day", "(rpd)", "daily",
                                    "quota exceeded", "exceeded your current quota")):
            return QUOTA_JOURNALIER
        return LIMITE_MINUTE
    if statut == 403 and "1010" in texte:
        # Pare-feu Cloudflare : la clé n'est pas en cause, c'est la
        # signature du client qui est refusée.
        return CLIENT_BLOQUE
    if statut in (401, 403):
        return CLE_REFUSEE
    if statut == 404 or "does not exist" in texte or "not found" in texte:
        # modèle retiré ou inaccessible : on passe au modèle suivant
        return MODELE_INTROUVABLE
    if statut in (500, 502, 503, 504) or "overloaded" in texte:
        return SURCHARGE
    if statut == 0:
        return RESEAU
    return REQUETE_INVALIDE


# ═══ GÉNÉRATION AVEC BASCULEMENT ═════════════════════════

# Marqueurs d'issue : des objets uniques, impossibles à confondre avec
# un texte généré.
MODELE_SUIVANT = object()
FOURNISSEUR_SUIVANT = object()


def _essayer_modele(fournisseur, modele, cle, prompt, temperature, max_tokens,
                    transport, attendre, journal, essais):
    """
    Essaie UN modèle, avec ses nouvelles tentatives. Retourne le texte en
    cas de succès, MODELE_SUIVANT s'il faut passer au modèle suivant,
    FOURNISSEUR_SUIVANT s'il faut écarter tout le fournisseur. Lève
    ErreurRequete si la requête elle-même est fautive.
    """
    charge = {"model": modele, "temperature": temperature, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]}
    # Les modèles qui réfléchissent avant de répondre (gpt-oss, Gemini 3.x)
    # consomment leur budget de tokens dans cette réflexion : effort réduit.
    if modele.startswith("openai/gpt-oss") or "gemini" in modele:
        charge["reasoning_effort"] = "low"

    attente = 15.0
    for tentative in range(1, 4):
        # Débit partagé entre tous les projets en cours : on attend son
        # tour plutôt que de se faire refuser par le fournisseur (429).
        from limiteur import LIMITEUR
        LIMITEUR.attendre(f"{fournisseur}:{modele}")
        statut, corps, entetes = transport(FOURNISSEURS[fournisseur]["url"], cle, charge)
        if statut == 200:
            try:
                donnees = json.loads(corps)
                choix = donnees["choices"][0]
                texte = choix["message"]["content"]
                fin = choix.get("finish_reason")
                usage = donnees.get("usage") or {}
                DERNIERS_TOKENS.clear()
                DERNIERS_TOKENS.update({"entree": usage.get("prompt_tokens", 0),
                                        "sortie": usage.get("completion_tokens", 0)})
            except (ValueError, KeyError, IndexError, TypeError):
                texte, fin = "", None
            if fin == "length":
                # Réponse COUPÉE faute de budget : un code tronqué ne doit
                # jamais être accepté. On redonne plus de budget, une fois.
                if charge["max_tokens"] < 16000:
                    charge["max_tokens"] *= 2
                    journal(f"  [TRONQUE]  {modele} : réponse tronquée, nouvel essai avec "
                            f"{charge['max_tokens']} tokens")
                    continue
                essais.append({"fournisseur": fournisseur, "modele": modele,
                               "issue": "echec", "raison": "reponse_tronquee"})
                journal(f"  -> {modele} : réponse encore tronquée, modèle suivant")
                return MODELE_SUIVANT
            if texte and texte.strip():
                essais.append({"fournisseur": fournisseur, "modele": modele,
                               "issue": "succes"})
                return texte
            genre, detail = SURCHARGE, "réponse vide"
        else:
            genre, detail = classer(statut, corps), f"{statut} {corps[:160]}"

        if genre == REQUETE_INVALIDE:
            raise ErreurRequete(f"{fournisseur} : requête refusée ({detail}) — "
                                f"basculer ne servirait à rien")
        if genre in (CLE_REFUSEE, CLIENT_BLOQUE):
            EN_PANNE[fournisseur] = genre
            essais.append({"fournisseur": fournisseur, "modele": modele,
                           "issue": "echec", "raison": genre, "detail": detail})
            journal(f"  -> {fournisseur} inutilisable ({genre}) : fournisseur suivant")
            return FOURNISSEUR_SUIVANT
        if genre in (QUOTA_JOURNALIER, MODELE_INTROUVABLE):
            EN_PANNE[f"{fournisseur}:{modele}"] = genre
            essais.append({"fournisseur": fournisseur, "modele": modele,
                           "issue": "echec", "raison": genre, "detail": detail})
            journal(f"  -> {modele} indisponible ({genre}) : modèle suivant")
            return MODELE_SUIVANT
        peut_reessayer = (genre == LIMITE_MINUTE and tentative < 3) or \
                         (genre in (SURCHARGE, RESEAU) and tentative < 2)
        if not peut_reessayer:
            essais.append({"fournisseur": fournisseur, "modele": modele,
                           "issue": "echec", "raison": genre, "detail": detail})
            journal(f"  -> {modele} indisponible ({genre}) : modèle suivant")
            return MODELE_SUIVANT
        delai = float(entetes.get("retry-after") or entetes.get("Retry-After") or attente)
        journal(f"  [ATTENTE] {modele} : {genre}, nouvel essai dans {delai:.0f} s ({tentative}/3)")
        attendre(delai)
        attente *= 2
    return MODELE_SUIVANT


def generer(prompt: str, temperature: float = 0.1, max_tokens: int = 4000,
            transport: Callable = None, attendre: Callable = time.sleep,
            journal: Callable = print, chaine: list = None,
            modeles: dict = None) -> Reponse:
    """
    Génère une réponse en parcourant la chaîne de fournisseurs.

    Retourne le texte, le fournisseur et le modèle réellement utilisés,
    et indique s'il y a eu basculement.
    """
    transport = transport or transport_http
    # Un autre usage (le juge, par exemple) peut imposer sa propre
    # chaîne et ses propres modèles.
    chaine = chaine or chaine_active()
    modeles = modeles or {}
    essais = []

    for rang, fournisseur in enumerate(chaine):
        if fournisseur in EN_PANNE:
            essais.append({"fournisseur": fournisseur, "issue": "ignore",
                           "raison": EN_PANNE[fournisseur]})
            continue
        cle = cle_de(fournisseur)
        if not cle:
            essais.append({"fournisseur": fournisseur, "issue": "ignore",
                           "raison": "clé absente"})
            continue

        liste = [m.strip() for m in (modeles.get(fournisseur)
                                     or modele_de(fournisseur)).split(",") if m.strip()]
        for indice, modele in enumerate(liste):
            cle_modele = f"{fournisseur}:{modele}"
            if cle_modele in EN_PANNE:
                essais.append({"fournisseur": fournisseur, "modele": modele,
                               "issue": "ignore", "raison": EN_PANNE[cle_modele]})
                continue
            resultat = _essayer_modele(fournisseur, modele, cle, prompt, temperature,
                                       max_tokens, transport, attendre, journal, essais)
            if isinstance(resultat, str):
                # Basculement : ni le premier fournisseur, ni son premier modèle.
                return Reponse(resultat, fournisseur, modele,
                               bascule=rang > 0 or indice > 0, essais=essais,
                               tokens=dict(DERNIERS_TOKENS))
            if resultat is FOURNISSEUR_SUIVANT:
                break           # clé refusée, pare-feu : tout le fournisseur est écarté
            # sinon : ce modèle est indisponible, on essaie le suivant

    raise ErreurFournisseurs(
        "Aucun fournisseur n'a pu générer le code : " +
        "; ".join(f"{e['fournisseur']} → {e['raison']}" for e in essais),
        essais)


def annoter_bascule(code: str, reponse: Reponse) -> str:
    """
    Signale dans le code produit qu'il vient du modèle de secours. La
    ligne SMAML-ATTENTION est reprise automatiquement dans le dépôt du
    Développeur, puis dans le rapport : l'humain sait d'où vient le code.
    """
    if not reponse.bascule:
        return code
    principal = (chaine_active() or ["groq"])[0]
    note = (f"# SMAML-ATTENTION: code généré par le modèle de secours "
            f"({reponse.modele}, {reponse.fournisseur}) après indisponibilité "
            f"de {principal} — qualité à surveiller\n")
    return note + code


if __name__ == "__main__":
    # Vérification en direct : chaque fournisseur répond-il ?
    #   py -X utf8 fournisseurs_llm.py
    print("Vérification des fournisseurs de génération\n")
    for nom in FOURNISSEURS:
        cle = cle_de(nom)
        if not cle:
            print(f"  {nom:<8} [ECHEC] clé absente ({' ou '.join(FOURNISSEURS[nom]['cles'])})")
            continue
        for modele in [m.strip() for m in modele_de(nom).split(",") if m.strip()]:
            statut, corps, _ = transport_http(
                FOURNISSEURS[nom]["url"], cle,
                {"model": modele, "max_tokens": 20,
                 "messages": [{"role": "user", "content": "Réponds juste : OK"}]},
                delai_s=30)
            if statut == 200:
                print(f"  {nom:<8} [OK] {modele} répond")
            else:
                print(f"  {nom:<8} [ECHEC] {modele} — {classer(statut, corps)} ({statut})")
    print(f"\nChaîne active : {' → '.join(chaine_active())}")