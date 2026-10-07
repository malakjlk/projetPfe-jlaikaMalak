"""
Adaptateurs de langage — SMAML
===============================
Un noyau commun, et un adaptateur par langage source.

Ce qui est COMMUN à tous les langages : le Manager, la supervision,
l'espace partagé, le Développeur (LLM), le Testeur, le Vérificateur,
l'Auditeur, le juge et le Réviseur — tous travaillent sur le code
PYTHON produit, quel que soit le langage d'origine.

Ce qui est PROPRE à chaque langage tient dans un adaptateur :
  • reconnaître ses fichiers ;
  • analyser son code (unités, paramètres, failles, gardes, données) ;
  • repérer les dépendances entre ses fichiers ;
  • extraire le code d'une unité ;
  • guider le Développeur sur les pièges de traduction du langage ;
  • exécuter le code d'origine, pour le Comparateur.

Ajouter un langage = écrire un adaptateur. Le noyau ne change pas.

Langages pris en charge : PHP (complet), COBOL et Fortran (analyse et
traduction ; la comparaison d'exécution demande GnuCOBOL ou gfortran).
"""

from __future__ import annotations

import os
import re
import shutil

# Langages legacy reconnus mais sans adaptateur : on sait les nommer,
# pour refuser clairement au lieu de répondre « 0 fichier trouvé ».
LANGAGES_CONNUS = {
    ".java": "Java", ".c": "C", ".h": "C", ".cpp": "C++", ".pl": "Perl",
    ".pm": "Perl", ".vb": "Visual Basic", ".bas": "BASIC", ".pas": "Pascal",
    ".rb": "Ruby", ".asp": "ASP classique", ".cfm": "ColdFusion",
    ".rpg": "RPG", ".pli": "PL/I", ".pro": "Prolog", ".adb": "Ada",
}


class AdaptateurLangage:
    """Interface d'un adaptateur. Chaque langage la réalise."""

    nom = "inconnu"
    extensions: tuple = ()

    def lister_sources(self, dossier: str) -> list:
        sources = []
        for racine, _, noms in os.walk(dossier):
            for nom in noms:
                if nom.lower().endswith(self.extensions):
                    sources.append(os.path.join(racine, nom))
        return sorted(sources)

    def analyser(self, code: str) -> dict:
        """Rapport au format commun : fonctions, classes, failles…"""
        raise NotImplementedError

    def dependances(self, fichiers: list) -> dict:
        """{fichier: [fichiers dont il dépend]}"""
        raise NotImplementedError

    def extraire_unite(self, code: str, nom: str) -> str:
        """Code source d'une unité (fonction, paragraphe…)."""
        raise NotImplementedError

    def consigne_traduction(self) -> str:
        """Pièges de traduction propres au langage, pour le Développeur."""
        return ""

    def executeur(self):
        """(disponible, raison) — pour le Comparateur."""
        return False, "aucun exécuteur pour ce langage"


# ═══ PHP — délègue au code existant ════════════════════

class AdaptateurPHP(AdaptateurLangage):
    nom = "PHP"
    extensions = (".php",)

    def analyser(self, code):
        from agent_analyste import analyser_code_php
        return analyser_code_php(code)

    def dependances(self, fichiers):
        from agent_analyste import construire_graphe, dependances_par_appels
        par_includes = construire_graphe(fichiers)
        par_appels = dependances_par_appels(fichiers)
        return {f: sorted(set(par_includes.get(f, [])) | set(par_appels.get(f, [])))
                for f in fichiers}

    def extraire_unite(self, code, nom):
        from agent_architecte import _source_module
        return _source_module(code, nom, "fonction")

    def executeur(self):
        chemin = shutil.which("php")
        return (True, chemin) if chemin else (False, "PHP n'est pas installé")


# ═══ COBOL ═════════════════════════════════════════════

