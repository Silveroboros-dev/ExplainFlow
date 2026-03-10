import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.schemas.requests import WorkflowAgentChatResponse, WorkflowAgentUiDirective
from app.routes import workflow as workflow_route


class FakeChatAgent:
    async def handle_chat_turn(self, _payload):  # noqa: ANN001
        return WorkflowAgentChatResponse(
            status="success",
            assistant_message="Agent response from test double.",
            selected_action="respond",
            workflow_id="wf-test",
            ui=WorkflowAgentUiDirective(active_panel="source", start_stream=False),
        )


class MissingWorkflowChatAgent:
    async def handle_chat_turn(self, _payload):  # noqa: ANN001
        raise KeyError("Unknown workflow_id: wf-missing")


def test_workflow_agent_chat_route_returns_response_model() -> None:
    original = workflow_route.chat_agent
    workflow_route.chat_agent = FakeChatAgent()
    try:
        client = TestClient(app)
        response = client.post(
            "/api/workflow/agent/chat",
            json={
                "message": "hello",
                "context": {
                    "source_text": "text",
                    "render_profile": {"visual_mode": "illustration"},
                    "artifact_scope": ["story_cards"],
                },
                "conversation": [{"role": "user", "text": "hello"}],
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "success"
        assert payload["assistant_message"] == "Agent response from test double."
        assert payload["workflow_id"] == "wf-test"
        assert payload["ui"]["active_panel"] == "source"
    finally:
        workflow_route.chat_agent = original


def test_workflow_agent_chat_route_returns_clean_404_for_unknown_workflow() -> None:
    original = workflow_route.chat_agent
    workflow_route.chat_agent = MissingWorkflowChatAgent()
    try:
        client = TestClient(app)
        response = client.post(
            "/api/workflow/agent/chat",
            json={
                "message": "hello",
                "context": {
                    "workflow_id": "wf-missing",
                    "source_text": "text",
                    "render_profile": {"visual_mode": "illustration"},
                    "artifact_scope": ["story_cards"],
                },
                "conversation": [{"role": "user", "text": "hello"}],
            },
        )
        assert response.status_code == 404
        payload = response.json()
        assert payload["detail"] == "Unknown workflow_id: wf-missing"
    finally:
        workflow_route.chat_agent = original
