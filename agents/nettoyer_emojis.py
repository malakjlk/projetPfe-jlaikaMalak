"""
Remplace les émoticônes par du texte dans le code du dossier.

    py -X utf8 nettoyer_emojis.py              montre ce qui changerait, sans rien modifier
    py -X utf8 nettoyer_emojis.py --appliquer  applique les remplacements

Les symboles ne sont pas supprimés mais REMPLACÉS par du texte : dans les
tests, « ✅ » et « ❌ » distinguent un succès d'un échec, et cette
information doit rester. Les accents du français ne sont jamais touchés.

Précautions : seuls les fichiers .py du dossier sont traités ; après
chaque modification, le fichier doit encore compiler, sinon l'original
est restauré ; les fins de ligne (Windows) sont conservées.
"""

import os
import py_compile
import re
import sys

REMPLACEMENTS = [
    ("✅", "[OK]"), ("❌", "[ECHEC]"), ("✓", "[OK]"), ("✗", "[X]"),
    ("⚠️", "[ATTENTION]"), ("⚠", "[ATTENTION]"), ("🔁", "[ITERATION]"),
    ("🔒", "[VERROU]"), ("⚖️", "[ARBITRAGE]"), ("⚖", "[ARBITRAGE]"),
    ("⏳", "[ATTENTE]"), ("✂️", "[TRONQUE]"), ("✂", "[TRONQUE]"),
    ("↪", "->"), ("▶", ">"), ("🔄", "[BASCULE]"), ("🚀", ""), ("💡", "[IDEE]"),
    ("📊", ""), ("📄", ""), ("🧪", ""), ("🔍", ""), ("🛑", "[ARRET]"), ("ℹ️", "[INFO]"),
]
# Tout autre symbole du registre des émoticônes, retiré (avec son sélecteur).
AUTRES = re.compile("[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U00002600-\U000026FF\uFE0F]")

ICI = os.path.dirname(os.path.abspath(__file__))


def nettoyer(texte: str) -> str:
    for symbole, remplacement in REMPLACEMENTS:
        texte = texte.replace(symbole, remplacement)
    return AUTRES.sub("", texte)


def main(appliquer: bool):
    modifies, restaures = 0, []
    for nom in sorted(os.listdir(ICI)):
        if not nom.endswith(".py") or nom == os.path.basename(__file__):
            continue
        chemin = os.path.join(ICI, nom)
        with open(chemin, encoding="utf-8", newline="") as f:     # newline="" : CRLF conservés
            original = f.read()
        nouveau = nettoyer(original)
        if nouveau == original:
            continue
        nombre = sum(original.count(s) for s, _ in REMPLACEMENTS) + len(AUTRES.findall(original))
        print(f"  {nom:<36} {nombre} symbole(s)")
        modifies += 1
        if not appliquer:
            continue
        with open(chemin, "w", encoding="utf-8", newline="") as f:
            f.write(nouveau)
        try:
            py_compile.compile(chemin, doraise=True)
        except py_compile.PyCompileError:
            with open(chemin, "w", encoding="utf-8", newline="") as f:
                f.write(original)
            restaures.append(nom)
    if not modifies:
        print("Aucune émoticône trouvée.")
    elif not appliquer:
        print(f"\n{modifies} fichier(s) seraient modifiés. Pour appliquer :"
              f"\n  py -X utf8 nettoyer_emojis.py --appliquer")
    else:
        print(f"\n{modifies - len(restaures)} fichier(s) modifié(s).")
        for nom in restaures:
            print(f"  {nom} : ne compilait plus après remplacement, original restauré")


if __name__ == "__main__":
    main("--appliquer" in sys.argv)
