from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def list_models():
    print("Listing available models...")
    for model in client.models.list():
        print(f" - {model.name}")

if __name__ == "__main__":
    list_models()
