import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.schemas.events import build_sse_event
from app.schemas.requests import ScriptPackScene
from app.services.interleaved_parser import (
    evaluate_scene_quality,
    extract_anchor_terms,
    normalized_scene_id,
)


def test_extract_anchor_terms_filters_stopwords_and_limits() -> None:
    text = "Explain quantum tunneling with detailed continuity and visuals for science students"
    anchors = extract_anchor_terms(text, limit=3)
    assert anchors == ["quantum", "tunneling", "detailed"]


def test_normalized_scene_id_defaults_when_missing() -> None:
    assert normalized_scene_id("", 2) == "scene-2"
    assert normalized_scene_id(" custom-scene ", 2) == "custom-scene"


def test_evaluate_scene_quality_pass_with_expected_content() -> None:
    scene = ScriptPackScene(
        scene_id="scene-1",
        title="Core concept",
        scene_goal="Explain it",
        narration_focus="quantum tunneling barrier transition",
        visual_prompt="clean diagram",
        claim_refs=["c1"],
        continuity_refs=["previous barrier"],
        acceptance_checks=["50-100 words"],
    )
    text = (
        "Quantum tunneling describes how particles transition through a barrier that would seem "
        "impossible in classical physics. This scene connects the previous barrier setup to the "
        "probability wave behavior and highlights why transition rates change with barrier width."
    )
    result = evaluate_scene_quality(
        scene=scene,
        generated_text=text,
        image_url="http://localhost/image.png",
        must_include=["quantum"],
        must_avoid=["gibberish"],
        continuity_hints=["previous barrier"],
        attempt=1,
    )
    assert result["status"] in {"PASS", "WARN"}
    assert result["scene_id"] == "scene-1"
    assert result["attempt"] == 1


def test_build_sse_event_serializes_payload() -> None:
    event = build_sse_event("status", {"message": "ok"})
    assert event["event"] == "status"
    assert event["data"] == '{"message": "ok"}'
