import asyncio
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.routes import generate_stream as generate_stream_route
from app.routes import workflow as workflow_route
from app.services.agent_coordinator import AgentCoordinator


class FakeLegacyStreamAgent:
    async def generate_stream_events(self, **_kwargs):  # noqa: ANN003
        yield {"event": "done", "data": "{}"}


class FakeWorkflowSceneRegenerateAgent:
    async def regenerate_workflow_scene(self, **kwargs):  # noqa: ANN003
        workflow_payload = kwargs["workflow_payload"]
        payload = kwargs["payload"]
        assert workflow_payload.content_signal["thesis"]["one_liner"] == "Cells need ATP"
        assert workflow_payload.render_profile["visual_mode"] == "diagram"
        assert workflow_payload.script_pack["scenes"][0]["scene_id"] == "scene-1"
        assert payload.scene_id == "scene-1"
        assert payload.prior_scene_context[0].scene_id == "scene-0"
        return {
            "status": "success",
            "scene_id": payload.scene_id,
            "text": "Regenerated narration.",
            "imageUrl": "/static/assets/scene-1.png",
            "audioUrl": "/static/assets/scene-1.mp3",
            "qa_status": "PASS",
            "qa_reasons": [],
            "qa_score": 0.91,
            "qa_word_count": 12,
            "auto_retries": 0,
        }


class FakeDirectScriptPackAgent:
    async def generate_script_pack_advanced(self, payload):  # noqa: ANN001
        assert payload.source_text == "Input text"
        assert payload.normalized_source_text == "Recovered source text"
        assert payload.source_text_origin == "pdf_text"
        assert payload.artifact_scope == ["storyboard", "voiceover"]
        assert payload.render_profile["visual_mode"] == "diagram"
        return {
            "status": "success",
            "script_pack": {"plan_id": "plan-direct", "scenes": [{"scene_id": "scene-1"}]},
            "planner_qa_summary": {"mode": "direct"},
            "trace": {"trace_id": "trace-direct"},
        }


class FakeWorkflowScriptPackAgent:
    async def generate_script_pack_advanced(self, payload):  # noqa: ANN001
        assert payload.source_text == "Input text"
        assert payload.artifact_scope == ["storyboard", "voiceover"]
        assert payload.render_profile["visual_mode"] == "diagram"
        return {
            "status": "success",
            "script_pack": {
                "plan_id": "plan-workflow",
                "plan_summary": "Summary",
                "audience_descriptor": "General audience (beginner)",
                "scene_count": 1,
                "artifact_type": "storyboard_grid",
                "scenes": [{"scene_id": "scene-1"}],
            },
            "planner_qa_summary": {"mode": "direct"},
            "claim_traceability": {"claims_total": 1, "claims_referenced": 1, "scene_claim_map": {"scene-1": ["c1"]}},
            "trace": {"trace_id": "trace-workflow"},
        }


def _signal_success_result() -> dict:
    return {
        "status": "success",
        "content_signal": {
            "thesis": {"one_liner": "Cells need ATP"},
            "key_claims": [{"claim_id": "c1", "claim_text": "Mitochondria generate ATP"}],
        },
    }


