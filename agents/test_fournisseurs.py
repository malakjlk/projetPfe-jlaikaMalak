"""
Tests du basculement entre fournisseurs de LLM.

    py -X utf8 test_fournisseurs.py

Aucun appel réseau : les réponses des fournisseurs sont simulées.
"""
import json
import os

import fournisseurs_llm as fl

resultats = []


def verifier(nom, condition):
    resultats.append((nom, bool(condition)))
    print(f"   {'[OK]' if condition else '[ECHEC]'} {nom}")


def ok(texte="def f():\n    return 1\n"):
    return 200, json.dumps({"choices": [{"message": {"content": texte}}]}), {}


def transport(scenario):
    """scenario : {'groq': [réponses successives], 'gemini': [...]}"""
    appels = []

    def envoyer(url, cle, charge):
        fournisseur = "groq" if "groq" in url else "gemini"
        appels.append(fournisseur)
        file = scenario[fournisseur]
        return file.pop(0) if len(file) > 1 else file[0]
    envoyer.appels = appels
    return envoyer


def reinitialiser():
    fl.EN_PANNE.clear()
    os.environ.update({"GROQ_TOKEN": "g", "GEMINI_API_KEY": "m"})
    for v in ("SMAML_STRICT", "SMAML_BASCULE_DEV", "SMAML_CHAINE_GENERATION"):
        os.environ.pop(v, None)


silence = dict(attendre=lambda s: None, journal=lambda *_: None)
QUOTA_JOUR = (429, "Rate limit reached on tokens per day (TPD): Limit 200000", {})

print("\n── Basculement du Développeur ──")

reinitialiser()
t = transport({"groq": [ok()], "gemini": [ok()]})
r = fl.generer("prompt", transport=t, **silence)
verifier("Groq disponible : il génère, sans basculement",
         r.fournisseur == "groq" and not r.bascule)

reinitialiser()
t = transport({"groq": [QUOTA_JOUR], "gemini": [ok()]})
r = fl.generer("prompt", transport=t, **silence)
verifier("quota journalier Groq épuisé : bascule immédiate sur Gemini",
         r.fournisseur == "gemini" and r.bascule and t.appels == ["groq", "gemini"])
t2 = transport({"groq": [ok()], "gemini": [ok()]})
r2 = fl.generer("prompt", transport=t2, **silence)
verifier("module suivant : Groq n'est plus sollicité (coupe-circuit)",
         t2.appels == ["gemini"] and r2.fournisseur == "gemini")

t3 = transport({"groq": [ok()], "gemini": [ok()]})
r3 = fl.generer("prompt", transport=t3, chaine=["groq"],
                modeles={"groq": "qwen/qwen3.8-27b"}, **silence)
verifier("quota de gpt-oss épuisé : un AUTRE modèle Groq (le juge) reste utilisable",
         r3.fournisseur == "groq" and r3.modele == "qwen/qwen3.8-27b")

reinitialiser()
t = transport({"groq": [(429, "Rate limit: tokens per minute", {}), ok()],
               "gemini": [ok()]})
r = fl.generer("prompt", transport=t, **silence)
verifier("limite par minute : on attend et on réessaie sur Groq, sans basculer",
         r.fournisseur == "groq" and not r.bascule and t.appels == ["groq", "groq"])

reinitialiser()
t = transport({"groq": [(503, "Service Unavailable", {})], "gemini": [ok()]})
r = fl.generer("prompt", transport=t, **silence)
verifier("surcharge persistante : un nouvel essai, puis bascule",
         r.fournisseur == "gemini" and t.appels == ["groq", "groq", "gemini"])

reinitialiser()
t = transport({"groq": [(0, "réseau : getaddrinfo failed", {})], "gemini": [ok()]})
r = fl.generer("prompt", transport=t, **silence)
verifier("coupure réseau : bascule sur Gemini", r.fournisseur == "gemini")

reinitialiser()
t = transport({"groq": [(400, "invalid request: context too long", {})],
               "gemini": [ok()]})
try:
    fl.generer("prompt", transport=t, **silence)
    verifier("requête invalide : PAS de basculement, erreur signalée", False)
except fl.ErreurRequete:
    verifier("requête invalide : PAS de basculement, erreur signalée",
             t.appels == ["groq"])

