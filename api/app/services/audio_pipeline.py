import time
from pathlib import Path

from fastapi import Request
from google.cloud import storage

from app.config import ASSET_DIR, BUCKET_NAME
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
        
        # Generate locally
        gTTS(text=narration, lang="en", slow=False).save(str(audio_path))

        # If GCS bucket is configured, upload and return GCS URL
        if BUCKET_NAME:
            try:
                storage_client = storage.Client()
                bucket = storage_client.bucket(BUCKET_NAME)
                blob = bucket.blob(audio_filename)
                blob.upload_from_filename(str(audio_path), content_type="audio/mpeg")
                return f"https://storage.googleapis.com/{BUCKET_NAME}/{audio_filename}"
            except Exception as exc:
                print(f"GCS audio upload failed for {audio_filename}: {exc}")
                # Fallback to local URL if GCS fails

        return f"{base_url(request)}/static/assets/{audio_filename}"
    except Exception as exc:
        print(f"Audio generation failed: {exc}")
        return ""
