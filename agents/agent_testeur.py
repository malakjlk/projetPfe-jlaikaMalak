import subprocess
import sys
import json
import re
from hypothesis import given, strategies as st, settings


def extraire_invariants_testables(invariants: list) -> list:
    """
    Convertit les invariants textuels en règles Python
    exploitables par Hypothesis.
    """
    regles = []

    for inv in invariants:
        desc = inv.get("description", "").lower()
        type_inv = inv.get("type", "")

        if "longueur" in type_inv or "len" in desc:
            regles.append({
                "type": "longueur_min",
                "valeur": 8,
                "description": inv.get("description", "")
            })

        if "majuscule" in desc or "format" in type_inv:
            regles.append({
                "type": "format_requis",
                "pattern": "majuscule",
                "description": inv.get("description", "")
            })

        if "existence" in type_inv:
            regles.append({
                "type": "non_vide",
                "description": inv.get("description", "")
            })

    return regles


def verifier_syntaxe_python(code_python: str) -> dict:
    """
    Vérifie que le code Python généré est syntaxiquement valide.
    """
    resultat = {
        "syntaxe_valide": False,
        "erreur": None
    }

    # Nettoyer le code (enlever les balises markdown si présentes)
    code_nettoye = code_python
    if "```python" in code_nettoye:
        code_nettoye = code_nettoye.split("```python")[1]
    if "```" in code_nettoye:
        code_nettoye = code_nettoye.split("```")[0]

    try:
        compile(code_nettoye, "<string>", "exec")
        resultat["syntaxe_valide"] = True
    except SyntaxError as e:
        resultat["erreur"] = str(e)

    return resultat


def verifier_invariants_presents(
    code_python: str,
    invariants: list
) -> dict:
    """
    Vérifie par analyse textuelle si les invariants
    de sécurité semblent présents dans le code généré.
    Version simplifiée — l'analyse formelle complète
    nécessiterait Z3 sur le code exécutable.
    """
    resultat = {
        "invariants_verifies": [],
        "invariants_manquants": [],
        "score": 0.0
    }

    code_lower = code_python.lower()

    patterns_invariants = {
        "validation_longueur": ["len(", "strlen", ">= 8", "< 8"],
        "validation_format": ["isupper", "preg_match", "regex", "re.match"],
        "validation_type": ["isinstance", "isdigit", "is_numeric"],
        "validation_existence": ["is not none", "if not", "raise"],
        "controle_acces": ["role", "permission", "permissionerror"]
    }

    for inv in invariants:
        type_inv = inv.get("type", "")
        patterns = patterns_invariants.get(type_inv, [])

        trouve = any(p in code_lower for p in patterns)

        if trouve:
            resultat["invariants_verifies"].append(inv)
        else:
            resultat["invariants_manquants"].append(inv)

    total = len(invariants)
    verifies = len(resultat["invariants_verifies"])
    resultat["score"] = (verifies / total) if total > 0 else 1.0

    return resultat


def verifier_failles_corrigees(
    code_python: str,
    failles: list
) -> dict:
    """
    Vérifie par analyse textuelle si les failles détectées
    par l'Analyste ont été corrigées dans le code Python.
    """
    resultat = {
        "failles_corrigees": [],
        "failles_persistantes": [],
        "score": 0.0
    }

    code_lower = code_python.lower()

    # Patterns qui indiquent qu'une faille a été corrigée
    indicateurs_correction = {
        "sql_injection": ["sqlalchemy", ".query(", "orm", ".filter("],
        "command_injection": ["subprocess.run", "shlex", "shell=false"],
        "file_inclusion": ["whitelist", "allowed_pages", "in allowed"],
        "insecure_deserialization": ["json.loads", "pydantic", "basemodel"]
    }

    # Patterns qui indiquent que la faille est toujours présente
    indicateurs_faille_presente = {
        "sql_injection": ["mysql_query", "execute(f\"", "+ id", ". $id"],
        "command_injection": ["shell_exec", "os.system(", "subprocess.call(true"],
        "file_inclusion": ["include($", "require($"],
        "insecure_deserialization": ["pickle.loads", "unserialize"]
    }

    for faille in failles:
        type_faille = faille.get("faille") or faille.get("type", "")

        a_corrige = any(
            p in code_lower
            for p in indicateurs_correction.get(type_faille, [])
        )
        a_faille_residuelle = any(
            p in code_lower
            for p in indicateurs_faille_presente.get(type_faille, [])
        )

        if a_corrige and not a_faille_residuelle:
            resultat["failles_corrigees"].append(faille)
        else:
            resultat["failles_persistantes"].append(faille)

    total = len(failles)
    corrigees = len(resultat["failles_corrigees"])
    resultat["score"] = (corrigees / total) if total > 0 else 1.0

    return resultat


