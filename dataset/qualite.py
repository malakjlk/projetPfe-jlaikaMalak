import json

paires_qualite = [
    {
        "id": 1,
        "code_php": """<?php
function processData($d) {
    $r = array();
    for($i=0;$i<count($d);$i++) {
        if($d[$i]['s']==1) {
            $r[] = $d[$i]['v']*1.2;
        } else {
            $r[] = $d[$i]['v'];
        }
    }
    return $r;
}""",
        "code_python": """from typing import List

def process_data(items: List[dict]) -> List[float]:
    result = []
    for item in items:
        if item['status'] == 1:
            result.append(item['value'] * 1.2)
        else:
            result.append(item['value'])
    return result""",
        "description": "Traitement données avec nommage lisible",
        "categorie": "qualite_code",
        "type_amelioration": "naming_clarity",
        "type_transformation": "quality_fix",
        "faille": None,
        "cwe": None,
        "severity": "low",
        "invariant": [
            "logique métier identique",
            "noms de variables explicites"
        ],
        "source": "manuel_qualite"
    },
    {
        "id": 2,
        "code_php": """<?php
function getUserFullName($userId) {
    $user = getUser($userId);
    $name = $user['first_name'] . ' ' . $user['last_name'];
    return $name;
}

function getAdminFullName($adminId) {
    $admin = getAdmin($adminId);
    $name = $admin['first_name'] . ' ' . $admin['last_name'];
    return $name;
}""",
        "code_python": """def get_full_name(entity: dict) -> str:
    return f"{entity['first_name']} {entity['last_name']}"

def get_user_full_name(user_id: int, db: Session) -> str:
    user = get_user(user_id, db)
    return get_full_name(user)

def get_admin_full_name(admin_id: int, db: Session) -> str:
    admin = get_admin(admin_id, db)
    return get_full_name(admin)""",
        "description": "Élimination de code dupliqué",
        "categorie": "qualite_code",
        "type_amelioration": "code_duplication",
        "type_transformation": "quality_fix",
        "faille": None,
        "cwe": None,
        "severity": "low",
        "invariant": [
            "logique de concaténation centralisée",
            "DRY principle respecté"
        ],
        "source": "manuel_qualite"
    },
    {
        "id": 3,
        "code_php": """<?php
function calculate($a, $b, $c, $d, $e, $f) {
    $result = ($a + $b) * $c - ($d / $e) + $f;
    if ($result > 100) {
        $result = 100;
    }
    if ($result < 0) {
        $result = 0;
    }
    return $result;
}""",
        "code_python": """def calculate_score(
    base_value: float,
    bonus: float,
    multiplier: float,
    penalty: float,
    divisor: float,
    adjustment: float,
    min_score: float = 0,
    max_score: float = 100
) -> float:
    raw_score = (base_value + bonus) * multiplier
    raw_score -= (penalty / divisor)
    raw_score += adjustment
    return max(min_score, min(max_score, raw_score))""",
        "description": "Fonction avec paramètres explicites et typés",
        "categorie": "qualite_code",
        "type_amelioration": "function_clarity",
        "type_transformation": "quality_fix",
        "faille": None,
        "cwe": None,
        "severity": "low",
        "invariant": [
            "résultat entre min_score et max_score",
            "paramètres nommés et typés"
        ],
        "source": "manuel_qualite"
    },
    {
        "id": 4,
        "code_php": """<?php
function getActiveUsers() {
    global $db;
    $users = array();
    $result = mysql_query("SELECT * FROM users WHERE active=1");
    while($row = mysql_fetch_array($result)) {
        if ($row['age'] >= 18) {
            if ($row['email'] != '') {
                $users[] = $row;
            }
        }
    }
    return $users;
}""",
        "code_python": """from typing import List

def get_active_users(db: Session) -> List[User]:
    return db.query(User).filter(
        User.active == True,
        User.age >= 18,
        User.email != ''
    ).all()""",
        "description": "Simplification avec ORM et filtres chaînés",
        "categorie": "qualite_code",
        "type_amelioration": "simplification",
        "type_transformation": "quality_fix",
        "faille": None,
        "cwe": None,
        "severity": "low",
        "invariant": [
            "uniquement utilisateurs actifs",
            "age >= 18",
            "email non vide"
        ],
        "source": "manuel_qualite"
    },
    {
        "id": 5,
        "code_php": """<?php
// Get user
function getUser($id) {
    // Connect to database
    $conn = connectDB();
    // Query database
    $sql = "SELECT * FROM users WHERE id=" . $id;
    // Execute query
    $result = mysql_query($sql);
    // Fetch result
    $user = mysql_fetch_array($result);
    // Return user
    return $user;
}""",
        "code_python": """def get_user(user_id: int, db: Session) -> User:
    \"\"\"
    Retrieve a user by their ID.

    Args:
        user_id: The unique identifier of the user
        db: Database session

    Returns:
        User object if found

    Raises:
        HTTPException: 404 if user not found
    \"\"\"
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404,
                          detail="User not found")
    return user""",
        "description": "Remplacement commentaires inutiles par docstring",
        "categorie": "qualite_code",
        "type_amelioration": "documentation",
        "type_transformation": "quality_fix",
        "faille": None,
        "cwe": None,
        "severity": "low",
        "invariant": [
            "docstring Python standard",
            "comportement documenté"
        ],
        "source": "manuel_qualite"
    },
    {
        "id": 6,
        "code_php": """<?php
function processOrder($order) {
    // 200 lines of mixed logic
    $total = 0;
    foreach($order['items'] as $item) {
        $price = $item['price'];
        if ($item['discount'] > 0) {
            $price = $price * (1 - $item['discount']/100);
        }
        $total += $price * $item['quantity'];
    }
    $tax = $total * 0.20;
    $total_with_tax = $total + $tax;
    sendConfirmationEmail($order['email'], $total_with_tax);
    saveOrder($order, $total_with_tax);
    return $total_with_tax;
}""",
        "code_python": """def calculate_item_price(item: dict) -> float:
    price = item['price']
    if item.get('discount', 0) > 0:
        price *= (1 - item['discount'] / 100)
    return price * item['quantity']

def calculate_order_total(items: list) -> float:
    subtotal = sum(
        calculate_item_price(item) for item in items
    )
    return subtotal * 1.20

def process_order(order: dict, db: Session) -> float:
    total = calculate_order_total(order['items'])
    save_order(order, total, db)
    send_confirmation_email(order['email'], total)
    return total""",
        "description": "Décomposition fonction longue en fonctions courtes",
        "categorie": "qualite_code",
        "type_amelioration": "function_decomposition",
        "type_transformation": "quality_fix",
        "faille": None,
        "cwe": None,
        "severity": "low",
        "invariant": [
            "total identique au calcul original",
            "TVA 20% préservée",
            "email envoyé après sauvegarde"
        ],
        "source": "manuel_qualite"
    },
    {
        "id": 7,
        "code_php": """<?php
$STATUS_ACTIVE = 1;
$STATUS_INACTIVE = 0;
$STATUS_PENDING = 2;
$MAX_LOGIN_ATTEMPTS = 5;
$SESSION_TIMEOUT = 3600;

function checkStatus($user) {
    global $STATUS_ACTIVE, $STATUS_INACTIVE,
           $STATUS_PENDING, $MAX_LOGIN_ATTEMPTS;
    if ($user['status'] == $STATUS_ACTIVE) {
        return true;
    }
    return false;
}""",
        "code_python": """from enum import Enum

class UserStatus(Enum):
    ACTIVE = 1
    INACTIVE = 0
    PENDING = 2

MAX_LOGIN_ATTEMPTS = 5
SESSION_TIMEOUT = 3600

def check_status(user: dict) -> bool:
    return user['status'] == UserStatus.ACTIVE.value""",
        "description": "Remplacement variables globales par Enum Python",
        "categorie": "qualite_code",
        "type_amelioration": "constants_enum",
        "type_transformation": "quality_fix",
        "faille": None,
        "cwe": None,
        "severity": "low",
        "invariant": [
            "valeurs des statuts préservées",
            "logique de vérification identique"
        ],
        "source": "manuel_qualite"
    },
    {
        "id": 8,
        "code_php": """<?php
function getUsers($type) {
    if ($type == 'admin') {
        return getAdmins();
    } else if ($type == 'customer') {
        return getCustomers();
    } else if ($type == 'vendor') {
        return getVendors();
    } else {
        return array();
    }
}""",
        "code_python": """from typing import List, Callable

USER_FETCHERS = {
    'admin': get_admins,
    'customer': get_customers,
    'vendor': get_vendors
}

def get_users(user_type: str, db: Session) -> List:
    fetcher = USER_FETCHERS.get(user_type)
    if not fetcher:
        return []
    return fetcher(db)""",
        "description": "Remplacement if/else par dictionnaire de fonctions",
        "categorie": "qualite_code",
        "type_amelioration": "pattern_simplification",
        "type_transformation": "quality_fix",
        "faille": None,
        "cwe": None,
        "severity": "low",
        "invariant": [
            "types de users supportés identiques",
            "liste vide si type inconnu"
        ],
        "source": "manuel_qualite"
    },
    {
        "id": 9,
        "code_php": """<?php
function getUserData($userId) {
    $user = getUser($userId);
    $name = $user['first_name'] . ' ' . $user['last_name'];
    $email = $user['email'];
    $age = date('Y') - date('Y', strtotime($user['birthdate']));
    return array('name' => $name,
                 'email' => $email,
                 'age' => $age);
}""",
        "code_python": """from pydantic import BaseModel
from datetime import date

class UserData(BaseModel):
    name: str
    email: str
    age: int

def get_user_data(user_id: int, db: Session) -> UserData:
    user = get_user(user_id, db)
    age = date.today().year - user.birthdate.year
    return UserData(
        name=f"{user.first_name} {user.last_name}",
        email=user.email,
        age=age
    )""",
        "description": "Retourner un modèle Pydantic au lieu d'un tableau",
        "categorie": "qualite_code",
        "type_amelioration": "typed_return",
        "type_transformation": "quality_fix",
        "faille": None,
        "cwe": None,
        "severity": "low",
        "invariant": [
            "structure retournée identique",
            "âge calculé correctement",
            "types garantis par Pydantic"
        ],
        "source": "manuel_qualite"
    },
    {
        "id": 10,
        "code_php": """<?php
function updateUser($id, $name, $email,
                    $phone, $address, $city,
                    $country, $zip) {
    $sql = "UPDATE users SET name='$name',
            email='$email', phone='$phone',
            address='$address', city='$city',
            country='$country', zip='$zip'
            WHERE id=$id";
    mysql_query($sql);
}""",
        "code_python": """from pydantic import BaseModel
from typing import Optional

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    zip_code: Optional[str] = None

def update_user(user_id: int,
                data: UserUpdate,
                db: Session) -> User:
    user = db.query(User).filter(
        User.id == user_id
    ).first()
    if not user:
        raise HTTPException(status_code=404,
                          detail="User not found")
    for field, value in data.dict(
        exclude_unset=True
    ).items():
        setattr(user, field, value)
    db.commit()
    return user""",
        "description": "Remplacer paramètres multiples par modèle Pydantic",
        "categorie": "qualite_code",
        "type_amelioration": "parameter_object",
        "type_transformation": "quality_fix",
        "faille": "sql_injection",
        "cwe": "CWE-89",
        "severity": "critical",
        "invariant": [
            "tous les champs mis à jour",
            "mise à jour partielle supportée"
        ],
        "source": "manuel_qualite"
    }
]

with open("paires_qualite.json", "w", encoding="utf-8") as f:
    json.dump(paires_qualite, f, ensure_ascii=False, indent=2)

print(f"Qualité code : {len(paires_qualite)} paires créées")
types = {}
for p in paires_qualite:
    t = p["type_amelioration"]
    types[t] = types.get(t, 0) + 1
print("\nPar type d'amélioration :")
for t, n in types.items():
    print(f"  {t} : {n}")
print("\nFichier : paires_qualite.json")