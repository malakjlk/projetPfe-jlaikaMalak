import json
import os

dataset_final = []
compteur = 1

fichiers = [
    ("paires_codesearchnet.json", "CodeSearchNet"),
    ("paires_securite.json", "Sécurité"),
    ("paires_erreurs.json", "Gestion erreurs"),
    ("paires_qualite.json", "Qualité code"),
    ("paires_architecture.json", "Architecture")
]

for fichier, nom in fichiers:
    if os.path.exists(fichier):
        with open(fichier, "r", encoding="utf-8") as f:
            paires = json.load(f)
        for p in paires:
            p["id"] = compteur
            compteur += 1
        dataset_final.extend(paires)
        print(f"{nom} : {len(paires)} paires")
    else:
        print(f"Fichier manquant : {fichier}")

with open("dataset_final.json", "w",
          encoding="utf-8") as f:
    json.dump(dataset_final, f,
              ensure_ascii=False, indent=2)

print(f"\nDataset final : {len(dataset_final)} paires")
print("\nPar source :")
sources = {}
for p in dataset_final:
    s = p.get("source", "inconnu")
    sources[s] = sources.get(s, 0) + 1
for s, n in sources.items():
    print(f"  {s} : {n}")

print("\nPar catégorie :")
cats = {}
for p in dataset_final:
    c = p.get("categorie", "inconnu")
    cats[c] = cats.get(c, 0) + 1
for c, n in sorted(cats.items()):
    print(f"  {c} : {n}")

print("\nFichier sauvegardé : dataset_final.json")