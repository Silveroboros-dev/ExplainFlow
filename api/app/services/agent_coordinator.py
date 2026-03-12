import asyncio
import time
from copy import deepcopy
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.events import add_checkpoint, init_trace_envelope, utc_now_iso
from app.schemas.requests import (
    AdvancedStreamRequest,
    ArtifactName,
    CheckpointName,
    ScriptPackRequest,
    TraceEnvelope,
)


ALL_CHECKPOINTS: tuple[CheckpointName, ...] = (
    "CP1_SIGNAL_READY",
    "CP2_ARTIFACTS_LOCKED",
    "CP3_RENDER_LOCKED",
    "CP4_SCRIPT_LOCKED",
    "CP5_STREAM_COMPLETE",
    "CP6_BUNDLE_FINALIZED",
)


def _default_checkpoint_state() -> dict[str, str]:
    return {checkpoint: "pending" for checkpoint in ALL_CHECKPOINTS}


class WorkflowState(BaseModel):
    workflow_id: str
    source_text: str
    source_manifest: dict[str, Any] | None = None
    normalized_source_text: str = ""
    source_text_origin: str | None = None
    content_signal: dict[str, Any] | None = None
    artifact_scope: list[ArtifactName] = Field(default_factory=list)
    render_profile: dict[str, Any] = Field(default_factory=dict)
    script_pack: dict[str, Any] | None = None
    planner_qa_summary: dict[str, Any] | None = None
    checkpoint_state: dict[str, str] = Field(default_factory=_default_checkpoint_state)
    trace: TraceEnvelope
    created_at_utc: str = Field(default_factory=utc_now_iso)
    updated_at_utc: str = Field(default_factory=utc_now_iso)
    latest_run_id: str | None = None
    latest_bundle_url: str | None = None
    last_error: str | None = None


