import asyncio
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.agent_coordinator import AgentCoordinator


def _signal_success_result() -> dict:
    return {
        "status": "success",
        "content_signal": {
            "thesis": {"one_liner": "Cells need ATP"},
            "key_claims": [{"claim_id": "c1", "claim_text": "Mitochondria generate ATP"}],
            "narrative_beats": [{"beat_id": "b1", "role": "hook", "message": "Cells need energy"}],
        },
    }


def test_join_gate_requires_signal_and_artifacts() -> None:
    async def run() -> None:
        coordinator = AgentCoordinator()
        started = await coordinator.start_workflow("Input text")
        workflow_id = started["workflow_id"]

        snap = await coordinator.get_snapshot(workflow_id)
        assert snap["join_gate_ready"] is False

        await coordinator.record_signal_result(
            workflow_id,
            source_text="Input text",
            result=_signal_success_result(),
        )
        snap = await coordinator.get_snapshot(workflow_id)
        assert snap["checkpoint_state"]["CP1_SIGNAL_READY"] == "passed"
        assert snap["join_gate_ready"] is False

        await coordinator.lock_artifacts(workflow_id, ["story_cards", "voiceover"])
        snap = await coordinator.get_snapshot(workflow_id)
        assert snap["checkpoint_state"]["CP2_ARTIFACTS_LOCKED"] == "passed"
        assert snap["join_gate_ready"] is True

    asyncio.run(run())


def test_render_and_script_gate_enforcement() -> None:
    async def run() -> None:
        coordinator = AgentCoordinator()
        started = await coordinator.start_workflow("Input text")
        workflow_id = started["workflow_id"]

        await coordinator.lock_render_profile(workflow_id, {"visual_mode": "illustration"})
        snap = await coordinator.get_snapshot(workflow_id)
        assert snap["checkpoint_state"]["CP3_RENDER_LOCKED"] == "pending"

        await coordinator.record_signal_result(
            workflow_id,
            source_text="Input text",
            result=_signal_success_result(),
        )
        await coordinator.lock_artifacts(workflow_id, ["story_cards"])
        snap = await coordinator.get_snapshot(workflow_id)
        assert snap["checkpoint_state"]["CP3_RENDER_LOCKED"] == "passed"

        script_request = await coordinator.build_script_pack_request(workflow_id)
        assert script_request.artifact_scope == ["story_cards"]

        with pytest.raises(ValueError):
            await coordinator.build_stream_request(workflow_id)

    asyncio.run(run())


def test_invalidation_matrix_artifacts_and_render_changes() -> None:
    async def run() -> None:
        coordinator = AgentCoordinator()
        started = await coordinator.start_workflow("Input text")
        workflow_id = started["workflow_id"]

        await coordinator.record_signal_result(
            workflow_id,
            source_text="Input text",
            result=_signal_success_result(),
        )
        await coordinator.lock_artifacts(workflow_id, ["story_cards"])
        await coordinator.lock_render_profile(workflow_id, {"visual_mode": "diagram"})
        await coordinator.record_script_pack_result(
            workflow_id,
            {"status": "success", "script_pack": {"scenes": [{"scene_id": "scene-1"}]}}
        )

        snap = await coordinator.get_snapshot(workflow_id)
        assert snap["checkpoint_state"]["CP4_SCRIPT_LOCKED"] == "passed"

        await coordinator.lock_artifacts(workflow_id, ["storyboard", "voiceover"])
        snap = await coordinator.get_snapshot(workflow_id)
        assert snap["checkpoint_state"]["CP2_ARTIFACTS_LOCKED"] == "passed"
        assert snap["checkpoint_state"]["CP3_RENDER_LOCKED"] == "passed"
        assert snap["checkpoint_state"]["CP4_SCRIPT_LOCKED"] == "pending"

        await coordinator.lock_render_profile(workflow_id, {"visual_mode": "illustration"})
        snap = await coordinator.get_snapshot(workflow_id)
        assert snap["checkpoint_state"]["CP3_RENDER_LOCKED"] == "passed"
        assert snap["checkpoint_state"]["CP4_SCRIPT_LOCKED"] == "pending"

    asyncio.run(run())
