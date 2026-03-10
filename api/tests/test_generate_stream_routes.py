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


def test_workflow_snapshot_route_returns_clean_404_for_unknown_workflow() -> None:
    client = TestClient(app)
    response = client.get("/api/workflow/wf-missing")

    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"] == "Unknown workflow_id: wf-missing"
