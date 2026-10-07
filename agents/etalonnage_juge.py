"""
Étalonnage du LLM juge — SMAML
===============================
La note du juge n'a de valeur que si elle concorde avec celle d'un
humain. Cet outil mesure cette concordance.

Méthode : notation À L'AVEUGLE
------------------------------
1. Préparer la grille, à partir d'un ou plusieurs rapports de migration :
       py -X utf8 etalonnage_juge.py preparer rapport_migration.json grille.csv
   Deux fichiers sont produits :
     • grille.csv          à remplir : une note humaine de 1 à 5 par critère
     • grille_codes.md     le PHP et le Python de chaque module, à lire
   Les notes du juge sont mises de côté dans un fichier séparé : tu ne les
   vois pas pendant que tu notes, sinon tu serais influencée.

2. Noter, dans grille.csv, la colonne note_humaine (1 à 5), avec la même
   grille que le juge.

3. Calculer l'accord :
       py -X utf8 etalonnage_juge.py calculer grille.csv

Mesures d'accord
----------------
  • kappa de Cohen pondéré (quadratique) : la référence pour des notes
    ordinales ; 0 = accord dû au hasard, 1 = accord parfait. Un écart de
    deux points est pénalisé quatre fois plus qu'un écart d'un point.
  • corrélation de Spearman : le juge classe-t-il les modules dans le
    même ordre que l'humain ?
  • accord exact et accord à un point près, écart moyen.

Interprétation du kappa (Landis et Koch, 1977) :
  < 0,20 faible · 0,21-0,40 passable · 0,41-0,60 modéré ·
  0,61-0,80 substantiel · > 0,80 presque parfait
"""

from __future__ import annotations

import csv
import json
import os
import sys

from agent_juge import GRILLE


# ═══ MESURES D'ACCORD ════════════════════════════════════

def kappa_pondere(humain: list, juge: list, k_min: int = 1, k_max: int = 5) -> float:
    """Kappa de Cohen à pondération quadratique, pour des notes ordinales."""
    n = len(humain)
    categories = list(range(k_min, k_max + 1))
    k = len(categories)
    if n == 0:
        return float("nan")
    observe = [[0] * k for _ in range(k)]
    for h, j in zip(humain, juge):
        observe[h - k_min][j - k_min] += 1
    marge_h = [sum(ligne) for ligne in observe]
    marge_j = [sum(observe[i][c] for i in range(k)) for c in range(k)]
    poids = [[(i - c) ** 2 / (k - 1) ** 2 for c in range(k)] for i in range(k)]
    desaccord_observe = sum(poids[i][c] * observe[i][c]
                            for i in range(k) for c in range(k)) / n
    desaccord_attendu = sum(poids[i][c] * marge_h[i] * marge_j[c]
                            for i in range(k) for c in range(k)) / (n * n)
    if desaccord_attendu == 0:
        return 1.0 if desaccord_observe == 0 else 0.0
    return 1 - desaccord_observe / desaccord_attendu


def _rangs(valeurs: list) -> list:
    """Rangs moyens, ex aequo compris."""
    ordre = sorted(range(len(valeurs)), key=lambda i: valeurs[i])
    rangs = [0.0] * len(valeurs)
    i = 0
    while i < len(ordre):
        j = i
        while j + 1 < len(ordre) and valeurs[ordre[j + 1]] == valeurs[ordre[i]]:
            j += 1
        moyen = (i + j) / 2 + 1
        for t in range(i, j + 1):
            rangs[ordre[t]] = moyen
        i = j + 1
    return rangs


