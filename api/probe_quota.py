import os
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

async def probe_quota():
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    # Using specific model names from the list
    models_to_test = [
        "gemini-3.1-pro-preview",
        "gemini-3-pro-image-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-flash-latest",
        "gemini-pro-latest"
    ]
    
    print(f"{'Model':<30} | {'Status':<15} | {'Details'}")
    print("-" * 75)

    for model_id in models_to_test:
        try:
            # Low-cost probe
            response = await client.aio.models.generate_content(
                model=model_id,
                contents="ping",
                config=types.GenerateContentConfig(max_output_tokens=1)
            )
            print(f"{model_id:<30} | {'AVAILABLE':<15} | OK")
        except Exception as e:
            err_msg = str(e).replace('\n', ' ')
            status = "EXHAUSTED" if any(x in err_msg.lower() for x in ["429", "resource_exhausted", "quota"]) else "ERROR"
            print(f"{model_id:<30} | {status:<15} | {err_msg[:45]}...")

if __name__ == "__main__":
    asyncio.run(probe_quota())
