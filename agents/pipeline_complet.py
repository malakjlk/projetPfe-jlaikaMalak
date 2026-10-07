"""
Point d'entrée de compatibilité — SMAML
========================================
L'ancienne « couche projet » n'existe plus : conformément à la
conception à 4 phases, c'est le Manager qui reçoit le projet et qui
organise tout (voir orchestration.py).

Ce fichier ne contient plus aucune logique de migration. Il conserve
seulement les noms qu'utilisent l'API et le benchmark, pour qu'ils
fonctionnent sans modification :

    migrer_projet(chemin, dossier_sortie)   → orchestration à 4 phases
    migrer_fichier(chemin_php)              → un projet d'un seul fichier
    PROGRESSION, reinitialiser_progression  → avancement pour l'interface

    py -X utf8 pipeline_complet.py application.zip [dossier_sortie]
"""

import os
import shutil
import sys
import tempfile

from orchestration import PROGRESSION, principal
from orchestration import migrer_projet as _migrer_projet


def reinitialiser_progression(fichiers: list):
    PROGRESSION.update({
        "fichiers": [os.path.basename(f) for f in fichiers],
        "statuts": {os.path.basename(f): "en_attente" for f in fichiers},
        "fichier_courant": None, "modules_termines": [],
        "coordinateur_courant": None})


def migrer_projet(chemin: str, dossier_sortie: str = "outputs_projet",
                  max_iterations: int = 5, **_options) -> dict:
    return _migrer_projet(chemin, dossier_sortie, max_iterations)


def migrer_fichier(chemin_php: str, contexte_projet: dict = None,
                   max_iterations: int = 5, **_options) -> dict:
    """Un fichier seul est migré comme un projet d'un seul fichier."""
    dossier = tempfile.mkdtemp(prefix="smaml_fichier_")
    shutil.copy(chemin_php, dossier)
    sortie = tempfile.mkdtemp(prefix="smaml_sortie_")
    rapport = _migrer_projet(dossier, sortie, max_iterations)
    fichier = (rapport.get("fichiers_migres") or [{}])[0]
    return {"fichier_source": os.path.basename(chemin_php),
            "modules": fichier.get("modules", []),
            "fonctions_migrees": [m.get("nom_python") for m in fichier.get("modules", [])],
            "rapport": rapport}


if __name__ == "__main__":
    principal(sys.argv[1:])