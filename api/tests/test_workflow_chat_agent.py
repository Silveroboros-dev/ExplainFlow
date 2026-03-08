import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.schemas.requests import WorkflowAgentChatContext, WorkflowAgentChatRequest
from app.services.agent_coordinator import AgentCoordinator
from app.services.workflow_chat_agent import PlannerDecision, WorkflowChatAgent


class FakeStoryAgent:
    async def generate_script_pack_advanced(self, _request):  # noqa: ANN001
        return {
            "status": "success",
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
            "script_pack": {
                "plan_id": "plan-1",
                "plan_summary": "summary",
                "audience_descriptor": "persona",
                "scene_count": 1,
                "scenes": [
                    {
                        "scene_id": "scene-1",
                        "title": "Scene 1",
                        "scene_goal": "Goal",
                        "narration_focus": "Focus",
                        "visual_prompt": "Prompt",
                        "claim_refs": ["c1"],
                        "continuity_refs": [],
                        "acceptance_checks": [],
                    }
                ],
            },
        }

    async def extract_signal(self, _request):  # noqa: ANN001
        return {
            "status": "success",
            "content_signal": {"thesis": {"one_liner": "Signal"}},
        }


def test_apply_render_profile_action_locks_artifacts_and_render() -> None:
    async def run() -> None:
        coordinator = AgentCoordinator()
        chat_agent = WorkflowChatAgent(
            coordinator=coordinator,
            story_agent=FakeStoryAgent(),
            client=object(),
        )

        async def fake_plan(**_kwargs):  # noqa: ANN003
            return PlannerDecision(
                action="apply_render_profile",
                assistant_message="Locking render profile now.",
            )

        chat_agent._plan_action = fake_plan  # type: ignore[method-assign]

        started = await coordinator.start_workflow("source text")
        workflow_id = started["workflow_id"]
        await coordinator.record_signal_result(
            workflow_id,
            source_text="source text",
            result={"status": "success", "content_signal": {"thesis": {"one_liner": "x"}}},
        )

        payload = WorkflowAgentChatRequest(
            message="Apply profile",
            context=WorkflowAgentChatContext(
                workflow_id=workflow_id,
                render_profile={"visual_mode": "illustration", "density": "standard"},
                artifact_scope=["story_cards", "voiceover"],
            ),
        )
        result = await chat_agent.handle_chat_turn(payload)

        assert result.status == "success"
        assert result.selected_action == "apply_render_profile"
        assert result.workflow is not None
        assert result.workflow["checkpoint_state"]["CP2_ARTIFACTS_LOCKED"] == "passed"
        assert result.workflow["checkpoint_state"]["CP3_RENDER_LOCKED"] == "passed"

    asyncio.run(run())


def test_apply_render_profile_action_reports_queued_state_before_signal_ready() -> None:
    async def run() -> None:
        coordinator = AgentCoordinator()
        chat_agent = WorkflowChatAgent(
            coordinator=coordinator,
            story_agent=FakeStoryAgent(),
            client=object(),
        )

        async def fake_plan(**_kwargs):  # noqa: ANN003
            return PlannerDecision(
                action="apply_render_profile",
                assistant_message="Locking render profile now.",
            )

        chat_agent._plan_action = fake_plan  # type: ignore[method-assign]

        started = await coordinator.start_workflow("source text")
        workflow_id = started["workflow_id"]

        payload = WorkflowAgentChatRequest(
            message="Apply render profile now",
            context=WorkflowAgentChatContext(
                workflow_id=workflow_id,
                render_profile={"visual_mode": "illustration", "density": "standard"},
                artifact_scope=["story_cards", "voiceover"],
            ),
        )
        result = await chat_agent.handle_chat_turn(payload)

        assert result.status == "success"
        assert result.selected_action == "apply_render_profile"
        assert result.workflow is not None
        assert result.workflow["checkpoint_state"]["CP2_ARTIFACTS_LOCKED"] == "passed"
        assert result.workflow["checkpoint_state"]["CP3_RENDER_LOCKED"] == "pending"
        assert "queued" in result.assistant_message.lower()
        assert "signal" in result.assistant_message.lower()

    asyncio.run(run())


