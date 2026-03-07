from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import ASSET_DIR
from app.main import app


def test_final_bundle_export_returns_zip_archive() -> None:
    image_name = "test_bundle_scene-1.png"
    audio_name = "test_bundle_scene-1.mp3"
    image_path = ASSET_DIR / image_name
    audio_path = ASSET_DIR / audio_name

    image_path.write_bytes(b"fake-png")
    audio_path.write_bytes(b"fake-mp3")

    try:
        client = TestClient(app)
        response = client.post(
            "/api/final-bundle/export",
            json={
                "topic": "Cell Energy",
                "scenes": [
                    {
                        "scene_id": "scene-1",
                        "title": "ATP Overview",
                        "text": "Cells use ATP as an energy currency.",
                        "image_url": f"http://testserver/static/assets/{image_name}",
                        "audio_url": f"http://testserver/static/assets/{audio_name}",
                    }
                ],
            },
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert "cell-energy-final-bundle.zip" in response.headers["content-disposition"]

        with ZipFile(BytesIO(response.content)) as archive:
            names = sorted(archive.namelist())
            assert names == [
                "audio/01-scene-1.mp3",
                "images/01-scene-1.png",
                "script.txt",
            ]
            transcript = archive.read("script.txt").decode("utf-8")
            assert "Scene 1: ATP Overview" in transcript
            assert "Cells use ATP as an energy currency." in transcript
    finally:
        image_path.unlink(missing_ok=True)
        audio_path.unlink(missing_ok=True)
