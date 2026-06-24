import json

paires_erreurs = [
    {
        "id": 1,
        "code_php": """<?php
function getUser($id) {
    try {
        $result = mysql_query("SELECT * FROM users WHERE id=$id");
        return mysql_fetch_array($result);
    } catch (Exception $e) {
        echo "Error: " . $e->getMessage();
        echo "Query: SELECT * FROM users WHERE id=$id";
    }
}""",
        "code_python": """def get_user(id: int, db: Session):
    try:
        return db.query(User).filter(User.id == id).first()
    except Exception as e:
        logger.error(f"Database error for user {id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )""",
        "description": "Récupérer utilisateur avec gestion d'erreur",
        "categorie": "gestion_erreurs",
        "type_erreur": "information_leakage",
        "type_transformation": "security_fix",
        "faille": "error_disclosure",
        "cwe": "CWE-209",
        "severity": "medium",
        "invariant": [
            "message d'erreur interne jamais exposé à l'utilisateur",
            "erreur loggée côté serveur uniquement"
        ],
        "source": "manuel_erreurs"
    },
    {
        "id": 2,
        "code_php": """<?php
function connectDB() {
    $conn = mysql_connect('localhost', 'root', 'password');
    if (!$conn) {
        die("Connection failed: " . mysql_error());
    }
    return $conn;
}""",
        "code_python": """import logging
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

def connect_db():
    try:
        engine = create_engine(
            "mysql://root:password@localhost/db"
        )
        engine.connect()
        return engine
    except SQLAlchemyError as e:
        logger.critical("Database connection failed")
        raise RuntimeError("Service unavailable")""",
        "description": "Connexion BDD avec gestion erreur propre",
        "categorie": "gestion_erreurs",
        "type_erreur": "information_leakage",
        "type_transformation": "security_fix",
        "faille": "error_disclosure",
        "cwe": "CWE-209",
        "severity": "medium",
        "invariant": [
            "détails de connexion jamais exposés",
            "erreur critique loggée"
        ],
        "source": "manuel_erreurs"
    },
    {
        "id": 3,
        "code_php": """<?php
function divideNumbers($a, $b) {
    return $a / $b;
}""",
        "code_python": """def divide_numbers(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Division par zéro impossible")
    return a / b""",
        "description": "Division avec gestion de l'erreur division par zéro",
        "categorie": "gestion_erreurs",
        "type_erreur": "missing_error_handling",
        "type_transformation": "quality_fix",
        "faille": None,
        "cwe": None,
        "severity": "low",
        "invariant": [
            "b != 0 avant division",
            "exception explicite si b == 0"
        ],
        "source": "manuel_erreurs"
    },
    {
        "id": 4,
        "code_php": """<?php
function readConfig($file) {
    $content = file_get_contents($file);
    if ($content === false) {
        die("Error reading file: " . $file);
    }
    return json_decode($content, true);
}""",
        "code_python": """import json
import logging

logger = logging.getLogger(__name__)

def read_config(file: str) -> dict:
    try:
        with open(file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Config file not found: {file}")
        raise RuntimeError("Configuration unavailable")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config: {str(e)}")
        raise ValueError("Invalid configuration format")""",
        "description": "Lire un fichier de configuration",
        "categorie": "gestion_erreurs",
        "type_erreur": "poor_error_handling",
        "type_transformation": "quality_fix",
        "faille": "error_disclosure",
        "cwe": "CWE-209",
        "severity": "medium",
        "invariant": [
            "chemin du fichier jamais exposé à l'utilisateur",
            "erreurs typées et loggées"
        ],
        "source": "manuel_erreurs"
    },
    {
        "id": 5,
        "code_php": """<?php
function processPayment($amount, $cardNumber) {
    if ($amount <= 0) {
        throw new Exception("Invalid amount: $amount");
    }
    return chargeCard($cardNumber, $amount);
}""",
        "code_python": """import logging

logger = logging.getLogger(__name__)

def process_payment(amount: float, card_number: str) -> bool:
    if amount <= 0:
        raise ValueError("Le montant doit être positif")
    try:
        return charge_card(card_number, amount)
    except PaymentError as e:
        logger.error(
            f"Payment failed for amount {amount}",
            extra={"error_code": e.code}
        )
        raise HTTPException(
            status_code=402,
            detail="Paiement refusé"
        )""",
        "description": "Traitement paiement avec gestion erreur sécurisée",
        "categorie": "gestion_erreurs",
        "type_erreur": "information_leakage",
        "type_transformation": "security_fix",
        "faille": "error_disclosure",
        "cwe": "CWE-209",
        "severity": "high",
        "invariant": [
            "numéro de carte jamais dans les logs",
            "montant validé avant traitement",
            "message d'erreur générique pour l'utilisateur"
        ],
        "source": "manuel_erreurs"
    },
    {
        "id": 6,
        "code_php": """<?php
function parseUserInput($data) {
    $decoded = json_decode($data);
    echo $decoded->username;
}""",
        "code_python": """import json
import logging
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

class UserInput(BaseModel):
    username: str

def parse_user_input(data: str) -> UserInput:
    try:
        parsed = json.loads(data)
        return UserInput(**parsed)
    except json.JSONDecodeError:
        raise ValueError("Format JSON invalide")
    except ValidationError as e:
        raise ValueError("Données utilisateur invalides")""",
        "description": "Parser une entrée JSON utilisateur",
        "categorie": "gestion_erreurs",
        "type_erreur": "missing_error_handling",
        "type_transformation": "quality_fix",
        "faille": None,
        "cwe": None,
        "severity": "medium",
        "invariant": [
            "JSON validé avant utilisation",
            "structure validée par Pydantic"
        ],
        "source": "manuel_erreurs"
    },
    {
        "id": 7,
        "code_php": """<?php
function sendRequest($url) {
    $response = file_get_contents($url);
    return json_decode($response, true);
}""",
        "code_python": """import httpx
import logging

logger = logging.getLogger(__name__)

async def send_request(url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        logger.warning(f"Request timeout for URL")
        raise TimeoutError("Service non disponible")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e.response.status_code}")
        raise RuntimeError("Erreur service externe")""",
        "description": "Requête HTTP avec gestion d'erreurs complète",
        "categorie": "gestion_erreurs",
        "type_erreur": "missing_error_handling",
        "type_transformation": "quality_fix",
        "faille": None,
        "cwe": None,
        "severity": "low",
        "invariant": [
            "timeout configuré",
            "status HTTP vérifié",
            "URL jamais loggée"
        ],
        "source": "manuel_erreurs"
    },
    {
        "id": 8,
        "code_php": """<?php
function deleteUser($userId) {
    $sql = "DELETE FROM users WHERE id=" . $userId;
    mysql_query($sql);
    echo "User $userId deleted successfully";
}""",
        "code_python": """import logging

logger = logging.getLogger(__name__)

def delete_user(user_id: int, db: Session) -> dict:
    user = db.query(User).filter(
        User.id == user_id
    ).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Utilisateur non trouvé"
        )
    db.delete(user)
    db.commit()
    logger.info(f"User deleted successfully")
    return {"message": "Utilisateur supprimé"}""",
        "description": "Supprimer utilisateur avec gestion erreur",
        "categorie": "gestion_erreurs",
        "type_erreur": "missing_validation",
        "type_transformation": "security_fix",
        "faille": "sql_injection",
        "cwe": "CWE-89",
        "severity": "critical",
        "invariant": [
            "utilisateur vérifié avant suppression",
            "ID utilisateur jamais dans message public",
            "action loggée sans données sensibles"
        ],
        "source": "manuel_erreurs"
    },
    {
        "id": 9,
        "code_php": """<?php
function validateAndSave($data) {
    if (empty($data['name'])) {
        return false;
    }
    saveToDatabase($data);
    return true;
}""",
        "code_python": """import logging
from pydantic import BaseModel, validator

logger = logging.getLogger(__name__)

class DataModel(BaseModel):
    name: str

    @validator('name')
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Le nom ne peut pas être vide')
        return v.strip()

def validate_and_save(data: dict, db: Session) -> bool:
    try:
        validated = DataModel(**data)
        save_to_database(validated, db)
        return True
    except ValueError as e:
        logger.warning(f"Validation failed: {str(e)}")
        raise HTTPException(
            status_code=422,
            detail=str(e)
        )""",
        "description": "Valider et sauvegarder des données",
        "categorie": "gestion_erreurs",
        "type_erreur": "poor_error_handling",
        "type_transformation": "quality_fix",
        "faille": None,
        "cwe": None,
        "severity": "low",
        "invariant": [
            "validation explicite avant sauvegarde",
            "erreur de validation retournée avec détail"
        ],
        "source": "manuel_erreurs"
    },
    {
        "id": 10,
        "code_php": """<?php
function importCSV($filename) {
    $file = fopen($filename, 'r');
    while ($row = fgetcsv($file)) {
        insertRow($row);
    }
    fclose($file);
}""",
        "code_python": """import csv
import logging

logger = logging.getLogger(__name__)

def import_csv(filename: str, db: Session) -> dict:
    imported = 0
    errors = 0
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    insert_row(row, db)
                    imported += 1
                except Exception as e:
                    logger.warning(f"Row skipped: {str(e)}")
                    errors += 1
        db.commit()
        return {"imported": imported, "errors": errors}
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Fichier non trouvé"
        )""",
        "description": "Import CSV avec gestion d'erreurs par ligne",
        "categorie": "gestion_erreurs",
        "type_erreur": "missing_error_handling",
        "type_transformation": "quality_fix",
        "faille": None,
        "cwe": None,
        "severity": "low",
        "invariant": [
            "erreurs par ligne isolées",
            "rapport import/erreurs retourné",
            "transaction committée uniquement si succès global"
        ],
        "source": "manuel_erreurs"
    }
]

with open("paires_erreurs.json", "w", encoding="utf-8") as f:
    json.dump(paires_erreurs, f, ensure_ascii=False, indent=2)

print(f"Gestion erreurs : {len(paires_erreurs)} paires créées")
types = {}
for p in paires_erreurs:
    t = p["type_erreur"]
    types[t] = types.get(t, 0) + 1
print("\nPar type d'erreur :")
for t, n in types.items():
    print(f"  {t} : {n}")
print("\nFichier : paires_erreurs.json")