def test_confirm_signal_action_generates_script_pack() -> None:
    async def run() -> None:
        coordinator = AgentCoordinator()
        chat_agent = WorkflowChatAgent(
            coordinator=coordinator,
            story_agent=FakeStoryAgent(),
            client=object(),
        )

        async def fake_plan(**_kwargs):  # noqa: ANN003
            return PlannerDecision(
                action="confirm_signal",
                assistant_message="Signal confirmed. Generating script pack.",
            )

        chat_agent._plan_action = fake_plan  # type: ignore[method-assign]

        started = await coordinator.start_workflow("source text")
        workflow_id = started["workflow_id"]
        await coordinator.record_signal_result(
            workflow_id,
            source_text="source text",
            result={"status": "success", "content_signal": {"thesis": {"one_liner": "x"}}},
        )
        await coordinator.lock_artifacts(workflow_id, ["story_cards", "voiceover"])
        await coordinator.lock_render_profile(workflow_id, {"visual_mode": "illustration"})

        payload = WorkflowAgentChatRequest(
            message="Confirm signal",
            context=WorkflowAgentChatContext(
                workflow_id=workflow_id,
                script_presentation_mode="auto",
            ),
        )
        result = await chat_agent.handle_chat_turn(payload)

        assert result.status == "success"
        assert result.selected_action == "confirm_signal"
        assert result.script_pack is not None
        assert result.planner_qa_summary is not None
        assert result.planner_qa_summary.mode == "repaired"
        assert result.ui.active_panel == "stream"
        assert result.workflow is not None
        assert result.workflow["checkpoint_state"]["CP4_SCRIPT_LOCKED"] == "passed"

    asyncio.run(run())


def test_generate_stream_action_sets_start_stream_flag() -> None:
    async def run() -> None:
        coordinator = AgentCoordinator()
        chat_agent = WorkflowChatAgent(
            coordinator=coordinator,
            story_agent=FakeStoryAgent(),
            client=object(),
        )

        async def fake_plan(**_kwargs):  # noqa: ANN003
            return PlannerDecision(
                action="generate_stream",
                assistant_message="Everything is ready. Starting stream now.",
            )

        chat_agent._plan_action = fake_plan  # type: ignore[method-assign]

        started = await coordinator.start_workflow("source text")
        workflow_id = started["workflow_id"]
        await coordinator.record_signal_result(
            workflow_id,
            source_text="source text",
            result={"status": "success", "content_signal": {"thesis": {"one_liner": "x"}}},
        )
        await coordinator.lock_artifacts(workflow_id, ["story_cards", "voiceover"])
        await coordinator.lock_render_profile(workflow_id, {"visual_mode": "illustration"})
        await coordinator.record_script_pack_result(
            workflow_id,
            {
                "status": "success",
                "script_pack": {
                    "plan_id": "plan-2",
                    "scene_count": 1,
                    "scenes": [
                        {
                            "scene_id": "scene-1",
                            "title": "Scene 1",
                            "scene_goal": "Goal",
                            "narration_focus": "Focus",
                            "visual_prompt": "Prompt",
                            "claim_refs": [],
                            "continuity_refs": [],
                            "acceptance_checks": [],
                        }
                    ],
                },
            },
        )

        payload = WorkflowAgentChatRequest(
            message="Generate stream",
            context=WorkflowAgentChatContext(workflow_id=workflow_id),
        )
        result = await chat_agent.handle_chat_turn(payload)

        assert result.status == "success"
        assert result.selected_action == "generate_stream"
        assert result.ui.start_stream is True
        assert result.script_pack is not None

    asyncio.run(run())


def test_non_explicit_prompt_does_not_execute_locked_action() -> None:
    async def run() -> None:
        coordinator = AgentCoordinator()
        chat_agent = WorkflowChatAgent(
            coordinator=coordinator,
            story_agent=FakeStoryAgent(),
            client=object(),
        )

        async def fake_plan(**_kwargs):  # noqa: ANN003
            return PlannerDecision(
                action="confirm_signal",
                assistant_message="I will generate script pack now.",
            )

        chat_agent._plan_action = fake_plan  # type: ignore[method-assign]

        started = await coordinator.start_workflow("source text")
        workflow_id = started["workflow_id"]
        await coordinator.record_signal_result(
            workflow_id,
            source_text="source text",
            result={"status": "success", "content_signal": {"thesis": {"one_liner": "x"}}},
        )
        await coordinator.lock_artifacts(workflow_id, ["story_cards", "voiceover"])
        await coordinator.lock_render_profile(workflow_id, {"visual_mode": "illustration"})

        payload = WorkflowAgentChatRequest(
            message="What should I do next?",
            context=WorkflowAgentChatContext(workflow_id=workflow_id),
        )
        result = await chat_agent.handle_chat_turn(payload)

        assert result.status == "success"
        assert result.selected_action == "respond"
        assert "confirm signal" in result.assistant_message.lower()
        assert result.workflow is not None
        assert result.workflow["checkpoint_state"]["CP4_SCRIPT_LOCKED"] == "pending"

    asyncio.run(run())


