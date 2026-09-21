import json
import os
import struct
import numpy as np

# FAISS est une bibliothèque compilée non signée : le Contrôle
# intelligent des applications de Windows peut en bloquer le chargement.
# Pour 3 060 exemples, une recherche exacte en numpy est aussi juste et
# à peine plus lente — FAISS ne devient indispensable qu'à partir de
# centaines de milliers de vecteurs. Le projet fonctionne donc avec ou
# sans lui.
try:
    import faiss
    FAISS_DISPONIBLE = True
except Exception:          # ImportError, ou DLL bloquée par Windows
    faiss = None
    FAISS_DISPONIBLE = False
from transformers import AutoTokenizer, AutoModel
import torch
from groq import Groq

# ─── REPLI NUMPY POUR L'INDEX FAISS ──────────────────
# Lit directement le fichier .faiss d'un index plat, sans FAISS : les
# vecteurs sont stockés tels quels après un court en-tête. La recherche
# donne les mêmes voisins que FAISS (vérifié sur IndexFlatIP et
# IndexFlatL2, écart de score < 1e-6).

class IndexPlatNumpy:
    """Remplace un index FAISS plat (IndexFlatIP / IndexFlatL2)."""
    def __init__(self, vecteurs, metrique):
        self.vecteurs = vecteurs
        self.metrique = metrique          # "IP" ou "L2"
        self.ntotal, self.d = vecteurs.shape

    def search(self, requetes, k):
        requetes = np.asarray(requetes, dtype="float32")
        k = min(k, self.ntotal)
        if self.metrique == "IP":
            scores = requetes @ self.vecteurs.T           # plus grand = plus proche
            ordre = np.argsort(-scores, axis=1, kind="stable")[:, :k]
        else:
            # distance L2 au carré, comme FAISS
            scores = (np.sum(requetes ** 2, axis=1, keepdims=True)
                      - 2 * requetes @ self.vecteurs.T
                      + np.sum(self.vecteurs ** 2, axis=1))
            ordre = np.argsort(scores, axis=1, kind="stable")[:, :k]
        valeurs = np.take_along_axis(scores, ordre, axis=1)
        return valeurs.astype("float32"), ordre.astype("int64")

def lire_index_plat(chemin):
    with open(chemin, "rb") as f:
        donnees = f.read()
    code = donnees[:4]
    if code not in (b"IxFI", b"IxF2"):
        raise ValueError(f"Index FAISS non plat ({code!r}) : lecture numpy impossible")
    pos = 4
    d, = struct.unpack_from("<i", donnees, pos); pos += 4
    ntotal, = struct.unpack_from("<q", donnees, pos); pos += 8
    pos += 16                                   # deux champs réservés
    pos += 1                                    # is_trained
    metric_type, = struct.unpack_from("<i", donnees, pos); pos += 4
    if metric_type > 1:
        pos += 4                                # metric_arg
    taille, = struct.unpack_from("<Q", donnees, pos); pos += 8
    if taille == ntotal * d * 4:                # format récent : octets
        vecteurs = np.frombuffer(donnees, dtype="<f4", count=ntotal * d, offset=pos)
    elif taille == ntotal * d:                  # format ancien : flottants
        vecteurs = np.frombuffer(donnees, dtype="<f4", count=taille, offset=pos)
    else:
        raise ValueError("Taille de vecteurs inattendue dans l'index FAISS")
    return IndexPlatNumpy(vecteurs.reshape(ntotal, d).copy(),
                          "IP" if code == b"IxFI" else "L2")


def normaliser_l2(vecteurs):
    """Équivalent de faiss.normalize_L2, en place."""
    normes = np.linalg.norm(vecteurs, axis=1, keepdims=True)
    normes[normes == 0] = 1.0
    vecteurs /= normes
    return vecteurs


# ─── CHARGEMENT DE LA BASE RAG ───────────────────────
print("Chargement de la base RAG...")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")

CHEMIN_INDEX = os.path.join(DATASET_DIR, "index_rag.faiss")
if FAISS_DISPONIBLE:
    index = faiss.read_index(CHEMIN_INDEX)
    MOTEUR_RECHERCHE = "FAISS"
else:
    index = lire_index_plat(CHEMIN_INDEX)
    MOTEUR_RECHERCHE = "numpy (FAISS indisponible)"

