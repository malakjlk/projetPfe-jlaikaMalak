"""
Mesure de modernisation — SMAML
================================
Le sujet demande une conversion vers une « architecture moderne ».
Encore faut-il pouvoir le mesurer : ce module note le code Python
produit sur sept indicateurs objectifs, tirés de l'analyse syntaxique
et non d'une impression de lecture.

Ce score n'entre PAS dans la décision du Réviseur : il ne dit rien de
la correction du code, seulement de son style d'architecture. Le
mélanger au score de confiance reviendrait à confondre « correct » et
« moderne ».

    py -X utf8 modernisation.py     (démonstration sur deux exemples)
"""

import ast

# Chaque indicateur vaut un poids ; le score est la somme des poids
# obtenus rapportée au total applicable. Un indicateur non applicable
# (pas de fonction, pas d'accès base) est retiré du calcul plutôt que
# compté comme un échec.
POIDS = {
    # Architecture moderne
    "annotations_types": 15,
    "validation_typee": 12,
    "injection_dependances": 12,
    "erreurs_typees": 15,
    "sans_etat_global": 8,
    "acces_donnees_parametre": 8,
    "documentation": 8,
    # Style fonctionnel — le PHP legacy en est l'exact opposé
    # (globales, superglobales, arguments modifiés sur place).
    # Une fonction sans effet de bord est aussi plus facile à
    # vérifier : Hypothesis et Z3 y sont bien plus efficaces.
    "fonctions_pures": 10,
    "arguments_preserves": 6,
    "style_declaratif": 6,
}


def _nettoyer(code: str) -> str:
    if "```python" in code:
        code = code.split("```python")[1]
    if "```" in code:
        code = code.split("```")[0]
    return code


