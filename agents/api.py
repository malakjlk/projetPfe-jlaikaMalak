"""
API SMAML — Migration d'application PHP → Python
=================================================
    uvicorn api:app --reload --port 8000

Trois différences avec la version précédente :

1. La migration tourne en TÂCHE DE FOND. Une migration orchestrée
   dure plusieurs minutes : une requête HTTP bloquante expirerait,
   et le frontend ne pourrait rien afficher pendant ce temps.
   POST /migrer-projet renvoie donc immédiatement un identifiant.

2. GET /jobs/{id} expose l'AVANCEMENT EN DIRECT : le module en cours,
   les étapes franchies, et le journal des sollicitations d'agents
   avec la justification donnée par le Manager. C'est lu dans l'état
   partagé du pipeline, sans rien y modifier.

3. GET /sante vérifie l'environnement (PHP, pdo_sqlite, CrossHair,
   modèle, cache) — utile avant une démonstration.
"""

import os
import shutil
import tempfile
import threading
import traceback
import uuid
from datetime import datetime

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

import cache_smaml
import crewai_pipeline
from pipeline_complet import migrer_fichier, migrer_projet

app = FastAPI(title="SMAML — Migration d'application PHP → Python")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Registre des migrations en cours ────────────────
# Une migration par identifiant : état, résultat, erreur.
TACHES = {}
_verrou = threading.Lock()


def _nouvelle_tache(libelle: str) -> str:
    identifiant = uuid.uuid4().hex[:12]
    with _verrou:
        TACHES[identifiant] = {
            "id": identifiant,
            "libelle": libelle,
            "statut": "en_cours",
            "debut": datetime.now().isoformat(timespec="seconds"),
            "fin": None,
            "resultat": None,
            "erreur": None,
        }
    return identifiant


def _terminer(identifiant: str, resultat=None, erreur=None):
    with _verrou:
        tache = TACHES.get(identifiant)
        if not tache:
            return
        tache["statut"] = "echec" if erreur else "termine"
        tache["resultat"] = resultat
        tache["erreur"] = erreur
        tache["fin"] = datetime.now().isoformat(timespec="seconds")


def _lancer(identifiant: str, travail, nettoyage=None):
    """Exécute la migration dans un fil séparé."""
    def executer():
        try:
            _terminer(identifiant, resultat=travail())
        except Exception as e:
            _terminer(identifiant,
                      erreur=f"{type(e).__name__} : {e}\n"
                             f"{traceback.format_exc()[-1500:]}")
        finally:
            if nettoyage:
                nettoyage()

    threading.Thread(target=executer, daemon=True).start()


def avancement_en_direct() -> dict:
    """
    Photographie de l'état partagé du pipeline.

    Le module en cours de migration écrit ses dépôts et son journal
    dans crewai_pipeline.ETAT. On le lit tel quel — en lecture seule —
    pour que l'interface montre le travail pendant qu'il se fait, au
    lieu d'un écran figé pendant plusieurs minutes.
    """
    etat = crewai_pipeline.ETAT
    try:
        structure = crewai_pipeline.etat_structure()
    except Exception:
        return {}
    return {
        "module": structure.get("module"),
        "statut": structure.get("statut"),
        "etapes": structure.get("etapes"),
        "tentatives": structure.get("tentatives_correction"),
        "max_tentatives": structure.get("max_tentatives"),
        "journal": structure.get("journal"),
        "points_attention": structure.get("points_attention"),
        "derniere_decision": structure.get("derniere_decision"),
        "versions": structure.get("versions"),
        "agents_indisponibles": structure.get("agents_indisponibles"),
        "code_python_partiel": (etat.get("code_python") or "")[:4000],
    }


# ─── Migration d'un projet complet (ZIP) ─────────────

@app.post("/migrer-projet")
async def migrer_projet_endpoint(fichier: UploadFile = File(...)):
    """Reçoit un ZIP d'application PHP et lance la migration."""
    if not fichier.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail="Envoie un fichier .zip contenant ton application PHP")

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(await fichier.read())
        chemin_zip = tmp.name
    dossier_sortie = tempfile.mkdtemp(prefix="smaml_sortie_")

    identifiant = _nouvelle_tache(fichier.filename)

    def travail():
        rapport = migrer_projet(chemin_zip, dossier_sortie=dossier_sortie)
        fichiers = {}
        for nom in sorted(os.listdir(dossier_sortie)):
            if nom.endswith(".py"):
                with open(os.path.join(dossier_sortie, nom),
                          "r", encoding="utf-8") as f:
                    fichiers[nom] = f.read()
        return {"rapport": rapport, "fichiers_python": fichiers,
                "cache": cache_smaml.statistiques()}

    def nettoyage():
        try:
            os.unlink(chemin_zip)
        except OSError:
            pass
        shutil.rmtree(dossier_sortie, ignore_errors=True)

    _lancer(identifiant, travail, nettoyage)
    return {"id": identifiant, "statut": "en_cours"}


