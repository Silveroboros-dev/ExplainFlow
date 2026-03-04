import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.schemas.events import (
    add_checkpoint,
    add_or_update_scene_trace,
    build_checkpoint_event,
    init_trace_envelope,
)


def test_checkpoint_event_and_trace_meta() -> None:
    trace = init_trace_envelope(
        trace_id="trace-abc",
        run_id="run-123",
        flow="advanced_stream",
        artifact_scope=["story_cards", "voiceover"],
    )
    cp = add_checkpoint(
        trace,
        checkpoint="CP1_SIGNAL_READY",
        status="passed",
        details={"source": "payload"},
    )
    event = build_checkpoint_event(trace, cp)
    assert event["event"] == "checkpoint"
    assert '"checkpoint": "CP1_SIGNAL_READY"' in event["data"]
    assert '"trace_id": "trace-abc"' in event["data"]


def test_scene_trace_updates_accumulate() -> None:
    trace = init_trace_envelope(
        trace_id="trace-xyz",
        run_id="run-456",
        flow="advanced_stream",
        artifact_scope=["story_cards"],
    )

    first = add_or_update_scene_trace(
        trace,
        scene_id="scene-1",
        scene_trace_id="trace-scene-1",
        claim_refs=["c1"],
    )
    assert first.scene_id == "scene-1"
    assert first.claim_refs == ["c1"]
    assert first.retries_used == 0

    updated = add_or_update_scene_trace(
        trace,
        scene_id="scene-1",
        scene_trace_id="trace-scene-1",
        qa_result={"status": "PASS", "score": 0.91},
        retries_used=1,
        word_count=88,
    )
    assert updated.retries_used == 1
    assert updated.word_count == 88
    assert len(updated.qa_history) == 1
    assert updated.qa_history[0]["status"] == "PASS"