def test_non_explicit_prompt_reflects_queued_render_state() -> None:
    async def run() -> None:
        coordinator = AgentCoordinator()
        chat_agent = WorkflowChatAgent(
            coordinator=coordinator,
            story_agent=FakeStoryAgent(),
            client=object(),
        )

        async def fake_plan(**_kwargs):  # noqa: ANN003
            return PlannerDecision(
                action="respond",
                assistant_message="Workflow looks ready.",
            )

        chat_agent._plan_action = fake_plan  # type: ignore[method-assign]

        started = await coordinator.start_workflow("source text")
        workflow_id = started["workflow_id"]
        await coordinator.lock_artifacts(workflow_id, ["story_cards", "voiceover"])
        await coordinator.lock_render_profile(workflow_id, {"visual_mode": "illustration"})

        payload = WorkflowAgentChatRequest(
            message="What should I do next?",
            context=WorkflowAgentChatContext(workflow_id=workflow_id),
        )
        result = await chat_agent.handle_chat_turn(payload)

        assert result.status == "success"
        assert result.selected_action == "respond"
        assert "queued" in result.assistant_message.lower()
        assert "signal" in result.assistant_message.lower()

    asyncio.run(run())


def test_product_question_returns_concept_answer() -> None:
    async def run() -> None:
        coordinator = AgentCoordinator()
        chat_agent = WorkflowChatAgent(
            coordinator=coordinator,
            story_agent=FakeStoryAgent(),
            client=object(),
        )

        async def fake_plan(**_kwargs):  # noqa: ANN003
            return PlannerDecision(
                action="respond",
                assistant_message="I can help with extraction, render profile lock, script pack generation, and stream launch.",
            )

        chat_agent._plan_action = fake_plan  # type: ignore[method-assign]

        result = await chat_agent.handle_chat_turn(
            WorkflowAgentChatRequest(
                message="what is the difference between signal and script pack?",
                context=WorkflowAgentChatContext(),
            )
        )

        assert result.status == "success"
        assert result.selected_action == "respond"
        assert "source-grounded" in result.assistant_message
        assert "scene-by-scene plan" in result.assistant_message

    asyncio.run(run())


def test_confirm_signal_why_question_does_not_navigate_back() -> None:
    async def run() -> None:
        coordinator = AgentCoordinator()
        chat_agent = WorkflowChatAgent(
            coordinator=coordinator,
            story_agent=FakeStoryAgent(),
            client=object(),
        )

        async def fake_plan(**_kwargs):  # noqa: ANN003
            return PlannerDecision(
                action="open_panel",
                panel="signal",
                assistant_message="You confirm the signal before script planning.",
            )

        chat_agent._plan_action = fake_plan  # type: ignore[method-assign]

        started = await coordinator.start_workflow("source text")
        workflow_id = started["workflow_id"]
        await coordinator.record_signal_result(
            workflow_id,
            source_text="source text",
            result={"status": "success", "content_signal": {"thesis": {"one_liner": "x"}}},
        )
        await coordinator.lock_artifacts(workflow_id, ["story_cards", "voiceover"])
        await coordinator.lock_render_profile(workflow_id, {"visual_mode": "illustration"})
        await coordinator.record_script_pack_result(
            workflow_id,
            {
                "status": "success",
                "script_pack": {
                    "plan_id": "plan-2",
                    "scene_count": 1,
                    "scenes": [
                        {
                            "scene_id": "scene-1",
                            "title": "Scene 1",
                            "scene_goal": "Goal",
                            "narration_focus": "Focus",
                            "visual_prompt": "Prompt",
                            "claim_refs": [],
                            "continuity_refs": [],
                            "acceptance_checks": [],
                        }
                    ],
                },
            },
        )

        payload = WorkflowAgentChatRequest(
            message="Why should I confirm the signal?",
            context=WorkflowAgentChatContext(
                workflow_id=workflow_id,
                active_panel="script",
            ),
        )
        result = await chat_agent.handle_chat_turn(payload)

        assert result.status == "success"
        assert result.selected_action == "respond"
        assert result.ui.active_panel == "script"
        assert "do not need" in result.assistant_message.lower()
        assert "script pack" in result.assistant_message.lower()

    asyncio.run(run())
