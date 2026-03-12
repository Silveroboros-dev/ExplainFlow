from typing import Any

from app.schemas.events import build_sse_event


def build_scene_prelude_events(
    *,
    scene_start_payload: dict[str, Any],
    trace_payload: dict[str, Any] | None = None,
    source_media_payloads: list[dict[str, Any]] | None = None,
    source_media_warning_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, str], ...]:
    events: list[dict[str, str]] = [
        build_sse_event("scene_start", scene_start_payload),
    ]

    for source_media_payload in source_media_payloads or []:
        payload = dict(source_media_payload)
        if trace_payload:
            payload["trace"] = trace_payload
        events.append(build_sse_event("source_media_ready", payload))

    if source_media_warning_payload is not None:
        warning_payload = dict(source_media_warning_payload)
        if trace_payload:
            warning_payload["trace"] = trace_payload
        events.append(build_sse_event("source_media_warning", warning_payload))

    return tuple(events)