class AgentCoordinator:
    """Single-loop state coordinator for the director workflow with strict stage gates."""

    def __init__(self) -> None:
        self._states: dict[str, WorkflowState] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _new_workflow_id() -> str:
        return f"wf-{uuid4().hex[:10]}"

    @staticmethod
    def _new_run_id() -> str:
        return f"workflow-run-{int(time.time())}-{uuid4().hex[:8]}"

    @staticmethod
    def _touch(state: WorkflowState) -> None:
        state.updated_at_utc = utc_now_iso()

    @staticmethod
    def _checkpoint_passed(state: WorkflowState, checkpoint: CheckpointName) -> bool:
        return state.checkpoint_state.get(checkpoint) == "passed"

    @staticmethod
    def _set_checkpoint(
        state: WorkflowState,
        checkpoint: CheckpointName,
        *,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        state.checkpoint_state[checkpoint] = status
        add_checkpoint(
            state.trace,
            checkpoint=checkpoint,
            status=status,  # type: ignore[arg-type]
            details=details or {},
        )

    @staticmethod
    def _invalidate_checkpoints(
        state: WorkflowState,
        checkpoints: list[CheckpointName],
        *,
        reason: str,
    ) -> None:
        for checkpoint in checkpoints:
            previous_status = state.checkpoint_state.get(checkpoint, "pending")
            if previous_status == "passed":
                add_checkpoint(
                    state.trace,
                    checkpoint=checkpoint,
                    status="skipped",
                    details={"reason": reason, "previous_status": previous_status},
            )
            state.checkpoint_state[checkpoint] = "pending"

    @staticmethod
    def _normalized_render_profile(
        render_profile: dict[str, Any],
        *,
        strip_asset_only_fields: bool = False,
    ) -> dict[str, Any]:
        normalized = deepcopy(render_profile) if isinstance(render_profile, dict) else {}
        normalized.pop("profile_id", None)
        if strip_asset_only_fields:
            normalized.pop("fidelity", None)
            normalized.pop("low_key_preview", None)
        return normalized

    @staticmethod
    def _join_gate_ready(state: WorkflowState) -> bool:
        return (
            state.checkpoint_state.get("CP1_SIGNAL_READY") == "passed"
            and state.checkpoint_state.get("CP2_ARTIFACTS_LOCKED") == "passed"
        )

    @staticmethod
    def _try_promote_render_lock(
        state: WorkflowState,
        *,
        source: str,
    ) -> None:
        if not state.render_profile:
            return
        if not AgentCoordinator._join_gate_ready(state):
            if state.checkpoint_state.get("CP3_RENDER_LOCKED") == "passed":
                state.checkpoint_state["CP3_RENDER_LOCKED"] = "pending"
            return
        if state.checkpoint_state.get("CP3_RENDER_LOCKED") == "passed":
            return
        AgentCoordinator._set_checkpoint(
            state,
            "CP3_RENDER_LOCKED",
            status="passed",
            details={
                "visual_mode": str(state.render_profile.get("visual_mode", "illustration")),
                "density": str(state.render_profile.get("density", "standard")),
                "source": source,
            },
        )

    @staticmethod
    def _snapshot(state: WorkflowState) -> dict[str, Any]:
        cp3_status = state.checkpoint_state.get("CP3_RENDER_LOCKED")
        return {
            "workflow_id": state.workflow_id,
            "source_text_chars": len(state.source_text),
            "source_manifest": deepcopy(state.source_manifest),
            "normalized_source_text_chars": len(state.normalized_source_text),
            "source_text_origin": state.source_text_origin,
            "artifact_scope": list(state.artifact_scope),
            "checkpoint_state": dict(state.checkpoint_state),
            "join_gate_ready": AgentCoordinator._join_gate_ready(state),
            "ready_for_script_pack": (
                state.checkpoint_state.get("CP1_SIGNAL_READY") == "passed"
                and state.checkpoint_state.get("CP2_ARTIFACTS_LOCKED") == "passed"
                and state.checkpoint_state.get("CP3_RENDER_LOCKED") == "passed"
            ),
            "ready_for_stream": (
                state.checkpoint_state.get("CP1_SIGNAL_READY") == "passed"
                and state.checkpoint_state.get("CP2_ARTIFACTS_LOCKED") == "passed"
                and state.checkpoint_state.get("CP3_RENDER_LOCKED") == "passed"
                and state.checkpoint_state.get("CP4_SCRIPT_LOCKED") == "passed"
            ),
            "has_signal": state.content_signal is not None,
            "has_render_profile": bool(state.render_profile),
            "render_profile_queued": bool(state.render_profile) and cp3_status == "pending",
            "has_script_pack": state.script_pack is not None,
            "planner_qa_summary": deepcopy(state.planner_qa_summary),
            "latest_run_id": state.latest_run_id,
            "latest_bundle_url": state.latest_bundle_url,
            "last_error": state.last_error,
            "trace": state.trace.model_dump(),
            "created_at_utc": state.created_at_utc,
            "updated_at_utc": state.updated_at_utc,
        }

    async def start_workflow(
        self,
        source_text: str,
        source_manifest: dict[str, Any] | None = None,
        normalized_source_text: str = "",
        source_text_origin: str | None = None,
    ) -> dict[str, Any]:
        async with self._lock:
            workflow_id = self._new_workflow_id()
            trace = init_trace_envelope(
                trace_id=f"trace-{uuid4().hex[:12]}",
                run_id=self._new_run_id(),
                flow="director_single_loop",
                artifact_scope=[],
            )
            state = WorkflowState(
                workflow_id=workflow_id,
                source_text=source_text,
                source_manifest=deepcopy(source_manifest) if isinstance(source_manifest, dict) else None,
                normalized_source_text=normalized_source_text,
                source_text_origin=source_text_origin,
                trace=trace,
            )
            self._states[workflow_id] = state
            return self._snapshot(state)

    async def get_snapshot(self, workflow_id: str) -> dict[str, Any]:
        async with self._lock:
            state = self._states.get(workflow_id)
            if state is None:
                raise KeyError(f"Unknown workflow_id: {workflow_id}")
            return self._snapshot(state)

    async def get_script_pack(self, workflow_id: str) -> dict[str, Any] | None:
        async with self._lock:
            state = self._states.get(workflow_id)
            if state is None:
                raise KeyError(f"Unknown workflow_id: {workflow_id}")
            if isinstance(state.script_pack, dict):
                return deepcopy(state.script_pack)
            return None

    async def get_content_signal(self, workflow_id: str) -> dict[str, Any] | None:
        async with self._lock:
            state = self._states.get(workflow_id)
            if state is None:
                raise KeyError(f"Unknown workflow_id: {workflow_id}")
            if isinstance(state.content_signal, dict):
                return deepcopy(state.content_signal)
            return None

    async def get_final_bundle_status(self, run_id: str) -> dict[str, Any]:
        async with self._lock:
            for state in self._states.values():
                if state.latest_run_id != run_id:
                    continue
                bundle_checkpoint = state.checkpoint_state.get("CP6_BUNDLE_FINALIZED", "pending")
                bundle_status = (
                    "ready"
                    if bundle_checkpoint == "passed"
                    else "failed" if bundle_checkpoint == "failed" else "pending"
                )
                return {
                    "workflow_id": state.workflow_id,
                    "run_id": run_id,
                    "bundle_status": bundle_status,
                    "bundle_url": state.latest_bundle_url,
                    "download_ready": False,
                    "export_endpoint": "/api/final-bundle/export",
                    "checkpoint_state": dict(state.checkpoint_state),
                    "last_error": state.last_error,
                    "updated_at_utc": state.updated_at_utc,
                }
        raise KeyError(f"Unknown run_id: {run_id}")

    async def record_signal_result(
        self,
        workflow_id: str,
        *,
        source_text: str,
        source_manifest: dict[str, Any] | None = None,
        normalized_source_text: str = "",
        source_text_origin: str | None = None,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        async with self._lock:
            state = self._states.get(workflow_id)
            if state is None:
                raise KeyError(f"Unknown workflow_id: {workflow_id}")

            normalized_manifest = deepcopy(source_manifest) if isinstance(source_manifest, dict) else None
            source_changed = (
                source_text != state.source_text
                or normalized_manifest != state.source_manifest
            )
            if source_changed:
                state.source_text = source_text
                state.source_manifest = normalized_manifest
                state.content_signal = None
                state.artifact_scope = []
                state.render_profile = {}
                state.script_pack = None
                state.planner_qa_summary = None
                state.latest_run_id = None
                state.latest_bundle_url = None
                state.last_error = None
                self._invalidate_checkpoints(
                    state,
                    list(ALL_CHECKPOINTS),
                    reason="source_changed",
                )

            state.normalized_source_text = normalized_source_text
            state.source_text_origin = source_text_origin

            if result.get("status") == "success" and isinstance(result.get("content_signal"), dict):
                state.content_signal = deepcopy(result["content_signal"])
                self._set_checkpoint(
                    state,
                    "CP1_SIGNAL_READY",
                    status="passed",
                    details={
                        "source_chars": len(source_text),
                        "normalized_source_chars": len(normalized_source_text),
                        "source_text_origin": source_text_origin or "",
                    },
                )
                state.last_error = None
                self._try_promote_render_lock(state, source="signal_ready")
            else:
                state.content_signal = None
                self._set_checkpoint(
                    state,
                    "CP1_SIGNAL_READY",
                    status="failed",
                    details={"error": str(result.get("message", "Signal extraction failed"))},
                )
                state.last_error = str(result.get("message", "Signal extraction failed"))

            self._touch(state)
            return self._snapshot(state)

    async def lock_artifacts(
        self,
        workflow_id: str,
        artifact_scope: list[ArtifactName],
    ) -> dict[str, Any]:
        async with self._lock:
            state = self._states.get(workflow_id)
            if state is None:
                raise KeyError(f"Unknown workflow_id: {workflow_id}")

            new_scope = list(dict.fromkeys(artifact_scope))
            changed = new_scope != state.artifact_scope
            state.artifact_scope = new_scope

            if changed:
                self._invalidate_checkpoints(
                    state,
                    ["CP4_SCRIPT_LOCKED", "CP5_STREAM_COMPLETE", "CP6_BUNDLE_FINALIZED"],
                    reason="artifact_scope_changed",
                )
                state.script_pack = None
                state.planner_qa_summary = None
                state.latest_run_id = None
                state.latest_bundle_url = None

            self._set_checkpoint(
                state,
                "CP2_ARTIFACTS_LOCKED",
                status="passed",
                details={"artifact_scope": new_scope},
            )
            self._try_promote_render_lock(state, source="artifacts_locked")
            self._touch(state)
            return self._snapshot(state)

    async def lock_render_profile(
        self,
        workflow_id: str,
        render_profile: dict[str, Any],
    ) -> dict[str, Any]:
        async with self._lock:
            state = self._states.get(workflow_id)
            if state is None:
                raise KeyError(f"Unknown workflow_id: {workflow_id}")

            semantic_changed = (
                self._normalized_render_profile(render_profile)
                != self._normalized_render_profile(state.render_profile)
            )
            script_inputs_changed = (
                self._normalized_render_profile(render_profile, strip_asset_only_fields=True)
                != self._normalized_render_profile(state.render_profile, strip_asset_only_fields=True)
            )
            state.render_profile = deepcopy(render_profile)
            if semantic_changed:
                invalidated: list[CheckpointName] = []
                if script_inputs_changed:
                    invalidated = ["CP4_SCRIPT_LOCKED", "CP5_STREAM_COMPLETE", "CP6_BUNDLE_FINALIZED"]
                    state.script_pack = None
                    state.planner_qa_summary = None
                    state.latest_run_id = None
                    state.latest_bundle_url = None
                if invalidated:
                    self._invalidate_checkpoints(
                        state,
                        invalidated,
                        reason="render_profile_changed",
                    )

            if self._join_gate_ready(state):
                self._set_checkpoint(
                    state,
                    "CP3_RENDER_LOCKED",
                    status="passed",
                    details={
                        "visual_mode": str(render_profile.get("visual_mode", "illustration")),
                        "density": str(render_profile.get("density", "standard")),
                        "source": "render_lock",
                    },
                )
            else:
                self._set_checkpoint(
                    state,
                    "CP3_RENDER_LOCKED",
                    status="pending",
                    details={
                        "waiting_for": ["CP1_SIGNAL_READY", "CP2_ARTIFACTS_LOCKED"],
                        "source": "render_lock_queued",
                    },
                )
            self._touch(state)
            return self._snapshot(state)

    async def build_script_pack_request(self, workflow_id: str) -> ScriptPackRequest:
        async with self._lock:
            state = self._states.get(workflow_id)
            if state is None:
                raise KeyError(f"Unknown workflow_id: {workflow_id}")

            if state.checkpoint_state.get("CP1_SIGNAL_READY") != "passed":
                raise ValueError("CP1_SIGNAL_READY must pass before script planning.")
            if state.checkpoint_state.get("CP2_ARTIFACTS_LOCKED") != "passed":
                raise ValueError("CP2_ARTIFACTS_LOCKED must pass before script planning.")
            if state.checkpoint_state.get("CP3_RENDER_LOCKED") != "passed":
                raise ValueError("CP3_RENDER_LOCKED must pass before script planning.")
            if state.content_signal is None:
                raise ValueError("Missing content signal.")

            return ScriptPackRequest(
                source_text=state.source_text,
                source_manifest=deepcopy(state.source_manifest),
                normalized_source_text=state.normalized_source_text,
                source_text_origin=state.source_text_origin,
                content_signal=deepcopy(state.content_signal),
                render_profile=deepcopy(state.render_profile),
                artifact_scope=deepcopy(state.artifact_scope),
            )

    async def record_script_pack_result(
        self,
        workflow_id: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        async with self._lock:
            state = self._states.get(workflow_id)
            if state is None:
                raise KeyError(f"Unknown workflow_id: {workflow_id}")

            if result.get("status") == "success" and isinstance(result.get("script_pack"), dict):
                state.script_pack = deepcopy(result["script_pack"])
                state.planner_qa_summary = (
                    deepcopy(result["planner_qa_summary"])
                    if isinstance(result.get("planner_qa_summary"), dict)
                    else None
                )
                scene_count = len(result["script_pack"].get("scenes", []))
                self._set_checkpoint(
                    state,
                    "CP4_SCRIPT_LOCKED",
                    status="passed",
                    details={"scene_count": scene_count},
                )
                state.last_error = None
            else:
                state.script_pack = None
                state.planner_qa_summary = None
                self._set_checkpoint(
                    state,
                    "CP4_SCRIPT_LOCKED",
                    status="failed",
                    details={"error": str(result.get("message", "Script pack generation failed"))},
                )
                state.last_error = str(result.get("message", "Script pack generation failed"))

            self._touch(state)
            return self._snapshot(state)

    async def build_stream_request(
        self,
        workflow_id: str,
        *,
        script_pack_override: dict[str, Any] | None = None,
    ) -> AdvancedStreamRequest:
        async with self._lock:
            state = self._states.get(workflow_id)
            if state is None:
                raise KeyError(f"Unknown workflow_id: {workflow_id}")

            required = (
                "CP1_SIGNAL_READY",
                "CP2_ARTIFACTS_LOCKED",
                "CP3_RENDER_LOCKED",
                "CP4_SCRIPT_LOCKED",
            )
            for checkpoint in required:
                if state.checkpoint_state.get(checkpoint) != "passed":
                    raise ValueError(f"{checkpoint} must pass before stream generation.")

            script_pack = script_pack_override if isinstance(script_pack_override, dict) else state.script_pack
            if not isinstance(script_pack, dict):
                raise ValueError("Missing script pack for stream generation.")

            return AdvancedStreamRequest(
                source_text=state.source_text,
                source_manifest=deepcopy(state.source_manifest),
                normalized_source_text=state.normalized_source_text,
                source_text_origin=state.source_text_origin,
                content_signal=deepcopy(state.content_signal or {}),
                render_profile=deepcopy(state.render_profile),
                script_pack=deepcopy(script_pack),
                script_pack_source_media_enriched=script_pack_override is None and isinstance(state.script_pack, dict),
                artifact_scope=deepcopy(state.artifact_scope),
            )

    async def record_stream_result(
        self,
        workflow_id: str,
        *,
        success: bool,
        run_id: str | None = None,
        bundle_url: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        async with self._lock:
            state = self._states.get(workflow_id)
            if state is None:
                raise KeyError(f"Unknown workflow_id: {workflow_id}")

            if success:
                self._set_checkpoint(
                    state,
                    "CP5_STREAM_COMPLETE",
                    status="passed",
                    details={"run_id": run_id or ""},
                )
                self._set_checkpoint(
                    state,
                    "CP6_BUNDLE_FINALIZED",
                    status="passed",
                    details={"bundle_url": bundle_url or ""},
                )
                state.latest_run_id = run_id
                state.latest_bundle_url = bundle_url
                state.last_error = None
            else:
                self._set_checkpoint(
                    state,
                    "CP5_STREAM_COMPLETE",
                    status="failed",
                    details={"error": error or "Unknown stream failure"},
                )
                self._set_checkpoint(
                    state,
                    "CP6_BUNDLE_FINALIZED",
                    status="failed",
                    details={"error": error or "Bundle not finalized"},
                )
                state.last_error = error or "Unknown stream failure"

            self._touch(state)
            return self._snapshot(state)
