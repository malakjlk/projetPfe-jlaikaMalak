"""
Fichiers annexes d'un projet — SMAML
=====================================
Un projet ne contient pas que du code. Aucun fichier ne doit être perdu,
mais tous ne demandent pas une traduction :

  statique        CSS, JavaScript, images, polices, documents
                  → COPIÉS tels quels : ils ne dépendent pas du langage
                    du serveur
  schema_sql      CREATE TABLE
                  → TRADUITS en modèles SQLAlchemy, de façon déterministe
                    (chaque type SQL a une correspondance exacte)
  donnees_sql     INSERT, sauvegardes
                  → CONSERVÉS : les données restent dans la base
  configuration   composer.json, .env, .htaccess, php.ini
                  → REMPLACÉS par leur équivalent Python, ou signalés
  vue             page PHP sans fonction, qui mêle HTML et PHP
                  → mise de côté pour la traduction en gabarit Jinja2
  autre           tout le reste → copié, et signalé
"""

from __future__ import annotations

import os
import re
import shutil

STATIQUES = {".css", ".js", ".mjs", ".map", ".png", ".jpg", ".jpeg", ".gif", ".svg",
             ".ico", ".webp", ".bmp", ".woff", ".woff2", ".ttf", ".eot", ".otf",
             ".mp4", ".webm", ".mp3", ".pdf", ".txt", ".md", ".csv", ".xml", ".json",
             ".html", ".htm"}
CONFIGURATIONS = {"composer.json": "remplacé par requirements.txt, produit par la migration",
                  "composer.lock": "remplacé par requirements.txt, produit par la migration",
                  ".env": "copié : à lire avec pydantic-settings (BaseSettings)",
                  ".env.example": "copié : modèle de configuration",
                  ".htaccess": "règles de réécriture d'URL : à reporter dans les routes FastAPI",
                  "php.ini": "réglages PHP : sans équivalent direct, à revoir à la main",
                  "web.config": "configuration IIS : à remplacer par la configuration du serveur ASGI"}

# ── Types SQL → (type SQLAlchemy, annotation Python) ──
TYPES_SQL = [
    (r"TINYINT\s*\(\s*1\s*\)|BOOLEAN|BOOL", "Boolean", "bool"),
    (r"BIGINT", "BigInteger", "int"),
    (r"SMALLINT|TINYINT|MEDIUMINT", "SmallInteger", "int"),
    (r"INT|INTEGER|SERIAL", "Integer", "int"),
    (r"(?:DECIMAL|NUMERIC)\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", "Numeric({0}, {1})", "Decimal"),
    (r"DECIMAL|NUMERIC", "Numeric", "Decimal"),
    (r"FLOAT|DOUBLE|REAL", "Float", "float"),
    (r"(?:VAR)?CHAR\s*\(\s*(\d+)\s*\)", "String({0})", "str"),
    (r"(?:TINY|MEDIUM|LONG)?TEXT", "Text", "str"),
    (r"DATETIME|TIMESTAMP", "DateTime", "datetime"),
    (r"DATE", "Date", "date"),
    (r"TIME", "Time", "time"),
    (r"JSON", "JSON", "dict"),
    (r"(?:TINY|MEDIUM|LONG)?BLOB|BINARY|VARBINARY", "LargeBinary", "bytes"),
    (r"ENUM\s*\(([^)]*)\)", "String(50)", "str"),
]


def _nom_classe(table: str) -> str:
    return "".join(p.capitalize() for p in re.split(r"[^A-Za-z0-9]+", table) if p)


def _type(definition: str):
    for motif, sqlalchemy, python in TYPES_SQL:
        m = re.match(motif, definition.strip(), re.I)
        if m:
            arguments = [a for a in m.groups() if a and a.isdigit()]
            return sqlalchemy.format(*arguments) if arguments else \
                re.sub(r"\(\{0\}.*\)", "", sqlalchemy), python
    return "String(255)", "str"


def _decouper(corps: str) -> list:
    """Sépare les définitions d'une table sur les virgules de premier niveau."""
    morceaux, niveau, courant = [], 0, ""
    for c in corps:
        niveau += (c == "(") - (c == ")")
        if c == "," and niveau == 0:
            morceaux.append(courant.strip())
            courant = ""
        else:
            courant += c
    if courant.strip():
        morceaux.append(courant.strip())
    return morceaux


