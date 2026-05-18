"""
Test de la clé API Groq (gratuit)
python test_groq.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv('GROQ_API_KEY')

if not api_key:
    print("❌ GROQ_API_KEY introuvable dans .env")
    exit(1)

print(f"✅ Clé trouvée : {api_key[:8]}{'*' * (len(api_key)-8)}")
print("🔄 Test de connexion à Groq...\n")

try:
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Tu es un assistant juridique spécialisé en droit burkinabè. Réponds en français."},
            {"role": "user", "content": "Quelle est la durée légale du travail au Burkina Faso selon le Code du travail ?"}
        ],
        max_tokens=200,
    )

    reponse = response.choices[0].message.content
    print(f"✅ Connexion réussie !")
    print(f"✅ Modèle : {response.model}")
    print(f"✅ Tokens utilisés : {response.usage.total_tokens}")
    print(f"\n💬 Réponse :\n{reponse}")

except ImportError:
    print("❌ Package 'openai' non installé : pip install openai")
except Exception as e:
    if "401" in str(e):
        print(f"❌ Clé invalide : {e}")
    elif "402" in str(e):
        print(f"❌ Solde insuffisant : {e}")
    else:
        print(f"❌ Erreur : {e}")