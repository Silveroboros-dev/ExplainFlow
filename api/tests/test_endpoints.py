import pytest
import requests
import json

BASE_URL = "http://localhost:8000"

def test_extract_signal():
    """Test that the extraction endpoint returns the correct structure based on the schema."""
    test_text = "The mitochondria is the powerhouse of the cell. It generates most of the chemical energy needed to power the cell's biochemical reactions."
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/extract-signal",
            json={"input_text": test_text},
            timeout=30
        )
    except requests.exceptions.ConnectionError:
        pytest.skip("Backend server is not running on localhost:8000. Start it to run integration tests.")
        
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    
    # Verify the core schema properties exist
    signal = data["content_signal"]
    assert "thesis" in signal
    assert "key_claims" in signal
    assert "narrative_beats" in signal
    assert "visual_candidates" in signal
    assert len(signal["narrative_beats"]) >= 1

def test_regenerate_scene():
    """Test that the regeneration endpoint returns the required media and text."""
    try:
        response = requests.post(
            f"{BASE_URL}/api/regenerate-scene",
            json={
                "scene_id": "test-scene-1",
                "current_text": "This is a placeholder text.",
                "instruction": "Make it sound more professional.",
                "visual_mode": "diagram"
            },
            timeout=60
        )
    except requests.exceptions.ConnectionError:
        pytest.skip("Backend server is not running on localhost:8000.")
        
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    
    # Verify the required properties for the frontend are present
    assert "scene_id" in data
    assert data["scene_id"] == "test-scene-1"
    assert "text" in data
    assert isinstance(data["text"], str)
    assert "imageUrl" in data
    assert "audioUrl" in data