reinitialiser()
os.environ["SMAML_STRICT"] = "1"
t = transport({"groq": [QUOTA_JOUR], "gemini": [ok()]})
try:
    fl.generer("prompt", transport=t, **silence)
    verifier("mode strict (benchmark) : aucun basculement", False)
except fl.ErreurFournisseurs:
    verifier("mode strict (benchmark) : aucun basculement", t.appels == ["groq"])

reinitialiser()
t = transport({"groq": [QUOTA_JOUR], "gemini": [(503, "overloaded", {})]})
try:
    fl.generer("prompt", transport=t, **silence)
    verifier("les deux en panne : erreur explicite, avec le détail", False)
except fl.ErreurFournisseurs as e:
    verifier("les deux en panne : erreur explicite, avec le détail",
             "groq" in str(e) and "gemini" in str(e))

reinitialiser()
os.environ.pop("GROQ_TOKEN")
t = transport({"groq": [ok()], "gemini": [ok()]})
r = fl.generer("prompt", transport=t, **silence)
verifier("clé Groq absente : Gemini prend le relais, signalé comme bascule",
         r.fournisseur == "gemini" and r.bascule)

reinitialiser()
r = fl.Reponse("def f(): pass\n", "gemini", "gemini-3.1-flash-lite", bascule=True)
annote = fl.annoter_bascule(r.texte, r)
verifier("le code du secours porte une ligne SMAML-ATTENTION",
         annote.startswith("# SMAML-ATTENTION: code généré par le modèle de secours"))
verifier("le code du fournisseur principal n'est pas annoté",
         fl.annoter_bascule("x", fl.Reponse("x", "groq", "m")) == "x")

verifier("403 / code 1010 : diagnostiqué comme pare-feu, pas comme clé refusée",
         fl.classer(403, "error code: 1010") == fl.CLIENT_BLOQUE
         and fl.classer(403, "invalid api key") == fl.CLE_REFUSEE)

print("── Plusieurs modèles par fournisseur ──")


def transport_par_modele(reponses):
    """reponses : {modèle: réponse} — le transport répond selon le MODÈLE."""
    appels = []

    def envoyer(url, cle, charge):
        appels.append(charge["model"])
        return reponses.get(charge["model"], ok())
    envoyer.appels = appels
    return envoyer


reinitialiser()
verifier("le secours Gemini comporte plusieurs modèles, dans l'ordre",
         fl.modele_de("gemini").split(",")[:2] == ["gemini-3.8-flash", "gemini-3.5-flash"])
t = transport_par_modele({"openai/gpt-oss-120b": QUOTA_JOUR,
                          "gemini-3.8-flash": (503, "high demand", {})})
r = fl.generer("prompt", transport=t, **silence)
verifier("gemini-3.8-flash surchargé : gemini-3.5-flash prend le relais",
         r.modele == "gemini-3.5-flash" and r.bascule)

reinitialiser()
os.environ["GROQ_MODEL"] = "modele-retire,openai/gpt-oss-120b"
t = transport_par_modele({"modele-retire": (404, "The model does not exist", {})})
r = fl.generer("prompt", transport=t, **silence)
verifier("modèle retiré (404) : on passe au modèle suivant, sans erreur de requête",
         r.modele == "openai/gpt-oss-120b")
os.environ.pop("GROQ_MODEL")

print("── Réponse tronquée ──")


def coupe(texte="def f():\n    return"):
    return 200, json.dumps({"choices": [{"message": {"content": texte},
                                         "finish_reason": "length"}]}), {}


reinitialiser()
budgets = []


def tronque_puis_complet(url, cle, charge):
    budgets.append(charge["max_tokens"])
    return coupe() if len(budgets) == 1 else ok()


r = fl.generer("prompt", max_tokens=4000, transport=tronque_puis_complet, **silence)
verifier("réponse tronquée : nouvel essai avec un budget doublé, réponse complète acceptée",
         budgets == [4000, 8000] and r.fournisseur == "groq" and "return 1" in r.texte)

reinitialiser()
t = transport_par_modele({"openai/gpt-oss-120b": coupe()})
r = fl.generer("prompt", max_tokens=8000, transport=t, **silence)
verifier("toujours tronquée : le code coupé n'est JAMAIS accepté, modèle suivant",
         r.fournisseur == "gemini" and "return 1" in r.texte)

ok_total = sum(1 for _, r in resultats if r)
print(f"\n{ok_total}/{len(resultats)} vérifications réussies")
if ok_total != len(resultats):
    raise SystemExit(1)