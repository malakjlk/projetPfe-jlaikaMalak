import subprocess
import json
import tempfile
import os


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
            ["py", "-3.11", "-m", "bandit", "-f", "json", chemin_temp],
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


def verifier_invariants_securite(
    code_python: str,
    invariants: list
) -> dict:
    """
    Vérifie que les invariants de sécurité du code legacy
    (Dimension 1) sont bien préservés dans le code généré.
    """
    resultat = {
        "invariants_preserves": [],
        "invariants_violes": [],
        "score": 0.0
    }

    code_lower = code_python.lower()

    patterns = {
        "validation_longueur": ["len(", ">= 8", "< 8", "strlen"],
        "validation_format": ["isupper", "preg_match", "re.match", "regex"],
        "validation_type": ["isinstance", "isdigit", "is_numeric"],
        "validation_existence": ["is not none", "raise", "if not"],
        "controle_acces": ["role", "permission", "permissionerror"]
    }

    for inv in invariants:
        type_inv = inv.get("type", "")
        mots_cles = patterns.get(type_inv, [])
        preserve = any(m in code_lower for m in mots_cles)

        if preserve:
            resultat["invariants_preserves"].append(inv)
        else:
            resultat["invariants_violes"].append(inv)

    total = len(invariants)
    preserves = len(resultat["invariants_preserves"])
    resultat["score"] = (preserves / total * 100) if total > 0 else 100.0

    return resultat


def auditer_dependances() -> dict:
    """
    Audit des dépendances Python via pip-audit (Dimension 2).
    Vérifie les CVE connues sur l'environnement actuel.
    """
    resultat = {
        "vulnerabilites": [],
        "nombre_dependances_auditees": 0,
        "erreur": None
    }

    try:
        process = subprocess.run(
            ["py", "-3.11", "-m", "pip_audit", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=60
        )

        if process.stdout:
            rapport = json.loads(process.stdout)
            dependances = rapport.get("dependencies", [])
            resultat["nombre_dependances_auditees"] = len(dependances)

            for dep in dependances:
                vulns = dep.get("vulns", [])
                for v in vulns:
                    resultat["vulnerabilites"].append({
                        "package": dep.get("name", ""),
                        "version": dep.get("version", ""),
                        "id": v.get("id", ""),
                        "description": v.get("description", "")[:150]
                    })

    except Exception as e:
        resultat["erreur"] = str(e)

    return resultat


def agent_auditeur(
    code_python: str,
    invariants: list,
    module_info: dict
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
        code_python, invariants
    )
    print(f"     Score : "
          f"{rapport['dimension_1_invariants']['score']:.0f}%")

    # Dimension 2 — Non-réintroduction de failles (Bandit)
    print("  Dimension 2 — Analyse statique Bandit...")
    rapport["dimension_2_bandit"] = lancer_bandit(code_python)
    nb_failles = len(rapport["dimension_2_bandit"]["failles_detectees"])
    print(f"     Failles détectées : {nb_failles}")
    print(f"     Score Bandit : "
          f"{rapport['dimension_2_bandit']['score_securite']:.0f}%")

    # Dimension 3 — Audit des dépendances
    print("  Dimension 3 — Audit des dépendances (pip-audit)...")
    rapport["dimension_3_dependances"] = auditer_dependances()
    nb_vulns = len(rapport["dimension_3_dependances"]["vulnerabilites"])
    print(f"     Dépendances auditées : "
          f"{rapport['dimension_3_dependances']['nombre_dependances_auditees']}")
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

    print(f"\n  📊 Score sécurité global : "
          f"{rapport['score_securite_global']:.1f}%")
    print(f"  🚦 Niveau d'alerte : {rapport['niveau_alerte']}")

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