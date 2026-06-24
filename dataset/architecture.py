import json

paires_architecture = [
    {
        "id": 1,
        "code_php": """<?php
// Fichier unique : index.php — tout en un
$conn = mysql_connect('localhost', 'root', 'pass');
mysql_select_db('shop', $conn);

if ($_GET['action'] == 'getProducts') {
    $result = mysql_query("SELECT * FROM products");
    while($row = mysql_fetch_array($result)) {
        echo json_encode($row);
    }
}

if ($_GET['action'] == 'getUser') {
    $id = $_GET['id'];
    $result = mysql_query(
        "SELECT * FROM users WHERE id=$id"
    );
    echo json_encode(mysql_fetch_array($result));
}""",
        "code_python": """# main.py — Architecture FastAPI modulaire
from fastapi import FastAPI
from routers import products, users

app = FastAPI(title="Shop API")
app.include_router(products.router, prefix="/products")
app.include_router(users.router, prefix="/users")

# routers/products.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter()

@router.get("/")
def get_products(db: Session = Depends(get_db)):
    return db.query(Product).all()

# routers/users.py
@router.get("/{user_id}")
def get_user(user_id: int,
             db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.id == user_id
    ).first()
    if not user:
        raise HTTPException(status_code=404)
    return user""",
        "description": "Migration monolithe PHP vers FastAPI modulaire",
        "categorie": "architecture_moderne",
        "pattern_source": "monolithic",
        "pattern_cible": "modular_fastapi",
        "type_transformation": "architecture_migration",
        "faille": "sql_injection",
        "cwe": "CWE-89",
        "severity": "critical",
        "invariant": [
            "endpoints fonctionnellement identiques",
            "séparation des responsabilités"
        ],
        "source": "manuel_architecture"
    },
    {
        "id": 2,
        "code_php": """<?php
class UserService {
    private $db;

    public function __construct() {
        $this->db = new Database();
    }

    public function getUser($id) {
        return $this->db->query(
            "SELECT * FROM users WHERE id=$id"
        );
    }

    public function saveUser($user) {
        $this->db->query(
            "INSERT INTO users VALUES (...)"
        );
        $this->sendWelcomeEmail($user['email']);
        $this->logActivity($user['id']);
    }

    private function sendWelcomeEmail($email) { }
    private function logActivity($userId) { }
}""",
        "code_python": """# Pattern Repository + Service Layer
from abc import ABC, abstractmethod

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_id(self, user_id: int) -> User:
        return self.db.query(User).filter(
            User.id == user_id
        ).first()

    def save(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        return user

class EmailService:
    async def send_welcome(self, email: str):
        pass

class ActivityLogger:
    def log(self, user_id: int, action: str):
        pass

class UserService:
    def __init__(self, repo: UserRepository,
                 email: EmailService,
                 logger: ActivityLogger):
        self.repo = repo
        self.email = email
        self.logger = logger

    def get_user(self, user_id: int) -> User:
        return self.repo.find_by_id(user_id)

    async def create_user(self, user: User) -> User:
        saved = self.repo.save(user)
        await self.email.send_welcome(user.email)
        self.logger.log(user.id, "created")
        return saved""",
        "description": "Migration vers pattern Repository + Service Layer",
        "categorie": "architecture_moderne",
        "pattern_source": "god_class",
        "pattern_cible": "repository_service",
        "type_transformation": "architecture_migration",
        "faille": None,
        "cwe": None,
        "severity": "low",
        "invariant": [
            "séparation données/logique/services",
            "injection de dépendances",
            "comportement fonctionnel identique"
        ],
        "source": "manuel_architecture"
    },
    {
        "id": 3,
        "code_php": """<?php
// Traitement synchrone bloquant
function processLargeFile($filename) {
    $lines = file($filename);
    $results = array();
    foreach($lines as $line) {
        $result = processLine($line);
        $results[] = $result;
        sleep(1); // simulate heavy processing
    }
    return $results;
}""",
        "code_python": """import asyncio
from typing import List

async def process_line_async(line: str) -> dict:
    await asyncio.sleep(1)
    return {"line": line.strip(), "processed": True}

async def process_large_file(
    filename: str
) -> List[dict]:
    with open(filename, 'r') as f:
        lines = f.readlines()

    tasks = [
        process_line_async(line)
        for line in lines
    ]
    results = await asyncio.gather(*tasks)
    return list(results)""",
        "description": "Migration traitement synchrone vers async/await",
        "categorie": "architecture_moderne",
        "pattern_source": "synchronous_blocking",
        "pattern_cible": "async_concurrent",
        "type_transformation": "architecture_migration",
        "faille": None,
        "cwe": None,
        "severity": "low",
        "invariant": [
            "tous les résultats retournés",
            "ordre des résultats préservé"
        ],
        "source": "manuel_architecture"
    },
    {
        "id": 4,
        "code_php": """<?php
// Configuration hardcodée partout dans le code
define('DB_HOST', 'localhost');
define('DB_NAME', 'myapp');
define('API_KEY', 'abc123');
define('MAX_UPLOAD_SIZE', 5242880);
define('SESSION_LIFETIME', 3600);

function getConfig($key) {
    $configs = array(
        'db_host' => DB_HOST,
        'api_key' => API_KEY
    );
    return $configs[$key];
}""",
        "code_python": """from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    db_host: str
    db_name: str
    api_key: str
    max_upload_size: int = 5242880
    session_lifetime: int = 3600

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()""",
        "description": "Migration configuration hardcodée vers pydantic-settings",
        "categorie": "architecture_moderne",
        "pattern_source": "hardcoded_config",
        "pattern_cible": "env_based_config",
        "type_transformation": "architecture_migration",
        "faille": "hardcoded_secret",
        "cwe": "CWE-798",
        "severity": "high",
        "invariant": [
            "toutes les configs accessibles",
            "secrets dans variables d'environnement",
            "valeurs par défaut préservées"
        ],
        "source": "manuel_architecture"
    },
    {
        "id": 5,
        "code_php": """<?php
// Session PHP classique
session_start();

function login($username, $password) {
    $user = authenticateUser($username, $password);
    if ($user) {
        $_SESSION['user_id'] = $user['id'];
        $_SESSION['role'] = $user['role'];
        $_SESSION['logged_in'] = true;
        return true;
    }
    return false;
}

function isLoggedIn() {
    return isset($_SESSION['logged_in'])
           && $_SESSION['logged_in'];
}

function getUserRole() {
    return $_SESSION['role'] ?? null;
}""",
        "code_python": """from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta

SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token"
)

def create_access_token(user_id: int,
                        role: str) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, SECRET_KEY,
                      algorithm=ALGORITHM)

def get_current_user(
    token: str = Depends(oauth2_scheme)
) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY,
                            algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Token invalide"
        )""",
        "description": "Migration sessions PHP vers JWT FastAPI",
        "categorie": "architecture_moderne",
        "pattern_source": "php_sessions",
        "pattern_cible": "jwt_oauth2",
        "type_transformation": "architecture_migration",
        "faille": "insecure_session",
        "cwe": "CWE-384",
        "severity": "high",
        "invariant": [
            "authentification préservée",
            "rôle utilisateur accessible",
            "expiration de session maintenue"
        ],
        "source": "manuel_architecture"
    }
]

with open("paires_architecture.json", "w",
          encoding="utf-8") as f:
    json.dump(paires_architecture, f,
              ensure_ascii=False, indent=2)

print(f"Architecture : {len(paires_architecture)} paires créées")
patterns = {}
for p in paires_architecture:
    pt = p["pattern_cible"]
    patterns[pt] = patterns.get(pt, 0) + 1
print("\nPar pattern cible :")
for pt, n in patterns.items():
    print(f"  {pt} : {n}")
print("\nFichier : paires_architecture.json")