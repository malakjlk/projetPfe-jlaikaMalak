from datasets import load_dataset
import json

print("Téléchargement CodeSearchNet PHP...")
dataset = load_dataset("code-search-net/code_search_net", "php")

paires = []
for exemple in dataset["train"]:
    code_php = exemple["whole_func_string"]
    description = exemple["func_documentation_string"]
    
    if not description or len(description) < 20:
        continue
    if len(code_php) > 1500 or len(code_php) < 50:
        continue
        
    paires.append({
        "id": len(paires) + 1,
        "code_php": code_php,
        "code_python": None,
        "description": description,
        "categorie": "fonction_normale",
        "faille": None,
        "invariant": None,
        "source": "CodeSearchNet"
    })
    
    if len(paires) == 3000:
        break

with open("paires_codesearchnet.json", "w", 
          encoding="utf-8") as f:
    json.dump(paires, f, ensure_ascii=False, indent=2)

print(f"Terminé ! {len(paires)} paires sauvegardées")
print("Fichier : paires_codesearchnet.json")