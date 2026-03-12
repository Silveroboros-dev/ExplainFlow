from pathlib import Path
import os

from dotenv import load_dotenv
from google import genai

try:
    import aiohttp
except Exception:  # pragma: no cover - optional runtime dependency
    aiohttp = None  # type: ignore[assignment]

load_dotenv()


def _patch_aiohttp_dns_error_alias() -> None:
    # google-genai 1.61.0 still references aiohttp.ClientConnectorDNSError,
    # but aiohttp 3.10.x no longer exposes that name at the top level.
    if aiohttp is None:
        return
    if hasattr(aiohttp, "ClientConnectorDNSError"):
        return
    connector_error = getattr(aiohttp, "ClientConnectorError", None)
    if connector_error is not None:
        setattr(aiohttp, "ClientConnectorDNSError", connector_error)


_patch_aiohttp_dns_error_alias()


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPO_ROOT / "schemas"
STATIC_DIR = Path(__file__).resolve().parent / "static"
ASSET_DIR = STATIC_DIR / "assets"
ASSET_DIR.mkdir(parents=True, exist_ok=True)

BUCKET_NAME = os.getenv("EXPLAINFLOW_BUCKET")


def get_gemini_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    return genai.Client(api_key=api_key)