# ─── Migration d'un fichier PHP isolé ────────────────

@app.post("/migrer")
async def migrer_fichier_endpoint(fichier: UploadFile = File(...)):
    """Reçoit un seul fichier .php et lance sa migration."""
    if not fichier.filename.lower().endswith(".php"):
        raise HTTPException(
            status_code=400, detail="Envoie un fichier .php")

    dossier = tempfile.mkdtemp(prefix="smaml_fichier_")
    chemin = os.path.join(dossier, os.path.basename(fichier.filename))
    with open(chemin, "wb") as f:
        f.write(await fichier.read())

    identifiant = _nouvelle_tache(fichier.filename)

    def travail():
        resultat = migrer_fichier(chemin, contexte_projet={})
        # Même forme que la migration de projet : le frontend
        # n'a ainsi qu'un seul format à savoir lire.
        modules = [{k: v for k, v in m.items() if k != "code_python"}
                   for m in resultat.get("modules", [])]
        livres = [m for m in modules
                  if m.get("decision_finale") == "LIVRER"]
        return {
            "rapport": {
                "fichiers_migres": [{
                    "source": resultat.get("fichier_source"),
                    "cible": os.path.splitext(
                        os.path.basename(chemin))[0] + ".py",
                    "statut": ("livré" if len(livres) == len(modules)
                               and modules else "partiel"),
                    "modules": modules,
                }],
                "statistiques": {
                    "total_fichiers": 1,
                    "fichiers_livres": int(bool(modules)
                                           and len(livres) == len(modules)),
                    "fichiers_en_echec": int(len(livres) != len(modules)),
                },
                "cache": cache_smaml.statistiques(),
            },
            "fichiers_python": {
                os.path.splitext(os.path.basename(chemin))[0] + ".py":
                    resultat.get("code_python_final")
                    or "\n\n".join(m.get("code_python", "")
                                   for m in resultat.get("modules", []))
            },
        }

    _lancer(identifiant, travail,
            lambda: shutil.rmtree(dossier, ignore_errors=True))
    return {"id": identifiant, "statut": "en_cours"}


# ─── Suivi ───────────────────────────────────────────

@app.get("/jobs/{identifiant}")
def suivre(identifiant: str):
    """État d'une migration : terminée, ou avancement en direct."""
    with _verrou:
        tache = TACHES.get(identifiant)
        if not tache:
            raise HTTPException(status_code=404, detail="Migration inconnue")
        reponse = dict(tache)
    if reponse["statut"] == "en_cours":
        reponse["en_direct"] = avancement_en_direct()
    return reponse


@app.get("/jobs")
def lister():
    with _verrou:
        return [{k: v for k, v in t.items() if k != "resultat"}
                for t in TACHES.values()]


# ─── Santé de l'environnement ────────────────────────

@app.get("/sante")
def sante():
    """
    Vérifie ce dont dépend le pipeline. À consulter avant une
    démonstration : une extension PHP manquante ou une clé absente
    dégrade silencieusement les résultats.
    """
    import subprocess

    php_version, extensions = None, ""
    try:
        php_version = subprocess.run(
            ["php", "-v"], capture_output=True, text=True,
            timeout=10).stdout.splitlines()[0]
        extensions = subprocess.run(
            ["php", "-m"], capture_output=True, text=True,
            timeout=10).stdout.lower()
    except Exception:
        pass

    try:
        import crosshair  # noqa: F401
        crosshair_ok = True
    except ImportError:
        crosshair_ok = False

    from agent_developpeur import GROQ_MODEL
    return {
        "php": php_version,
        "pdo_sqlite": "pdo_sqlite" in extensions,
        "crosshair": crosshair_ok,
        "modele_generation": GROQ_MODEL,
        "orchestrateur": crewai_pipeline.DESCRIPTIONS_MODELES.get(
            crewai_pipeline.MODELE_ACTIF),
        "bascule_autorisee": crewai_pipeline.BASCULE_AUTORISEE,
        "cle_groq": bool(os.getenv("GROQ_TOKEN")),
        "cle_gemini": bool(os.getenv("GEMINI_API_KEY")),
        "mode": os.getenv("SMAML_MODE") or "direct",
        "mode_strict": bool(os.getenv("SMAML_STRICT")),
        "cache": cache_smaml.statistiques(),
    }