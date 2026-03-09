from pathlib import Path
import os

from dotenv import load_dotenv
from google import genai

load_dotenv()


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPO_ROOT / "schemas"
STATIC_DIR = Path(__file__).resolve().parent / "static"
ASSET_DIR = STATIC_DIR / "assets"
ASSET_DIR.mkdir(parents=True, exist_ok=True)

BUCKET_NAME = os.getenv("EXPLAINFLOW_BUCKET")


def get_gemini_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    return genai.Client(api_key=api_key)
