import google.generativeai as genai

import os
genai.configure(api_key=os.getenv("GEMINI_TOKEN"))


model = genai.GenerativeModel("gemini-1.5-flash")

prompt = """Tu es un expert en migration de code PHP vers Python moderne avec FastAPI.

Code PHP à convertir :
function validatePassword($password) {
    if (strlen($password) < 8) {
        throw new Exception('Trop court');
    }
    return true;
}

Génère le code Python équivalent avec FastAPI, Pydantic, et annotations de types."""

response = model.generate_content(prompt)
print(response.text)