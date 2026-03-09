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
        assert snap["has_render_profile"] is True
        assert snap["render_profile_queued"] is True

        await coordinator.record_signal_result(
            workflow_id,
            source_text="Input text",
            result=_signal_success_result(),
        )
        await coordinator.lock_artifacts(workflow_id, ["story_cards"])
        snap = await coordinator.get_snapshot(workflow_id)
        assert snap["checkpoint_state"]["CP3_RENDER_LOCKED"] == "passed"
        assert snap["render_profile_queued"] is False

        script_request = await coordinator.build_script_pack_request(workflow_id)
        assert script_request.artifact_scope == ["story_cards"]
        assert script_request.source_text == "Input text"

        with pytest.raises(ValueError):
            await coordinator.build_stream_request(workflow_id)

    asyncio.run(run())


def test_queued_render_profile_survives_normalized_source_text_update() -> None:
    async def run() -> None:
        coordinator = AgentCoordinator()
        started = await coordinator.start_workflow("Input text")
        workflow_id = started["workflow_id"]

        await coordinator.lock_artifacts(workflow_id, ["story_cards"])
        await coordinator.lock_render_profile(workflow_id, {"visual_mode": "illustration"})

        snap = await coordinator.get_snapshot(workflow_id)
        assert snap["checkpoint_state"]["CP3_RENDER_LOCKED"] == "pending"
        assert snap["has_render_profile"] is True

        await coordinator.record_signal_result(
            workflow_id,
            source_text="Input text",
            normalized_source_text="Recovered PDF text",
            source_text_origin="pdf_text",
            result=_signal_success_result(),
        )

        snap = await coordinator.get_snapshot(workflow_id)
        assert snap["checkpoint_state"]["CP1_SIGNAL_READY"] == "passed"
        assert snap["checkpoint_state"]["CP3_RENDER_LOCKED"] == "passed"
        assert snap["has_render_profile"] is True
        assert snap["render_profile_queued"] is False
        assert snap["ready_for_script_pack"] is True

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
            {
                "status": "success",
                "script_pack": {"scenes": [{"scene_id": "scene-1"}]},
                "planner_qa_summary": {
                    "mode": "repaired",
                    "summary": "Planner applied deterministic repairs before locking the script pack.",
                    "initial_hard_issue_count": 1,
                    "initial_warning_count": 0,
                    "final_warning_count": 0,
                    "repair_applied": True,
                    "replan_attempted": False,
                    "details": [],
                },
            }
        )

        snap = await coordinator.get_snapshot(workflow_id)
        assert snap["checkpoint_state"]["CP4_SCRIPT_LOCKED"] == "passed"
        assert snap["planner_qa_summary"]["mode"] == "repaired"

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


def test_fidelity_only_render_update_preserves_script_pack_lock() -> None:
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
        await coordinator.lock_render_profile(
            workflow_id,
            {
                "profile_id": "rp-preview",
                "visual_mode": "illustration",
                "density": "standard",
                "fidelity": "medium",
                "low_key_preview": True,
            },
        )
        await coordinator.record_script_pack_result(
            workflow_id,
            {"status": "success", "script_pack": {"scenes": [{"scene_id": "scene-1"}]}},
        )
        await coordinator.record_stream_result(
            workflow_id,
            success=True,
            run_id="run-preview",
            bundle_url="/api/final-bundle/run-preview",
        )

        snap = await coordinator.get_snapshot(workflow_id)
        assert snap["checkpoint_state"]["CP4_SCRIPT_LOCKED"] == "passed"
        assert snap["checkpoint_state"]["CP6_BUNDLE_FINALIZED"] == "passed"

        await coordinator.lock_render_profile(
            workflow_id,
            {
                "profile_id": "rp-high",
                "visual_mode": "illustration",
                "density": "standard",
                "fidelity": "high",
                "low_key_preview": True,
            },
        )

        snap = await coordinator.get_snapshot(workflow_id)
        assert snap["checkpoint_state"]["CP3_RENDER_LOCKED"] == "passed"
        assert snap["checkpoint_state"]["CP4_SCRIPT_LOCKED"] == "passed"
        assert snap["checkpoint_state"]["CP5_STREAM_COMPLETE"] == "passed"
        assert snap["checkpoint_state"]["CP6_BUNDLE_FINALIZED"] == "passed"
        assert snap["ready_for_stream"] is True
        assert snap["has_script_pack"] is True
        assert snap["latest_run_id"] == "run-preview"
        assert snap["latest_bundle_url"] == "/api/final-bundle/run-preview"

    asyncio.run(run())


def test_source_manifest_propagates_into_script_and_stream_requests() -> None:
    async def run() -> None:
        coordinator = AgentCoordinator()
        source_manifest = {
            "assets": [
                {
                    "asset_id": "asset-audio-1",
                    "modality": "audio",
                    "uri": "http://example.com/audio.mp3",
                    "duration_ms": 120000,
                }
            ]
        }
        started = await coordinator.start_workflow("Input text", source_manifest, "Recovered source text", "pdf_text")
        workflow_id = started["workflow_id"]

        await coordinator.record_signal_result(
            workflow_id,
            source_text="Input text",
            source_manifest=source_manifest,
            normalized_source_text="Recovered source text",
            source_text_origin="pdf_text",
            result=_signal_success_result(),
        )
        await coordinator.lock_artifacts(workflow_id, ["story_cards"])
        await coordinator.lock_render_profile(workflow_id, {"visual_mode": "illustration"})
        await coordinator.record_script_pack_result(
            workflow_id,
            {"status": "success", "script_pack": {"scenes": [{"scene_id": "scene-1"}]}},
        )

        script_request = await coordinator.build_script_pack_request(workflow_id)
        stream_request = await coordinator.build_stream_request(workflow_id)

        assert script_request.source_manifest is not None
        assert stream_request.source_manifest is not None
        assert script_request.source_manifest.assets[0].asset_id == "asset-audio-1"
        assert stream_request.source_manifest.assets[0].asset_id == "asset-audio-1"
        assert script_request.normalized_source_text == "Recovered source text"
        assert stream_request.normalized_source_text == "Recovered source text"
        assert script_request.source_text_origin == "pdf_text"
        assert stream_request.source_text_origin == "pdf_text"

    asyncio.run(run())


def test_final_bundle_status_lookup_by_run_id() -> None:
    async def run() -> None:
        coordinator = AgentCoordinator()
        started = await coordinator.start_workflow("Input text")
        workflow_id = started["workflow_id"]

        await coordinator.record_stream_result(
            workflow_id,
            success=True,
            run_id="run-preview",
            bundle_url="/api/final-bundle/run-preview",
        )

        bundle = await coordinator.get_final_bundle_status("run-preview")
        assert bundle["workflow_id"] == workflow_id
        assert bundle["run_id"] == "run-preview"
        assert bundle["bundle_status"] == "ready"
        assert bundle["bundle_url"] == "/api/final-bundle/run-preview"
        assert bundle["download_ready"] is False
        assert bundle["export_endpoint"] == "/api/final-bundle/export"

    asyncio.run(run())
