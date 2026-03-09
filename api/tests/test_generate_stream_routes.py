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