def test_generate_quick_artifact_route_returns_http_400_for_input_error() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/generate-quick-artifact",
        json={
            "topic": "",
            "audience": "General",
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert "Provide a topic" in payload["message"]


def test_generate_script_pack_advanced_route_builds_request_from_body() -> None:
    original_agent = generate_stream_route.agent
    generate_stream_route.agent = FakeDirectScriptPackAgent()

    try:
        client = TestClient(app)
        response = client.post(
            "/api/generate-script-pack-advanced",
            json={
                "source_text": "Input text",
                "source_manifest": {"assets": []},
                "normalized_source_text": "Recovered source text",
                "source_text_origin": "pdf_text",
                "content_signal": {"thesis": {"one_liner": "Cells need ATP"}},
                "render_profile": {"visual_mode": "diagram"},
                "artifact_scope": ["storyboard", "voiceover", "invalid"],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "success"
        assert payload["script_pack"]["plan_id"] == "plan-direct"
        assert payload["planner_qa_summary"]["mode"] == "direct"
        assert payload["trace"]["trace_id"] == "trace-direct"
    finally:
        generate_stream_route.agent = original_agent


def test_final_bundle_route_returns_bundle_metadata_for_known_run_id() -> None:
    original_coordinator = workflow_route.coordinator
    workflow_route.coordinator = AgentCoordinator()

    try:
        async def seed() -> None:
            started = await workflow_route.coordinator.start_workflow("Input text")
            await workflow_route.coordinator.record_stream_result(
                started["workflow_id"],
                success=True,
                run_id="run-route",
                bundle_url="/api/final-bundle/run-route",
            )

        asyncio.run(seed())

        client = TestClient(app)
        response = client.get("/api/final-bundle/run-route")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "success"
        assert payload["run_id"] == "run-route"
        assert payload["final_bundle"]["bundle_status"] == "ready"
        assert payload["final_bundle"]["export_endpoint"] == "/api/final-bundle/export"
    finally:
        workflow_route.coordinator = original_coordinator


def test_legacy_generate_stream_route_sets_deprecation_headers() -> None:
    original_agent = generate_stream_route.agent
    generate_stream_route.agent = FakeLegacyStreamAgent()

    try:
        client = TestClient(app)
        response = client.get(
            "/api/generate-stream",
            params={
                "topic": "Cells",
                "audience": "Beginner",
                "tone": "Clear",
                "visual_mode": "illustration",
            },
        )

        assert response.status_code == 200
        assert response.headers["deprecation"] == "true"
        assert response.headers["x-explainflow-legacy"] == "true"
        assert "legacy_route_notice" in response.text
    finally:
        generate_stream_route.agent = original_agent


def test_workflow_recovery_routes_return_saved_signal_and_script_pack() -> None:
    original_coordinator = workflow_route.coordinator
    workflow_route.coordinator = AgentCoordinator()

    try:
        async def seed() -> str:
            started = await workflow_route.coordinator.start_workflow("Input text")
            workflow_id = started["workflow_id"]
            await workflow_route.coordinator.record_signal_result(
                workflow_id,
                source_text="Input text",
                result=_signal_success_result(),
            )
            await workflow_route.coordinator.lock_artifacts(workflow_id, ["story_cards"])
            await workflow_route.coordinator.lock_render_profile(workflow_id, {"visual_mode": "illustration"})
            await workflow_route.coordinator.record_script_pack_result(
                workflow_id,
                {"status": "success", "script_pack": {"plan_id": "plan-1", "scenes": [{"scene_id": "scene-1"}]}},
            )
            return workflow_id

        workflow_id = asyncio.run(seed())

        client = TestClient(app)
        signal_response = client.get(f"/api/workflow/{workflow_id}/content-signal")
        script_response = client.get(f"/api/workflow/{workflow_id}/script-pack")

        assert signal_response.status_code == 200
        assert signal_response.json()["status"] == "success"
        assert signal_response.json()["content_signal"]["thesis"]["one_liner"] == "Cells need ATP"

        assert script_response.status_code == 200
        assert script_response.json()["status"] == "success"
        assert script_response.json()["script_pack"]["plan_id"] == "plan-1"
    finally:
        workflow_route.coordinator = original_coordinator


def test_workflow_apply_profile_route_locks_artifacts_and_render() -> None:
    original_coordinator = workflow_route.coordinator
    workflow_route.coordinator = AgentCoordinator()

    try:
        async def seed() -> str:
            started = await workflow_route.coordinator.start_workflow("Input text")
            workflow_id = started["workflow_id"]
            await workflow_route.coordinator.record_signal_result(
                workflow_id,
                source_text="Input text",
                result=_signal_success_result(),
            )
            return workflow_id

        workflow_id = asyncio.run(seed())

        client = TestClient(app)
        response = client.post(
            f"/api/workflow/{workflow_id}/apply-profile",
            json={
                "artifact_scope": ["storyboard", "voiceover"],
                "render_profile": {
                    "visual_mode": "diagram",
                    "density": "standard",
                },
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "success"
        assert payload["workflow"]["checkpoint_state"]["CP2_ARTIFACTS_LOCKED"] == "passed"
        assert payload["workflow"]["checkpoint_state"]["CP3_RENDER_LOCKED"] == "passed"
        assert payload["workflow"]["ready_for_script_pack"] is True
    finally:
        workflow_route.coordinator = original_coordinator


def test_workflow_generate_script_pack_route_returns_shared_response_shape() -> None:
    original_coordinator = workflow_route.coordinator
    original_agent = workflow_route.agent
    workflow_route.coordinator = AgentCoordinator()
    workflow_route.agent = FakeWorkflowScriptPackAgent()

    try:
        async def seed() -> str:
            started = await workflow_route.coordinator.start_workflow("Input text")
            workflow_id = started["workflow_id"]
            await workflow_route.coordinator.record_signal_result(
                workflow_id,
                source_text="Input text",
                result=_signal_success_result(),
            )
            await workflow_route.coordinator.lock_artifacts(workflow_id, ["storyboard", "voiceover"])
            await workflow_route.coordinator.lock_render_profile(workflow_id, {"visual_mode": "diagram"})
            return workflow_id

        workflow_id = asyncio.run(seed())

        client = TestClient(app)
        response = client.post(f"/api/workflow/{workflow_id}/generate-script-pack")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "success"
        assert payload["workflow_id"] == workflow_id
        assert payload["script_pack"]["plan_id"] == "plan-workflow"
        assert payload["planner_qa_summary"]["mode"] == "direct"
        assert payload["claim_traceability"]["claims_total"] == 1
        assert payload["script_trace"]["trace_id"] == "trace-workflow"
        assert payload["workflow"]["checkpoint_state"]["CP4_SCRIPT_LOCKED"] == "passed"
    finally:
        workflow_route.coordinator = original_coordinator
        workflow_route.agent = original_agent


def test_workflow_snapshot_route_returns_clean_404_for_unknown_workflow() -> None:
    client = TestClient(app)
    response = client.get("/api/workflow/wf-missing")

    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"] == "Unknown workflow_id: wf-missing"


def test_workflow_scene_regeneration_route_uses_locked_workflow_context() -> None:
    original_coordinator = workflow_route.coordinator
    original_agent = workflow_route.agent
    workflow_route.coordinator = AgentCoordinator()
    workflow_route.agent = FakeWorkflowSceneRegenerateAgent()

    try:
        async def seed() -> str:
            started = await workflow_route.coordinator.start_workflow("Input text")
            workflow_id = started["workflow_id"]
            await workflow_route.coordinator.record_signal_result(
                workflow_id,
                source_text="Input text",
                result=_signal_success_result(),
            )
            await workflow_route.coordinator.lock_artifacts(workflow_id, ["story_cards"])
            await workflow_route.coordinator.lock_render_profile(workflow_id, {"visual_mode": "diagram"})
            await workflow_route.coordinator.record_script_pack_result(
                workflow_id,
                {
                    "status": "success",
                    "script_pack": {
                        "plan_id": "plan-1",
                        "plan_summary": "Summary",
                        "audience_descriptor": "General audience (beginner)",
                        "scene_count": 1,
                        "artifact_type": "storyboard_grid",
                        "scenes": [
                            {
                                "scene_id": "scene-1",
                                "title": "Hook",
                                "scene_goal": "Explain ATP.",
                                "narration_focus": "Focus on ATP.",
                                "visual_prompt": "Show ATP generation.",
                                "claim_refs": ["c1"],
                                "continuity_refs": [],
                                "acceptance_checks": [],
                            }
                        ],
                    },
                },
            )
            return workflow_id

        workflow_id = asyncio.run(seed())

        client = TestClient(app)
        response = client.post(
            f"/api/workflow/{workflow_id}/regenerate-scene",
            json={
                "scene_id": "scene-1",
                "instruction": "Make it more visual.",
                "current_text": "Old narration.",
                "prior_scene_context": [
                    {
                        "scene_id": "scene-0",
                        "title": "Setup",
                        "text": "Prior context.",
                    }
                ],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "success"
        assert payload["workflow_id"] == workflow_id
        assert payload["scene_id"] == "scene-1"
        assert payload["qa_status"] == "PASS"
        assert payload["imageUrl"] == "/static/assets/scene-1.png"
    finally:
        workflow_route.coordinator = original_coordinator
        workflow_route.agent = original_agent


def test_build_stream_request_marks_stored_script_pack_as_already_enriched() -> None:
    coordinator = AgentCoordinator()

    async def run() -> None:
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
                "script_pack": {
                    "plan_id": "plan-1",
                    "plan_summary": "Summary",
                    "audience_descriptor": "General audience (beginner)",
                    "scene_count": 1,
                    "artifact_type": "storyboard_grid",
                    "scenes": [
                        {
                            "scene_id": "scene-1",
                            "title": "Hook",
                            "scene_goal": "Explain ATP.",
                            "narration_focus": "Focus on ATP.",
                            "visual_prompt": "Show ATP generation.",
                            "claim_refs": ["c1"],
                            "continuity_refs": [],
                            "acceptance_checks": [],
                        }
                    ],
                },
            },
        )

        locked_request = await coordinator.build_stream_request(workflow_id)
        override_request = await coordinator.build_stream_request(
            workflow_id,
            script_pack_override={
                "plan_id": "plan-override",
                "plan_summary": "Override",
                "audience_descriptor": "General audience (beginner)",
                "scene_count": 1,
                "artifact_type": "storyboard_grid",
                "scenes": [
                    {
                        "scene_id": "scene-1",
                        "title": "Override",
                        "scene_goal": "Explain ATP differently.",
                        "narration_focus": "Override focus.",
                        "visual_prompt": "Show ATP generation differently.",
                        "claim_refs": ["c1"],
                        "continuity_refs": [],
                        "acceptance_checks": [],
                    }
                ],
            },
        )

        assert locked_request.script_pack_source_media_enriched is True
        assert override_request.script_pack_source_media_enriched is False

    asyncio.run(run())