def traduire_schema_sql(sql: str):
    """
    CREATE TABLE → modèles SQLAlchemy 2.0 (style déclaratif typé).
    Retourne (code Python, {table: classe}) ou (None, {}).
    """
    sql = re.sub(r"--[^\n]*|/\*.*?\*/", "", sql, flags=re.S)
    # Le corps d'une table se délimite en COMPTANT les parenthèses : une
    # expression régulière s'arrêterait au milieu de TINYINT(1) DEFAULT…
    tables = []
    for m in re.finditer(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"\[]?(\w+)[`\"\]]?\s*\(",
                         sql, re.I):
        debut, niveau, i, dans_chaine = m.end(), 1, m.end(), False
        while i < len(sql) and niveau:
            if sql[i] == "'":
                dans_chaine = not dans_chaine
            elif not dans_chaine:
                niveau += (sql[i] == "(") - (sql[i] == ")")
            i += 1
        tables.append((m.group(1), sql[debut:i - 1]))
    if not tables:
        return None, {}
    classes, blocs, types_utilises, annotations = {}, [], set(), set()
    for table, corps in tables:
        classe = _nom_classe(table)
        classes[table] = classe
        colonnes, cles_primaires, uniques, etrangeres = [], set(), set(), {}
        for definition in _decouper(corps):
            d = definition.strip()
            pk = re.match(r"PRIMARY\s+KEY\s*\(([^)]*)\)", d, re.I)
            if pk:
                cles_primaires |= {c.strip(" `\"") for c in pk.group(1).split(",")}
                continue
            un = re.match(r"UNIQUE(?:\s+(?:KEY|INDEX))?(?:\s+[`\"]?\w+[`\"]?)?\s*\(([^)]*)\)", d, re.I)
            if un:
                uniques |= {c.strip(" `\"") for c in un.group(1).split(",")}
                continue
            fk = re.match(r"(?:CONSTRAINT\s+\w+\s+)?FOREIGN\s+KEY\s*\(\s*[`\"]?(\w+)[`\"]?\s*\)\s*"
                          r"REFERENCES\s+[`\"]?(\w+)[`\"]?\s*\(\s*[`\"]?(\w+)", d, re.I)
            if fk:
                etrangeres[fk.group(1)] = f"{fk.group(2)}.{fk.group(3)}"
                continue
            if re.match(r"(KEY|INDEX|CHECK|CONSTRAINT)\b", d, re.I):
                continue
            col = re.match(r"[`\"]?(\w+)[`\"]?\s+(.+)", d, re.S)
            if col:
                colonnes.append((col.group(1), col.group(2)))
        lignes = [f"class {classe}(Base):", f'    """Table « {table} »."""',
                  f'    __tablename__ = "{table}"', ""]
        for nom, reste in colonnes:
            type_sa, type_py = _type(reste)
            types_utilises.add(re.sub(r"\(.*", "", type_sa))
            annotations.add(type_py)
            options = []
            if nom in etrangeres:
                options.append(f'ForeignKey("{etrangeres[nom]}")')
                types_utilises.add("ForeignKey")
            if nom in cles_primaires or re.search(r"PRIMARY\s+KEY", reste, re.I):
                options.append("primary_key=True")
            if re.search(r"AUTO_INCREMENT|SERIAL|IDENTITY", reste, re.I):
                options.append("autoincrement=True")
            if nom in uniques or re.search(r"\bUNIQUE\b", reste, re.I):
                options.append("unique=True")
            if re.search(r"NOT\s+NULL", reste, re.I) and "primary_key=True" not in options:
                options.append("nullable=False")
            defaut = re.search(r"DEFAULT\s+('(?:[^']*)'|[\w.]+)", reste, re.I)
            if defaut and defaut.group(1).upper() not in ("NULL", "CURRENT_TIMESTAMP"):
                options.append(f"server_default={defaut.group(1).strip(chr(39))!r}")
            optionnel = "nullable=False" not in options and "primary_key=True" not in options
            annotation = f"Optional[{type_py}]" if optionnel else type_py
            arguments = ", ".join([type_sa] + options)
            lignes.append(f"    {nom}: Mapped[{annotation}] = mapped_column({arguments})")
        blocs.append("\n".join(lignes))

    imports_py = []
    if "Decimal" in annotations:
        imports_py.append("from decimal import Decimal")
    dates = sorted({a for a in annotations if a in ("date", "datetime", "time")})
    if dates:
        imports_py.append(f"from datetime import {', '.join(dates)}")
    entete = ['"""Modèles SQLAlchemy traduits depuis le schéma SQL, sans LLM : chaque',
              'type SQL a une correspondance exacte."""', "",
              *imports_py, "from typing import Optional", "",
              f"from sqlalchemy import {', '.join(sorted(types_utilises))}",
              "from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column", "", "",
              "class Base(DeclarativeBase):", "    pass", ""]
    return "\n".join(entete) + "\n\n" + "\n\n\n".join(blocs) + "\n", classes


