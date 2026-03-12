from __future__ import annotations

import os
import sys
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from unittest.mock import patch
from zipfile import ZipFile

from PIL import Image
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


def test_final_bundle_upscale_returns_upscaled_asset_urls() -> None:
    image_name = "test_bundle_upscale_scene-1.png"
    image_path = ASSET_DIR / image_name
    Image.new("RGB", (3, 2), color=(25, 50, 75)).save(image_path, format="PNG")

    created_path: Path | None = None
    try:
        client = TestClient(app)
        response = client.post(
            "/api/final-bundle/upscale",
            json={
                "scale_factor": 2,
                "scenes": [
                    {
                        "scene_id": "scene-1",
                        "image_url": f"http://testserver/static/assets/{image_name}",
                    }
                ],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "success"
        assert payload["upscaled_count"] == 1
        new_url = payload["scenes"][0]["image_url"]
        assert isinstance(new_url, str)
        assert new_url != f"http://testserver/static/assets/{image_name}"

        created_path = ASSET_DIR / Path(urlparse(new_url).path).name
        assert created_path.exists()

        with Image.open(created_path) as upscaled:
            assert upscaled.size == (6, 4)
    finally:
        image_path.unlink(missing_ok=True)
        if created_path is not None:
            created_path.unlink(missing_ok=True)


def test_source_asset_upload_returns_manifest_assets() -> None:
    created_paths: list[Path] = []
    try:
        client = TestClient(app)
        response = client.post(
            "/api/source-assets/upload",
            files=[
                ("files", ("slide-1.png", b"fake-png", "image/png")),
                ("files", ("meeting.mp3", b"fake-mp3", "audio/mpeg")),
                ("files", ("deck.pdf", b"%PDF-1.4 fake", "application/pdf")),
            ],
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "success"
        assert len(payload["assets"]) == 3
        assert [asset["modality"] for asset in payload["assets"]] == ["image", "audio", "pdf_page"]

        for asset in payload["assets"]:
            created_path = ASSET_DIR / Path(urlparse(asset["uri"]).path).name
            created_paths.append(created_path)
            assert created_path.exists()
    finally:
        for path in created_paths:
            path.unlink(missing_ok=True)


def test_source_asset_upload_rejects_oversized_file() -> None:
    existing_assets = {path.name for path in ASSET_DIR.iterdir()}
    oversized_payload = b"0" * ((1024 * 1024) + 1)

    with patch.dict(os.environ, {"EXPLAINFLOW_MAX_SOURCE_UPLOAD_BYTES": str(1024 * 1024)}):
        client = TestClient(app)
        response = client.post(
            "/api/source-assets/upload",
            files=[
                ("files", ("too-large.png", oversized_payload, "image/png")),
            ],
        )

    assert response.status_code == 413
    payload = response.json()
    assert "upload limit" in payload["detail"]
    assert {path.name for path in ASSET_DIR.iterdir()} == existing_assets


def test_quick_video_download_returns_attachment() -> None:
    video_name = "quick_video_test.mp4"
    video_path = ASSET_DIR / video_name
    video_path.write_bytes(b"fake-mp4")

    try:
        client = TestClient(app)
        response = client.get(
            "/api/quick-video/download",
            params={
                "video_url": f"http://testserver/static/assets/{video_name}",
                "filename": "proof reel final",
            },
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "video/mp4"
        assert 'attachment; filename="proof-reel-final.mp4"' in response.headers["content-disposition"]
        assert response.content == b"fake-mp4"
    finally:
        video_path.unlink(missing_ok=True)


def test_quick_video_download_rejects_missing_asset() -> None:
    client = TestClient(app)
    response = client.get(
        "/api/quick-video/download",
        params={"video_url": "http://testserver/static/assets/does-not-exist.mp4"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Quick MP4 asset not found."


def test_final_bundle_video_export_returns_video_metadata() -> None:
    client = TestClient(app)

    with patch(
        "app.routes.assets.build_advanced_video",
        return_value=("http://testserver/static/assets/advanced_export.mp4", 12345),
    ) as mocked:
        response = client.post(
            "/api/final-bundle/video",
            json={
                "topic": "Cell Energy",
                "scenes": [
                    {
                        "scene_id": "scene-1",
                        "title": "ATP Overview",
                        "text": "Cells use ATP as an energy currency.",
                        "image_url": "http://testserver/static/assets/scene-1.png",
                        "audio_url": "http://testserver/static/assets/scene-1.mp3",
                    }
                ],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["video_url"] == "http://testserver/static/assets/advanced_export.mp4"
    assert payload["duration_ms"] == 12345
    mocked.assert_called_once()


def test_final_bundle_video_download_returns_attachment() -> None:
    video_name = "advanced_export_test.mp4"
    video_path = ASSET_DIR / video_name
    video_path.write_bytes(b"fake-mp4")

    try:
        client = TestClient(app)
        response = client.get(
            "/api/final-bundle/video/download",
            params={
                "video_url": f"http://testserver/static/assets/{video_name}",
                "filename": "studio export final",
            },
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "video/mp4"
        assert 'attachment; filename="studio-export-final.mp4"' in response.headers["content-disposition"]
        assert response.content == b"fake-mp4"
    finally:
        video_path.unlink(missing_ok=True)


def test_final_bundle_video_download_rejects_missing_asset() -> None:
    client = TestClient(app)
    response = client.get(
        "/api/final-bundle/video/download",
        params={"video_url": "http://testserver/static/assets/does-not-exist.mp4"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Advanced MP4 asset not found."
