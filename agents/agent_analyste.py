from tree_sitter import Language, Parser
import tree_sitter_php as tsPHP
import json

# Initialiser le parser PHP
PHP_LANGUAGE = Language(tsPHP.language_php())
parser = Parser(PHP_LANGUAGE)

def analyser_code_php(code_php: str) -> dict:
    """
    Agent Analyste — SMAML
    Analyse complète d'un code PHP et produit un rapport
    JSON structuré exploitable par les autres agents.
    """
    
    tree = parser.parse(bytes(code_php, "utf8"))
    root = tree.root_node
    
    rapport = {
        "langage_source": "php",
        "fonctions": [],
        "variables_globales": [],
        "invariants_securite": [],
        "failles_potentielles": [],
        "dependances": [],
        "metriques": {
            "nombre_fonctions": 0,
            "nombre_invariants": 0,
            "nombre_failles": 0,
            "complexite_estimee": "faible"
        }
    }

    def get_text(node):
        return code_php[node.start_byte:node.end_byte]

    def parcourir(node):

        # ─── FONCTIONS ───────────────────────────────
        if node.type == "function_definition":
            nom = ""
            parametres = []
            corps = ""
            for child in node.children:
                if child.type == "name":
                    nom = get_text(child)
                if child.type == "formal_parameters":
                    for param in child.children:
                        if param.type == "simple_parameter":
                            parametres.append(get_text(param))
                if child.type == "compound_statement":
                    corps = get_text(child)[:200]
            if nom:
                rapport["fonctions"].append({
                    "nom": nom,
                    "parametres": parametres,
                    "corps_resume": corps,
                    "lignes": {
                        "debut": node.start_point[0] + 1,
                        "fin": node.end_point[0] + 1
                    }
                })

        # ─── INVARIANTS DE SÉCURITÉ ──────────────────
        if node.type == "if_statement":
            contenu = get_text(node)
            
            # Validations de longueur
            if "strlen" in contenu or "mb_strlen" in contenu:
                rapport["invariants_securite"].append({
                    "type": "validation_longueur",
                    "description": "Vérification de longueur de champ",
                    "code": contenu[:150],
                    "a_preserver": True
                })
            
            # Validations de format
            if "preg_match" in contenu or "filter_var" in contenu:
                rapport["invariants_securite"].append({
                    "type": "validation_format",
                    "description": "Vérification de format ou pattern",
                    "code": contenu[:150],
                    "a_preserver": True
                })
            
            # Validations numériques
            if "is_numeric" in contenu or "is_int" in contenu:
                rapport["invariants_securite"].append({
                    "type": "validation_type",
                    "description": "Vérification de type numérique",
                    "code": contenu[:150],
                    "a_preserver": True
                })
            
            # Contrôle d'accès
            if any(mot in contenu.lower() for mot in [
                "role", "permission", "access", "auth",
                "admin", "privilege"
            ]):
                rapport["invariants_securite"].append({
                    "type": "controle_acces",
                    "description": "Vérification de droits ou rôle",
                    "code": contenu[:150],
                    "a_preserver": True
                })
            
            # Vérification existence
            if "isset" in contenu or "empty" in contenu:
                rapport["invariants_securite"].append({
                    "type": "validation_existence",
                    "description": "Vérification d'existence de variable",
                    "code": contenu[:150],
                    "a_preserver": True
                })

        # ─── FAILLES POTENTIELLES ────────────────────
        if node.type == "function_call_expression":
            contenu = get_text(node)
            
            # SQL Injection
            if any(f in contenu for f in [
                "mysql_query", "mysqli_query", "pg_query"
            ]):
                rapport["failles_potentielles"].append({
                    "type": "sql_injection",
                    "cwe": "CWE-89",
                    "severity": "critical",
                    "code": contenu[:100],
                    "description": "Requête SQL potentiellement vulnérable"
                })
            
            # Command Injection
            if any(f in contenu for f in [
                "shell_exec", "exec", "system",
                "passthru", "popen"
            ]):
                rapport["failles_potentielles"].append({
                    "type": "command_injection",
                    "cwe": "CWE-78",
                    "severity": "critical",
                    "code": contenu[:100],
                    "description": "Exécution de commande système dangereuse"
                })
            
            # File Inclusion
            if any(f in contenu for f in [
                "include", "require",
                "include_once", "require_once"
            ]):
                rapport["failles_potentielles"].append({
                    "type": "file_inclusion",
                    "cwe": "CWE-98",
                    "severity": "high",
                    "code": contenu[:100],
                    "description": "Inclusion de fichier dynamique"
                })
            
            # Désérialisation
            if "unserialize" in contenu:
                rapport["failles_potentielles"].append({
                    "type": "insecure_deserialization",
                    "cwe": "CWE-502",
                    "severity": "critical",
                    "code": contenu[:100],
                    "description": "Désérialisation non sécurisée"
                })
            
            # Secrets hardcodés
            if any(f in contenu for f in [
                "mysql_connect", "mysqli_connect",
                "pg_connect"
            ]):
                rapport["dependances"].append({
                    "type": "connexion_base_donnees",
                    "code": contenu[:100]
                })

        # ─── VARIABLES GLOBALES ──────────────────────
        if node.type == "variable_name":
            contenu = get_text(node)
            if contenu in ["$_GET", "$_POST", "$_REQUEST",
                          "$_SESSION", "$_COOKIE", "$_FILES"]:
                if contenu not in rapport["variables_globales"]:
                    rapport["variables_globales"].append(contenu)

        # Continuer le parcours
        for child in node.children:
            parcourir(child)

    parcourir(root)

    # Calculer les métriques
    rapport["metriques"]["nombre_fonctions"] = len(rapport["fonctions"])
    rapport["metriques"]["nombre_invariants"] = len(rapport["invariants_securite"])
    rapport["metriques"]["nombre_failles"] = len(rapport["failles_potentielles"])
    
    nb_failles = len(rapport["failles_potentielles"])
    if nb_failles == 0:
        rapport["metriques"]["complexite_estimee"] = "faible"
    elif nb_failles <= 2:
        rapport["metriques"]["complexite_estimee"] = "moyenne"
    else:
        rapport["metriques"]["complexite_estimee"] = "elevee"

    return rapport


