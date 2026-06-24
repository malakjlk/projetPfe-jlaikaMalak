import json

paires_failles = [
    # ═══════════════════════════════════════
    # CWE-89 — SQL Injection (4 variantes)
    # ═══════════════════════════════════════
    {
        "id": 1,
        "code_php": """<?php
function getUser($id) {
    $sql = "SELECT * FROM users WHERE id = " . $id;
    $result = mysql_query($sql);
    return mysql_fetch_array($result);
}""",
        "code_python": """def get_user(id: int, db: Session):
    return db.query(User).filter(User.id == id).first()""",
        "description": "Récupérer un utilisateur par ID",
        "categorie": "base_de_donnees",
        "faille": "sql_injection",
        "cwe": "CWE-89",
        "severity": "critical",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "Utiliser ORM au lieu de requête dynamique"
    },
    {
        "id": 2,
        "code_php": """<?php
function loginUser($username, $password) {
    $sql = "SELECT * FROM users WHERE username='"
           . $username . "' AND password='" . $password . "'";
    return mysql_query($sql);
}""",
        "code_python": """def login_user(username: str, password: str,
               db: Session):
    user = db.query(User).filter(
        User.username == username
    ).first()
    if user and verify_password(password, user.password):
        return user
    return None""",
        "description": "Authentification utilisateur",
        "categorie": "authentification",
        "faille": "sql_injection",
        "cwe": "CWE-89",
        "severity": "critical",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "ORM + vérification hash mot de passe"
    },
    {
        "id": 3,
        "code_php": """<?php
function searchProducts($keyword) {
    $sql = "SELECT * FROM products WHERE name LIKE '%" 
           . $keyword . "%'";
    return mysql_query($sql);
}""",
        "code_python": """def search_products(keyword: str, db: Session):
    return db.query(Product).filter(
        Product.name.like(f"%{keyword}%")
    ).all()""",
        "description": "Rechercher des produits par mot-clé",
        "categorie": "base_de_donnees",
        "faille": "sql_injection",
        "cwe": "CWE-89",
        "severity": "critical",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "Utiliser ORM avec paramètres préparés"
    },
    {
        "id": 4,
        "code_php": """<?php
function deleteRecord($table, $id) {
    $sql = "DELETE FROM " . $table . " WHERE id=" . $id;
    mysql_query($sql);
}""",
        "code_python": """def delete_record(model, id: int, db: Session):
    record = db.query(model).filter(
        model.id == id
    ).first()
    if record:
        db.delete(record)
        db.commit()""",
        "description": "Supprimer un enregistrement",
        "categorie": "base_de_donnees",
        "faille": "sql_injection",
        "cwe": "CWE-89",
        "severity": "critical",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "ORM avec modèle typé, pas de nom de table dynamique"
    },

    # ═══════════════════════════════════════
    # CWE-79 — XSS (3 variantes)
    # ═══════════════════════════════════════
    {
        "id": 5,
        "code_php": """<?php
function showUserInput($input) {
    echo "<div>" . $input . "</div>";
}""",
        "code_python": """from markupsafe import escape

def show_user_input(input: str) -> str:
    return f"<div>{escape(input)}</div>" """,
        "description": "Afficher une entrée utilisateur",
        "categorie": "affichage",
        "faille": "xss",
        "cwe": "CWE-79",
        "severity": "high",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "Échapper les caractères spéciaux HTML"
    },
    {
        "id": 6,
        "code_php": """<?php
function renderComment($comment) {
    echo "<p class='comment'>" . $comment['text'] . "</p>";
}""",
        "code_python": """from markupsafe import escape

def render_comment(comment: dict) -> str:
    safe_text = escape(comment['text'])
    return f"<p class='comment'>{safe_text}</p>" """,
        "description": "Afficher un commentaire utilisateur",
        "categorie": "affichage",
        "faille": "xss",
        "cwe": "CWE-79",
        "severity": "high",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "Échapper le contenu avant insertion dans HTML"
    },
    {
        "id": 7,
        "code_php": """<?php
function showError($message) {
    echo "<div class='error'>" . $_GET['msg'] . "</div>";
}""",
        "code_python": """from markupsafe import escape
from fastapi import Request

def show_error(request: Request) -> str:
    msg = request.query_params.get('msg', '')
    return f"<div class='error'>{escape(msg)}</div>" """,
        "description": "Afficher un message d'erreur depuis l'URL",
        "categorie": "affichage",
        "faille": "xss",
        "cwe": "CWE-79",
        "severity": "high",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "Ne jamais injecter $_GET directement dans HTML"
    },

    # ═══════════════════════════════════════
    # CWE-798 — Hardcoded Secret (2 variantes)
    # ═══════════════════════════════════════
    {
        "id": 8,
        "code_php": """<?php
define('DB_PASSWORD', 'admin123');
function connectDB() {
    return mysql_connect('localhost', 'root', DB_PASSWORD);
}""",
        "code_python": """import os
from sqlalchemy import create_engine

def connect_db():
    password = os.environ.get('DB_PASSWORD')
    engine = create_engine(
        f"mysql://root:{password}@localhost/db"
    )
    return engine""",
        "description": "Connexion à la base de données",
        "categorie": "configuration",
        "faille": "hardcoded_secret",
        "cwe": "CWE-798",
        "severity": "high",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "Utiliser variables d'environnement"
    },
    {
        "id": 9,
        "code_php": """<?php
function sendEmail($to, $subject, $body) {
    $apiKey = 'sk-live-abc123xyz789';
    $ch = curl_init('https://api.mailservice.com/send');
    curl_setopt($ch, CURLOPT_HTTPHEADER, 
                ['Authorization: Bearer ' . $apiKey]);
}""",
        "code_python": """import os
import httpx

async def send_email(to: str, subject: str, body: str):
    api_key = os.environ.get('MAIL_API_KEY')
    async with httpx.AsyncClient() as client:
        await client.post(
            'https://api.mailservice.com/send',
            headers={'Authorization': f'Bearer {api_key}'},
            json={'to': to, 'subject': subject, 'body': body}
        )""",
        "description": "Envoyer un email via API",
        "categorie": "communication",
        "faille": "hardcoded_secret",
        "cwe": "CWE-798",
        "severity": "high",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "Clé API dans variable d'environnement"
    },

    # ═══════════════════════════════════════
    # CWE-434 — Unrestricted Upload (2 variantes)
    # ═══════════════════════════════════════
    {
        "id": 10,
        "code_php": """<?php
function uploadFile($file) {
    $name = $file['name'];
    move_uploaded_file($file['tmp_name'],
                       'uploads/' . $name);
}""",
        "code_python": """import os
from fastapi import UploadFile
import uuid

async def upload_file(file: UploadFile):
    ext = file.filename.split('.')[-1]
    allowed = ['jpg', 'png', 'pdf']
    if ext.lower() not in allowed:
        raise ValueError('Type non autorisé')
    safe_name = str(uuid.uuid4()) + '.' + ext
    with open(f'uploads/{safe_name}', 'wb') as f:
        f.write(await file.read())""",
        "description": "Upload de fichier utilisateur",
        "categorie": "fichiers",
        "faille": "unrestricted_upload",
        "cwe": "CWE-434",
        "severity": "high",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "Valider extension + renommer fichier"
    },
    {
        "id": 11,
        "code_php": """<?php
function uploadAvatar($userId, $file) {
    $ext = pathinfo($file['name'], PATHINFO_EXTENSION);
    $path = 'avatars/' . $userId . '.' . $ext;
    move_uploaded_file($file['tmp_name'], $path);
    return $path;
}""",
        "code_python": """from fastapi import UploadFile
from PIL import Image
import uuid, os

async def upload_avatar(user_id: int, file: UploadFile):
    allowed = ['jpg', 'jpeg', 'png']
    ext = file.filename.split('.')[-1].lower()
    if ext not in allowed:
        raise ValueError('Format non autorisé')
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise ValueError('Fichier trop volumineux')
    safe_name = f"{uuid.uuid4()}.{ext}"
    path = f"avatars/{safe_name}"
    with open(path, 'wb') as f:
        f.write(content)
    return path""",
        "description": "Upload avatar utilisateur",
        "categorie": "fichiers",
        "faille": "unrestricted_upload",
        "cwe": "CWE-434",
        "severity": "high",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "Valider extension + taille + renommer"
    },

    # ═══════════════════════════════════════
    # CWE-22 — Path Traversal (2 variantes)
    # ═══════════════════════════════════════
    {
        "id": 12,
        "code_php": """<?php
function readFile($filename) {
    $content = file_get_contents('files/' . $filename);
    return $content;
}""",
        "code_python": """import os

def read_file(filename: str) -> str:
    base_dir = os.path.abspath('files')
    safe_path = os.path.abspath(
        os.path.join(base_dir, filename)
    )
    if not safe_path.startswith(base_dir):
        raise ValueError('Accès non autorisé')
    with open(safe_path, 'r') as f:
        return f.read()""",
        "description": "Lire un fichier par nom",
        "categorie": "fichiers",
        "faille": "path_traversal",
        "cwe": "CWE-22",
        "severity": "high",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "Vérifier que le chemin reste dans le répertoire autorisé"
    },
    {
        "id": 13,
        "code_php": """<?php
function downloadFile($file) {
    $path = '/var/www/downloads/' . $file;
    header('Content-Type: application/octet-stream');
    readfile($path);
}""",
        "code_python": """import os
from fastapi.responses import FileResponse

def download_file(file: str):
    base_dir = os.path.abspath('/var/www/downloads')
    safe_path = os.path.abspath(
        os.path.join(base_dir, file)
    )
    if not safe_path.startswith(base_dir):
        raise PermissionError('Accès refusé')
    if not os.path.exists(safe_path):
        raise FileNotFoundError('Fichier introuvable')
    return FileResponse(safe_path)""",
        "description": "Télécharger un fichier",
        "categorie": "fichiers",
        "faille": "path_traversal",
        "cwe": "CWE-22",
        "severity": "high",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "Vérifier chemin absolu avant accès"
    },

    # ═══════════════════════════════════════
    # CWE-78 — Command Injection (2 variantes)
    # ═══════════════════════════════════════
    {
        "id": 14,
        "code_php": """<?php
function pingHost($host) {
    $output = shell_exec('ping -c 4 ' . $host);
    return $output;
}""",
        "code_python": """import subprocess

def ping_host(host: str) -> str:
    if not host.replace('.', '').isalnum():
        raise ValueError('Hôte invalide')
    result = subprocess.run(
        ['ping', '-c', '4', host],
        capture_output=True,
        text=True,
        timeout=10
    )
    return result.stdout""",
        "description": "Ping un hôte réseau",
        "categorie": "reseau",
        "faille": "command_injection",
        "cwe": "CWE-78",
        "severity": "critical",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "Utiliser liste d'arguments au lieu de chaîne shell"
    },
    {
        "id": 15,
        "code_php": """<?php
function convertImage($filename, $format) {
    system('convert uploads/' . $filename 
           . ' output.' . $format);
}""",
        "code_python": """import subprocess
import os

def convert_image(filename: str, format: str):
    allowed_formats = ['jpg', 'png', 'gif', 'webp']
    if format.lower() not in allowed_formats:
        raise ValueError('Format non autorisé')
    safe_filename = os.path.basename(filename)
    subprocess.run(
        ['convert', f'uploads/{safe_filename}',
         f'output.{format}'],
        check=True,
        timeout=30
    )""",
        "description": "Convertir une image",
        "categorie": "fichiers",
        "faille": "command_injection",
        "cwe": "CWE-78",
        "severity": "critical",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "Valider format + utiliser liste d'arguments"
    },

    # ═══════════════════════════════════════
    # CWE-256 — Mot de passe en clair (1 variante)
    # ═══════════════════════════════════════
    {
        "id": 16,
        "code_php": """<?php
function storePassword($userId, $password) {
    $sql = "UPDATE users SET password='" 
           . $password . "' WHERE id=" . $userId;
    mysql_query($sql);
}""",
        "code_python": """import bcrypt

def store_password(user_id: int, password: str,
                   db: Session):
    hashed = bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')
    user = db.query(User).filter(
        User.id == user_id
    ).first()
    user.password = hashed
    db.commit()""",
        "description": "Stocker le mot de passe utilisateur",
        "categorie": "authentification",
        "faille": "plaintext_password",
        "cwe": "CWE-256",
        "severity": "critical",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "Hacher avec bcrypt avant stockage"
    },

    # ═══════════════════════════════════════
    # CWE-384 — Session non sécurisée (1 variante)
    # ═══════════════════════════════════════
    {
        "id": 17,
        "code_php": """<?php
function loginSuccess($userId) {
    session_start();
    $_SESSION['user_id'] = $userId;
    $_SESSION['logged_in'] = true;
}""",
        "code_python": """from fastapi import Response
import secrets
import time

def login_success(user_id: int, response: Response):
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        key='session_token',
        value=token,
        httponly=True,
        secure=True,
        samesite='strict',
        max_age=3600
    )
    return {'token': token, 'user_id': user_id}""",
        "description": "Créer une session après login",
        "categorie": "authentification",
        "faille": "insecure_session",
        "cwe": "CWE-384",
        "severity": "high",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "Token sécurisé + cookie httponly + secure"
    },

    # ═══════════════════════════════════════
    # CWE-601 — Redirection ouverte (1 variante)
    # ═══════════════════════════════════════
    {
        "id": 18,
        "code_php": """<?php
function redirect($url) {
    header('Location: ' . $_GET['redirect']);
    exit();
}""",
        "code_python": """from fastapi.responses import RedirectResponse
from urllib.parse import urlparse

def redirect(url: str):
    parsed = urlparse(url)
    allowed_hosts = ['monsite.com', 'www.monsite.com']
    if parsed.netloc and parsed.netloc not in allowed_hosts:
        raise ValueError('Redirection non autorisée')
    return RedirectResponse(url=url)""",
        "description": "Rediriger vers une URL",
        "categorie": "navigation",
        "faille": "open_redirect",
        "cwe": "CWE-601",
        "severity": "medium",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "Valider le domaine cible avant redirection"
    },

    # ═══════════════════════════════════════
    # CWE-502 — Désérialisation (1 variante)
    # ═══════════════════════════════════════
    {
        "id": 19,
        "code_php": """<?php
function loadUserData($data) {
    $user = unserialize($data);
    return $user;
}""",
        "code_python": """import json
from pydantic import BaseModel

class UserData(BaseModel):
    id: int
    name: str
    email: str

def load_user_data(data: str) -> UserData:
    parsed = json.loads(data)
    return UserData(**parsed)""",
        "description": "Charger des données utilisateur sérialisées",
        "categorie": "donnees",
        "faille": "insecure_deserialization",
        "cwe": "CWE-502",
        "severity": "critical",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "Utiliser JSON + Pydantic au lieu de unserialize"
    },

    # ═══════════════════════════════════════
    # CWE-98 — Inclusion de fichier (1 variante)
    # ═══════════════════════════════════════
    {
        "id": 20,
        "code_php": """<?php
function loadPage($page) {
    include($_GET['page'] . '.php');
}""",
        "code_python": """from fastapi import HTTPException

ALLOWED_PAGES = ['home', 'about', 'contact', 'products']

def load_page(page: str) -> str:
    if page not in ALLOWED_PAGES:
        raise HTTPException(
            status_code=404,
            detail='Page non trouvée'
        )
    with open(f'pages/{page}.html', 'r') as f:
        return f.read()""",
        "description": "Charger une page dynamiquement",
        "categorie": "navigation",
        "faille": "file_inclusion",
        "cwe": "CWE-98",
        "severity": "critical",
        "type_transformation": "security_fix",
        "invariant": [],
        "source": "manuel_securite",
        "correction": "Whitelist des pages autorisées uniquement"
    }
]

