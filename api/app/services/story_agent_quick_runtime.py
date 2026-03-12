import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from google.genai import types

from app.schemas.requests import QuickArtifactBlockSchema, QuickArtifactSchema
from app.services.interleaved_parser import extract_parts_from_response
from app.services.story_agent_quick_artifact import (
    build_quick_block_image_prompt,
    build_quick_hero_image_prompt,
)


async def generate_quick_block_image(
    *,
    client: Any,
    save_image_and_get_url: Callable[..., Awaitable[str]],
    style_guide: str,
    request: Request,
    topic: str,
    audience: str,
    tone: str,
    visual_mode: str,
    artifact: QuickArtifactSchema,
    block: QuickArtifactBlockSchema,
    content_signal: dict[str, Any] | None = None,
) -> str:
    prompt = build_quick_block_image_prompt(
        topic=topic,
        audience=audience,
        tone=tone,
        visual_mode=visual_mode,
        style_guide=style_guide,
        artifact=artifact,
        block=block,
        content_signal=content_signal,
    )
    response = await client.aio.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.6),
    )
    _, image_bytes = extract_parts_from_response(response)
    if not image_bytes:
        return ""
    return await save_image_and_get_url(
        request=request,
        scene_id=f"{artifact.artifact_id}-{block.block_id}",
        image_bytes=image_bytes,
        prefix="quick_block",
    )


async def populate_quick_block_visuals(
    *,
    generate_block_image: Callable[..., Awaitable[str]],
    request: Request,
    topic: str,
    audience: str,
    tone: str,
    visual_mode: str,
    artifact: QuickArtifactSchema,
    content_signal: dict[str, Any] | None = None,
    only_block_ids: set[str] | None = None,
    force_block_ids: set[str] | None = None,
) -> QuickArtifactSchema:
    visualized = artifact.model_copy(deep=True)
    tasks: list[asyncio.Task[str]] = []
    task_indices: list[int] = []
    targeted_block_ids = set(only_block_ids or {block.block_id for block in visualized.blocks})
    targeted_block_ids.update(force_block_ids or set())
    for index, block in enumerate(visualized.blocks):
        if block.block_id not in targeted_block_ids:
            continue
        tasks.append(
            asyncio.create_task(
                generate_block_image(
                    request=request,
                    topic=topic,
                    audience=audience,
                    tone=tone,
                    visual_mode=visual_mode,
                    artifact=visualized,
                    block=block,
                    content_signal=content_signal,
                )
            )
        )
        task_indices.append(index)
    if not tasks:
        return visualized
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for index, result in zip(task_indices, results):
        if isinstance(result, Exception) or not result:
            continue
        visualized.blocks[index] = visualized.blocks[index].model_copy(update={"image_url": result})
    return visualized


async def generate_quick_hero_image(
    *,
    client: Any,
    save_image_and_get_url: Callable[..., Awaitable[str]],
    style_guide: str,
    request: Request,
    topic: str,
    audience: str,
    tone: str,
    visual_mode: str,
    artifact: QuickArtifactSchema,
    content_signal: dict[str, Any] | None = None,
) -> str:
    prompt = build_quick_hero_image_prompt(
        topic=topic,
        audience=audience,
        tone=tone,
        visual_mode=visual_mode,
        style_guide=style_guide,
        artifact=artifact,
        content_signal=content_signal,
    )
    response = await client.aio.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.6),
    )
    _, image_bytes = extract_parts_from_response(response)
    if not image_bytes:
        return ""
    return await save_image_and_get_url(
        request=request,
        scene_id=artifact.artifact_id,
        image_bytes=image_bytes,
        prefix="quick_hero",
    )