def mesurer_modernisation(code_python: str) -> dict:
    """
    Note le code généré sur sept indicateurs d'architecture moderne.
    Retourne le score, le détail et les indicateurs non applicables.
    """
    resultat = {"score": 0.0, "indicateurs": {}, "non_applicables": [],
                "erreur": None}

    # Sans code, il n'y a rien à mesurer : renvoyer 25 % laisserait
    # croire à une évaluation, alors qu'aucun indicateur n'a été évalué.
    if not (code_python or "").strip():
        resultat["erreur"] = "aucun code produit"
        resultat["score"] = None
        return resultat

    try:
        arbre = ast.parse(_nettoyer(code_python))
    except SyntaxError as e:
        resultat["erreur"] = f"code non analysable : {e}"
        return resultat

    texte = _nettoyer(code_python)
    fonctions = [n for n in ast.walk(arbre)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    classes = [n for n in ast.walk(arbre) if isinstance(n, ast.ClassDef)]

    # ── 1. Annotations de types ──
    if fonctions:
        annotes = 0
        total_annotables = 0
        for fonction in fonctions:
            arguments = [a for a in fonction.args.args if a.arg != "self"]
            total_annotables += len(arguments) + 1      # + le retour
            annotes += sum(1 for a in arguments if a.annotation is not None)
            annotes += 1 if fonction.returns is not None else 0
        resultat["indicateurs"]["annotations_types"] = (
            annotes / total_annotables if total_annotables else 0.0)
    else:
        resultat["non_applicables"].append("annotations_types")

    # ── 2. Validation typée des entrées (Pydantic, dataclass, Enum) ──
    bases = [b.id if isinstance(b, ast.Name) else
             (b.attr if isinstance(b, ast.Attribute) else "")
             for c in classes for b in c.bases]
    decorateurs = [d.id if isinstance(d, ast.Name) else
                   (d.attr if isinstance(d, ast.Attribute) else "")
                   for c in classes for d in c.decorator_list]
    resultat["indicateurs"]["validation_typee"] = 1.0 if (
        "BaseModel" in bases or "Enum" in bases or "dataclass" in decorateurs
        or "field_validator" in texte or "validator" in texte) else 0.0

    # ── 3. Injection de dépendances ──
    # Les ressources (session, moteur, client) arrivent en paramètre
    # au lieu d'être créées ou lues dans une variable globale.
    ressources = ("db", "session", "conn", "connexion", "moteur", "engine",
                  "client", "repo", "repository")
    injectees = any(a.arg.lower() in ressources
                    for f in fonctions for a in f.args.args)
    resultat["indicateurs"]["injection_dependances"] = 1.0 if (
        injectees or "Depends(" in texte) else 0.0

    # ── 4. Gestion d'erreurs typée ──
    # Une exception explicite plutôt qu'un die(), un echo ou un return
    # muet — c'est la traduction correcte du legacy PHP.
    leves = [n for n in ast.walk(arbre) if isinstance(n, ast.Raise)]
    exceptions_nommees = 0
    for leve in leves:
        cible = leve.exc
        if isinstance(cible, ast.Call) and isinstance(cible.func, ast.Name):
            exceptions_nommees += 0 if cible.func.id == "Exception" else 1
        elif isinstance(cible, ast.Call) and isinstance(cible.func, ast.Attribute):
            exceptions_nommees += 1
    if leves:
        resultat["indicateurs"]["erreurs_typees"] = (
            exceptions_nommees / len(leves))
    else:
        # Aucun rejet dans le code : l'indicateur ne s'applique que si
        # la fonction est censée en avoir un.
        resultat["non_applicables"].append("erreurs_typees")

    # ── 5. Absence d'état global ──
    globales = [n for n in ast.walk(arbre) if isinstance(n, ast.Global)]
    affectations_module = [
        n for n in arbre.body
        if isinstance(n, ast.Assign)
        and not all(isinstance(c, ast.Name) and c.id.isupper()
                    for c in n.targets if isinstance(c, ast.Name))]
    resultat["indicateurs"]["sans_etat_global"] = 0.0 if (
        globales or len(affectations_module) > 2) else 1.0

    # ── 6. Accès aux données paramétré ──
    # Requête paramétrée ou ORM, jamais de concaténation.
    touche_donnees = any(mot in texte for mot in
                         ("execute", "query", "select", "insert", "update",
                          "delete"))
    if touche_donnees:
        concatenation = ("\" + " in texte or "' + " in texte
                         or "%s\" %" in texte or "f\"SELECT" in texte
                         or "f\"select" in texte)
        parametre = (":" in texte and "text(" in texte) or "%s" in texte \
            or "?" in texte or ".filter(" in texte or "bindparams" in texte
        resultat["indicateurs"]["acces_donnees_parametre"] = (
            0.0 if concatenation else (1.0 if parametre else 0.5))
    else:
        resultat["non_applicables"].append("acces_donnees_parametre")

    # ── 7. Documentation ──
    if fonctions or classes:
        documentes = sum(1 for n in fonctions + classes
                         if ast.get_docstring(n))
        resultat["indicateurs"]["documentation"] = (
            documentes / len(fonctions + classes))
    else:
        resultat["non_applicables"].append("documentation")

    # ── 8. Fonctions pures ──
    # Une fonction est tenue pour pure si elle n'écrit dans aucune
    # globale, ne modifie pas ses arguments et ne provoque aucun effet
    # observable (écriture, affichage, appel réseau ou base).
    EFFETS = ("print", "open", "write", "execute", "commit", "send",
              "post", "get", "delete", "add", "save", "log", "input")

    def a_un_effet(fonction) -> bool:
        for noeud in ast.walk(fonction):
            if isinstance(noeud, ast.Global):
                return True
            if isinstance(noeud, ast.Call):
                nom = ""
                if isinstance(noeud.func, ast.Name):
                    nom = noeud.func.id
                elif isinstance(noeud.func, ast.Attribute):
                    nom = noeud.func.attr
                if nom.lower() in EFFETS:
                    return True
        return False

    def modifie_ses_arguments(fonction) -> bool:
        noms_arguments = {a.arg for a in fonction.args.args}
        # Alias : « for ligne in lignes » fait de `ligne` un élément du
        # tableau reçu. Le modifier revient à modifier l'argument, ce
        # qui est l'effet de bord le plus courant dans le code legacy.
        for noeud in ast.walk(fonction):
            if isinstance(noeud, ast.For) and isinstance(noeud.iter, ast.Name) \
                    and noeud.iter.id in noms_arguments \
                    and isinstance(noeud.target, ast.Name):
                noms_arguments.add(noeud.target.id)
        for noeud in ast.walk(fonction):
            # arg[...] = ... ou arg.attribut = ...
            cibles = []
            if isinstance(noeud, (ast.Assign, ast.AugAssign)):
                cibles = (noeud.targets if isinstance(noeud, ast.Assign)
                          else [noeud.target])
            for cible in cibles:
                base = cible
                while isinstance(base, (ast.Subscript, ast.Attribute)):
                    base = base.value
                if isinstance(base, ast.Name) and base.id in noms_arguments \
                        and base is not cible:
                    return True
            # arg.append(...), arg.update(...), arg.pop(...)
            if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute):
                if (isinstance(noeud.func.value, ast.Name)
                        and noeud.func.value.id in noms_arguments
                        and noeud.func.attr in ("append", "extend", "update",
                                                "pop", "remove", "insert",
                                                "clear", "sort")):
                    return True
        return False

    if fonctions:
        pures = sum(1 for f in fonctions if not a_un_effet(f))
        if pures == 0 and touche_donnees:
            # Un module dont toutes les fonctions accèdent aux données
            # ne PEUT pas être pur : l'indicateur ne s'applique pas.
            resultat["non_applicables"].append("fonctions_pures")
        else:
            resultat["indicateurs"]["fonctions_pures"] = pures / len(fonctions)

        preserves = sum(1 for f in fonctions if not modifie_ses_arguments(f))
        resultat["indicateurs"]["arguments_preserves"] = (
            preserves / len(fonctions))
    else:
        resultat["non_applicables"].extend(["fonctions_pures",
                                            "arguments_preserves"])

    # ── 9. Style déclaratif ──
    # Compréhensions et fonctions d'agrégation plutôt que boucles
    # avec accumulateur.
    comprehensions = sum(1 for n in ast.walk(arbre) if isinstance(
        n, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)))
    agregations = sum(texte.count(m) for m in
                      ("sum(", "map(", "filter(", "any(", "all(", "sorted(",
                       "min(", "max("))
    boucles = sum(1 for n in ast.walk(arbre)
                  if isinstance(n, (ast.For, ast.While)))
    declaratif = comprehensions + agregations
    if declaratif or boucles:
        resultat["indicateurs"]["style_declaratif"] = (
            declaratif / (declaratif + boucles))
    else:
        resultat["non_applicables"].append("style_declaratif")

    # ── Score : moyenne pondérée des indicateurs applicables ──
    total_poids = sum(POIDS[i] for i in resultat["indicateurs"])
    if total_poids:
        obtenu = sum(POIDS[i] * v for i, v in resultat["indicateurs"].items())
        resultat["score"] = round(100 * obtenu / total_poids, 1)
    return resultat


