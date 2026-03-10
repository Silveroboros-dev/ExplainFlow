import subprocess
import time
from pathlib import Path

from fastapi import Request

from app.config import ASSET_DIR
from app.services.image_pipeline import base_url


def _ffmpeg_atempo_filter(playback_rate: float) -> str:
    rate = max(playback_rate, 0.1)
    filters: list[str] = []

    while rate > 2.0:
        filters.append("atempo=2.0")
        rate /= 2.0
    while rate < 0.5:
        filters.append("atempo=0.5")
        rate /= 0.5

    filters.append(f"atempo={rate:.3f}")
    return ",".join(filters)


def _apply_playback_rate(*, source_path: Path, output_path: Path, playback_rate: float) -> bool:
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source_path),
                "-filter:a",
                _ffmpeg_atempo_filter(playback_rate),
                "-vn",
                str(output_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        print(f"Audio tempo adjustment failed: {exc}")
        try:
            output_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False

    return output_path.exists() and output_path.stat().st_size > 0


def generate_audio_and_get_url(
    request: Request,
    scene_id: str,
    text: str,
    prefix: str,
    *,
    playback_rate: float = 1.0,
) -> str:
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
        if abs(playback_rate - 1.0) > 0.001:
            sped_audio_path = ASSET_DIR / f"{prefix}_{scene_id}_{ts}_tempo.mp3"
            if _apply_playback_rate(
                source_path=audio_path,
                output_path=sped_audio_path,
                playback_rate=playback_rate,
            ):
                try:
                    audio_path.unlink(missing_ok=True)
                except Exception:
                    pass
                audio_path = sped_audio_path
                audio_filename = sped_audio_path.name
        return f"{base_url(request)}/static/assets/{audio_filename}"
    except Exception as exc:
        print(f"Audio generation failed: {exc}")
        return ""
