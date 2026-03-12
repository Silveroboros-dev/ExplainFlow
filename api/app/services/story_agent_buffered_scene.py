from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Request


@dataclass(frozen=True)
class BufferedScenePassResult:
    events: tuple[dict[str, str], ...]
    text: str
    image_url: str
    audio_url: str
    word_count: int


async def execute_buffered_scene_pass(
    *,
    stream_scene_assets: Callable[..., AsyncIterator[dict[str, str]]],
    request: Request,
    stream_kwargs: dict[str, Any],
    prelude_events: list[dict[str, str]] | tuple[dict[str, str], ...] | None = None,
) -> BufferedScenePassResult:
    events = list(prelude_events or [])
    scene_result: dict[str, Any] = {}

    async for event in stream_scene_assets(
        request=request,
        result_collector=scene_result,
        **stream_kwargs,
    ):
        events.append(event)

    return BufferedScenePassResult(
        events=tuple(events),
        text=str(scene_result.get("text", "")),
        image_url=str(scene_result.get("image_url", "")),
        audio_url=str(scene_result.get("audio_url", "")),
        word_count=int(scene_result.get("word_count", 0)),
    )