def resume_modernisation(mesure: dict) -> str:
    """Une ligne lisible pour le journal de migration."""
    if mesure.get("erreur"):
        return f"modernisation non mesurée ({mesure['erreur']})"
    faibles = [nom for nom, valeur in mesure["indicateurs"].items()
               if valeur < 0.5]
    detail = (" — à renforcer : " + ", ".join(n.replace("_", " ")
                                              for n in faibles)
              if faibles else "")
    return f"modernisation {mesure['score']:.0f}%{detail}"


if __name__ == "__main__":
    import json

    LEGACY = '''
def get_user(email):
    conn = connect()
    sql = "SELECT * FROM users WHERE email='" + email + "'"
    resultat = conn.execute(sql)
    if not resultat:
        raise Exception("introuvable")
    return resultat
'''

    MODERNE = '''
from typing import Optional
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session


class Utilisateur(BaseModel):
    email: str
    nom: str


def get_user(email: str, db: Session = Depends(get_db)) -> Optional[Utilisateur]:
    """Retourne l'utilisateur correspondant à l'adresse fournie."""
    ligne = db.execute(text("SELECT * FROM users WHERE email = :email"),
                       {"email": email}).fetchone()
    if ligne is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return Utilisateur(**dict(ligne))
'''

    for titre, code in (("Code de style legacy", LEGACY),
                        ("Code de style moderne", MODERNE)):
        mesure = mesurer_modernisation(code)
        print(f"\n{titre} : {resume_modernisation(mesure)}")
        print(json.dumps(mesure["indicateurs"], indent=2, ensure_ascii=False))