paires_invariants = [
    # ═══════════════════════════════════════
    # Invariants — Validation
    # ═══════════════════════════════════════
    {
        "id": 21,
        "code_php": """<?php
function validatePassword($password) {
    if (strlen($password) < 8) {
        throw new Exception('Trop court');
    }
    if (!preg_match('/[A-Z]/', $password)) {
        throw new Exception('Majuscule requise');
    }
    if (!preg_match('/[0-9]/', $password)) {
        throw new Exception('Chiffre requis');
    }
    return true;
}""",
        "code_python": """def validate_password(password: str) -> bool:
    if len(password) < 8:
        raise ValueError('Trop court')
    if not any(c.isupper() for c in password):
        raise ValueError('Majuscule requise')
    if not any(c.isdigit() for c in password):
        raise ValueError('Chiffre requis')
    return True""",
        "description": "Validation mot de passe",
        "categorie": "validation",
        "faille": None,
        "cwe": None,
        "severity": "medium",
        "type_transformation": "invariant_preservation",
        "invariant": [
            "len(password) >= 8",
            "any(c.isupper() for c in password)",
            "any(c.isdigit() for c in password)"
        ],
        "source": "manuel_invariant",
        "correction": None
    },
    {
        "id": 22,
        "code_php": """<?php
function validateEmail($email) {
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        throw new Exception('Email invalide');
    }
    if (strlen($email) > 255) {
        throw new Exception('Email trop long');
    }
    return true;
}""",
        "code_python": """import re

def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValueError('Email invalide')
    if len(email) > 255:
        raise ValueError('Email trop long')
    return True""",
        "description": "Validation format email",
        "categorie": "validation",
        "faille": None,
        "cwe": None,
        "severity": "medium",
        "type_transformation": "invariant_preservation",
        "invariant": [
            "re.match(pattern, email) is not None",
            "len(email) <= 255"
        ],
        "source": "manuel_invariant",
        "correction": None
    },
    {
        "id": 23,
        "code_php": """<?php
function validateAge($age) {
    if (!is_numeric($age)) {
        throw new Exception('Age invalide');
    }
    if ($age < 18 || $age > 120) {
        throw new Exception('Age hors limites');
    }
    return true;
}""",
        "code_python": """def validate_age(age: int) -> bool:
    if not isinstance(age, int):
        raise TypeError('Age invalide')
    if age < 18 or age > 120:
        raise ValueError('Age hors limites')
    return True""",
        "description": "Validation de l'âge",
        "categorie": "validation",
        "faille": None,
        "cwe": None,
        "severity": "medium",
        "type_transformation": "invariant_preservation",
        "invariant": [
            "isinstance(age, int)",
            "age >= 18",
            "age <= 120"
        ],
        "source": "manuel_invariant",
        "correction": None
    },
    {
        "id": 24,
        "code_php": """<?php
function validatePhone($phone) {
    $phone = preg_replace('/\D/', '', $phone);
    if (strlen($phone) < 10 || strlen($phone) > 15) {
        throw new Exception('Téléphone invalide');
    }
    return $phone;
}""",
        "code_python": """import re

def validate_phone(phone: str) -> str:
    cleaned = re.sub(r'\D', '', phone)
    if len(cleaned) < 10 or len(cleaned) > 15:
        raise ValueError('Téléphone invalide')
    return cleaned""",
        "description": "Validation numéro de téléphone",
        "categorie": "validation",
        "faille": None,
        "cwe": None,
        "severity": "low",
        "type_transformation": "invariant_preservation",
        "invariant": [
            "len(cleaned) >= 10",
            "len(cleaned) <= 15",
            "cleaned.isdigit()"
        ],
        "source": "manuel_invariant",
        "correction": None
    },

    # ═══════════════════════════════════════
    # Invariants — Authentification
    # ═══════════════════════════════════════
    {
        "id": 25,
        "code_php": """<?php
function checkLoginAttempts($userId) {
    $attempts = getAttempts($userId);
    if ($attempts >= 5) {
        throw new Exception('Compte bloqué');
    }
    return true;
}""",
        "code_python": """def check_login_attempts(user_id: int,
                        db: Session) -> bool:
    attempts = db.query(LoginAttempt).filter(
        LoginAttempt.user_id == user_id,
        LoginAttempt.created_at > datetime.now() 
        - timedelta(minutes=15)
    ).count()
    if attempts >= 5:
        raise PermissionError('Compte bloqué')
    return True""",
        "description": "Vérifier les tentatives de connexion",
        "categorie": "authentification",
        "faille": None,
        "cwe": None,
        "severity": "high",
        "type_transformation": "invariant_preservation",
        "invariant": [
            "attempts < 5",
            "blocage après 5 tentatives en 15 minutes"
        ],
        "source": "manuel_invariant",
        "correction": None
    },
    {
        "id": 26,
        "code_php": """<?php
function checkTokenExpiry($token) {
    $data = getTokenData($token);
    if (time() > $data['expires_at']) {
        throw new Exception('Token expiré');
    }
    return $data;
}""",
        "code_python": """from datetime import datetime

def check_token_expiry(token: str, db: Session):
    data = db.query(Token).filter(
        Token.value == token
    ).first()
    if not data:
        raise ValueError('Token invalide')
    if datetime.now() > data.expires_at:
        raise PermissionError('Token expiré')
    return data""",
        "description": "Vérifier l'expiration d'un token",
        "categorie": "authentification",
        "faille": None,
        "cwe": None,
        "severity": "high",
        "type_transformation": "invariant_preservation",
        "invariant": [
            "token existe en base",
            "datetime.now() <= data.expires_at"
        ],
        "source": "manuel_invariant",
        "correction": None
    },

    # ═══════════════════════════════════════
    # Invariants — Contrôle d'accès
    # ═══════════════════════════════════════
    {
        "id": 27,
        "code_php": """<?php
function checkUserRole($user, $requiredRole) {
    if (!isset($user['role'])) {
        throw new Exception('Rôle manquant');
    }
    if ($user['role'] !== $requiredRole) {
        throw new Exception('Accès refusé');
    }
    return true;
}""",
        "code_python": """def check_user_role(user: dict,
                   required_role: str) -> bool:
    if 'role' not in user:
        raise KeyError('Rôle manquant')
    if user['role'] != required_role:
        raise PermissionError('Accès refusé')
    return True""",
        "description": "Vérification du rôle utilisateur",
        "categorie": "controle_acces",
        "faille": None,
        "cwe": None,
        "severity": "high",
        "type_transformation": "invariant_preservation",
        "invariant": [
            "'role' in user",
            "user['role'] == required_role"
        ],
        "source": "manuel_invariant",
        "correction": None
    },
    {
        "id": 28,
        "code_php": """<?php
function canAccessResource($userId, $resourceId) {
    $resource = getResource($resourceId);
    if ($resource['owner_id'] !== $userId) {
        throw new Exception('Accès refusé');
    }
    return true;
}""",
        "code_python": """def can_access_resource(user_id: int,
                       resource_id: int,
                       db: Session) -> bool:
    resource = db.query(Resource).filter(
        Resource.id == resource_id
    ).first()
    if not resource:
        raise ValueError('Ressource introuvable')
    if resource.owner_id != user_id:
        raise PermissionError('Accès refusé')
    return True""",
        "description": "Vérifier l'accès à une ressource",
        "categorie": "controle_acces",
        "faille": None,
        "cwe": None,
        "severity": "high",
        "type_transformation": "invariant_preservation",
        "invariant": [
            "resource existe",
            "resource.owner_id == user_id"
        ],
        "source": "manuel_invariant",
        "correction": None
    },

    # ═══════════════════════════════════════
    # Invariants — Calculs financiers
    # ═══════════════════════════════════════
    {
        "id": 29,
        "code_php": """<?php
function calculateSalary($brut, $cotisations) {
    if ($brut <= 0) {
        throw new Exception('Salaire invalide');
    }
    if ($cotisations < 0 || $cotisations >= $brut) {
        throw new Exception('Cotisations invalides');
    }
    return $brut - $cotisations;
}""",
        "code_python": """def calculate_salary(brut: float,
                   cotisations: float) -> float:
    if brut <= 0:
        raise ValueError('Salaire invalide')
    if cotisations < 0 or cotisations >= brut:
        raise ValueError('Cotisations invalides')
    return brut - cotisations""",
        "description": "Calcul du salaire net",
        "categorie": "calcul_financier",
        "faille": None,
        "cwe": None,
        "severity": "medium",
        "type_transformation": "invariant_preservation",
        "invariant": [
            "brut > 0",
            "cotisations >= 0",
            "cotisations < brut",
            "result == brut - cotisations",
            "result > 0"
        ],
        "source": "manuel_invariant",
        "correction": None
    },
    {
        "id": 30,
        "code_php": """<?php
function applyDiscount($price, $discount) {
    if ($price <= 0) {
        throw new Exception('Prix invalide');
    }
    if ($discount < 0 || $discount > 100) {
        throw new Exception('Remise invalide');
    }
    return $price * (1 - $discount / 100);
}""",
        "code_python": """def apply_discount(price: float,
                  discount: float) -> float:
    if price <= 0:
        raise ValueError('Prix invalide')
    if discount < 0 or discount > 100:
        raise ValueError('Remise invalide')
    return price * (1 - discount / 100)""",
        "description": "Appliquer une remise sur un prix",
        "categorie": "calcul_financier",
        "faille": None,
        "cwe": None,
        "severity": "medium",
        "type_transformation": "invariant_preservation",
        "invariant": [
            "price > 0",
            "0 <= discount <= 100",
            "result >= 0",
            "result <= price"
        ],
        "source": "manuel_invariant",
        "correction": None
    },

    # ═══════════════════════════════════════
    # Invariants — Chiffrement
    # ═══════════════════════════════════════
    {
        "id": 31,
        "code_php": """<?php
function hashPassword($password) {
    if (strlen($password) < 8) {
        throw new Exception('Trop court');
    }
    return password_hash($password, PASSWORD_BCRYPT);
}""",
        "code_python": """import bcrypt

def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError('Trop court')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(
        password.encode('utf-8'), salt
    ).decode('utf-8')""",
        "description": "Hachage du mot de passe avec bcrypt",
        "categorie": "chiffrement",
        "faille": None,
        "cwe": None,
        "severity": "high",
        "type_transformation": "invariant_preservation",
        "invariant": [
            "len(password) >= 8",
            "algorithme == 'bcrypt'",
            "len(hash_result) > 0"
        ],
        "source": "manuel_invariant",
        "correction": None
    },

    # ═══════════════════════════════════════
    # Invariants — Validation des données
    # ═══════════════════════════════════════
    {
        "id": 32,
        "code_php": """<?php
function validateAmount($amount) {
    if (!is_numeric($amount)) {
        throw new Exception('Montant invalide');
    }
    if ($amount <= 0) {
        throw new Exception('Montant doit être positif');
    }
    if ($amount > 999999.99) {
        throw new Exception('Montant trop élevé');
    }
    return round($amount, 2);
}""",
        "code_python": """def validate_amount(amount: float) -> float:
    if not isinstance(amount, (int, float)):
        raise TypeError('Montant invalide')
    if amount <= 0:
        raise ValueError('Montant doit être positif')
    if amount > 999999.99:
        raise ValueError('Montant trop élevé')
    return round(amount, 2)""",
        "description": "Validation d'un montant financier",
        "categorie": "validation",
        "faille": None,
        "cwe": None,
        "severity": "medium",
        "type_transformation": "invariant_preservation",
        "invariant": [
            "isinstance(amount, (int, float))",
            "amount > 0",
            "amount <= 999999.99",
            "result == round(amount, 2)"
        ],
        "source": "manuel_invariant",
        "correction": None
    },
    {
        "id": 33,
        "code_php": """<?php
function validateFutureDate($date) {
    $timestamp = strtotime($date);
    if ($timestamp === false) {
        throw new Exception('Date invalide');
    }
    if ($timestamp <= time()) {
        throw new Exception('La date doit être future');
    }
    return $date;
}""",
        "code_python": """from datetime import datetime

def validate_future_date(date: str) -> str:
    try:
        parsed = datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise ValueError('Date invalide')
    if parsed <= datetime.now():
        raise ValueError('La date doit être future')
    return date""",
        "description": "Validation qu'une date est dans le futur",
        "categorie": "validation",
        "faille": None,
        "cwe": None,
        "severity": "low",
        "type_transformation": "invariant_preservation",
        "invariant": [
            "date est parseable en datetime",
            "parsed > datetime.now()"
        ],
        "source": "manuel_invariant",
        "correction": None
    },
    {
        "id": 34,
        "code_php": """<?php
function validateStringLength($str, $max) {
    if (strlen($str) === 0) {
        throw new Exception('Champ vide');
    }
    if (strlen($str) > $max) {
        throw new Exception('Trop long');
    }
    return trim($str);
}""",
        "code_python": """def validate_string_length(s: str,
                          max_len: int) -> str:
    if len(s) == 0:
        raise ValueError('Champ vide')
    if len(s) > max_len:
        raise ValueError('Trop long')
    return s.strip()""",
        "description": "Validation longueur d'une chaîne",
        "categorie": "validation",
        "faille": None,
        "cwe": None,
        "severity": "low",
        "type_transformation": "invariant_preservation",
        "invariant": [
            "len(s) > 0",
            "len(s) <= max_len",
            "result == s.strip()"
        ],
        "source": "manuel_invariant",
        "correction": None
    },
    {
        "id": 35,
        "code_php": """<?php
function validateUniqueEmail($email, $userId) {
    $sql = "SELECT id FROM users WHERE email=? AND id!=?";
    $stmt = $pdo->prepare($sql);
    $stmt->execute([$email, $userId]);
    if ($stmt->rowCount() > 0) {
        throw new Exception('Email déjà utilisé');
    }
    return true;
}""",
        "code_python": """def validate_unique_email(email: str,
                         user_id: int,
                         db: Session) -> bool:
    existing = db.query(User).filter(
        User.email == email,
        User.id != user_id
    ).first()
    if existing:
        raise ValueError('Email déjà utilisé')
    return True""",
        "description": "Vérifier unicité de l'email",
        "categorie": "validation",
        "faille": None,
        "cwe": None,
        "severity": "medium",
        "type_transformation": "invariant_preservation",
        "invariant": [
            "aucun autre utilisateur avec le même email",
            "user.id != user_id pour l'exclusion"
        ],
        "source": "manuel_invariant",
        "correction": None
    }
]

