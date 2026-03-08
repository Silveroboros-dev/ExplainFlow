from datetime import datetime, timezone
import json
from typing import Any

from app.schemas.requests import (
    ArtifactName,
    CheckpointName,
    CheckpointRecord,
    CheckpointStatus,
    SceneTraceRecord,
    TraceEnvelope,
)


def build_sse_event(event: str, payload: dict[str, Any]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(payload)}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_trace_envelope(
    *,
    trace_id: str,
    run_id: str,
    flow: str,
    artifact_scope: list[ArtifactName],
) -> TraceEnvelope:
    return TraceEnvelope(
        trace_id=trace_id,
        run_id=run_id,
        flow=flow,
        started_at_utc=utc_now_iso(),
        artifact_scope=artifact_scope,
    )


def add_checkpoint(
    trace: TraceEnvelope,
    *,
    checkpoint: CheckpointName,
    status: CheckpointStatus,
    details: dict[str, Any] | None = None,
) -> CheckpointRecord:
    record = CheckpointRecord(
        checkpoint=checkpoint,
        status=status,
        timestamp_utc=utc_now_iso(),
        details=details or {},
    )
    trace.checkpoints.append(record)
    return record


def build_checkpoint_event(
    trace: TraceEnvelope,
    record: CheckpointRecord,
) -> dict[str, str]:
    return build_sse_event(
        "checkpoint",
        {
            "checkpoint": record.checkpoint,
            "status": record.status,
            "timestamp_utc": record.timestamp_utc,
            "details": record.details,
            "trace": trace_meta(trace, checkpoint=record.checkpoint),
        },
    )


def add_or_update_scene_trace(
    trace: TraceEnvelope,
    *,
    scene_id: str,
    scene_trace_id: str,
    claim_refs: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    render_strategy: str | None = None,
    media_asset_ids: list[str] | None = None,
    qa_result: dict[str, Any] | None = None,
    retries_used: int | None = None,
    word_count: int | None = None,
) -> SceneTraceRecord:
    scene_record = next((s for s in trace.scenes if s.scene_id == scene_id), None)
    if scene_record is None:
        scene_record = SceneTraceRecord(
            scene_id=scene_id,
            scene_trace_id=scene_trace_id,
            claim_refs=claim_refs or [],
            evidence_refs=evidence_refs or [],
            render_strategy=render_strategy,
            media_asset_ids=media_asset_ids or [],
        )
        trace.scenes.append(scene_record)

    if claim_refs is not None:
        scene_record.claim_refs = claim_refs
    if evidence_refs is not None:
        scene_record.evidence_refs = evidence_refs
    if render_strategy is not None:
        scene_record.render_strategy = render_strategy  # type: ignore[assignment]
    if media_asset_ids is not None:
        scene_record.media_asset_ids = media_asset_ids
    if qa_result is not None:
        scene_record.qa_history.append(qa_result)
    if retries_used is not None:
        scene_record.retries_used = retries_used
    if word_count is not None:
        scene_record.word_count = word_count

    return scene_record


def trace_meta(
    trace: TraceEnvelope,
    *,
    checkpoint: CheckpointName | None = None,
    scene_trace_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "trace_id": trace.trace_id,
        "run_id": trace.run_id,
        "flow": trace.flow,
    }
    if checkpoint:
        payload["checkpoint"] = checkpoint
    if scene_trace_id:
        payload["scene_trace_id"] = scene_trace_id
    return payload
