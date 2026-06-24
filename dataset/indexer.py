from transformers import AutoTokenizer, AutoModel
import torch
import faiss
import json
import numpy as np

print("Chargement du dataset...")
with open("dataset_final.json", "r",
          encoding="utf-8") as f:
    dataset = json.load(f)

dataset = [p for p in dataset if p.get("code_php")]
print(f"Paires à indexer : {len(dataset)}")

print("Chargement CodeBERT (premiere fois = telechargement)...")
tokenizer = AutoTokenizer.from_pretrained(
    "microsoft/codebert-base")
model = AutoModel.from_pretrained(
    "microsoft/codebert-base")
model.eval()

def encoder(code):
    inputs = tokenizer(
        code,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=True
    )
    with torch.no_grad():
        outputs = model(**inputs)
    return outputs.last_hidden_state[:,0,:].numpy()[0]

print("Encodage en cours...")
vecteurs = []
for i, paire in enumerate(dataset):
    vecteur = encoder(paire["code_php"])
    vecteurs.append(vecteur)
    if i % 100 == 0:
        print(f"  {i}/{len(dataset)} encodés...")

vecteurs = np.array(vecteurs).astype("float32")

print("Creation index FAISS...")
index = faiss.IndexFlatIP(768)
faiss.normalize_L2(vecteurs)
index.add(vecteurs)
faiss.write_index(index, "index_rag.faiss")

print(f"\nIndex créé : {index.ntotal} vecteurs")

# Sauvegarder les métadonnées
with open("metadata.json", "w", encoding="utf-8") as f:
    json.dump([{
        "id": p["id"],
        "description": p.get("description", ""),
        "categorie": p.get("categorie", ""),
        "source": p.get("source", ""),
        "cwe": p.get("cwe"),
        "severity": p.get("severity")
    } for p in dataset], f, ensure_ascii=False, indent=2)

print("Métadonnées sauvegardées : metadata.json")

# Test de recherche
print("\nTest de recherche...")
requete = encoder("""<?php
function getUser($id) {
    $sql = "SELECT * FROM users WHERE id=" . $id;
    return mysql_query($sql);
}""")
requete = np.array([requete]).astype("float32")
faiss.normalize_L2(requete)
distances, indices = index.search(requete, k=3)

print("Top 3 résultats pour une requête SQL injection :")
for i, idx in enumerate(indices[0]):
    p = dataset[idx]
    print(f"\n{i+1}. [{p.get('categorie')}]"
          f" {p.get('description','')[:60]}")
    print(f"   Source: {p.get('source')}"
          f" | CWE: {p.get('cwe', 'N/A')}")