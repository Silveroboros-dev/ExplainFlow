import re
from typing import Any

from app.schemas.requests import ScriptPackScene


def extract_anchor_terms(text: str, limit: int = 4) -> list[str]:
    if not text:
        return []

    stopwords = {
        "about",
        "across",
        "after",
        "again",
        "also",
        "being",
        "between",
        "clear",
        "detail",
        "explain",
        "focus",
        "further",
        "have",
        "into",
        "just",
        "make",
        "more",
        "only",
        "point",
        "scene",
        "should",
        "that",
        "their",
        "there",
        "these",
        "this",
        "with",
    }

    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{3,}", text.lower())
    anchors: list[str] = []
    for token in tokens:
        if token in stopwords:
            continue
        if token not in anchors:
            anchors.append(token)
        if len(anchors) >= limit:
            break
    return anchors


def normalized_scene_id(raw: str, default_idx: int) -> str:
    candidate = (raw or "").strip()
    if not candidate:
        return f"scene-{default_idx}"
    return candidate


def evaluate_scene_quality(
    *,
    scene: ScriptPackScene,
    generated_text: str,
    image_url: str,
    must_include: list[str],
    must_avoid: list[str],
    continuity_hints: list[str],
    attempt: int,
    artifact_type: str | None = None,
) -> dict[str, Any]:
    text = (generated_text or "").strip()
    text_lower = text.lower()
    words = re.findall(r"\b[\w'-]+\b", text)
    word_count = len(words)
    reasons: list[str] = []
    score = 1.0

    hard_fail = False
    if not text:
        hard_fail = True
        reasons.append("No narration text returned.")
    if not image_url:
        hard_fail = True
        reasons.append("No inline image returned.")

    min_words = 50
    max_words = 100
    layout_template = scene.layout_template
    if not layout_template:
        if artifact_type == "slide_thumbnail":
            layout_template = "hero_thumbnail"
        elif artifact_type == "comparison_one_pager":
            layout_template = "modular_poster"
        elif artifact_type == "technical_infographic":
            layout_template = "layered_mechanism"
        elif artifact_type == "process_diagram":
            layout_template = "process_flow"

    if layout_template in {"hero_thumbnail", "thumbnail_variant"}:
        min_words = 18
        max_words = 40
    elif layout_template == "modular_poster":
        min_words = 60
        max_words = 90
    elif layout_template in {"layered_mechanism", "detail_callout", "process_flow", "zoom_detail"}:
        min_words = 40
        max_words = 85

    if word_count and (word_count < min_words or word_count > max_words):
        score -= 0.3
        reasons.append(f"Narration length is {word_count} words (target {min_words}-{max_words}).")

    focus_tokens = extract_anchor_terms(scene.narration_focus, limit=5)
    if focus_tokens and not any(token in text_lower for token in focus_tokens):
        score -= 0.2
        reasons.append("Narration drifted away from the planned scene focus.")

    missing_include = [term for term in must_include if term and term.lower() not in text_lower]
    if missing_include:
        score -= min(0.25, 0.1 * len(missing_include))
        reasons.append(f"Missing must_include cues: {', '.join(missing_include[:3])}.")

    violated_avoid = [term for term in must_avoid if term and term.lower() in text_lower]
    if violated_avoid:
        score -= min(0.3, 0.15 * len(violated_avoid))
        reasons.append(f"Contains must_avoid cues: {', '.join(violated_avoid[:3])}.")

    continuity_terms = [
        token
        for hint in continuity_hints
        for token in extract_anchor_terms(hint, limit=1)
    ]
    if continuity_terms and not any(token in text_lower for token in continuity_terms[:3]):
        score -= 0.1
        reasons.append("Weak continuity tie to earlier scenes.")

    score = max(0.0, min(score, 1.0))
    if hard_fail or score < 0.55:
        status = "FAIL"
    elif score < 0.8:
        status = "WARN"
    else:
        status = "PASS"

    if not reasons and status == "PASS":
        reasons = ["Scene passed quality checks."]

    return {
        "scene_id": scene.scene_id,
        "status": status,
        "score": round(score, 2),
        "reasons": reasons,
        "attempt": attempt,
        "word_count": word_count,
    }


def extract_parts_from_chunk(chunk: Any) -> tuple[list[str], list[bytes]]:
    text_parts: list[str] = []
    image_parts: list[bytes] = []

    candidates = getattr(chunk, "candidates", [])
    if not candidates:
        return text_parts, image_parts

    content = getattr(candidates[0], "content", None)
    parts = getattr(content, "parts", []) if content else []
    for part in parts:
        text = getattr(part, "text", None)
        if text:
            text_parts.append(text)

        inline_data = getattr(part, "inline_data", None)
        image_bytes = getattr(inline_data, "data", None) if inline_data else None
        if image_bytes:
            image_parts.append(image_bytes)

    return text_parts, image_parts


def append_text_part(current_text: str, text_part: str) -> tuple[str, str]:
    """Merge a model-emitted text fragment and return (updated_full_text, incremental_delta).

    Gemini responses may arrive as strict deltas OR as cumulative text snapshots.
    This helper normalizes both into a stable incremental delta stream.
    """
    if not text_part:
        return current_text, ""

    if text_part.startswith(current_text):
        delta = text_part[len(current_text):]
        return text_part, delta

    if current_text.startswith(text_part):
        return current_text, ""

    max_overlap = min(len(current_text), len(text_part))
    overlap = 0
    for idx in range(max_overlap, 0, -1):
        if current_text.endswith(text_part[:idx]):
            overlap = idx
            break

    delta = text_part[overlap:]
    return current_text + delta, delta


def extract_parts_from_response(response: Any) -> tuple[str, bytes | None]:
    full_text = ""
    image_bytes: bytes | None = None

    for candidate in getattr(response, "candidates", []):
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", []) if content else []
        for part in parts:
            text = getattr(part, "text", None)
            if text:
                full_text, _ = append_text_part(full_text, text)
            inline_data = getattr(part, "inline_data", None)
            if inline_data and getattr(inline_data, "data", None):
                image_bytes = inline_data.data

    return full_text, image_bytes