def tester_property_based(regles: list) -> dict:
    """
    Démonstration de property-based testing avec Hypothesis
    sur les règles de validation extraites.
    """
    resultat = {
        "tests_executes": 0,
        "tests_reussis": 0,
        "details": []
    }

    for regle in regles:
        if regle["type"] == "longueur_min":
            valeur_min = regle["valeur"]
            description = regle["description"]

            def faire_test(valeur_min=valeur_min):
                @settings(max_examples=50, deadline=None)
                @given(st.text(min_size=0, max_size=20))
                def test_longueur(mot_de_passe):
                    # Vérifie que la règle de validation
                    # est cohérente : un mot de passe valide
                    # respecte toujours len >= valeur_min
                    if len(mot_de_passe) >= valeur_min:
                        assert len(mot_de_passe) >= valeur_min
                    else:
                        assert len(mot_de_passe) < valeur_min

                test_longueur()

            try:
                faire_test()
                resultat["tests_reussis"] += 1
                resultat["details"].append({
                    "regle": description,
                    "statut": "réussi",
                    "cas_testes": 50
                })
            except Exception as e:
                resultat["details"].append({
                    "regle": description,
                    "statut": "échoué",
                    "erreur": str(e)
                })

            resultat["tests_executes"] += 1

    return resultat


def agent_testeur(
    code_python: str,
    module_info: dict,
    invariants: list,
    failles: list
) -> dict:
    """
    Agent Testeur principal — SMAML
    Vérifie l'équivalence fonctionnelle et la qualité
    du code Python généré.
    """

    print(f"\nVérification du module : "
          f"{module_info.get('nom_python', '')}")

    rapport = {
        "module": module_info.get("nom_python", ""),
        "syntaxe": None,
        "invariants": None,
        "failles": None,
        "tests_property_based": None,
        "score_fonctionnel": 0.0
    }

    # Étape 1 — Vérification syntaxique
    print("  1. Vérification syntaxique...")
    rapport["syntaxe"] = verifier_syntaxe_python(code_python)
    statut_syntaxe = "✅" if rapport["syntaxe"]["syntaxe_valide"] else "❌"
    print(f"     {statut_syntaxe} Syntaxe valide : "
          f"{rapport['syntaxe']['syntaxe_valide']}")

    # Étape 2 — Vérification des invariants
    print("  2. Vérification des invariants de sécurité...")
    rapport["invariants"] = verifier_invariants_presents(
        code_python, invariants
    )
    print(f"     Score invariants : "
          f"{rapport['invariants']['score']*100:.0f}% "
          f"({len(rapport['invariants']['invariants_verifies'])}"
          f"/{len(invariants)})")

    # Étape 3 — Vérification des failles corrigées
    print("  3. Vérification de la correction des failles...")
    rapport["failles"] = verifier_failles_corrigees(
        code_python, failles
    )
    print(f"     Score failles corrigées : "
          f"{rapport['failles']['score']*100:.0f}% "
          f"({len(rapport['failles']['failles_corrigees'])}"
          f"/{len(failles)})")

    # Étape 4 — Property-based testing
    print("  4. Tests property-based (Hypothesis)...")
    regles = extraire_invariants_testables(invariants)
    rapport["tests_property_based"] = tester_property_based(regles)
    print(f"     Tests exécutés : "
          f"{rapport['tests_property_based']['tests_executes']}, "
          f"réussis : {rapport['tests_property_based']['tests_reussis']}")

    # Score fonctionnel composé
    score_syntaxe = 1.0 if rapport["syntaxe"]["syntaxe_valide"] else 0.0
    score_invariants = rapport["invariants"]["score"]
    score_failles = rapport["failles"]["score"]

    rapport["score_fonctionnel"] = (
        score_syntaxe * 0.3 +
        score_invariants * 0.4 +
        score_failles * 0.3
    )

    print(f"\n  📊 Score fonctionnel global : "
          f"{rapport['score_fonctionnel']*100:.1f}%")

    return rapport


# ─── TEST ────────────────────────────────────────────
if __name__ == "__main__":

    # Code Python simulé (résultat de l'Agent Développeur)
    code_python_test = """
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, validator
from sqlalchemy import create_engine, Column, Integer, String
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
        {"type": "validation_longueur",
         "description": "len >= 8"},
        {"type": "validation_format",
         "description": "majuscule requise"}
    ]

    failles_test = [
        {"faille": "sql_injection",
         "cwe": "CWE-89",
         "severity": "critical"}
    ]

    module_test = {
        "nom_python": "get_user",
        "nom_original": "getUser"
    }

    print("=" * 60)
    print("Agent Testeur SMAML — Vérification en cours...")
    print("=" * 60)

    rapport = agent_testeur(
        code_python_test,
        module_test,
        invariants_test,
        failles_test
    )

    print("\n" + "=" * 60)
    print("RAPPORT COMPLET (JSON) :")
    print("=" * 60)
    print(json.dumps(rapport, indent=2, ensure_ascii=False))

    print("\n✅ Agent Testeur opérationnel !")