class AdaptateurCOBOL(AdaptateurLangage):
    """
    COBOL : programmes découpés en divisions ; la logique est dans la
    PROCEDURE DIVISION, organisée en PARAGRAPHES appelés par PERFORM.
    Un paragraphe devient une fonction Python. Les données de la
    WORKING-STORAGE deviennent un état explicite.
    """

    nom = "COBOL"
    extensions = (".cbl", ".cob", ".cobol", ".cpy")

    _PROGRAMME = re.compile(r"PROGRAM-ID\.\s*([A-Z0-9-]+)", re.I)
    _PROCEDURE = re.compile(r"PROCEDURE\s+DIVISION(?:\s+USING\s+([^.]*))?\.", re.I)
    # Un paragraphe : un nom seul sur sa ligne, terminé par un point,
    # en zone A (au plus 7 espaces de marge, format fixe ou libre).
    _PARAGRAPHE = re.compile(r"^\s{0,7}([A-Z0-9][A-Z0-9-]*)\.\s*$", re.I | re.M)
    _MOTS_RESERVES = {"EXIT", "GOBACK", "STOP", "END-IF", "END-PERFORM", "CONTINUE"}

    @staticmethod
    def _sans_commentaires(code: str) -> str:
        lignes = []
        for ligne in code.splitlines():
            # format fixe : un * ou / en colonne 7 marque un commentaire
            if len(ligne) > 6 and ligne[6] in "*/":
                continue
            lignes.append(re.sub(r"\*>.*$", "", ligne))   # format libre
        return "\n".join(lignes)

    def _paragraphes(self, code: str) -> list:
        """[(nom, début, fin)] des paragraphes de la PROCEDURE DIVISION."""
        procedure = self._PROCEDURE.search(code)
        if not procedure:
            return []
        trouves = [m for m in self._PARAGRAPHE.finditer(code, procedure.end())
                   if m.group(1).upper() not in self._MOTS_RESERVES]
        bornes = []
        for i, m in enumerate(trouves):
            fin = trouves[i + 1].start() if i + 1 < len(trouves) else len(code)
            bornes.append((m.group(1).upper(), m.start(), fin))
        return bornes

    def analyser(self, code):
        propre = self._sans_commentaires(code)
        programme = self._PROGRAMME.search(propre)
        procedure = self._PROCEDURE.search(propre)
        parametres = ([p for p in re.split(r"[\s,]+", procedure.group(1) or "") if p]
                      if procedure else [])

        fonctions = []
        for nom, debut, fin in self._paragraphes(propre):
            corps = propre[debut:fin]
            fonctions.append({
                "nom": nom,
                "parametres": parametres if not fonctions else [],
                "corps_resume": corps.strip()[:300],
                "lignes": {"debut": propre.count("\n", 0, debut) + 1,
                           "fin": propre.count("\n", 0, fin) + 1},
                "appelle": sorted(set(re.findall(r"PERFORM\s+([A-Z0-9-]+)", corps, re.I))),
            })

        donnees = []
        for niveau, nom, pic in re.findall(
                r"^\s*(01|77)\s+([A-Z0-9-]+)(?:\s+PIC(?:TURE)?\s+([^\s.]+))?",
                propre, re.I | re.M):
            entree = {"nom": nom.upper(), "niveau": niveau, "pic": (pic or "").upper()}
            if "V" in entree["pic"]:
                entree["remarque"] = ("décimal à virgule fixe : à traduire avec "
                                      "decimal.Decimal, jamais float")
            donnees.append(entree)

        # Failles et gardes, au FORMAT COMMUN de l'Analyste PHP, et
        # rattachées au paragraphe qui les contient.
        failles, gardes = [], []
        for nom, debut, fin in self._paragraphes(propre):
            corps = propre[debut:fin]
            for bloc in re.findall(r"EXEC\s+SQL(.*?)END-EXEC", corps, re.I | re.S):
                if re.search(r"\bPREPARE\b|\bEXECUTE\s+IMMEDIATE\b", bloc, re.I):
                    failles.append({
                        "type": "sql_injection", "cwe": "CWE-89",
                        "severity": "critical", "fonction": nom,
                        "code": " ".join(bloc.split())[:160],
                        "description": "SQL dynamique (PREPARE / EXECUTE IMMEDIATE) "
                                       "construit à l'exécution"})
            for condition in re.findall(r"\bIF\s+(.+?)(?:\n|\bTHEN\b)", corps, re.I):
                if re.search(r"(<|>|=|\bLESS\b|\bGREATER\b|\bEQUAL\b|\bNOT\b)",
                             condition, re.I):
                    longueur = re.search(r"\bLENGTH\b", condition, re.I)
                    gardes.append({
                        "type": "validation_longueur" if longueur else "validation_format",
                        "description": f"condition à préserver : {condition.strip()[:120]}",
                        "code": condition.strip()[:160], "fonction": nom,
                        "a_preserver": True})

        return {
            "langage_source": "COBOL",
            "programme": programme.group(1).upper() if programme else None,
            "fonctions": fonctions,
            "classes": [],
            "variables_globales": donnees,
            "failles_potentielles": failles,
            "invariants_securite": gardes,
            "dependances": sorted(set(re.findall(r"\bCOPY\s+([A-Z0-9-]+)", propre, re.I))
                                  | set(re.findall(r"\bCALL\s+['\"]([A-Z0-9-]+)['\"]",
                                                   propre, re.I))),
            "metriques": {"lignes": len(code.splitlines()),
                          "paragraphes": len(fonctions)},
        }

    def dependances(self, fichiers):
        """
        Un programme dépend des sous-programmes qu'il appelle (CALL) et des
        copybooks qu'il inclut (COPY).
        """
        programmes, copybooks = {}, {}
        for f in fichiers:
            with open(f, encoding="utf-8", errors="ignore") as source:
                code = self._sans_commentaires(source.read())
            nom = self._PROGRAMME.search(code)
            if nom:
                programmes[nom.group(1).upper()] = f
            copybooks[os.path.splitext(os.path.basename(f))[0].upper()] = f
        graphe = {}
        for f in fichiers:
            with open(f, encoding="utf-8", errors="ignore") as source:
                code = self._sans_commentaires(source.read())
            appels = {c.upper() for c in re.findall(r"\bCALL\s+['\"]([A-Z0-9-]+)['\"]", code, re.I)}
            copies = {c.upper() for c in re.findall(r"\bCOPY\s+([A-Z0-9-]+)", code, re.I)}
            deps = {programmes[a] for a in appels if a in programmes} | \
                   {copybooks[c] for c in copies if c in copybooks}
            graphe[f] = sorted(d for d in deps if d != f)
        return graphe

    def extraire_unite(self, code, nom):
        propre = self._sans_commentaires(code)
        for paragraphe, debut, fin in self._paragraphes(propre):
            if paragraphe == nom.upper():
                return propre[debut:fin].strip()
        return code

    # ── Données : traduction DÉTERMINISTE, sans LLM ──
    _ENTREE_DONNEE = re.compile(
        r"^\s*(\d{2})\s+([A-Z0-9-]+)(?:\s+PIC(?:TURE)?\s+(S?[X9]\S*?))?"
        r"(?:\s+OCCURS\s+(\d+)(?:\s+TIMES)?)?\s*\.\s*$", re.I | re.M)

    @staticmethod
    def _nom_champ(nom: str) -> str:
        return re.sub(r"[^a-z0-9_]", "_", nom.lower()).strip("_")

    @staticmethod
    def _nom_classe(nom: str) -> str:
        return "".join(p.capitalize() for p in re.split(r"[^A-Za-z0-9]+", nom) if p)

    @staticmethod
    def _type_pic(pic: str):
        """(type Python, valeur par défaut, longueur, nombre de décimales)"""
        pic = pic.upper().rstrip(".")
        def taille(motif):
            total = 0
            for symbole, repetition in re.findall(motif, pic):
                total += int(repetition) if repetition else 1
            return total
        if "X" in pic:
            return "str", '""', taille(r"(X)(?:\((\d+)\))?"), None
        if "V" in pic:
            decimales = pic.split("V", 1)[1]
            echelle = sum(int(r) if r else 1 for _, r in re.findall(r"(9)(?:\((\d+)\))?", decimales))
            return "Decimal", 'Decimal("0")', None, echelle
        return "int", "0", None, None

    def traduire_donnees(self, code: str):
        """
        Traduit les définitions de données (copybook, WORKING-STORAGE) en
        dataclasses Python, de façon déterministe : chaque clause PIC a une
        correspondance exacte. Les champs gardent les règles du COBOL : un
        PIC X(n) est tronqué à n caractères, un décimal à son nombre de
        décimales (troncature, comme un MOVE COBOL sans ROUNDED).
        Retourne (code Python, noms des classes) ou (None, []).
        """
        entrees = [(int(n), nom.upper(), (pic or "").upper(), occurs)
                   for n, nom, pic, occurs in self._ENTREE_DONNEE.findall(
                       self._sans_commentaires(code))]
        if not entrees:
            return None, []

        classes = []          # [(nom_classe, [(champ, type, défaut, longueur, échelle, pic, occurs)])]
        pile = []             # [(niveau, nom_classe)]

        def nouvelle_classe(nom):
            classes.append((self._nom_classe(nom), []))
            return classes[-1][0]

        for i, (niveau, nom, pic, occurs) in enumerate(entrees):
            while pile and pile[-1][0] >= niveau:
                pile.pop()
            groupe = not pic and i + 1 < len(entrees) and entrees[i + 1][0] > niveau
            parent = pile[-1][1] if pile else None
            if groupe:
                classe = nouvelle_classe(nom)
                if parent:
                    champs = dict(classes)[parent]
                    champs.append((self._nom_champ(nom), classe, f"field(default_factory={classe})",
                                   None, None, "groupe", occurs))
                pile.append((niveau, classe))
            elif pic:
                if parent is None:
                    parent = nouvelle_classe("DonneesProgramme") if not classes or \
                        classes[-1][0] != "DonneesProgramme" else "DonneesProgramme"
                    pile.append((0, parent))
                typ, defaut, longueur, echelle = self._type_pic(pic)
                dict(classes)[parent].append((self._nom_champ(nom), typ, defaut,
                                              longueur, echelle, pic, occurs))

        lignes = ['"""Structures de données traduites depuis COBOL, sans LLM : chaque',
                  'clause PIC a une correspondance exacte en Python."""', "",
                  "from dataclasses import dataclass, field",
                  "from decimal import Decimal, ROUND_DOWN", "from typing import List", ""]
        for nom_classe, champs in reversed(classes):    # les sous-groupes d'abord
            lignes += ["", "@dataclass", f"class {nom_classe}:",
                       f'    """Enregistrement COBOL {nom_classe}."""']
            if not champs:
                lignes.append("    pass")
            regles = []
            for champ, typ, defaut, longueur, echelle, pic, occurs in champs:
                if occurs:
                    fabrique = defaut.replace("field(default_factory=", "").rstrip(")") \
                        if defaut.startswith("field") else None
                    element = f"{fabrique}()" if fabrique else defaut
                    lignes.append(f"    {champ}: List[{typ}] = field(default_factory=lambda: "
                                  f"[{element} for _ in range({occurs})])  # OCCURS {occurs}")
                else:
                    lignes.append(f"    {champ}: {typ} = {defaut}  # PIC {pic}")
                if longueur and not occurs:
                    regles.append(f"        self.{champ} = str(self.{champ})[:{longueur}]")
                if echelle is not None and not occurs:
                    quantum = "1" if echelle == 0 else "0." + "0" * (echelle - 1) + "1"
                    regles.append(f"        self.{champ} = Decimal(self.{champ}).quantize("
                                  f'Decimal("{quantum}"), rounding=ROUND_DOWN)')
            if regles:
                lignes += ["", "    def __post_init__(self):",
                           "        # règles du COBOL : longueur fixe, décimales fixes"] + regles
        return "\n".join(lignes) + "\n", [c for c, _ in classes]

    def consigne_traduction(self):
        return (
            "LE CODE SOURCE EST EN COBOL, PAS EN PHP. Toutes les mentions de "
            "« PHP » dans ces consignes désignent ce code COBOL.\n"
            "Pièges de traduction COBOL → Python à respecter :\n"
            "- Un paragraphe COBOL devient une fonction Python ; PERFORM devient "
            "un appel de fonction.\n"
            "- Les données de la WORKING-STORAGE sont un état partagé : rends-le "
            "explicite (paramètres, valeurs de retour, ou dataclass), jamais de "
            "variable globale.\n"
            "- Un champ PIC avec V (ex. PIC 9(5)V99) est un DÉCIMAL À VIRGULE "
            "FIXE : utilise decimal.Decimal, JAMAIS float, et respecte le nombre "
            "de décimales.\n"
            "- Un champ PIC X(n) a une longueur fixe : COBOL complète par des "
            "espaces et tronque au-delà de n caractères.\n"
            "- EXEC SQL devient une requête SQLAlchemy paramétrée ; le SQL "
            "dynamique (PREPARE) ne doit jamais concaténer d'entrée.\n"
            "- DISPLAY devient un journal (logging) ; STOP RUN ou GOBACK devient "
            "un retour de fonction.")

    def executeur(self):
        chemin = shutil.which("cobc")
        return ((True, chemin) if chemin else
                (False, "compilateur GnuCOBOL (cobc) non installé : "
                        "l'équivalence d'exécution n'est pas mesurable"))


