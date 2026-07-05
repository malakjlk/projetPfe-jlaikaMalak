from groq import Groq

import os
client = Groq(api_key=os.getenv("GROQ_TOKEN"))

prompt = """Tu es un expert en migration de code PHP vers Python moderne avec FastAPI.

Code PHP à convertir :
function validatePassword($password) {
    if (strlen($password) < 8) {
        throw new Exception('Trop court');
    }
    return true;
}

Génère le code Python équivalent avec FastAPI, Pydantic, et annotations de types."""

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "user", "content": prompt}
    ]
)

print(response.choices[0].message.content)