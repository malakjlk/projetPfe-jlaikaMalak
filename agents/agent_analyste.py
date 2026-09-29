import re

from tree_sitter import Language, Parser
import tree_sitter_php as tsPHP
import json

PHP_LANGUAGE = Language(tsPHP.language_php())
parser = Parser(PHP_LANGUAGE)


def analyser_code_php(code_php: str) -> dict:
    """
    Agent Analyste — SMAML
    Analyse un code PHP (fonctions, classes, invariants, failles).
    Découpe en OCTETS puis décode (supporte les accents UTF-8).
    """
    code_bytes = code_php.encode("utf8")
    tree = parser.parse(code_bytes)
    root = tree.root_node

    rapport = {
        "langage_source": "php",
        "fonctions": [],
        "classes": [],
        "variables_globales": [],
        "invariants_securite": [],
        "failles_potentielles": [],
        "dependances": [],
        "metriques": {
            "nombre_fonctions": 0,
            "nombre_classes": 0,
            "nombre_invariants": 0,
            "nombre_failles": 0,
            "complexite_estimee": "faible"
        }
    }

    def get_text(node):
        return code_bytes[node.start_byte:node.end_byte].decode(
            "utf8", errors="ignore")

    def _fonction_englobante(node) -> str:
        parent = node.parent
        while parent:
            if parent.type in ("function_definition", "method_declaration"):
                for child in parent.children:
                    if child.type == "name":
                        return get_text(child)
                return ""
            parent = parent.parent
        return ""

    def _ajouter_invariant(invariant: dict):
        """Ajoute l'invariant s'il n'est pas déjà présent."""
        cle = (invariant["type"], invariant["fonction"],
               invariant["code"][:60])
        for existant in rapport["invariants_securite"]:
            if (existant["type"], existant["fonction"],
                    existant["code"][:60]) == cle:
                return
        rapport["invariants_securite"].append(invariant)

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
                    "nom": nom, "parametres": parametres,
                    "corps_resume": corps,
                    "lignes": {"debut": node.start_point[0] + 1,
                               "fin": node.end_point[0] + 1}
                })

        # ─── CLASSES (PHP orienté objet) ─────────────
        if node.type == "class_declaration":
            nom_classe = ""
            classe_parente = ""
            methodes = []
            proprietes = []
            for child in node.children:
                if child.type == "name":
                    nom_classe = get_text(child)
                # Héritage : extends ClasseParente
                if child.type == "base_clause":
                    for sub in child.children:
                        if sub.type == "name":
                            classe_parente = get_text(sub)
                if child.type == "declaration_list":
                    for membre in child.children:
                        if membre.type == "method_declaration":
                            nom_methode = ""
                            params = []
                            for sub in membre.children:
                                if sub.type == "name":
                                    nom_methode = get_text(sub)
                                if sub.type == "formal_parameters":
                                    for pr in sub.children:
                                        if pr.type == "simple_parameter":
                                            params.append(get_text(pr))
                            if nom_methode:
                                methodes.append({"nom": nom_methode,
                                                 "parametres": params})
                        if membre.type == "property_declaration":
                            for sub in membre.children:
                                if sub.type == "property_element":
                                    proprietes.append(
                                        get_text(sub).split("=")[0].strip())
            if nom_classe:
                rapport["classes"].append({
                    "nom": nom_classe, "methodes": methodes,
                    "proprietes": proprietes,
                    "classe_parente": classe_parente,
                    "lignes": {"debut": node.start_point[0] + 1,
                               "fin": node.end_point[0] + 1}
                })

        # ─── ASSAINISSEMENT ET HACHAGE ───────────────
        # Ces protections ne sont pas des « if » : ce sont des appels.
        # Les chercher uniquement dans les conditions revenait à les
        # ignorer, alors que ce sont les garanties les plus fortes du
        # code d'origine.
        if node.type == "function_call_expression":
            appel = get_text(node)
            fonction_parente = _fonction_englobante(node)

            if any(f in appel for f in ["htmlspecialchars", "htmlentities",
                                        "strip_tags", "addslashes"]):
                _ajouter_invariant({
                    "type": "assainissement_sortie",
                    "description": "Échappement des données avant restitution",
                    "code": appel[:150], "fonction": fonction_parente,
                    "a_preserver": True})
            if "filter_var" in appel and "SANITIZE" in appel.upper():
                _ajouter_invariant({
                    "type": "assainissement_sortie",
                    "description": "Nettoyage de l'entrée utilisateur",
                    "code": appel[:150], "fonction": fonction_parente,
                    "a_preserver": True})
            if any(f in appel for f in ["password_hash", "password_verify",
                                        "crypt("]):
                _ajouter_invariant({
                    "type": "hachage_mot_de_passe",
                    "description": "Mot de passe haché, jamais en clair",
                    "code": appel[:150], "fonction": fonction_parente,
                    "a_preserver": True})

        # ─── INVARIANTS DE SÉCURITÉ ──────────────────
        if node.type == "if_statement":
            contenu = get_text(node)
            fonction_parente = ""
            parent = node.parent
            while parent:
                if parent.type in ("function_definition",
                                   "method_declaration"):
                    for child in parent.children:
                        if child.type == "name":
                            fonction_parente = get_text(child)
                    break
                parent = parent.parent

            if "strlen" in contenu or "mb_strlen" in contenu:
                rapport["invariants_securite"].append({
                    "type": "validation_longueur",
                    "description": "Vérification de longueur de champ",
                    "code": contenu[:150], "fonction": fonction_parente,
                    "a_preserver": True})
            if "preg_match" in contenu or "filter_var" in contenu:
                rapport["invariants_securite"].append({
                    "type": "validation_format",
                    "description": "Vérification de format ou pattern",
                    "code": contenu[:150], "fonction": fonction_parente,
                    "a_preserver": True})
            if "is_numeric" in contenu or "is_int" in contenu:
                rapport["invariants_securite"].append({
                    "type": "validation_type",
                    "description": "Vérification de type numérique",
                    "code": contenu[:150], "fonction": fonction_parente,
                    "a_preserver": True})
            if any(mot in contenu.lower() for mot in [
                    "role", "permission", "access", "auth",
                    "admin", "privilege"]):
                rapport["invariants_securite"].append({
                    "type": "controle_acces",
                    "description": "Vérification de droits ou rôle",
                    "code": contenu[:150], "fonction": fonction_parente,
                    "a_preserver": True})
            if "isset" in contenu or "empty" in contenu:
                rapport["invariants_securite"].append({
                    "type": "validation_existence",
                    "description": "Vérification d'existence de variable",
                    "code": contenu[:150], "fonction": fonction_parente,
                    "a_preserver": True})

            # ── Gardes qui REJETTENT ──
            # Un « if » suivi d'un throw, d'un die ou d'un return
            # négatif est une garde : c'est ce qui empêche une donnée
            # invalide de passer. Son contenu dit ce qu'elle protège.
            rejette = any(mot in contenu for mot in
                          ["throw", "die(", "exit(", "return false",
                           "return null", "return FALSE", "return NULL"])
            condition = contenu.split("{")[0]

            if rejette:
                borne = re.search(r"[<>]=?\s*-?\d+(?:\.\d+)?", condition)
                if borne and "strlen" not in condition:
                    _ajouter_invariant({
                        "type": "validation_intervalle",
                        "description": f"Borne sur une valeur ({borne.group()})",
                        "code": contenu[:150], "fonction": fonction_parente,
                        "a_preserver": True})

                if re.search(r"!\s*\$\w+|===?\s*(false|null)|"
                             r"(false|null)\s*===?", condition, re.IGNORECASE):
                    _ajouter_invariant({
                        "type": "validation_existence",
                        "description": "Rejet si la valeur est absente ou fausse",
                        "code": contenu[:150], "fonction": fonction_parente,
                        "a_preserver": True})

            # ── Comparaison d'identifiants ──
            # « if ($user["password"] == $password) » est le cœur d'une
            # authentification : la comparaison doit être préservée.
            if re.search(r"(password|passwd|mot_de_passe|token|jeton|"
                         r"secret|hash)", condition, re.IGNORECASE) and \
                    re.search(r"===?|!==?", condition):
                _ajouter_invariant({
                    "type": "comparaison_authentification",
                    "description": "Comparaison d'identifiant ou de secret",
                    "code": contenu[:150], "fonction": fonction_parente,
                    "a_preserver": True})

        # ─── FAILLES POTENTIELLES ────────────────────
        if node.type == "function_call_expression":
            contenu = get_text(node)
            fonction_parente = ""
            parent = node.parent
            while parent:
                if parent.type in ("function_definition",
                                   "method_declaration"):
                    for child in parent.children:
                        if child.type == "name":
                            fonction_parente = get_text(child)
                    break
                parent = parent.parent

            if any(f in contenu for f in ["mysql_query", "mysqli_query",
                                          "pg_query"]):
                rapport["failles_potentielles"].append({
                    "type": "sql_injection", "cwe": "CWE-89",
                    "severity": "critical", "code": contenu[:100],
                    "description": "Requête SQL potentiellement vulnérable",
                    "fonction": fonction_parente})
            if any(f in contenu for f in ["shell_exec", "exec", "system",
                                          "passthru", "popen"]):
                rapport["failles_potentielles"].append({
                    "type": "command_injection", "cwe": "CWE-78",
                    "severity": "critical", "code": contenu[:100],
                    "description": "Exécution de commande système dangereuse",
                    "fonction": fonction_parente})
            if any(f in contenu for f in ["include", "require",
                                          "include_once", "require_once"]):
                rapport["failles_potentielles"].append({
                    "type": "file_inclusion", "cwe": "CWE-98",
                    "severity": "high", "code": contenu[:100],
                    "description": "Inclusion de fichier dynamique",
                    "fonction": fonction_parente})
            if "unserialize" in contenu:
                rapport["failles_potentielles"].append({
                    "type": "insecure_deserialization", "cwe": "CWE-502",
                    "severity": "critical", "code": contenu[:100],
                    "description": "Désérialisation non sécurisée",
                    "fonction": fonction_parente})
            if any(f in contenu for f in ["mysql_connect", "mysqli_connect",
                                          "pg_connect"]):
                rapport["dependances"].append({
                    "type": "connexion_base_donnees", "code": contenu[:100]})

        # ─── VARIABLES GLOBALES ──────────────────────
        if node.type == "variable_name":
            contenu = get_text(node)
            if contenu in ["$_GET", "$_POST", "$_REQUEST",
                           "$_SESSION", "$_COOKIE", "$_FILES"]:
                if contenu not in rapport["variables_globales"]:
                    rapport["variables_globales"].append(contenu)

        for child in node.children:
            parcourir(child)

    parcourir(root)

    rapport["metriques"]["nombre_fonctions"] = len(rapport["fonctions"])
    rapport["metriques"]["nombre_classes"] = len(rapport["classes"])
    rapport["metriques"]["nombre_invariants"] = len(
        rapport["invariants_securite"])
    rapport["metriques"]["nombre_failles"] = len(
        rapport["failles_potentielles"])

    nb = len(rapport["failles_potentielles"])
    rapport["metriques"]["complexite_estimee"] = (
        "faible" if nb == 0 else "moyenne" if nb <= 2 else "elevee")

    return rapport


if __name__ == "__main__":
    code = """<?php
class OutilsTexte {
    public static function genererRapport($commande) {
        $sortie = shell_exec("echo " . $commande);
        return $sortie;
    }
}
"""
    r = analyser_code_php(code)
    print(f"Fonctions : {r['metriques']['nombre_fonctions']}")
    print(f"Classes : {r['metriques']['nombre_classes']}")
    for c in r["classes"]:
        print(f"  - {c['nom']} : {[m['nom'] for m in c['methodes']]}")
    print(f"Failles : {r['metriques']['nombre_failles']}")
    assert r["metriques"]["nombre_classes"] == 1
    assert r["metriques"]["nombre_failles"] == 1
    print("\n✅ Analyste détecte classes ET failles dans les méthodes")