def spearman(a: list, b: list) -> float:
    if len(a) < 2:
        return float("nan")
    ra, rb = _rangs(a), _rangs(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else float("nan")


def interpreter_kappa(k: float) -> str:
    if k != k:
        return "indéterminé"
    for seuil, libelle in ((0.20, "faible"), (0.40, "passable"), (0.60, "modéré"),
                           (0.80, "substantiel")):
        if k <= seuil:
            return libelle
    return "presque parfait"


def mesures(humain: list, juge: list) -> dict:
    ecarts = [abs(h - j) for h, j in zip(humain, juge)]
    return {
        "effectif": len(humain),
        "kappa_pondere": round(kappa_pondere(humain, juge), 3),
        "spearman": round(spearman(humain, juge), 3),
        "accord_exact": round(100 * sum(e == 0 for e in ecarts) / len(ecarts), 1),
        "accord_a_un_point": round(100 * sum(e <= 1 for e in ecarts) / len(ecarts), 1),
        "ecart_moyen": round(sum(ecarts) / len(ecarts), 2),
    }


# ═══ PRÉPARATION ET CALCUL ═══════════════════════════════

def preparer(rapports: list, grille_csv: str):
    lignes, codes, notes_juge = [], [], {}
    for chemin in rapports:
        with open(chemin, encoding="utf-8") as f:
            rapport = json.load(f)
        for fichier in rapport.get("fichiers_migres", []):
            for module in fichier.get("modules", []):
                jugement = module.get("jugement") or {}
                if jugement.get("statut") != "evalue":
                    continue
                ident = f"{fichier['source']}::{module['nom_python']}"
                codes.append((ident, module.get("code_php", ""),
                              module.get("code_python", "")))
                for critere in GRILLE:
                    lignes.append({"module": ident, "critere": critere,
                                   "note_humaine": ""})
                    notes_juge[f"{ident}|{critere}"] = \
                        jugement["criteres"][critere]["note"]

    with open(grille_csv, "w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=["module", "critere", "note_humaine"])
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    with open(grille_csv + ".juge.json", "w", encoding="utf-8") as f:
        json.dump(notes_juge, f, ensure_ascii=False, indent=2)

    racine = os.path.splitext(grille_csv)[0]
    with open(racine + "_codes.md", "w", encoding="utf-8") as f:
        f.write("# Codes à évaluer\n\nGrille :\n\n")
        for cle, (titre, echelle) in GRILLE.items():
            f.write(f"- **{cle}** — {titre}. {echelle}\n")
        for ident, php, python in codes:
            f.write(f"\n---\n\n## {ident}\n\n### PHP d'origine\n\n"
                    f"```php\n{php}\n```\n\n### Python migré\n\n"
                    f"```python\n{python}\n```\n")
    print(f"{len(codes)} module(s) à noter, {len(lignes)} note(s) à donner.")
    print(f"  à remplir : {grille_csv}")
    print(f"  à lire    : {racine}_codes.md")


def calculer(grille_csv: str) -> dict:
    with open(grille_csv + ".juge.json", encoding="utf-8") as f:
        notes_juge = json.load(f)
    par_critere, global_h, global_j = {}, [], []
    with open(grille_csv, encoding="utf-8") as f:
        for ligne in csv.DictReader(f):
            if not (ligne.get("note_humaine") or "").strip():
                continue
            h = int(ligne["note_humaine"])
            j = notes_juge[f"{ligne['module']}|{ligne['critere']}"]
            par_critere.setdefault(ligne["critere"], ([], []))
            par_critere[ligne["critere"]][0].append(h)
            par_critere[ligne["critere"]][1].append(j)
            global_h.append(h)
            global_j.append(j)
    if not global_h:
        sys.exit("Aucune note humaine dans la grille.")

    resultat = {"global": mesures(global_h, global_j),
                "par_critere": {c: mesures(h, j) for c, (h, j) in par_critere.items()}}
    g = resultat["global"]
    print(f"Accord juge / humain sur {g['effectif']} notes :")
    print(f"  kappa pondéré : {g['kappa_pondere']} ({interpreter_kappa(g['kappa_pondere'])})")
    print(f"  Spearman      : {g['spearman']}")
    print(f"  accord exact  : {g['accord_exact']} %   à un point près : "
          f"{g['accord_a_un_point']} %   écart moyen : {g['ecart_moyen']}")
    print("\nPar critère :")
    for c, m in resultat["par_critere"].items():
        print(f"  {c:<20} kappa {m['kappa_pondere']:>6}  "
              f"({interpreter_kappa(m['kappa_pondere'])})  écart moyen {m['ecart_moyen']}")
    return resultat


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "preparer":
        preparer(sys.argv[2:-1], sys.argv[-1])
    elif len(sys.argv) == 3 and sys.argv[1] == "calculer":
        calculer(sys.argv[2])
    else:
        print(__doc__)