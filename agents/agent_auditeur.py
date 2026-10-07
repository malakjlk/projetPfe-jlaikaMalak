import subprocess
import json
import re as _re_aud
import tempfile
import os
import sys


def lancer_bandit(code_python: str) -> dict:
    """
    Lance Bandit (analyse statique de sécurité Python)
    sur le code généré et retourne le rapport JSON.
    """

    # Nettoyer le code (enlever les balises markdown)
    code_nettoye = code_python
    if "```python" in code_nettoye:
        code_nettoye = code_nettoye.split("```python")[1]
    if "```" in code_nettoye:
        code_nettoye = code_nettoye.split("```")[0]

    # Sauvegarder dans un fichier temporaire
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(code_nettoye)
        chemin_temp = f.name

    resultat = {
        "failles_detectees": [],
        "score_securite": 100.0,
        "erreur": None
    }

    try:
        process = subprocess.run(
            [sys.executable, "-m", "bandit", "-f", "json", chemin_temp],
            capture_output=True,
            text=True,
            timeout=30
        )

        if process.stdout:
            rapport_bandit = json.loads(process.stdout)

            for issue in rapport_bandit.get("results", []):
                resultat["failles_detectees"].append({
                    "type": issue.get("test_name", ""),
                    "cwe": issue.get("issue_cwe", {}).get("id", "N/A"),
                    "severity": issue.get("issue_severity", "").lower(),
                    "confidence": issue.get("issue_confidence", "").lower(),
                    "description": issue.get("issue_text", ""),
                    "ligne": issue.get("line_number", 0)
                })

            # Calcul du score sécurité
            nb_failles = len(resultat["failles_detectees"])
            penalites = {
                "high": 25,
                "medium": 10,
                "low": 5
            }
            penalite_totale = sum(
                penalites.get(f["severity"], 5)
                for f in resultat["failles_detectees"]
            )
            resultat["score_securite"] = max(0, 100 - penalite_totale)

    except Exception as e:
        resultat["erreur"] = str(e)
    finally:
        os.unlink(chemin_temp)

    return resultat


# ─── DIMENSION 1 : INVARIANTS RÉELLEMENT APPLIQUÉS ───
# Chercher « len( » dans le texte du code ne prouve rien : le mot peut
# venir d'un commentaire, d'une docstring ou d'un calcul sans rapport.
# On analyse donc la STRUCTURE du code et on ne retient que les gardes
# qui lèvent réellement une exception — c'est la seule chose qui
# empêche une donnée invalide de passer.

def _extraire_gardes(code_python: str) -> list:
    """
    Conditions qui protègent la fonction : un `if` dont le corps lève
    une exception, ou une assertion. Retourne pour chacune le texte de
    la condition, sa ligne, et les nombres qu'elle contient.
    """
    import ast

    code = code_python
    if "```python" in code:
        code = code.split("```python")[1]
    if "```" in code:
        code = code.split("```")[0]

    try:
        arbre = ast.parse(code)
    except SyntaxError:
        return []

    def leve_exception(corps) -> bool:
        for noeud in corps:
            if isinstance(noeud, ast.Raise):
                return True
            # un return dans une garde compte aussi comme un rejet
            if isinstance(noeud, ast.Return):
                valeur = noeud.value
                if valeur is None or (isinstance(valeur, ast.Constant)
                                      and valeur.value in (False, None)):
                    return True
        return False

    gardes = []
    for noeud in ast.walk(arbre):
        # Un « except » qui relève une exception est aussi une garde :
        # c'est la façon pythonique d'écrire « if (!$conn) die(...) ».
        if isinstance(noeud, ast.ExceptHandler) and leve_exception(noeud.body):
            try:
                type_attrape = (ast.unparse(noeud.type) if noeud.type
                                else "Exception")
            except Exception:
                type_attrape = "Exception"
            gardes.append({"texte": f"except {type_attrape} -> raise",
                           "ligne": getattr(noeud, "lineno", 0),
                           "nombres": [], "genre": "exception"})
            continue

        condition = None
        if isinstance(noeud, ast.If) and leve_exception(noeud.body):
            condition = noeud.test
        elif isinstance(noeud, ast.Assert):
            condition = noeud.test
        if condition is None:
            continue
        try:
            texte = ast.unparse(condition)
        except Exception:
            continue
        nombres = [n.value for n in ast.walk(condition)
                   if isinstance(n, ast.Constant)
                   and isinstance(n.value, (int, float))
                   and not isinstance(n.value, bool)]
        gardes.append({"texte": texte, "ligne": getattr(noeud, "lineno", 0),
                       "nombres": nombres, "genre": "condition"})
    return gardes