with open(os.path.join(DATASET_DIR, "metadata.json"),
          "r", encoding="utf-8") as f:
    metadata = json.load(f)

tokenizer = AutoTokenizer.from_pretrained("microsoft/codebert-base")
model = AutoModel.from_pretrained("microsoft/codebert-base")
model.eval()

print(f"Base RAG chargée : {index.ntotal} exemples indexés "
      f"— recherche : {MOTEUR_RECHERCHE}")


# ─── RETRIEVER ───────────────────────────────────────
def retriever(code_php: str, k: int = 5) -> list:
    """Cherche les k exemples les plus similaires dans la base RAG."""
    inputs = tokenizer(code_php, return_tensors="pt", truncation=True,
                       max_length=512, padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
    vecteur = outputs.last_hidden_state[:, 0, :].numpy()
    vecteur = np.array(vecteur).astype("float32")
    if FAISS_DISPONIBLE:
        faiss.normalize_L2(vecteur)
    else:
        normaliser_l2(vecteur)
    distances, indices = index.search(vecteur, k)
    exemples = []
    for i, idx in enumerate(indices[0]):
        if idx < len(metadata):
            exemple = metadata[idx].copy()
            exemple["score_similarite"] = float(distances[0][i])
            exemples.append(exemple)
    return exemples


# ─── APPEL LLM ───────────────────────────────────────
# Modèle Groq configurable : llama-3.3-70b-versatile a été retiré par
# Groq le 16 août 2026 ; remplaçant recommandé : openai/gpt-oss-120b.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

import cache_smaml


def appeler_llm(prompt: str, token: str, max_tentatives: int = 4) -> str:
    """
    Appelle le LLM de génération (GROQ_MODEL) via l'API Groq.
    En cas de rate limit (429), attend et réessaie (backoff
    exponentiel) au lieu de basculer sur le fallback — sinon un
    benchmark entier peut être contaminé par du code de secours.
    """
    import time
    client = Groq(api_key=token)
    attente = 20  # secondes, doublée à chaque tentative
    for tentative in range(1, max_tentatives + 1):
        try:
            params = dict(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=4000,
            )
            # gpt-oss raisonne avant de répondre, et ce raisonnement
            # consomme le budget de tokens : effort réduit pour qu'il
            # reste de la place pour le code.
            if GROQ_MODEL.startswith("openai/gpt-oss"):
                params["reasoning_effort"] = "low"
            response = client.chat.completions.create(**params)
            return response.choices[0].message.content
        except Exception as e:
            est_rate_limit = ("429" in str(e)
                              or "RateLimit" in type(e).__name__
                              or "rate limit" in str(e).lower())
            if est_rate_limit and tentative < max_tentatives:
                print(f"  ⏳ Rate limit Groq — attente {attente}s "
                      f"(tentative {tentative}/{max_tentatives})...")
                time.sleep(attente)
                attente *= 2
            else:
                raise


# ─── PATRONS DE CORRECTION SÉCURISÉE ─────────────────
# Few-shot ciblé sécurité : on montre au LLM COMMENT corriger
# chaque type de faille (sinon il réécrit la même faille en Python).
# ─── PATRONS DE MIGRATION DES VALIDATIONS ────────────
# Le LLM migre mal certaines validations PHP (ex. filter_var
# email → mécanisme Pydantic bancal). On lui montre la
# traduction Python correcte, simple et FIABLE.
PATRONS_VALIDATION = {
    "typage_php": (
        "Compatibilité de typage PHP : PHP convertit automatiquement les "
        "chaînes numériques en nombres ('42' == 42, is_numeric('3.14') est "
        "vrai, '10' / '2' vaut 5). Le code Python DOIT accepter les nombres "
        "ET les chaînes numériques. En début de fonction, convertis chaque "
        "paramètre numérique ainsi :\n"
        "  if isinstance(x, str):\n"
        "      try:\n"
        "          x = float(x) if ('.' in x or 'e' in x.lower()) else int(x)\n"
        "      except ValueError:\n"
        "          raise HTTPException(status_code=400, detail='Valeur non numérique')\n"
        "Pour traduire is_numeric($x) : accepte int, float, OU chaîne "
        "convertible (le motif try/except ci-dessus). N'utilise JAMAIS "
        "isinstance(x, (int, float)) seul ni x.isdigit() seul : ils "
        "rejettent '42' ou '3.14' que PHP accepte."
    ),
    "number_format": (
        "Formatage de nombres : `number_format($x, 2)` en PHP ajoute des "
        "SÉPARATEURS DE MILLIERS ('1,234,567.00'). La traduction Python "
        "correcte est f\"{x:,.2f}\" (le ',' dans le format ajoute les "
        "séparateurs) — PAS f\"{x:.2f}\" qui les omet."
    ),
    "filter_var_email": (
        "Validation d'email : `filter_var($x, FILTER_VALIDATE_EMAIL)` "
        "se traduit par une vérification simple et fiable, PAS par un "
        "modèle Pydantic. Utilise :\n"
        "  import re\n"
        "  if not re.match(r'^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$', email):\n"
        "      raise HTTPException(status_code=400, detail='Email invalide')"
    ),
    "preg_match": (
        "Validation par expression régulière : `preg_match('/motif/', $x)` "
        "se traduit par `re.match(r'motif', x)` (module re). Lève "
        "HTTPException si le motif ne correspond pas."
    ),
    "filter_var_url": (
        "Validation d'URL : utilise "
        "`re.match(r'^https?://', url)` plutôt qu'un modèle Pydantic."
    ),
}


PATRONS_CORRECTION = {
    "sql_injection": (
        "Injection SQL (CWE-89) : NE JAMAIS concaténer de variables dans "
        "une requête. Utilise l'ORM SQLAlchemy avec requêtes paramétrées.\n"
        "  Dangereux : db.execute(f\"SELECT * FROM users WHERE id={id}\")\n"
        "  Sûr : db.query(User).filter(User.id == id).first()"
    ),
    "command_injection": (
        "Injection de commande (CWE-78) : NE JAMAIS passer d'entrée "
        "utilisateur à un shell. Utilise subprocess avec une liste "
        "d'arguments et shell=False, ou une fonction Python native.\n"
        "  Dangereux : os.system(cmd) / subprocess.run(cmd, shell=True) / os.popen(cmd)\n"
        "  Sûr : subprocess.run([\"echo\", valeur], shell=False, "
        "capture_output=True, text=True, timeout=5).stdout"
    ),
    "insecure_deserialization": (
        "Désérialisation non sécurisée (CWE-502) : NE JAMAIS utiliser "
        "pickle sur des données non fiables. Utilise json.\n"
        "  Dangereux : pickle.loads(data)\n"
        "  Sûr : json.loads(data)  # avec try/except json.JSONDecodeError"
    ),
    "file_inclusion": (
        "Inclusion de fichier (CWE-98) : NE JAMAIS inclure un chemin "
        "construit depuis une entrée utilisateur. Valide contre une "
        "liste blanche et utilise pathlib (empêche la traversée ../)."
    ),
}


# ─── GÉNÉRATEUR DE CODE ──────────────────────────────
def generer_code_python(
    code_php: str,
    module_info: dict,
    invariants: list,
    failles: list,
    contexte_projet: str = "",
    feedback: dict = None
) -> str:
    """
    Génère le code Python équivalent au code PHP via RAG + LLM (Groq).

    contexte_projet : modules déjà migrés (imports inter-fichiers).
    feedback : feedback correctif du Réviseur (itération).
    """
    GROQ_TOKEN = os.getenv("GROQ_TOKEN")

    # Étape 1 — RAG (désactivable pour l'étude d'ablation)
    if os.getenv("SMAML_SANS_RAG"):
        print(f"\n  [ablation] RAG désactivé pour : "
              f"{module_info.get('nom_original', '')}")
        exemples = []
    else:
        print(f"\n  Recherche RAG pour : "
              f"{module_info.get('nom_original', '')}")
        exemples = retriever(code_php, k=3)
        print(f"  {len(exemples)} exemples similaires trouvés :")
        for ex in exemples:
            print(f"    - [{ex.get('categorie', '')}] "
                  f"{ex.get('description', '')[:50]} "
                  f"(score: {ex.get('score_similarite', 0):.3f})")

    # Étape 2 — Prompt enrichi
    exemples_text = ""
    for i, ex in enumerate(exemples):
        php = ex.get('code_php', '')[:200]
        py = ex.get('code_python', '')[:200]
        if php and py:
            exemples_text += f"""
Exemple {i+1} :
PHP : {php}
Python : {py}
---"""

    invariants_text = "\n".join([
        f"- {inv.get('type', '')}: {inv.get('description', '')}"
        for inv in invariants
    ])

    # Failles + patron de correction sécurisée
    # (patrons désactivables pour l'étude d'ablation)
    sans_patrons = bool(os.getenv("SMAML_SANS_PATRONS"))
    if sans_patrons:
        print("  [ablation] Patrons de correction/validation désactivés")
    lignes_failles = []
    for f in failles:
        type_faille = f.get('type', '') or f.get('faille', '')
        lignes_failles.append(
            f"- {type_faille} ({f.get('cwe', '')}): "
            f"{f.get('description', '')}"
        )
        patron = None if sans_patrons else PATRONS_CORRECTION.get(type_faille)
        if patron:
            lignes_failles.append(f"  → {patron}")
    failles_text = "\n".join(lignes_failles)

    # Détecter les validations PHP à migrer et injecter leur patron
    # (évite les migrations bancales type filter_var → Pydantic cassé)
    patrons_valid = []
    if not sans_patrons:
        if "FILTER_VALIDATE_EMAIL" in code_php or (
                "filter_var" in code_php and "EMAIL" in code_php.upper()):
            patrons_valid.append(PATRONS_VALIDATION["filter_var_email"])
        if "FILTER_VALIDATE_URL" in code_php:
            patrons_valid.append(PATRONS_VALIDATION["filter_var_url"])
        if "preg_match" in code_php:
            patrons_valid.append(PATRONS_VALIDATION["preg_match"])
        if "number_format" in code_php:
            patrons_valid.append(PATRONS_VALIDATION["number_format"])
        # Typage PHP-compatible : si le code manipule des nombres
        # (is_numeric, arithmétique ou comparaison numérique sur des
        # variables), le Python doit accepter les chaînes numériques
        # comme le fait PHP ('42' == 42).
        import re as _re
        manipule_nombres = (
            "is_numeric" in code_php
            or "is_int" in code_php
            or "is_float" in code_php
            or _re.search(r"\$\w+\s*[*/%]\s*", code_php)
            or _re.search(r"\$\w+\s*[<>]=?\s*-?\d", code_php)
            or _re.search(r"\$\w+\s*==?\s*-?\d", code_php)
        )
        if manipule_nombres:
            patrons_valid.append(PATRONS_VALIDATION["typage_php"])
    bloc_validation = ""
    if patrons_valid:
        bloc_validation = ("\nPATRONS DE MIGRATION DES VALIDATIONS "
                           "(suis-les EXACTEMENT) :\n"
                           + "\n".join(f"- {p}" for p in patrons_valid) + "\n")

    # Bloc contexte projet
    bloc_contexte = ""
    if contexte_projet:
        bloc_contexte = f"""
Modules Python DÉJÀ migrés dans ce projet. Si tu as besoin d'une de
ces fonctions/classes, importe-la avec EXACTEMENT le nom listé
ci-dessous (from <module> import <nom_exact>). N'invente JAMAIS un
nom absent de cette liste (par ex. n'importe pas le nom d'une classe
PHP si elle a été refactorée en fonctions) :
{contexte_projet}
"""

    # Bloc feedback correctif
    bloc_feedback = ""
    if feedback and feedback.get("instructions"):
        instructions = "\n".join(feedback["instructions"])
        bloc_feedback = f"""
ATTENTION — Ta version précédente contenait des erreurs.
Corrige impérativement les points suivants :
{instructions}
"""

    # Bloc points d'attention + contraintes de révision (Architecte)
    bloc_architecte = ""
    points = module_info.get("points_attention") or []
    contraintes = module_info.get("contraintes_revision") or []
    if points:
        bloc_architecte += ("\nPOINTS D'ATTENTION signalés par l'Architecte "
                            "(traite-les explicitement) :\n"
                            + "\n".join(f"- {p}" for p in points) + "\n")
    if contraintes:
        bloc_architecte += ("\nPLAN RÉVISÉ — les corrections précédentes n'ont "
                            "pas suffi. Contraintes de conception OBLIGATOIRES :\n"
                            + "\n".join(f"- {c}" for c in contraintes) + "\n")

    # Consigne structurelle (fonction / classe Python / refactoring)
    if module_info.get("type") == "classe":
        methodes = ", ".join(module_info.get("methodes_python", []))
        parent = module_info.get("classe_parente", "")
        if module_info.get("cible_migration") == "classe_python":
            if parent:
                consigne_structure = (
                    f"Génère une CLASSE Python nommée EXACTEMENT "
                    f"{module_info.get('nom_python', '')} qui HÉRITE de la "
                    f"classe {parent} (syntaxe : class "
                    f"{module_info.get('nom_python', '')}({parent}):). "
                    f"Importe {parent} depuis son module SEULEMENT s'il "
                    f"apparaît dans le contexte projet ci-dessus. Si {parent} "
                    f"n'y figure pas, c'est qu'elle est définie dans CE MÊME "
                    f"fichier : dans ce cas n'écris AUCUN import pour {parent} "
                    f"(ne mets jamais 'from votre_module' ni de nom de module "
                    f"inventé). Méthodes : {methodes} (snake_case). "
                    f"Appelle super().__init__() dans __init__. Chaque nom "
                    f"défini UNE SEULE FOIS."
                )
            else:
                consigne_structure = (
                    f"Génère une CLASSE Python nommée EXACTEMENT "
                    f"{module_info.get('nom_python', '')} avec les méthodes "
                    f"{methodes} (snake_case). Conserve l'état (les propriétés "
                    f"deviennent des attributs d'instance initialisés dans "
                    f"__init__). Chaque nom défini UNE SEULE FOIS."
                )
        else:
            consigne_structure = (
                f"REFACTORE cette classe sans état en FONCTIONS de module "
                f"(programmation fonctionnelle) : une fonction par méthode, "
                f"nommées EXACTEMENT {methodes}, au niveau du module, PAS de "
                f"classe. Chaque nom défini UNE SEULE FOIS."
            )
    else:
        consigne_structure = (
            f"La fonction principale doit s'appeler EXACTEMENT : "
            f"{module_info.get('nom_python', 'fonction')} (au niveau du "
            f"module, PAS dans une classe, définie UNE SEULE FOIS — jamais "
            f"deux versions de la même fonction)."
        )

    prompt = f"""Tu es un expert en migration de code PHP vers Python moderne avec FastAPI.

Code PHP à convertir :
```php
{code_php}
```

Exemples similaires de migration réussie :
{exemples_text}
{bloc_contexte}
Invariants de sécurité à préserver obligatoirement :
{invariants_text}

Failles à corriger dans le code Python généré :
{failles_text}
{bloc_validation}{bloc_architecte}{bloc_feedback}
CONTRAINTES STRICTES (le code sera assemblé dans un projet plus large) :
1. {consigne_structure}
2. Ne génère PAS de `app = FastAPI()`, PAS de création de moteur/tables SQLAlchemy globales, PAS de code d'exemple : UNIQUEMENT le code demandé et les modèles Pydantic strictement nécessaires.
3. Si des modules du projet sont listés ci-dessus, importe leurs fonctions au lieu de les redéfinir.
4. Utilise les annotations de types Python, la gestion d'erreurs avec HTTPException, et l'ORM SQLAlchemy pour tout accès base de données (jamais de SQL concaténé).
5. Pour tout modèle Pydantic (BaseModel), chaque champ Optional DOIT avoir une valeur par défaut (ex: `nom: Optional[str] = None`), sinon l'instanciation et l'héritage échouent.
6. NE SUR-INTERPRÈTE PAS les paramètres : un paramètre PHP simple ($session, $data, $id...) doit rester un type Python simple (str, int...) SAUF si le code PHP montre clairement un accès objet ($x->prop) ou un accès BDD. Par exemple `if (empty($session))` se traduit `if not session:` (pas `if not session.id:`). N'invente pas d'attributs (.id, .value) qui n'existent pas dans le code PHP d'origine.
7. Termine le code par des lignes de commentaire EN FRANÇAIS qui explicitent ce qui serait sinon resté implicite, une information par ligne :
   # SMAML-HYPOTHESE: <hypothèse faite pendant la traduction>
   # SMAML-INCERTAIN: <point dont tu n'es pas sûr>
   # SMAML-ATTENTION: <point que les vérificateurs ne doivent pas manquer>
   Écris au moins une ligne SMAML-HYPOTHESE. S'il n'y a rien d'incertain, n'écris pas de ligne SMAML-INCERTAIN.
   Ces trois lignes sont rédigées en français, comme le reste de tes commentaires.
Réponds UNIQUEMENT avec le code Python."""

    # Étape 3 — Appel LLM
    # Cache : une génération identique (même prompt, même modèle) est
    # relue au lieu d'être redemandée au LLM. C'est l'étape la plus
    # coûteuse du pipeline, et la boucle de correction la répète.
    cache_gen = cache_smaml.lire(
        "generation", cache_smaml.empreinte("generation",
                                            [prompt, GROQ_MODEL]))
    if cache_gen:
        print(f"\n  Code Python réutilisé depuis le cache "
              f"(génération identique déjà faite)")
        return cache_gen

    print(f"\n  Génération du code Python via {GROQ_MODEL} (Groq)...")
    try:
        code_python = appeler_llm(prompt, GROQ_TOKEN)
        if not code_python or len(code_python.strip()) < 10:
            raise Exception("Réponse vide du modèle")
        cache_smaml.ecrire(
            "generation",
            cache_smaml.empreinte("generation", [prompt, GROQ_MODEL]),
            code_python)
    except Exception as e:
        print(f"  LLM non disponible : {type(e).__name__} - {str(e)[:150]}")
        # Mode STRICT (activé par le benchmark) : un basculement sur le
        # code de secours fausserait toute la mesure — mieux vaut arrêter
        # le run que produire des résultats contaminés.
        if os.getenv("SMAML_STRICT"):
            raise RuntimeError(
                f"[MODE STRICT] LLM indisponible ({type(e).__name__}) — "
                f"run interrompu pour ne pas contaminer les mesures avec "
                f"du code de secours. Relance quand le quota/réseau est "
                f"rétabli."
            ) from e
        print(f"  Mode démonstration — code Python généré localement")
        code_python = generer_code_fallback(module_info, invariants, failles)

    return code_python


def generer_code_fallback(module_info: dict, invariants: list,
                          failles: list) -> str:
    """Squelette Python de secours quand le LLM est indisponible."""
    nom = module_info.get("nom_python", "fonction")
    params = module_info.get("parametres", [])
    params_python = [f"{p.replace('$', '').strip()}: str" for p in params]
    params_str = ", ".join(params_python)
    if params_str:
        params_str += ", db: Session = Depends(get_db)"
    else:
        params_str = "db: Session = Depends(get_db)"

    return f"""from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/{nom.replace('_', '-')}")
def {nom}({params_str}):
    \"\"\"
    Migré depuis PHP : {module_info.get('nom_original', '')}
    Invariants préservés : {len(invariants)} | Failles corrigées : {len(failles)}
    \"\"\"
    try:
        return {{"status": "success", "message": "Opération réussie"}}
    except Exception as e:
        logger.error(f"Erreur dans {nom}: {{str(e)}}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")
"""


def nettoyer_code(code_python: str) -> str:
    """Enlève les balises markdown et les métadonnées SMAML du code."""
    code = code_python
    if "```python" in code:
        code = code.split("```python")[1]
    elif "```" in code:
        code = code.split("```")[1]
    if "```" in code:
        code = code.split("```")[0]
    code = "\n".join(l for l in code.split("\n")
                     if not _LIGNE_META.match(l))
    return code.strip()


# ═══ DÉPÔT EXPLICITE DU DÉVELOPPEUR ═══════════════════
# Le Développeur ne dépose pas seulement du code : il déclare aussi
# ses dépendances, les hypothèses qu'il a faites et ce dont il n'est
# pas sûr. Les hypothèses et incertitudes viennent du LLM (lignes
# SMAML-*), les dépendances sont extraites du code lui-même.
import re as _re_meta
_LIGNE_META = _re_meta.compile(
    r"^\s*#\s*SMAML-(HYPOTHESE|INCERTAIN|ATTENTION)\s*:\s*(.*)$")


def extraire_metadonnees(code_python: str) -> dict:
    """Lit les lignes SMAML-* laissées par le LLM à la fin du code."""
    meta = {"hypotheses_faites": [], "points_incertains": [],
            "points_attention": []}
    cle = {"HYPOTHESE": "hypotheses_faites",
           "INCERTAIN": "points_incertains",
           "ATTENTION": "points_attention"}
    for ligne in (code_python or "").split("\n"):
        m = _LIGNE_META.match(ligne)
        if m and m.group(2).strip():
            meta[cle[m.group(1)]].append(m.group(2).strip())
    return meta


def extraire_dependances(code_python: str) -> list:
    """Modules importés par le code (AST, ou regex si code invalide)."""
    import ast
    modules = []
    try:
        for noeud in ast.walk(ast.parse(code_python)):
            if isinstance(noeud, ast.Import):
                modules += [a.name for a in noeud.names]
            elif isinstance(noeud, ast.ImportFrom) and noeud.module:
                modules.append(noeud.module)
    except SyntaxError:
        modules = _re_meta.findall(
            r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))",
            code_python, _re_meta.MULTILINE)
        modules = [a or b for a, b in modules]
    vus = []
    for m in modules:
        if m not in vus:
            vus.append(m)
    return vus


