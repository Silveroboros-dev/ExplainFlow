from typing import Any, Awaitable, Callable

from google.genai import types

from app.services.source_ingest import best_effort_manifest_text


async def normalize_transcript_source_text(
    *,
    client: Any,
    source_text: str,
    source_manifest: Any,
    source_manifest_summary: Callable[[Any], str],
    build_transcript_normalization_prompt: Callable[..., str],
    parse_json_object_response: Callable[[str], dict[str, Any]],
    transcript_normalization_model: Callable[[], str],
    transcript_only_video_mode: Callable[[Any], bool],
) -> tuple[str, str]:
    inventory_text = source_manifest_summary(source_manifest)
    prompt = build_transcript_normalization_prompt(
        transcript_text=source_text,
        source_inventory_text=inventory_text,
    )
    response = await client.aio.models.generate_content(
        model=transcript_normalization_model(),
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    payload = parse_json_object_response(response.text)
    normalized_text = str(payload.get("normalized_source_text", "")).strip() or source_text
    origin = str(payload.get("source_text_origin", "")).strip() or (
        "youtube_transcript_normalized"
        if transcript_only_video_mode(source_manifest)
        else "video_transcript_normalized"
    )
    return normalized_text[:20000], origin


async def build_signal_extraction_contents(
    *,
    document_text: str,
    source_manifest: Any,
    schema_text: str,
    version: str,
    uploaded_assets: Any | None,
    source_manifest_summary: Callable[[Any], str],
    build_signal_extraction_prompt: Callable[..., str],
    transcript_only_video_mode: Callable[[Any], bool],
    build_asset_augmented_contents: Callable[..., Awaitable[tuple[str | list[Any], list[str], int]]],
) -> tuple[str | list[Any], list[str], int]:
    inventory_text = source_manifest_summary(source_manifest)
    prompt = build_signal_extraction_prompt(
        document_text=document_text,
        schema_text=schema_text,
        version=version,
        source_inventory_text=inventory_text,
        transcript_only_video=transcript_only_video_mode(source_manifest),
    )
    return await build_asset_augmented_contents(
        prompt=prompt,
        source_manifest=source_manifest,
        uploaded_assets=uploaded_assets,
    )


async def recover_normalized_source_text(
    *,
    client: Any,
    input_text: str,
    normalized_source_text: str,
    source_text_origin: str | None,
    source_manifest: Any,
    uploaded_assets: Any | None,
    source_manifest_summary: Callable[[Any], str],
    build_source_text_recovery_prompt: Callable[..., str],
    build_asset_augmented_contents: Callable[..., Awaitable[tuple[str | list[Any], list[str], int]]],
    parse_json_object_response: Callable[[str], dict[str, Any]],
    asset_recovery_model: Callable[[], str],
) -> tuple[str, str | None]:
    provided_text = str(input_text or "").strip()
    if provided_text:
        return provided_text, "pasted_text"

    supplied_normalized = str(normalized_source_text or "").strip()
    if supplied_normalized:
        return supplied_normalized, (source_text_origin or "normalized_source_text")

    manifest_text, manifest_origin = best_effort_manifest_text(source_manifest)
    if manifest_text:
        return manifest_text[:20000], manifest_origin

    inventory_text = source_manifest_summary(source_manifest)
    prompt = build_source_text_recovery_prompt(source_inventory_text=inventory_text)
    contents, _, uploaded_count = await build_asset_augmented_contents(
        prompt=prompt,
        source_manifest=source_manifest,
        uploaded_assets=uploaded_assets,
    )
    if uploaded_count == 0:
        return "", None

    response = await client.aio.models.generate_content(
        model=asset_recovery_model(),
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    payload = parse_json_object_response(response.text)
    recovered_text = str(payload.get("normalized_source_text", "")).strip()
    recovered_origin = str(payload.get("source_text_origin", "")).strip() or "gemini_asset_text"
    return recovered_text[:20000], recovered_origin


async def extract_signal_structural(
    *,
    client: Any,
    normalized_source_text: str,
    source_manifest: Any,
    uploaded_assets: Any | None,
    source_manifest_summary: Callable[[Any], str],
    build_structural_signal_prompt: Callable[..., str],
    transcript_only_video_mode: Callable[[Any], bool],
    build_asset_augmented_contents: Callable[..., Awaitable[tuple[str | list[Any], list[str], int]]],
    signal_structural_model: Callable[[], str],
    parse_json_object_response: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    inventory_text = source_manifest_summary(source_manifest)
    prompt = build_structural_signal_prompt(
        document_text=normalized_source_text,
        source_inventory_text=inventory_text,
        transcript_only_video=transcript_only_video_mode(source_manifest),
    )
    contents, _, _ = await build_asset_augmented_contents(
        prompt=prompt,
        source_manifest=source_manifest,
        uploaded_assets=uploaded_assets,
    )
    response = await client.aio.models.generate_content(
        model=signal_structural_model(),
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )
    payload = parse_json_object_response(response.text)
    payload.pop("narrative_beats", None)
    payload.pop("visual_candidates", None)
    return payload


async def extract_signal_creative(
    *,
    client: Any,
    normalized_source_text: str,
    structural_signal: dict[str, Any],
    source_manifest: Any,
    fallback_to_pro: bool,
    build_creative_signal_prompt: Callable[..., str],
    transcript_only_video_mode: Callable[[Any], bool],
    signal_creative_model: Callable[[], str],
    signal_structural_model: Callable[[], str],
    parse_json_object_response: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    prompt = build_creative_signal_prompt(
        document_text=normalized_source_text,
        structural_signal=structural_signal,
        transcript_only_video=transcript_only_video_mode(source_manifest),
    )
    models_to_try = [signal_creative_model()]
    structural_model = signal_structural_model()
    if fallback_to_pro and structural_model not in models_to_try:
        models_to_try.append(structural_model)

    last_error: Exception | None = None
    for model_name in models_to_try:
        try:
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    response_mime_type="application/json",
                ),
            )
            return parse_json_object_response(response.text)
        except Exception as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    raise ValueError("Creative signal extraction failed without a model response.")


async def extract_signal_one_pass(
    *,
    client: Any,
    input_text: str,
    source_manifest: Any,
    prompt_version: str,
    uploaded_assets: Any | None,
    load_schema_text: Callable[[str], str],
    build_signal_extraction_contents: Callable[..., Awaitable[tuple[str | list[Any], list[str], int]]],
    signal_structural_model: Callable[[], str],
    parse_json_object_response: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    schema_text = load_schema_text("content_signal.schema.json")
    extraction_contents, _, _ = await build_signal_extraction_contents(
        document_text=input_text,
        source_manifest=source_manifest,
        schema_text=schema_text,
        version=prompt_version,
        uploaded_assets=uploaded_assets,
    )
    response = await client.aio.models.generate_content(
        model=signal_structural_model(),
        contents=extraction_contents,
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )
    return parse_json_object_response(response.text)