MOTS_ACCES = ("role", "permission", "droit", "admin", "auth", "token",
              "jeton", "session", "habilitation")


# Certains invariants ne sont pas des gardes mais des APPELS : un
# échappement, un hachage, une comparaison de secret. Les chercher
# parmi les conditions reviendrait à les déclarer systématiquement
# violés.
APPELS_ATTENDUS = {
    "assainissement_sortie": ("html.escape", "escape(", "markupsafe",
                              "bleach", "quote(", "sanitize"),
    "hachage_mot_de_passe": ("bcrypt", "passlib", "hashlib", "argon2",
                             "pbkdf2", "generate_password_hash",
                             "check_password_hash", "scrypt"),
    "comparaison_authentification": ("compare_digest", "checkpw", "verify(",
                                     "check_password"),
}

# Une comparaison vaut authentification seulement si elle porte sur un
# secret : accepter n'importe quel « == » déclarerait l'invariant
# préservé dans presque tout code. On regarde donc ce qui entoure le
# signe de comparaison, car le secret est souvent indexé
# (user["password"] == mot_de_passe).
MOTS_SECRET = ("password", "passwd", "mot_de_passe", "token", "jeton",
               "secret", "hash", "digest", "pwd")


def _comparaison_de_secret(code: str):
    """Comparaison portant sur un secret, ou None."""
    for comparaison in _re_aud.finditer(r"[!=]=", code):
        debut = max(0, comparaison.start() - 45)
        entourage = code[debut:comparaison.end() + 45].lower()
        if any(mot in entourage for mot in MOTS_SECRET):
            return code[debut:comparaison.end() + 20].strip().splitlines()[-1]
    return None


def _appel_correspondant(invariant: dict, code_python: str):
    """Appel attendu pour un invariant qui n'est pas une garde."""
    type_inv = (invariant.get("type") or "").lower()
    attendus = APPELS_ATTENDUS.get(type_inv)
    if not attendus:
        return None
    if type_inv == "comparaison_authentification":
        trouve = _comparaison_de_secret(code_python)
        if trouve:
            return f"comparaison de secret : {trouve[:60]}"
    code = code_python.lower()
    for appel in attendus:
        if appel.lower() in code:
            return appel
    return None


def _garde_correspondante(invariant: dict, gardes: list, seuil):
    """Garde qui applique cet invariant, ou None."""
    type_inv = (invariant.get("type") or "").lower()

    for garde in gardes:
        texte = garde["texte"].lower()

        if type_inv == "validation_longueur":
            if "len(" in texte or "strlen" in texte:
                if seuil is None or seuil in garde["nombres"]:
                    return garde, None
                return garde, (f"seuil différent : attendu {seuil}, "
                               f"trouvé {garde['nombres'] or 'aucun'}")

        elif type_inv == "validation_format":
            if any(m in texte for m in ("isupper", "islower", "isalpha",
                                        "isdigit", "match(", "search(",
                                        "fullmatch", "regex")):
                return garde, None

        elif type_inv == "validation_existence":
            if ("is none" in texte or "== none" in texte
                    or texte.startswith("not ")
                    or garde.get("genre") == "exception"):
                return garde, None

        elif type_inv == "validation_type":
            if any(m in texte for m in ("isinstance", "isdigit", "type(",
                                        "isnumeric")):
                return garde, None

        elif type_inv in ("controle_acces", "validation_role"):
            if any(m in texte for m in MOTS_ACCES):
                return garde, None

        else:
            # Invariant numérique : comparaison avec le même seuil
            if seuil is not None and seuil in garde["nombres"]:
                return garde, None

    return None, None


