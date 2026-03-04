import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.agent_coordinator import AgentCoordinator


REPLAY_CASES = [
    {
        "name": "happy_path",
        "source": "Cells use ATP for energy.",
        "artifact_scope": ["story_cards", "voiceover"],
        "render_profile": {"visual_mode": "illustration", "density": "standard"},
        "expect_join_gate": True,
        "expect_ready_for_script": True,
    },
    {
        "name": "artifact_switch_invalidates_downstream",
        "source": "DNA stores genetic instructions.",
        "artifact_scope": ["thumbnail"],
        "render_profile": {"visual_mode": "diagram", "density": "detailed"},
        "relock_scope": ["storyboard", "voiceover"],
        "expect_join_gate": True,
        "expect_cp3_after_relock": "passed",
    },
]


def _signal_success(topic: str) -> dict:
    return {
        "status": "success",
        "content_signal": {
            "thesis": {"one_liner": topic},
            "key_claims": [{"claim_id": "c1", "claim_text": topic}],
            "narrative_beats": [{"beat_id": "b1", "role": "hook", "message": topic}],
        },
    }


def test_replay_harness_cases() -> None:
    async def run() -> None:
        coordinator = AgentCoordinator()

        for case in REPLAY_CASES:
            started = await coordinator.start_workflow(case["source"])
            workflow_id = started["workflow_id"]

            await coordinator.record_signal_result(
                workflow_id,
                source_text=case["source"],
                result=_signal_success(case["source"]),
            )
            await coordinator.lock_artifacts(workflow_id, case["artifact_scope"])

            snap = await coordinator.get_snapshot(workflow_id)
            assert snap["join_gate_ready"] is case["expect_join_gate"]

            await coordinator.lock_render_profile(workflow_id, case["render_profile"])
            snap = await coordinator.get_snapshot(workflow_id)
            assert snap["ready_for_script_pack"] is case.get("expect_ready_for_script", True)

            relock_scope = case.get("relock_scope")
            if relock_scope:
                await coordinator.lock_artifacts(workflow_id, relock_scope)
                snap = await coordinator.get_snapshot(workflow_id)
                assert snap["checkpoint_state"]["CP3_RENDER_LOCKED"] == case["expect_cp3_after_relock"]

    asyncio.run(run())
