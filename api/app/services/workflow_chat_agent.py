from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Literal

from google.genai import types
from pydantic import BaseModel, Field

from app.config import get_gemini_client
from app.schemas.requests import (
    ArtifactName,
    SignalExtractionRequest,
    WorkflowAgentAction,
    WorkflowAgentChatContext,
    WorkflowAgentChatRequest,
    WorkflowAgentChatResponse,
    WorkflowAgentUiDirective,
    WorkflowPanelName,
)
from app.services.agent_coordinator import AgentCoordinator
from app.services.gemini_story_agent import GeminiStoryAgent


class PlannerDecision(BaseModel):
    action: WorkflowAgentAction = "respond"
    panel: WorkflowPanelName | None = None
    assistant_message: str = Field(
        default=(
            "I can help with extraction, render profile lock, script pack generation, and stream launch."
        )
    )


class WorkflowChatAgent:
    """Gemini-backed single-turn planner that executes one safe workflow action per turn."""

    def __init__(
        self,
        *,
        coordinator: AgentCoordinator,
        story_agent: GeminiStoryAgent,
        client: Any | None = None,
    ) -> None:
        self._coordinator = coordinator
        self._story_agent = story_agent
        self._client = client or get_gemini_client()

    @staticmethod
    def _safe_json(data: Any) -> str:
        try:
            return json.dumps(data, ensure_ascii=True)
        except Exception:
            return "{}"

    @staticmethod
    def _default_artifact_scope(render_profile: dict[str, Any]) -> list[ArtifactName]:
        artifact_type = str(render_profile.get("artifact_type", "")).strip().lower()
        if artifact_type == "slide_thumbnail":
            return ["thumbnail", "social_caption"]
        if artifact_type == "storyboard_grid":
            return ["storyboard", "voiceover", "social_caption"]
        if artifact_type == "comparison_one_pager":
            return ["story_cards", "social_caption"]
        return ["story_cards", "voiceover"]

    @staticmethod
    def _missing_checkpoints(snapshot: dict[str, Any], required: tuple[str, ...]) -> list[str]:
        checkpoint_state = snapshot.get("checkpoint_state")
        if not isinstance(checkpoint_state, dict):
            return list(required)
        return [
            checkpoint
            for checkpoint in required
            if checkpoint_state.get(checkpoint) != "passed"
        ]

    def _response(
        self,
        *,
        assistant_message: str,
        selected_action: WorkflowAgentAction = "respond",
        workflow_id: str | None = None,
        workflow: dict[str, Any] | None = None,
        content_signal: dict[str, Any] | None = None,
        script_pack: dict[str, Any] | None = None,
        ui: WorkflowAgentUiDirective | None = None,
        status: Literal["success", "error"] = "success",
        message: str | None = None,
    ) -> WorkflowAgentChatResponse:
        return WorkflowAgentChatResponse(
            status=status,
            assistant_message=assistant_message,
            selected_action=selected_action,
            workflow_id=workflow_id,
            workflow=workflow,
            content_signal=content_signal,
            script_pack=script_pack,
            ui=ui or WorkflowAgentUiDirective(),
            message=message,
        )

    @staticmethod
    def _checkpoint_passed(snapshot: dict[str, Any] | None, checkpoint: str) -> bool:
        if not isinstance(snapshot, dict):
            return False
        checkpoint_state = snapshot.get("checkpoint_state")
        if not isinstance(checkpoint_state, dict):
            return False
        return checkpoint_state.get(checkpoint) == "passed"

    @staticmethod
    def _concept_response(
        message: str,
        snapshot: dict[str, Any] | None = None,
    ) -> str | None:
        normalized = " ".join(message.lower().replace("?", " ").replace("-", " ").split())
        if (
            "signal" in normalized
            and "script pack" in normalized
            and any(token in normalized for token in ("difference", "different", "vs", "versus"))
        ):
            return (
                "Signal is the extracted, source-grounded inventory of claims, concepts, and beats. "
                "Script pack is the scene-by-scene plan built from that signal plus the locked render profile, "
                "and it is what the generator uses to produce the final scenes."
            )
        if "what is" in normalized and "signal" in normalized:
            return (
                "The content signal is the structured extraction layer. It turns the source into a stable, "
                "style-agnostic set of claims, concepts, and narrative beats before any rendering choices are applied."
            )
        if "what is" in normalized and "script pack" in normalized:
            return (
                "The script pack is the approved scene plan for generation. It maps the locked signal and render "
                "profile into scene titles, narration focus, visual prompts, and claim references."
            )
        if "what is" in normalized and "render profile" in normalized:
            return (
                "The render profile is the set of audience, style, density, and output controls that shape how "
                "ExplainFlow turns the signal into scenes."
            )
        if "what is" in normalized and "artifact scope" in normalized:
            return (
                "Artifact scope defines which outputs the run is expected to produce, such as story cards, "
                "voiceover, storyboard frames, or social captions."
            )
        if (
            "why" in normalized
            and "confirm" in normalized
            and "signal" in normalized
        ):
            if WorkflowChatAgent._checkpoint_passed(snapshot, "CP4_SCRIPT_LOCKED"):
                return (
                    "Confirming the signal is what allows ExplainFlow to treat the extracted structure as approved "
                    "input for script planning. In this run the script pack is already locked, so you do not need "
                    "to confirm the signal again unless you change the source or the render profile."
                )
            return (
                "Confirming the signal tells ExplainFlow the extracted claims and beats are stable enough to use for "
                "script planning. It is the approval step that prevents scene generation from drifting off an "
                "unreviewed signal."
            )
        return None

    @staticmethod
    def _is_next_step_question(message: str) -> bool:
        normalized = " ".join(message.lower().replace("?", " ").split())
        return any(
            phrase in normalized
            for phrase in (
                "what should i do next",
                "what do i do next",
                "what next",
                "next step",
                "next steps",
            )
        )

    @staticmethod
    def _resolved_assistant_message(planner_message: str, fallback_message: str) -> str:
        cleaned = planner_message.strip()
        if not cleaned:
            return fallback_message
        if cleaned == PlannerDecision().assistant_message:
            return fallback_message
        return cleaned

    @classmethod
    def _next_step_message(cls, snapshot: dict[str, Any] | None) -> str:
        if not isinstance(snapshot, dict):
            return "No workflow is active yet. Start with Extract Signal."

        cp1 = cls._checkpoint_passed(snapshot, "CP1_SIGNAL_READY")
        cp2 = cls._checkpoint_passed(snapshot, "CP2_ARTIFACTS_LOCKED")
        cp3 = cls._checkpoint_passed(snapshot, "CP3_RENDER_LOCKED")
        cp4 = cls._checkpoint_passed(snapshot, "CP4_SCRIPT_LOCKED")
        cp5 = cls._checkpoint_passed(snapshot, "CP5_STREAM_COMPLETE")
        cp6 = cls._checkpoint_passed(snapshot, "CP6_BUNDLE_FINALIZED")
        has_render_profile = bool(snapshot.get("has_render_profile"))
        render_profile_queued = bool(snapshot.get("render_profile_queued"))
        has_artifacts = bool(snapshot.get("artifact_scope"))

        if cp6:
            return "Final bundle is complete. You can rerun with a revised profile or source."
        if cp5:
            return "Stream is complete. Final bundle is ready for review or download."
        if cp4:
            return "Script pack is locked. Review it if needed, then generate stream."
        if not cp1:
            if has_artifacts and render_profile_queued:
                return (
                    "Signal extraction is still pending. Artifact scope is locked and render settings "
                    "are queued until the signal is ready."
                )
            if has_artifacts:
                return "Signal extraction is still pending. Artifact scope is locked while the signal finishes."
            if has_render_profile:
                return (
                    "Signal extraction is still pending. Render settings are saved, but artifact scope "
                    "still needs to be locked."
                )
            return "Signal extraction is not complete yet. Wait for the result or keep shaping the render profile."
        if not cp2:
            return "Signal is extracted. Next, apply profile to lock artifact scope and render settings."
        if not cp3:
            if render_profile_queued:
                return "Artifact scope is locked. Render settings are queued and will lock when the signal gate clears."
            if has_render_profile:
                return "Artifact scope is locked. Render settings are saved but not locked yet."
            return "Artifact scope is locked. Next, apply profile to lock render settings."
        if not cp4:
            return "Signal and render profile are ready. Next, confirm signal to generate script pack."
        return "Script pack is locked. Review it if needed, then generate stream."

    @staticmethod
    def _is_explicit_action_request(action: WorkflowAgentAction, message: str) -> bool:
        normalized = message.lower()
        if action == "extract_signal":
            return any(keyword in normalized for keyword in ("extract", "analyze", "ingest", "start extraction"))
        if action == "apply_render_profile":
            return (
                "apply profile" in normalized
                or "lock profile" in normalized
                or ("apply" in normalized and "render" in normalized)
            )
        if action in {"confirm_signal", "generate_script_pack"}:
            return (
                "confirm signal" in normalized
                or "approve signal" in normalized
                or "generate script" in normalized
                or "script pack" in normalized
            )
        if action == "generate_stream":
            return (
                "generate stream" in normalized
                or "start stream" in normalized
                or "run stream" in normalized
                or "start generation" in normalized
            )
        return True

    async def _plan_action(
        self,
        *,
        message: str,
        context: WorkflowAgentChatContext,
        snapshot: dict[str, Any] | None,
        conversation: list[dict[str, str]],
    ) -> PlannerDecision:
        snapshot_summary = {
            "workflow_id": snapshot.get("workflow_id") if isinstance(snapshot, dict) else None,
            "checkpoint_state": snapshot.get("checkpoint_state") if isinstance(snapshot, dict) else {},
            "ready_for_script_pack": snapshot.get("ready_for_script_pack") if isinstance(snapshot, dict) else False,
            "ready_for_stream": snapshot.get("ready_for_stream") if isinstance(snapshot, dict) else False,
            "has_render_profile": snapshot.get("has_render_profile") if isinstance(snapshot, dict) else False,
            "render_profile_queued": snapshot.get("render_profile_queued") if isinstance(snapshot, dict) else False,
            "artifact_scope": snapshot.get("artifact_scope") if isinstance(snapshot, dict) else [],
        }
        context_summary = {
            "active_panel": context.active_panel,
            "source_text_chars": len(context.source_text or ""),
            "artifact_scope": context.artifact_scope,
            "script_presentation_mode": context.script_presentation_mode,
            "render_profile_keys": sorted(context.render_profile.keys())[:18]
            if isinstance(context.render_profile, dict)
            else [],
        }
        history_summary = conversation[-8:]
        prompt = (
            "You are ExplainFlow's workflow support agent. Choose exactly one next action.\n"
            "Allowed actions: respond, open_panel, extract_signal, apply_render_profile, "
            "confirm_signal, generate_script_pack, generate_stream.\n"
            "ExplainFlow concepts:\n"
            "- content signal = source-grounded claims, concepts, and narrative beats extracted before rendering.\n"
            "- render profile = audience, style, density, and output controls for the run.\n"
            "- script pack = approved scene plan created from the locked signal plus render profile.\n"
            "- final bundle = generated scene assets after the stream completes.\n"
            "Rules:\n"
            "- Never claim completion without executing the action.\n"
            "- Respect strict workflow gates from checkpoint_state.\n"
            "- If prerequisites are missing, choose respond or open_panel and explain clearly.\n"
            "- If the user asks a conceptual product question, choose respond and answer it directly.\n"
            "- Keep assistant_message concise (<=2 sentences).\n"
            "- Use open_panel when user asks to inspect a stage.\n"
            "- Use confirm_signal when user intent is to approve signal and continue.\n"
            "- Use generate_stream only when user explicitly asks to run stream now.\n"
            "Output JSON only.\n\n"
            f"Conversation_tail={self._safe_json(history_summary)}\n"
            f"Current_user_message={json.dumps(message)}\n"
            f"Context={self._safe_json(context_summary)}\n"
            f"Workflow_snapshot={self._safe_json(snapshot_summary)}\n"
        )
        response = await self._client.aio.models.generate_content(
            model="gemini-3.1-pro-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=PlannerDecision,
            ),
        )
        if not response.text:
            raise ValueError("Planner returned empty response.")
        return PlannerDecision.model_validate_json(response.text)

    async def _safe_snapshot(self, workflow_id: str | None) -> dict[str, Any] | None:
        if not workflow_id:
            return None
        try:
            return await self._coordinator.get_snapshot(workflow_id)
        except Exception:
            return None

    async def handle_chat_turn(
        self,
        payload: WorkflowAgentChatRequest,
    ) -> WorkflowAgentChatResponse:
        message = payload.message.strip()
        if not message:
            return self._response(
                assistant_message="Please type a request so I can plan the next workflow action.",
                status="error",
                message="Empty agent message.",
            )

        context = payload.context
        workflow_id = context.workflow_id
        snapshot = await self._safe_snapshot(workflow_id)
        if snapshot is None:
            workflow_id = None

        conversation = [
            {"role": turn.role, "text": turn.text}
            for turn in payload.conversation
            if isinstance(turn.text, str) and turn.text.strip()
        ]

        try:
            decision = await self._plan_action(
                message=message,
                context=context,
                snapshot=snapshot,
                conversation=conversation,
            )
        except Exception as exc:
            return self._response(
                assistant_message=(
                    "I could not run Gemini planning for this turn. "
                    "Please retry in a few seconds."
                ),
                status="error",
                message=str(exc),
                workflow_id=workflow_id,
                workflow=snapshot,
            )

        action = decision.action
        concept_response = self._concept_response(message, snapshot)
        if concept_response is not None:
            return self._response(
                assistant_message=concept_response,
                selected_action="respond",
                workflow_id=workflow_id,
                workflow=snapshot,
                ui=WorkflowAgentUiDirective(
                    active_panel=context.active_panel,
                    start_stream=False,
                ),
            )

        if action in {
            "extract_signal",
            "apply_render_profile",
            "confirm_signal",
            "generate_script_pack",
            "generate_stream",
        } and not self._is_explicit_action_request(action, message):
            return self._response(
                assistant_message=self._next_step_message(snapshot),
                selected_action="respond",
                workflow_id=workflow_id,
                workflow=snapshot,
                ui=WorkflowAgentUiDirective(
                    active_panel=context.active_panel or "source",
                    start_stream=False,
                ),
            )

        if action == "open_panel":
            panel = decision.panel or context.active_panel or "source"
            return self._response(
                assistant_message=self._resolved_assistant_message(
                    decision.assistant_message,
                    self._next_step_message(snapshot),
                ),
                selected_action="open_panel",
                workflow_id=workflow_id,
                workflow=snapshot,
                ui=WorkflowAgentUiDirective(active_panel=panel, start_stream=False),
            )

        if action == "extract_signal":
            source_text = (context.source_text or "").strip()
            if not source_text:
                return self._response(
                    assistant_message=(
                        "Paste source material first, then ask me to extract signal."
                    ),
                    selected_action="extract_signal",
                    workflow_id=workflow_id,
                    workflow=snapshot,
                    ui=WorkflowAgentUiDirective(active_panel="source", start_stream=False),
                    status="error",
                    message="Missing source_text.",
                )

            if not workflow_id:
                started = await self._coordinator.start_workflow(source_text)
                workflow_id = str(started["workflow_id"])
                snapshot = started

            extraction_result = await self._story_agent.extract_signal(
                SignalExtractionRequest(input_text=source_text)
            )
            snapshot = await self._coordinator.record_signal_result(
                workflow_id,
                source_text=source_text,
                result=extraction_result,
            )
            if extraction_result.get("status") != "success":
                detail = str(extraction_result.get("message", "Signal extraction failed."))
                return self._response(
                    assistant_message=detail,
                    selected_action="extract_signal",
                    workflow_id=workflow_id,
                    workflow=snapshot,
                    ui=WorkflowAgentUiDirective(active_panel="source", start_stream=False),
                    status="error",
                    message=detail,
                )
            content_signal_raw = extraction_result.get("content_signal")
            content_signal = content_signal_raw if isinstance(content_signal_raw, dict) else None
            return self._response(
                assistant_message="Signal extracted. Next, apply profile to lock artifacts and render settings.",
                selected_action="extract_signal",
                workflow_id=workflow_id,
                workflow=snapshot,
                content_signal=content_signal,
                ui=WorkflowAgentUiDirective(active_panel="profile", start_stream=False),
            )

        if action == "apply_render_profile":
            if not workflow_id:
                return self._response(
                    assistant_message=(
                        "Run extraction first so the workflow can be initialized."
                    ),
                    selected_action="apply_render_profile",
                    workflow_id=None,
                    workflow=snapshot,
                    ui=WorkflowAgentUiDirective(active_panel="source", start_stream=False),
                    status="error",
                    message="Missing workflow_id.",
                )
            render_profile = (
                deepcopy(context.render_profile)
                if isinstance(context.render_profile, dict)
                else {}
            )
            if not render_profile:
                return self._response(
                    assistant_message=(
                        "Complete Render Profile inputs first, then ask me to apply them."
                    ),
                    selected_action="apply_render_profile",
                    workflow_id=workflow_id,
                    workflow=snapshot,
                    ui=WorkflowAgentUiDirective(active_panel="profile", start_stream=False),
                    status="error",
                    message="Missing render_profile.",
                )

            artifact_scope = (
                list(context.artifact_scope)
                if context.artifact_scope
                else self._default_artifact_scope(render_profile)
            )
            await self._coordinator.lock_artifacts(workflow_id, artifact_scope)
            snapshot = await self._coordinator.lock_render_profile(workflow_id, render_profile)
            return self._response(
                assistant_message=self._next_step_message(snapshot),
                selected_action="apply_render_profile",
                workflow_id=workflow_id,
                workflow=snapshot,
                ui=WorkflowAgentUiDirective(active_panel="signal", start_stream=False),
            )

        if action in {"confirm_signal", "generate_script_pack"}:
            if not workflow_id:
                return self._response(
                    assistant_message=(
                        "Start from signal extraction first, then I can generate script pack."
                    ),
                    selected_action=action,
                    workflow_id=None,
                    workflow=snapshot,
                    ui=WorkflowAgentUiDirective(active_panel="source", start_stream=False),
                    status="error",
                    message="Missing workflow_id.",
                )
            snapshot = await self._coordinator.get_snapshot(workflow_id)
            if not bool(snapshot.get("ready_for_script_pack")):
                missing = self._missing_checkpoints(
                    snapshot,
                    ("CP1_SIGNAL_READY", "CP2_ARTIFACTS_LOCKED", "CP3_RENDER_LOCKED"),
                )
                detail = f"Script pack gate is blocked. Missing: {', '.join(missing)}."
                return self._response(
                    assistant_message=detail,
                    selected_action=action,
                    workflow_id=workflow_id,
                    workflow=snapshot,
                    ui=WorkflowAgentUiDirective(active_panel="signal", start_stream=False),
                    status="error",
                    message=detail,
                )

            script_request = await self._coordinator.build_script_pack_request(workflow_id)
            script_result = await self._story_agent.generate_script_pack_advanced(script_request)
            snapshot = await self._coordinator.record_script_pack_result(workflow_id, script_result)
            if script_result.get("status") != "success":
                detail = str(script_result.get("message", "Script pack generation failed."))
                return self._response(
                    assistant_message=detail,
                    selected_action=action,
                    workflow_id=workflow_id,
                    workflow=snapshot,
                    ui=WorkflowAgentUiDirective(active_panel="script", start_stream=False),
                    status="error",
                    message=detail,
                )

            script_pack_raw = script_result.get("script_pack")
            script_pack = script_pack_raw if isinstance(script_pack_raw, dict) else None
            target_panel: WorkflowPanelName = (
                "stream" if context.script_presentation_mode == "auto" else "script"
            )
            return self._response(
                assistant_message=(
                    "Script pack generated and locked. Review it, then generate stream."
                    if context.script_presentation_mode == "review"
                    else "Script pack generated and locked. Next, generate stream."
                ),
                selected_action=action,
                workflow_id=workflow_id,
                workflow=snapshot,
                script_pack=script_pack,
                ui=WorkflowAgentUiDirective(active_panel=target_panel, start_stream=False),
            )

        if action == "generate_stream":
            if not workflow_id:
                return self._response(
                    assistant_message=(
                        "Initialize workflow and script pack first, then ask me to start stream."
                    ),
                    selected_action="generate_stream",
                    workflow_id=None,
                    workflow=snapshot,
                    ui=WorkflowAgentUiDirective(active_panel="source", start_stream=False),
                    status="error",
                    message="Missing workflow_id.",
                )
            snapshot = await self._coordinator.get_snapshot(workflow_id)
            if not bool(snapshot.get("ready_for_stream")):
                missing = self._missing_checkpoints(
                    snapshot,
                    ("CP1_SIGNAL_READY", "CP2_ARTIFACTS_LOCKED", "CP3_RENDER_LOCKED", "CP4_SCRIPT_LOCKED"),
                )
                detail = f"Stream gate is blocked. Missing: {', '.join(missing)}."
                return self._response(
                    assistant_message=detail,
                    selected_action="generate_stream",
                    workflow_id=workflow_id,
                    workflow=snapshot,
                    ui=WorkflowAgentUiDirective(active_panel="stream", start_stream=False),
                    status="error",
                    message=detail,
                )
            script_pack = await self._coordinator.get_script_pack(workflow_id)
            return self._response(
                assistant_message="Stream gate is ready. Starting generation stream now.",
                selected_action="generate_stream",
                workflow_id=workflow_id,
                workflow=snapshot,
                script_pack=script_pack,
                ui=WorkflowAgentUiDirective(active_panel="stream", start_stream=True),
            )

        return self._response(
            assistant_message=(
                self._concept_response(message, snapshot)
                or (
                    self._next_step_message(snapshot)
                    if self._is_next_step_question(message)
                    else None
                )
                or self._resolved_assistant_message(
                    decision.assistant_message,
                    self._next_step_message(snapshot),
                )
            ),
            selected_action="respond",
            workflow_id=workflow_id,
            workflow=snapshot,
            ui=WorkflowAgentUiDirective(
                active_panel=context.active_panel or "source",
                start_stream=False,
            ),
        )