def extraire_code_classe(code_complet: str, nom_classe: str) -> str:
    """Extrait le code d'une CLASSE PHP complète (comptage d'accolades)."""
    lignes = code_complet.split('\n')
    debut = -1
    fin = -1
    accolades = 0
    dans_classe = False
    for i, ligne in enumerate(lignes):
        if f"class {nom_classe}" in ligne:
            debut = i
            dans_classe = True
        if dans_classe:
            accolades += ligne.count('{')
            accolades -= ligne.count('}')
            if accolades == 0 and debut != -1 and i > debut:
                fin = i
                break
    if debut >= 0 and fin >= 0:
        return '\n'.join(lignes[debut:fin+1])
    return f"class {nom_classe} {{ }}"


def extraire_code_module(code_complet: str, nom_fonction: str) -> str:
    """Extrait le code d'une fonction PHP (comptage d'accolades)."""
    lignes = code_complet.split('\n')
    debut = -1
    fin = -1
    accolades = 0
    dans_fonction = False
    for i, ligne in enumerate(lignes):
        if f"function {nom_fonction}" in ligne:
            debut = i
            dans_fonction = True
        if dans_fonction:
            accolades += ligne.count('{')
            accolades -= ligne.count('}')
            if accolades == 0 and debut != -1 and i > debut:
                fin = i
                break
    if debut >= 0 and fin >= 0:
        return '\n'.join(lignes[debut:fin+1])
    return f"function {nom_fonction}() {{ }}"