def _seuil_invariant(invariant: dict):
    """Seuil numérique attendu, tiré du code PHP d'origine."""
    import re as _re
    texte = f"{invariant.get('code', '')} {invariant.get('description', '')}"
    nombres = _re.findall(r"-?\d+(?:\.\d+)?", texte)
    if not nombres:
        return None
    valeur = float(nombres[0])
    return int(valeur) if valeur == int(valeur) else valeur


def verifier_invariants_securite(code_python: str, invariants: list,
                                 rapport_formel: dict = None) -> dict:
    """
    Vérifie que les invariants du code legacy sont réellement appliqués
    dans le code généré (Dimension 1).

    Deux sources de preuve, de la plus forte à la plus faible :
      1. le Vérificateur de propriétés, quand il a pu se prononcer :
         un contre-exemple de Z3 est une réfutation formelle ;
      2. l'analyse structurelle du code : existe-t-il une garde qui
         rejette l'entrée invalide ?
    """
    resultat = {"invariants_preserves": [], "invariants_violes": [],
                "invariants_douteux": [], "preuves": [], "score": 0.0}

    gardes = _extraire_gardes(code_python)

    # Propriétés déjà tranchées par le Vérificateur (Z3)
    refutees = {p.get("libelle", "") for p in
                ((rapport_formel or {}).get("proprietes") or [])
                if p.get("statut") == "refutee"}

    for invariant in invariants:
        seuil = _seuil_invariant(invariant)
        description = invariant.get("description", "")

        refute = any(description[:30] in libelle or str(seuil) in libelle
                     for libelle in refutees) if refutees else False
        if refute:
            resultat["invariants_violes"].append(invariant)
            resultat["preuves"].append({
                "invariant": description, "verdict": "violé",
                "source": "Vérificateur de propriétés (contre-exemple)"})
            continue

        appel = _appel_correspondant(invariant, code_python)
        if appel:
            resultat["invariants_preserves"].append(invariant)
            resultat["preuves"].append({
                "invariant": description, "verdict": "préservé",
                "source": f"appel attendu présent : {appel}"})
            continue
        if (invariant.get("type") or "").lower() in APPELS_ATTENDUS:
            resultat["invariants_violes"].append(invariant)
            resultat["preuves"].append({
                "invariant": description, "verdict": "violé",
                "source": "aucune protection équivalente trouvée dans le "
                          "code migré"})
            continue

        garde, reserve = _garde_correspondante(invariant, gardes, seuil)
        if garde and not reserve:
            resultat["invariants_preserves"].append(invariant)
            resultat["preuves"].append({
                "invariant": description, "verdict": "préservé",
                "source": f"garde ligne {garde['ligne']} : {garde['texte'][:70]}"})
        elif garde and reserve:
            resultat["invariants_douteux"].append(invariant)
            resultat["preuves"].append({
                "invariant": description, "verdict": "douteux",
                "source": f"garde ligne {garde['ligne']} — {reserve}"})
        else:
            resultat["invariants_violes"].append(invariant)
            resultat["preuves"].append({
                "invariant": description, "verdict": "violé",
                "source": "aucune garde ne rejette l'entrée invalide"})

    total = len(invariants)
    if total == 0:
        resultat["score"] = 100.0
    else:
        # un invariant douteux compte pour la moitié
        valeur = (len(resultat["invariants_preserves"])
                  + 0.5 * len(resultat["invariants_douteux"]))
        resultat["score"] = valeur / total * 100
    return resultat


# ─── DÉPENDANCES DU MODULE MIGRÉ ─────────────────────
# L'audit doit porter sur ce que le code généré importe, pas sur
# l'environnement de développement. Auditer les 200 paquets installés
# donnerait le même verdict pour tous les modules : on mesurerait le
# poste de travail, pas la migration.

