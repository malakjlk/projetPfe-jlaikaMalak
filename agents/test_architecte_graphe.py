"""
Tests du découpage en services par partitionnement de graphe (Louvain).

    py -X utf8 test_architecte_graphe.py
"""
import random
from agent_architecte import decouper_en_services, resume_services

resultats = []


def verifier(nom, condition):
    resultats.append((nom, bool(condition)))
    print(f"   {'[OK]' if condition else '[ECHEC]'} {nom}")


def module(nom, fichier, code, appelle=()):
    return {"nom": nom, "fichier": fichier, "code": code, "appelle": set(appelle)}


# Une boutique à deux domaines métier, plus un utilitaire commun
BOUTIQUE = [
    module("getUserByEmail", "db.php", "SELECT * FROM users WHERE email = $e"),
    module("updateUser", "db.php", "UPDATE users SET nom = $n"),
    module("login", "login.php", "$u = getUserByEmail($e);", ["getUserByEmail", "hashPassword"]),
    module("hashPassword", "utils.php", "return password_hash($p);"),
    module("createOrder", "orders.php", "INSERT INTO orders VALUES ($id)", ["hashPassword"]),
    module("listOrders", "orders.php", "SELECT * FROM orders", ["createOrder"]),
    module("addItem", "orders.php", "INSERT INTO order_items VALUES ($i)", ["createOrder"]),
]

print("\n── Découpage d'une boutique à deux domaines ──")
d = decouper_en_services(BOUTIQUE)
print("\n" + resume_services(d) + "\n")
noms = {s["nom"]: s for s in d["services"]}
verifier("la méthode utilisée est Louvain", d["metriques"]["methode"] == "louvain")
verifier("deux services se dégagent : utilisateurs et commandes",
         len(d["services"]) == 2)
verifier("contrainte métier : les modules d'une même table restent ensemble",
         any({"getUserByEmail", "updateUser"} <= set(s["modules"]) for s in d["services"]))
verifier("login rejoint le domaine dont il lit les données (users)",
         any({"login", "getUserByEmail"} <= set(s["modules"]) for s in d["services"]))
verifier("addItem rejoint les commandes par ses appels, malgré une table distincte",
         any({"addItem", "createOrder"} <= set(s["modules"]) for s in d["services"]))
verifier("hashPassword, appelé par les deux domaines, devient une bibliothèque partagée",
         d["bibliotheques_partagees"] == ["hashPassword"])
verifier("la modularité est mesurée", d["metriques"]["modularite"] is not None
         or d["metriques"]["appels_inter_services"] == 0)

print("── Reproductibilité ──")
melange = BOUTIQUE[:]
random.seed(7)
random.shuffle(melange)
d2 = decouper_en_services(melange)
verifier("même découpage quel que soit l'ordre des modules",
         sorted(s["modules"] for s in d["services"]) ==
         sorted(s["modules"] for s in d2["services"]))

print("── Projet trop couplé ──")
MONO = [module("a", "x.php", "SELECT * FROM users"),
        module("b", "x.php", "UPDATE users SET x=1", ["a"]),
        module("c", "y.php", "DELETE FROM users", ["b"])]
d3 = decouper_en_services(MONO)
verifier("un seul domaine : un service, et le monolithe modulaire est recommandé",
         len(d3["services"]) == 1 and any("monolithe" in o for o in d3["obstacles"]))

print("── Obstacles ──")
SESSION = [module("connecter", "s.php", "$_SESSION['u'] = $u; SELECT * FROM users")]
d4 = decouper_en_services(SESSION)
verifier("la dépendance à $_SESSION est signalée comme obstacle",
         any("session" in o for o in d4["obstacles"]))

ok = sum(1 for _, r in resultats if r)
print(f"\n{ok}/{len(resultats)} vérifications réussies")
if ok != len(resultats):
    raise SystemExit(1)