# ═══ FORTRAN ═══════════════════════════════════════════

class AdaptateurFortran(AdaptateurLangage):
    """
    Fortran : programmes, sous-programmes (SUBROUTINE), fonctions et
    modules. Les SUBROUTINE et FUNCTION deviennent des fonctions Python.
    Pièges : tableaux indexés à partir de 1 et rangés par colonnes, typage
    implicite, état global des blocs COMMON, résultats rendus par les
    arguments (INTENT(OUT)).
    """

    nom = "Fortran"
    extensions = (".f", ".for", ".f77", ".f90", ".f95", ".f03", ".f08")

    _UNITE = re.compile(
        r"^[ \t]*(?:(?:RECURSIVE|PURE|ELEMENTAL|INTEGER|REAL(?:\*\d+)?|LOGICAL|"
        r"DOUBLE\s+PRECISION|COMPLEX|CHARACTER(?:\*\d+)?)\s+)*"
        r"(SUBROUTINE|FUNCTION|PROGRAM)\s+(\w+)\s*(?:\(([^)]*)\))?", re.I | re.M)
    _FIN = re.compile(r"^[ \t]*END(?:\s*(?:SUBROUTINE|FUNCTION|PROGRAM)(?:\s+\w+)?)?\s*$",
                      re.I | re.M)
    _OPERATEURS = r"(\.LT\.|\.GT\.|\.LE\.|\.GE\.|\.EQ\.|\.NE\.|<|>|==|/=)"

    @staticmethod
    def _sans_commentaires(code: str) -> str:
        lignes = []
        for ligne in code.splitlines():
            # forme fixe : C, c, * ou ! en colonne 1 ; forme libre : ! n'importe où
            if ligne[:1] in ("C", "c", "*", "!") and not re.match(r"^\s*(CALL|COMMON|CHARACTER|COMPLEX|CONTAINS|CLOSE|CONTINUE)\b", ligne, re.I):
                continue
            lignes.append(re.sub(r"!.*$", "", ligne))
        return "\n".join(lignes)

    def _unites(self, code: str) -> list:
        """[(type, nom, paramètres, début, fin)]"""
        unites = []
        for m in self._UNITE.finditer(code):
            fin = self._FIN.search(code, m.end())
            unites.append((m.group(1).upper(), m.group(2).upper(),
                           [p.strip() for p in (m.group(3) or "").split(",") if p.strip()],
                           m.start(), fin.end() if fin else len(code)))
        return unites

    def analyser(self, code):
        propre = self._sans_commentaires(code)
        fonctions, gardes = [], []
        for genre, nom, parametres, debut, fin in self._unites(propre):
            if genre == "PROGRAM":
                parametres = []
            corps = propre[debut:fin]
            fonctions.append({
                "nom": nom, "parametres": parametres, "genre": genre.lower(),
                "corps_resume": corps.strip()[:300],
                "lignes": {"debut": propre.count("\n", 0, debut) + 1,
                           "fin": propre.count("\n", 0, fin) + 1},
                "appelle": sorted({c.upper() for c in re.findall(r"\bCALL\s+(\w+)", corps, re.I)}),
            })
            for condition in re.findall(r"\bIF\s*\((.+?)\)\s*(?:THEN|STOP|RETURN|CALL|ERROR)",
                                        corps, re.I):
                if re.search(self._OPERATEURS, condition, re.I):
                    gardes.append({"type": "validation_format", "fonction": nom,
                                   "description": f"condition à préserver : {condition.strip()[:120]}",
                                   "code": condition.strip()[:160], "a_preserver": True})

        donnees = [{"nom": f"/{bloc.upper()}/", "niveau": "COMMON", "pic": "",
                    "remarque": "bloc COMMON : état global partagé, à rendre explicite"}
                   for bloc in re.findall(r"\bCOMMON\s*/\s*(\w+)\s*/", propre, re.I)]
        if re.search(r"DOUBLE\s+PRECISION|REAL\s*\*\s*8|REAL\s*\(\s*8\s*\)", propre, re.I):
            donnees.append({"nom": "precision", "niveau": "type", "pic": "",
                            "remarque": "double précision : float Python (64 bits) ou numpy.float64"})
        if not re.search(r"IMPLICIT\s+NONE", propre, re.I):
            donnees.append({"nom": "typage_implicite", "niveau": "type", "pic": "",
                            "remarque": "pas d'IMPLICIT NONE : les variables en I à N sont "
                                        "des entiers (division entière !)"})

        dependances = {u.upper() for u in re.findall(r"^\s*USE\s+(\w+)", propre, re.I | re.M)}
        dependances |= {i for i in re.findall(r"INCLUDE\s+['\"]([^'\"]+)['\"]", propre, re.I)}
        for f in fonctions:
            dependances |= set(f["appelle"])
        return {
            "langage_source": "Fortran",
            "programme": next((f["nom"] for f in fonctions if f["genre"] == "program"), None),
            "fonctions": [f for f in fonctions if f["genre"] != "program"] or fonctions,
            "classes": [],
            "variables_globales": donnees,
            "failles_potentielles": [],
            "invariants_securite": gardes,
            "dependances": sorted(dependances),
            "metriques": {"lignes": len(code.splitlines()), "unites": len(fonctions)},
        }

    def dependances(self, fichiers):
        """Un fichier dépend des modules qu'il USE et des sous-programmes qu'il CALL."""
        definit, contenus = {}, {}
        for f in fichiers:
            with open(f, encoding="utf-8", errors="ignore") as source:
                code = self._sans_commentaires(source.read())
            contenus[f] = code
            for module in re.findall(r"^\s*MODULE\s+(?!PROCEDURE)(\w+)", code, re.I | re.M):
                definit[module.upper()] = f
            for _, nom, _, _, _ in self._unites(code):
                definit.setdefault(nom, f)
        graphe = {}
        for f, code in contenus.items():
            utilises = {u.upper() for u in re.findall(r"^\s*USE\s+(\w+)", code, re.I | re.M)}
            utilises |= {c.upper() for c in re.findall(r"\bCALL\s+(\w+)", code, re.I)}
            graphe[f] = sorted({definit[u] for u in utilises if u in definit} - {f})
        return graphe

    def extraire_unite(self, code, nom):
        propre = self._sans_commentaires(code)
        for _, unite, _, debut, fin in self._unites(propre):
            if unite == nom.upper():
                return propre[debut:fin].strip()
        return code

    def traduire_donnees(self, code: str):
        """
        Constantes PARAMETER d'un module Fortran → constantes Python, sans
        LLM. Les exposants en double précision (3.14d0) deviennent des
        exposants Python (3.14e0).
        """
        propre = self._sans_commentaires(code)
        constantes = re.findall(
            r"(INTEGER|REAL(?:\s*\(\s*\d+\s*\)|\*\d+)?|DOUBLE\s+PRECISION|LOGICAL|"
            r"CHARACTER[^,:]*)\s*,\s*PARAMETER\s*::\s*(\w+)\s*=\s*([^\n]+)", propre, re.I)
        if not constantes:
            return None, []
        lignes = ['"""Constantes traduites depuis Fortran, sans LLM."""', "",
                  "from typing import Final", ""]
        noms = []
        for genre, nom, valeur in constantes:
            valeur = re.sub(r"(\d)[dD]([+-]?\d+)", r"\1e\2", valeur.strip())
            valeur = re.sub(r"\.TRUE\.", "True", re.sub(r"\.FALSE\.", "False", valeur, flags=re.I),
                            flags=re.I)
            genre = genre.upper()
            python = ("int" if genre.startswith("INTEGER") else "bool" if genre.startswith("LOGICAL")
                      else "str" if genre.startswith("CHARACTER") else "float")
            lignes.append(f"{nom.upper()}: Final[{python}] = {valeur}  # {genre} PARAMETER")
            noms.append(nom.upper())
        return "\n".join(lignes) + "\n", noms

    def consigne_traduction(self):
        return (
            "LE CODE SOURCE EST EN FORTRAN, PAS EN PHP. Toutes les mentions de "
            "« PHP » dans ces consignes désignent ce code Fortran.\n"
            "Pièges de traduction Fortran → Python à respecter :\n"
            "- Les tableaux Fortran commencent à l'INDICE 1 ; en Python à 0. Décale "
            "chaque indice, et les bornes des boucles DO (DO I = 1, N devient range(n)).\n"
            "- Les tableaux à plusieurs dimensions sont rangés PAR COLONNES : avec "
            "numpy, utilise order=\"F\" ou transpose explicitement.\n"
            "- Sans IMPLICIT NONE, les variables commençant par I, J, K, L, M ou N sont "
            "des ENTIERS : la division entre entiers est une division ENTIÈRE (utilise //).\n"
            "- Un SUBROUTINE rend ses résultats par ses ARGUMENTS (INTENT(OUT) ou "
            "INOUT) : en Python, renvoie-les avec return, en tuple si plusieurs.\n"
            "- Un bloc COMMON est un état global partagé : rends-le explicite "
            "(paramètres ou dataclass), jamais de variable globale.\n"
            "- DOUBLE PRECISION et REAL*8 sont des flottants 64 bits : float Python "
            "ou numpy.float64. Préserve l'ordre des opérations.\n"
            "- GOTO devient une structure de contrôle (boucle, break, return) ; "
            "STOP devient une exception ou un retour.")

    def executeur(self):
        chemin = shutil.which("gfortran")
        return ((True, chemin) if chemin else
                (False, "compilateur gfortran non installé : l'équivalence "
                        "d'exécution n'est pas mesurable"))


ADAPTATEURS = {"php": AdaptateurPHP(), "cobol": AdaptateurCOBOL(),
               "fortran": AdaptateurFortran()}


def adaptateur(langage: str) -> AdaptateurLangage:
    return ADAPTATEURS[(langage or "php").lower()]


def detecter_langages(dossier: str) -> dict:
    """
    Inventaire des langages du projet. Le langage principal est celui
    qui compte le plus de fichiers parmi les langages pris en charge.
    """
    comptes, inconnus = {}, {}
    for racine, _, noms in os.walk(dossier):
        for nom in noms:
            extension = os.path.splitext(nom)[1].lower()
            cle = next((c for c, a in ADAPTATEURS.items() if extension in a.extensions), None)
            if cle:
                comptes[cle] = comptes.get(cle, 0) + 1
            elif extension in LANGAGES_CONNUS:
                langage = LANGAGES_CONNUS[extension]
                inconnus[langage] = inconnus.get(langage, 0) + 1
    principal = max(comptes, key=comptes.get) if comptes else None
    return {"principal": principal,
            "pris_en_charge": comptes,
            "non_pris_en_charge": inconnus,
            "adaptateurs_disponibles": [a.nom for a in ADAPTATEURS.values()]}