# Fusionner et sauvegarder
toutes_paires = paires_failles + paires_invariants

with open("paires_securite.json", "w",
          encoding="utf-8") as f:
    json.dump(toutes_paires, f,
              ensure_ascii=False, indent=2)

# Statistiques détaillées
print(f"Dataset sécurité créé : {len(toutes_paires)} paires")
print(f"\n--- Répartition ---")
print(f"Failles (security_fix)        : {len(paires_failles)}")
print(f"Invariants (invariant_preserv): {len(paires_invariants)}")

print(f"\n--- Par sévérité ---")
severites = {}
for p in toutes_paires:
    s = p["severity"]
    severites[s] = severites.get(s, 0) + 1
for s in ["critical", "high", "medium", "low"]:
    print(f"  {s:10} : {severites.get(s, 0)}")

print(f"\n--- Par CWE ---")
cwes = {}
for p in toutes_paires:
    c = p["cwe"] or "N/A (invariant)"
    cwes[c] = cwes.get(c, 0) + 1
for c, n in sorted(cwes.items()):
    print(f"  {c:15} : {n}")

print(f"\n--- Par catégorie ---")
cats = {}
for p in toutes_paires:
    c = p["categorie"]
    cats[c] = cats.get(c, 0) + 1
for c, n in sorted(cats.items()):
    print(f"  {c:20} : {n}")

print("\nFichier sauvegardé : paires_securite.json")