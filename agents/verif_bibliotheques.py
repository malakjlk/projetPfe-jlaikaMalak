"""
Vérifie quelles bibliothèques du projet se chargent, et lesquelles
sont bloquées par Windows (Contrôle intelligent des applications).

Usage : py -X utf8 verif_bibliotheques.py
"""
import subprocess

# (module Python, rôle dans SMAML)
BIBLIOTHEQUES = [
    ("numpy", "calcul — utilisé partout"),
    ("torch", "CodeBERT (encodage RAG)"),
    ("transformers", "CodeBERT (encodage RAG)"),
    ("faiss", "index de recherche RAG"),
    ("z3", "solveur du Vérificateur de propriétés"),
    ("crosshair", "exécution symbolique du Vérificateur"),
    ("tree_sitter", "parseur de l'Analyste"),
    ("tree_sitter_php", "grammaire PHP de l'Analyste"),
    ("tree_sitter_languages", "grammaires (autre paquet possible)"),
    ("groq", "génération du code"),
    ("crewai", "orchestration"),
    ("fastapi", "API"),
]

print("=" * 64)
print(f"{'Bibliothèque':<24}{'État':<16}Rôle")
print("=" * 64)
bloquees = []
for module, role in BIBLIOTHEQUES:
    try:
        __import__(module)
        etat = "OK"
    except ModuleNotFoundError:
        etat = "non installée"
    except Exception as e:
        texte = str(e).lower()
        if "strat" in texte or "policy" in texte or "dll load failed" in texte:
            etat = "BLOQUÉE"
            bloquees.append(module)
        else:
            etat = f"erreur"
            print(f"   ({module} : {type(e).__name__} — {str(e)[:60]})")
    print(f"{module:<24}{etat:<16}{role}")

# PHP est un exécutable, pas un module Python
try:
    sortie = subprocess.run(["php", "-m"], capture_output=True,
                            text=True, timeout=15)
    php = "OK" if sortie.returncode == 0 else "erreur"
    sqlite = "OK" if "pdo_sqlite" in sortie.stdout.lower() else "absent"
except Exception as e:
    texte = str(e).lower()
    php = "BLOQUÉ" if ("strat" in texte or "policy" in texte) else "absent"
    sqlite = "?"
print(f"{'php (exécutable)':<24}{php:<16}exécution du PHP d'origine")
print(f"{'pdo_sqlite':<24}{sqlite:<16}base simulée du Comparateur")

print("=" * 64)
if bloquees:
    print(f"Bloquées par Windows : {', '.join(bloquees)}")
else:
    print("Aucune bibliothèque bloquée.")
print("« non installée » est normal pour les paquets de grammaire que "
      "ton projet n'utilise pas.")