def dependances_du_code(code_python: str) -> dict:
    """
    Paquets tiers importés par le code, et leurs propres dépendances.

    Une faille dans une dépendance de fastapi affecte bien le module :
    on remonte donc la chaîne. La bibliothèque standard et les modules
    du projet sont exclus.
    """
    import ast
    import importlib.metadata as metadonnees

    code = code_python
    if "```python" in code:
        code = code.split("```python")[1]
    if "```" in code:
        code = code.split("```")[0]

    racines = set()
    try:
        arbre = ast.parse(code)
    except SyntaxError:
        return {"paquets": [], "absents": [], "erreur": "code non analysable"}
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            racines.update(a.name.split(".")[0] for a in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and noeud.module and not noeud.level:
            racines.add(noeud.module.split(".")[0])

    standard = getattr(sys, "stdlib_module_names", set())
    racines = {r for r in racines if r not in standard}

    # module importé → paquet installé (ex. sqlalchemy → SQLAlchemy)
    try:
        table = metadonnees.packages_distributions()
    except Exception:
        table = {}

    a_traiter, paquets, absents = [], set(), []
    for racine in sorted(racines):
        noms = table.get(racine)
        if noms:
            a_traiter.extend(noms)
        else:
            absents.append(racine)      # module du projet, ou non installé

    # Remontée des dépendances transitives
    vus = set()
    while a_traiter:
        paquet = a_traiter.pop()
        cle = paquet.lower().replace("_", "-")
        if cle in vus:
            continue
        vus.add(cle)
        paquets.add(cle)
        try:
            exigences = metadonnees.requires(paquet) or []
        except Exception:
            continue
        for exigence in exigences:
            # « uvicorn>=0.1 ; extra == "all" » → les extras sont ignorés
            if "extra ==" in exigence:
                continue
            nom = exigence.split(";")[0].strip()
            for separateur in ("[", "(", "<", ">", "=", "!", "~", " "):
                nom = nom.split(separateur)[0]
            if nom:
                a_traiter.append(nom.strip())

    return {"paquets": sorted(paquets), "absents": sorted(absents),
            "erreur": None}


_AUDIT_ENVIRONNEMENT = {"fait": False, "vulnerabilites": {}, "erreur": None}


def _auditer_environnement() -> dict:
    """
    Lance pip-audit UNE fois par exécution et conserve le relevé.
    Le filtrage par module se fait ensuite dessus : inutile de
    rescanner 200 paquets à chaque module.
    """
    if _AUDIT_ENVIRONNEMENT["fait"]:
        return _AUDIT_ENVIRONNEMENT

    par_paquet = {}
    try:
        process = subprocess.run(
            [sys.executable, "-m", "pip_audit", "--format", "json"],
            capture_output=True, text=True, timeout=180
        )
        if process.stdout:
            rapport = json.loads(process.stdout)
            for dep in rapport.get("dependencies", []):
                nom = dep.get("name", "").lower().replace("_", "-")
                for v in dep.get("vulns", []):
                    par_paquet.setdefault(nom, []).append({
                        "package": dep.get("name", ""),
                        "version": dep.get("version", ""),
                        "id": v.get("id", ""),
                        "description": (v.get("description") or "")[:150],
                    })
    except Exception as e:
        _AUDIT_ENVIRONNEMENT["erreur"] = str(e)

    _AUDIT_ENVIRONNEMENT["vulnerabilites"] = par_paquet
    _AUDIT_ENVIRONNEMENT["fait"] = True
    return _AUDIT_ENVIRONNEMENT


def auditer_dependances(code_python: str) -> dict:
    """
    Dimension 3 — vulnérabilités connues des dépendances DU MODULE.
    """
    dependances = dependances_du_code(code_python)
    environnement = _auditer_environnement()

    vulnerabilites = []
    for paquet in dependances["paquets"]:
        vulnerabilites.extend(environnement["vulnerabilites"].get(paquet, []))

    return {
        "vulnerabilites": vulnerabilites,
        "dependances_du_module": dependances["paquets"],
        "nombre_dependances_auditees": len(dependances["paquets"]),
        "imports_non_installes": dependances["absents"],
        "paquets_vulnerables_environnement": len(
            environnement["vulnerabilites"]),
        "erreur": dependances["erreur"] or environnement["erreur"],
    }


def agent_auditeur(
    code_python: str,
    invariants: list,
    module_info: dict,
    rapport_formel: dict = None
) -> dict:
    """
    Agent Auditeur Sécurité principal — SMAML
    Couvre les 3 dimensions de sécurité du projet.
    """

    print(f"\nAudit de sécurité du module : "
          f"{module_info.get('nom_python', '')}")

    rapport = {
        "module": module_info.get("nom_python", ""),
        "dimension_1_invariants": None,
        "dimension_2_bandit": None,
        "dimension_3_dependances": None,
        "score_securite_global": 0.0,
        "niveau_alerte": "OK"
    }

    # Dimension 1 — Préservation des invariants legacy
    print("  Dimension 1 — Préservation des invariants de sécurité...")
    rapport["dimension_1_invariants"] = verifier_invariants_securite(
        code_python, invariants, rapport_formel
    )
    dim1 = rapport["dimension_1_invariants"]
    print(f"     Score : {dim1['score']:.0f}%")
    for preuve in dim1["preuves"]:
        print(f"       {preuve['verdict']:<9} {preuve['invariant'][:40]:<42}"
              f" {preuve['source'][:60]}")

    # Dimension 2 — Non-réintroduction de failles (Bandit)
    print("  Dimension 2 — Analyse statique Bandit...")
    rapport["dimension_2_bandit"] = lancer_bandit(code_python)
    nb_failles = len(rapport["dimension_2_bandit"]["failles_detectees"])
    print(f"     Failles détectées : {nb_failles}")
    print(f"     Score Bandit : "
          f"{rapport['dimension_2_bandit']['score_securite']:.0f}%")

    # Dimension 3 — Audit des dépendances
    print("  Dimension 3 — Audit des dépendances (pip-audit)...")
    rapport["dimension_3_dependances"] = auditer_dependances(code_python)
    nb_vulns = len(rapport["dimension_3_dependances"]["vulnerabilites"])
    dim3 = rapport["dimension_3_dependances"]
    print(f"     Dépendances du module : "
          f"{', '.join(dim3['dependances_du_module']) or 'aucune'}")
    print(f"     Vulnérabilités trouvées : {nb_vulns}")

    # Calcul du score sécurité global
    score_dim1 = rapport["dimension_1_invariants"]["score"]
    score_dim2 = rapport["dimension_2_bandit"]["score_securite"]
    score_dim3 = 100.0 if nb_vulns == 0 else max(0, 100 - nb_vulns * 10)

    rapport["score_securite_global"] = (
        score_dim1 * 0.4 +
        score_dim2 * 0.4 +
        score_dim3 * 0.2
    )

    # Niveau d'alerte
    failles_high = [
        f for f in rapport["dimension_2_bandit"]["failles_detectees"]
        if f["severity"] == "high"
    ]
    if failles_high or rapport["dimension_1_invariants"]["invariants_violes"]:
        rapport["niveau_alerte"] = "CRITIQUE"
    elif rapport["score_securite_global"] < 80:
        rapport["niveau_alerte"] = "ATTENTION"
    else:
        rapport["niveau_alerte"] = "OK"

    print(f"\n   Score sécurité global : "
          f"{rapport['score_securite_global']:.1f}%")
    print(f"  Niveau d'alerte : {rapport['niveau_alerte']}")

    return rapport


# ─── TEST ────────────────────────────────────────────
if __name__ == "__main__":

    code_python_test = """
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, validator
from sqlalchemy.orm import sessionmaker

class UserRequest(BaseModel):
    id: int
    username: str
    password: str

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Le mot de passe doit avoir au moins 8 caracteres")
        if not any(char.isupper() for char in v):
            raise ValueError("Majuscule requise")
        return v

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur non trouve")
    return user.__dict__
"""

    invariants_test = [
        {"type": "validation_longueur", "description": "len >= 8"},
        {"type": "validation_format", "description": "majuscule requise"}
    ]

    module_test = {
        "nom_python": "get_user",
        "nom_original": "getUser"
    }

    print("=" * 60)
    print("Agent Auditeur Sécurité SMAML — Audit en cours...")
    print("=" * 60)

    rapport = agent_auditeur(code_python_test, invariants_test, module_test)

    print("\n" + "=" * 60)
    print("RAPPORT COMPLET (JSON) :")
    print("=" * 60)
    print(json.dumps(rapport, indent=2, ensure_ascii=False))

    print("\n Agent Auditeur opérationnel !")