# ─── TEST COMPLET ────────────────────────────────────
if __name__ == "__main__":

    code_test = """<?php
function validatePassword($password) {
    if (strlen($password) < 8) {
        throw new Exception('Trop court');
    }
    if (!preg_match('/[A-Z]/', $password)) {
        throw new Exception('Majuscule requise');
    }
    if (!is_numeric(strlen($password))) {
        throw new Exception('Erreur longueur');
    }
    return true;
}

function getUser($id) {
    if (!isset($id)) {
        throw new Exception('ID manquant');
    }
    $sql = "SELECT * FROM users WHERE id=" . $id;
    $result = mysql_query($sql);
    return mysql_fetch_array($result);
}

function executeCommand($cmd) {
    $output = shell_exec($cmd);
    return $output;
}

function loadPage($page) {
    include($page . '.php');
}
"""

    print("Agent Analyste SMAML — Analyse en cours...")
    print("=" * 60)

    rapport = analyser_code_php(code_test)

    print(json.dumps(rapport, indent=2, ensure_ascii=False))

    print("\n" + "=" * 60)
    print("RÉSUMÉ DE L'ANALYSE :")
    print(f"  Fonctions détectées    : {rapport['metriques']['nombre_fonctions']}")
    print(f"  Invariants sécurité    : {rapport['metriques']['nombre_invariants']}")
    print(f"  Failles potentielles   : {rapport['metriques']['nombre_failles']}")
    print(f"  Complexité estimée     : {rapport['metriques']['complexite_estimee']}")
    print(f"  Variables superglobales: {rapport['variables_globales']}")
    print("\nAgent Analyste complet et opérationnel !")