# ─── AGENT DÉVELOPPEUR PRINCIPAL ─────────────────────
def agent_developpeur(rapport_analyste: dict, plan_architecte: dict,
                      code_php_source: str, contexte_projet: str = "") -> dict:
    """Agent Développeur : migre le VRAI code PHP reçu en paramètre."""
    resultat = {
        "modules_generes": [],
        "statistiques": {"total_modules": 0, "modules_reussis": 0,
                         "exemples_rag_utilises": 0}
    }
    modules = plan_architecte.get("modules", [])
    invariants = plan_architecte.get("invariants_a_preserver", [])
    failles = plan_architecte.get("priorites_securite", [])

    print("\n" + "=" * 60)
    print("Agent Développeur SMAML — Génération en cours...")
    print("=" * 60)

    for module in modules:
        print(f"\nModule : {module['nom_original']} → {module['nom_python']}")
        if module.get("type") == "classe":
            code_php_module = extraire_code_classe(
                code_php_source, module["nom_original"])
        else:
            code_php_module = extraire_code_module(
                code_php_source, module["nom_original"])
        code_python = generer_code_python(
            code_php_module, module, invariants, failles,
            contexte_projet=contexte_projet)
        resultat["modules_generes"].append({
            "nom_original": module["nom_original"],
            "nom_python": module["nom_python"],
            "code_python": code_python,
            "exemples_rag": 3, "statut": "généré"
        })
        resultat["statistiques"]["modules_reussis"] += 1
        resultat["statistiques"]["exemples_rag_utilises"] += 3

    resultat["statistiques"]["total_modules"] = len(modules)
    return resultat