def classer(chemin: str, extensions_source: tuple) -> str:
    nom = os.path.basename(chemin).lower()
    extension = os.path.splitext(nom)[1]
    if nom in CONFIGURATIONS:
        return "configuration"
    if nom.endswith(".twig"):
        return "vue"
    if extension == ".sql":
        with open(chemin, encoding="utf-8", errors="ignore") as f:
            return "schema_sql" if re.search(r"CREATE\s+TABLE", f.read(), re.I) else "donnees_sql"
    if extension in STATIQUES:
        return "statique"
    return "autre"


def traiter_annexes(dossier: str, fichiers: list, dossier_sortie: str,
                    extensions_source: tuple = (".php",)) -> dict:
    """
    Classe et traite chaque fichier non-code. Retourne le rapport, et les
    signatures des modèles produits (pour informer le Développeur).
    """
    rapport, signatures, schemas = [], [], []
    for relatif in sorted(fichiers):
        chemin = os.path.join(dossier, relatif)
        if not os.path.isfile(chemin):
            continue
        categorie = classer(chemin, extensions_source)
        entree = {"fichier": relatif, "categorie": categorie}
        if categorie == "schema_sql":
            schemas.append(relatif)
            continue
        if categorie == "vue":
            entree["action"] = "converti en gabarit Jinja2 (voir templates/)"
            rapport.append(entree)
            continue
        destination = {"statique": "static", "donnees_sql": "donnees",
                       "configuration": "configuration", "autre": "autres"}[categorie]
        if not (categorie == "configuration" and os.path.basename(relatif).lower()
                in ("composer.json", "composer.lock")):
            chemin_relatif = relatif.replace("\\", "/")
            premier = chemin_relatif.split("/", 1)
            # Un dossier public d'origine (static, public, assets) est fusionné
            # avec celui du projet produit : pas de static/static/…
            if categorie == "statique" and len(premier) == 2 and \
                    premier[0].lower() in ("static", "public", "assets", "www"):
                chemin_relatif = premier[1]
            cible = os.path.join(dossier_sortie, destination, chemin_relatif)
            os.makedirs(os.path.dirname(cible), exist_ok=True)
            shutil.copy2(chemin, cible)
            entree["cible"] = f"{destination}/{chemin_relatif}"
        entree["action"] = {
            "statique": "copié tel quel",
            "donnees_sql": "conservé : les données restent dans la base",
            "autre": "copié, et signalé : traitement à décider",
        }.get(categorie) or CONFIGURATIONS.get(os.path.basename(relatif).lower(), "copié")
        rapport.append(entree)

    if schemas:
        sql = "\n".join(open(os.path.join(dossier, s), encoding="utf-8", errors="ignore").read()
                        for s in schemas)
        code, classes = traduire_schema_sql(sql)
        if code:
            with open(os.path.join(dossier_sortie, "models.py"), "w", encoding="utf-8") as f:
                f.write(code)
            for s in schemas:
                rapport.append({"fichier": s, "categorie": "schema_sql", "cible": "models.py",
                                "action": "traduit en modèles SQLAlchemy, sans LLM",
                                "tables": classes})
            signatures = [f"{classe} (modèle SQLAlchemy de la table « {table} », à importer : "
                          f"from models import {classe})" for table, classe in classes.items()]
    return {"fichiers": rapport, "signatures_modeles": signatures}