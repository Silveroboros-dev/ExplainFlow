import time

from fastapi import Request

from app.config import ASSET_DIR


def base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def save_image_and_get_url(request: Request, scene_id: str, image_bytes: bytes, prefix: str) -> str:
    ts = int(time.time() * 1000)
    img_filename = f"{prefix}_{scene_id}_{ts}.png"
    img_path = ASSET_DIR / img_filename
    img_path.write_bytes(image_bytes)
    return f"{base_url(request)}/static/assets/{img_filename}"
