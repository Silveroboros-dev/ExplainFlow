import time

from fastapi import Request

from app.config import ASSET_DIR
from app.services.image_pipeline import base_url


def generate_audio_and_get_url(request: Request, scene_id: str, text: str, prefix: str) -> str:
    narration = text.strip()
    if not narration:
        return ""

    try:
        from gtts import gTTS
    except Exception as exc:
        print(f"Audio generation unavailable (gTTS import failed): {exc}")
        return ""

    try:
        ts = int(time.time() * 1000)
        audio_filename = f"{prefix}_{scene_id}_{ts}.mp3"
        audio_path = ASSET_DIR / audio_filename
        gTTS(text=narration, lang="en", slow=False).save(str(audio_path))
        return f"{base_url(request)}/static/assets/{audio_filename}"
    except Exception as exc:
        print(f"Audio generation failed: {exc}")
        return ""
