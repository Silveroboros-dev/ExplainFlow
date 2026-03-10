import asyncio
import json
import os
import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch
from unittest.mock import AsyncMock

from fastapi import Request
from PIL import Image, ImageChops

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.schemas.events import build_sse_event
from app.schemas.requests import (
    AdvancedStreamRequest,
    QuickArtifactOverrideRequest,
    QuickArtifactRequest,
    QuickArtifactSchema,
    QuickBlockOverrideRequest,
    QuickReelRequest,
    QuickVideoRequest,
    QuickVideoSchema,
    ScriptPack,
    ScriptPackRequest,
    ScriptPackScene,
    SignalExtractionRequest,
    SourceMediaRefSchema,
)
from app.services.gemini_story_agent import GeminiStoryAgent
from app.services.image_pipeline import (
    asset_path_from_url,
    compose_thumbnail_cover_and_get_url,
    save_image_and_get_url,
)
from app.services.interleaved_parser import (
    append_text_part,
    evaluate_scene_quality,
    extract_anchor_terms,
    normalized_scene_id,
)
from app.services.source_ingest import locate_excerpt_in_page_text
from app.services.source_ingest import validate_video_manifest_constraints
from app.services.video_pipeline import build_quick_video_segment


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class RoutingFakeModels:
    def __init__(
        self,
        *,
        outline_payload: dict[str, Any] | list[dict[str, Any]],
        salience_payload: dict[str, Any] | None = None,
        forward_pull_payload: dict[str, Any] | None = None,
    ) -> None:
        self.outline_payload = outline_payload
        self.salience_payload = salience_payload or {"items": []}
        self.forward_pull_payload = forward_pull_payload or {
            "bait": None,
            "hook": None,
            "threats": [],
            "rewards": [],
            "payloads": [],
        }
        self.prompts: list[str] = []
        self.outline_call_count = 0

    async def generate_content(self, *, model, contents, config):  # noqa: ANN001
        prompt = str(contents)
        self.prompts.append(prompt)
        if "counterfactual deletion" in prompt:
            return FakeResponse(json.dumps(self.salience_payload))
        if "Bait-Hook-Threat-Reward-Payload lens" in prompt:
            return FakeResponse(json.dumps(self.forward_pull_payload))
        self.outline_call_count += 1
        if isinstance(self.outline_payload, list):
            index = min(self.outline_call_count - 1, len(self.outline_payload) - 1)
            return FakeResponse(json.dumps(self.outline_payload[index]))
        return FakeResponse(json.dumps(self.outline_payload))


class RoutingFakeClient:
    def __init__(
        self,
        *,
        outline_payload: dict[str, Any] | list[dict[str, Any]],
        salience_payload: dict[str, Any] | None = None,
        forward_pull_payload: dict[str, Any] | None = None,
    ) -> None:
        self.models = RoutingFakeModels(
            outline_payload=outline_payload,
            salience_payload=salience_payload,
            forward_pull_payload=forward_pull_payload,
        )
        self.aio = self


class CapturingStreamModels:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate_content_stream(self, *, model, contents, config):  # noqa: ANN001
        self.prompts.append(str(contents))
        return EmptyAsyncStream()


class EmptyAsyncStream:
    def __aiter__(self):  # noqa: ANN204
        return self

    async def __anext__(self):  # noqa: ANN204
        raise StopAsyncIteration


class CapturingStreamClient:
    def __init__(self) -> None:
        self.models = CapturingStreamModels()
        self.aio = self


class ExtractionFakeFiles:
    def __init__(self) -> None:
        self.upload_calls: list[tuple[str, str | None]] = []
        self.deleted_names: list[str] = []

    async def upload(self, *, file, config=None):  # noqa: ANN001
        mime_type = getattr(config, "mime_type", None)
        self.upload_calls.append((str(file), mime_type))
        return SimpleNamespace(
            name=f"files/{len(self.upload_calls)}",
            uri=f"gs://demo/uploaded-{len(self.upload_calls)}",
            mime_type=mime_type or "application/octet-stream",
        )

    async def delete(self, *, name, config=None):  # noqa: ANN001
        self.deleted_names.append(name)
        return SimpleNamespace()


class ExtractionFakeModels:
    def __init__(self, response_text: str | None = None, response_router=None) -> None:  # noqa: ANN001
        self.response_text = response_text or "{}"
        self.response_router = response_router
        self.contents: list[Any] = []

    async def generate_content(self, *, model, contents, config):  # noqa: ANN001
        self.contents.append(contents)
        prompt = contents[0] if isinstance(contents, list) and contents and isinstance(contents[0], str) else str(contents)
        if self.response_router is not None:
            return FakeResponse(self.response_router(str(prompt), len(self.contents)))
        return FakeResponse(self.response_text)


class ExtractionFakeClient:
    def __init__(self, response_text: str | None = None, response_router=None) -> None:  # noqa: ANN001
        self.files = ExtractionFakeFiles()
        self.models = ExtractionFakeModels(response_text=response_text, response_router=response_router)
        self.aio = SimpleNamespace(files=self.files, models=self.models)


def test_extract_anchor_terms_filters_stopwords_and_limits() -> None:
    text = "Explain quantum tunneling with detailed continuity and visuals for science students"
    anchors = extract_anchor_terms(text, limit=3)
    assert anchors == ["quantum", "tunneling", "detailed"]


def test_signal_model_tiering_defaults() -> None:
    with patch.dict(os.environ, {}, clear=True):
        assert GeminiStoryAgent._signal_structural_model() == "gemini-3.1-pro-preview"
        assert GeminiStoryAgent._signal_source_text_model() == "gemini-3-flash-preview"
        assert GeminiStoryAgent._planner_precompute_model() == "gemini-3-flash-preview"
        assert GeminiStoryAgent._signal_creative_model() == "gemini-3.1-pro-preview"


def test_validate_video_manifest_constraints_requires_transcript_for_longer_video() -> None:
    message = validate_video_manifest_constraints(
        source_manifest={
            "assets": [
                {
                    "asset_id": "video-1",
                    "modality": "video",
                    "uri": "http://example.com/video.mp4",
                    "duration_ms": 3 * 60 * 1000,
                }
            ]
        },
        source_text="",
        normalized_source_text="",
    )
    assert message is not None
    assert "longer than 2 minutes" in message


def test_validate_video_manifest_constraints_allows_longer_video_with_transcript() -> None:
    message = validate_video_manifest_constraints(
        source_manifest={
            "assets": [
                {
                    "asset_id": "video-1",
                    "modality": "video",
                    "uri": "http://example.com/video.mp4",
                    "duration_ms": 8 * 60 * 1000,
                }
            ]
        },
        source_text="Transcript text already provided.",
        normalized_source_text="",
    )
    assert message is None


def test_validate_video_manifest_constraints_rejects_too_long_video() -> None:
    message = validate_video_manifest_constraints(
        source_manifest={
            "assets": [
                {
                    "asset_id": "video-1",
                    "modality": "video",
                    "uri": "http://example.com/video.mp4",
                    "duration_ms": 11 * 60 * 1000,
                    "transcript_text": "Transcript available.",
                }
            ]
        },
        source_text="",
        normalized_source_text="",
    )
    assert message == "Video uploads are currently limited to 10 minutes."


def test_validate_video_manifest_constraints_allows_youtube_with_transcript_without_duration() -> None:
    message = validate_video_manifest_constraints(
        source_manifest={
            "assets": [
                {
                    "asset_id": "video-yt-1",
                    "modality": "video",
                    "uri": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "title": "Demo clip",
                }
            ]
        },
        source_text="Transcript text already provided.",
        normalized_source_text="",
    )
    assert message is None


def test_parse_json_object_response_unwraps_stringified_json_object() -> None:
    payload = GeminiStoryAgent._parse_json_object_response('"{\\"narrative_beats\\": [], \\"visual_candidates\\": []}"')
    assert payload == {"narrative_beats": [], "visual_candidates": []}


def test_generate_quick_artifact_uses_quick_model_and_normalizes_blocks() -> None:
    client = ExtractionFakeClient(
        response_text=json.dumps(
            {
                "artifact_id": "artifact-1",
                "title": "AI Moral Competence",
                "subtitle": "A fast structured brief",
                "summary": "Focus the audience on the central distinction.",
                "visual_style": "diagram",
                "hero_direction": "Clean editorial cover.",
                "blocks": [
                    {
                        "block_id": "hook",
                        "label": "Hook",
                        "title": "Why now",
                        "body": "LLMs are entering sensitive domains before evaluation standards are settled.",
                        "bullets": ["Sensitive domains", "Standards lagging"],
                        "visual_direction": "Hero tension frame",
                        "emphasis": "hook",
                    },
                    {
                        "block_id": "core",
                        "label": "Core",
                        "title": "What is missing",
                        "body": "Moral performance can look strong without durable moral competence.",
                        "bullets": [],
                        "visual_direction": "Two-column distinction",
                        "emphasis": "core",
                    },
                ],
            }
        )
    )
    agent = GeminiStoryAgent()
    agent.client = client

    result = asyncio.run(
        agent.generate_quick_artifact(
            QuickArtifactRequest(
                topic="Evaluating moral competence in LLMs",
                audience="Investors",
                tone="Executive",
                visual_mode="diagram",
            ),
            request=SimpleNamespace(url=SimpleNamespace(scheme="http", netloc="127.0.0.1:8000")),
        )
    )

    assert result["status"] == "success"
    artifact = QuickArtifactSchema.model_validate(result["artifact"])
    assert len(artifact.blocks) == 4
    assert client.models.contents
    assert "lightweight Quick mode" in str(client.models.contents[0])


def test_generate_quick_artifact_attaches_video_source_media_from_claims() -> None:
    client = ExtractionFakeClient(
        response_text=json.dumps(
            {
                "artifact_id": "artifact-2",
                "title": "Video-backed brief",
                "subtitle": "Grounded in clip evidence",
                "summary": "Quick artifact uses transcript-backed proof clips.",
                "visual_style": "hybrid",
                "hero_direction": "Lead with the on-screen reveal moment.",
                "blocks": [
                    {
                        "block_id": "hook",
                        "label": "Hook",
                        "title": "The reveal",
                        "body": "The CEO points to the key chart as the main inflection appears.",
                        "bullets": ["Lead with the reveal."],
                        "visual_direction": "Use the actual source clip.",
                        "emphasis": "hook",
                        "claim_refs": ["c1"],
                    },
                    {
                        "block_id": "core",
                        "label": "Core",
                        "title": "Context",
                        "body": "Explain why that visual matters.",
                        "bullets": [],
                        "visual_direction": "Keep the context clean.",
                        "emphasis": "core",
                        "claim_refs": ["c1"],
                    },
                    {
                        "block_id": "proof",
                        "label": "Proof",
                        "title": "Support",
                        "body": "Anchor the claim in the source media.",
                        "bullets": [],
                        "visual_direction": "Clip and callout.",
                        "emphasis": "proof",
                        "claim_refs": ["c1"],
                    },
                    {
                        "block_id": "takeaway",
                        "label": "Takeaway",
                        "title": "What matters",
                        "body": "Carry the implication forward.",
                        "bullets": [],
                        "visual_direction": "Tight close.",
                        "emphasis": "action",
                        "claim_refs": ["c1"],
                    },
                ],
            }
        )
    )
    agent = GeminiStoryAgent()
    agent.client = client

    result = asyncio.run(
        agent.generate_quick_artifact(
            QuickArtifactRequest(
                topic="Hardware launch recap",
                audience="Operators",
                tone="Practical",
                visual_mode="hybrid",
                source_manifest={
                    "assets": [
                        {
                            "asset_id": "video-1",
                            "modality": "video",
                            "uri": "http://example.com/launch.mp4",
                            "duration_ms": 90000,
                        }
                    ]
                },
                content_signal={
                    "thesis": {"one_liner": "The live demo reveal anchors the product message."},
                    "key_claims": [
                        {
                            "claim_id": "c1",
                            "claim_text": "The CEO reveals the new hardware while pointing to the adoption chart.",
                            "evidence_snippets": [
                                {
                                    "evidence_id": "e1",
                                    "modality": "video",
                                    "asset_id": "video-1",
                                    "start_ms": 12000,
                                    "end_ms": 18000,
                                    "transcript_text": "As you can see here, this adoption line bends upward right after launch.",
                                    "visual_context": "CEO on stage pointing to a chart with the adoption spike highlighted.",
                                }
                            ],
                        }
                    ],
                },
            ),
            request=SimpleNamespace(url=SimpleNamespace(scheme="http", netloc="127.0.0.1:8000")),
        )
    )

    assert result["status"] == "success"
    artifact = QuickArtifactSchema.model_validate(result["artifact"])
    assert artifact.blocks[0].source_media
    assert artifact.blocks[0].source_media[0].asset_id == "video-1"
    assert artifact.blocks[0].source_media[0].modality == "video"


def test_generate_quick_artifact_overwrites_model_source_media_and_generates_hero_image() -> None:
    client = ExtractionFakeClient(
        response_router=lambda prompt, index: json.dumps(
            {
                "artifact_id": "artifact-3",
                "title": "Video-backed brief",
                "subtitle": "Grounded in clip evidence",
                "summary": "Quick artifact uses transcript-backed proof clips.",
                "visual_style": "hybrid",
                "hero_direction": "Lead with the on-screen reveal moment.",
                "blocks": [
                    {
                        "block_id": "hook",
                        "label": "Hook",
                        "title": "The reveal",
                        "body": "The CEO points to the key chart as the main inflection appears.",
                        "bullets": [],
                        "visual_direction": "Use the actual source clip.",
                        "emphasis": "hook",
                        "claim_refs": ["c1"],
                        "evidence_refs": ["bogus-evidence"],
                        "source_media": [
                            {
                                "asset_id": "hallucinated-video",
                                "modality": "video",
                                "usage": "proof_clip",
                                "claim_refs": ["c1"],
                                "evidence_refs": ["bogus-evidence"],
                                "start_ms": 4,
                                "end_ms": 7,
                            }
                        ],
                    },
                    {
                        "block_id": "core",
                        "label": "Core",
                        "title": "Context",
                        "body": "Explain why that visual matters.",
                        "bullets": [],
                        "visual_direction": "Keep the context clean.",
                        "emphasis": "core",
                        "claim_refs": ["c1"],
                    },
                    {
                        "block_id": "proof",
                        "label": "Proof",
                        "title": "Support",
                        "body": "Anchor the claim in the source media.",
                        "bullets": [],
                        "visual_direction": "Clip and callout.",
                        "emphasis": "proof",
                        "claim_refs": ["c1"],
                    },
                    {
                        "block_id": "takeaway",
                        "label": "Takeaway",
                        "title": "What matters",
                        "body": "Carry the implication forward.",
                        "bullets": [],
                        "visual_direction": "Tight close.",
                        "emphasis": "action",
                        "claim_refs": ["c1"],
                    },
                ],
            }
            if index == 1
            else "{}"
        )
    )
    agent = GeminiStoryAgent()
    agent.client = client

    with patch.object(
        GeminiStoryAgent,
        "_generate_quick_hero_image",
        autospec=True,
        return_value="http://127.0.0.1:8000/static/assets/quick_hero_demo.png",
    ):
        result = asyncio.run(
            agent.generate_quick_artifact(
                QuickArtifactRequest(
                    topic="Hardware launch recap",
                    audience="Operators",
                    tone="Practical",
                    visual_mode="hybrid",
                    source_manifest={
                        "assets": [
                            {
                                "asset_id": "video-1",
                                "modality": "video",
                                "uri": "http://example.com/launch.mp4",
                                "duration_ms": 90000,
                            }
                        ]
                    },
                    content_signal={
                        "thesis": {"one_liner": "The live demo reveal anchors the product message."},
                        "key_claims": [
                            {
                                "claim_id": "c1",
                                "claim_text": "The CEO reveals the new hardware while pointing to the adoption chart.",
                                "evidence_snippets": [
                                    {
                                        "evidence_id": "e1",
                                        "modality": "video",
                                        "asset_id": "video-1",
                                        "start_ms": 12000,
                                        "end_ms": 18000,
                                        "transcript_text": "As you can see here, this adoption line bends upward right after launch.",
                                        "visual_context": "CEO on stage pointing to a chart with the adoption spike highlighted.",
                                    }
                                ],
                            }
                        ],
                    },
                ),
                request=SimpleNamespace(url=SimpleNamespace(scheme="http", netloc="127.0.0.1:8000")),
            )
        )

    artifact = QuickArtifactSchema.model_validate(result["artifact"])
    assert artifact.hero_image_url == "http://127.0.0.1:8000/static/assets/quick_hero_demo.png"
    assert artifact.blocks[0].source_media
    assert all(item.asset_id != "hallucinated-video" for item in artifact.blocks[0].source_media)
    assert "bogus-evidence" not in artifact.blocks[0].evidence_refs
    assert artifact.blocks[0].source_media[0].asset_id == "video-1"


def test_generate_quick_reel_builds_ordered_segments_from_blocks() -> None:
    agent = GeminiStoryAgent()

    result = asyncio.run(
        agent.generate_quick_reel(
            QuickReelRequest(
                artifact={
                    "artifact_id": "artifact-reel",
                    "title": "Battery launch brief",
                    "subtitle": "A fast operator update",
                    "summary": "Summarize the reveal, the proof, and the implication.",
                    "visual_style": "hybrid",
                    "hero_direction": "Use the reveal frame as the cover.",
                    "blocks": [
                        {
                            "block_id": "block-1",
                            "label": "Hook",
                            "title": "The reveal",
                            "body": "Lead with the reveal. Show the chart bend immediately. Keep the setup short.",
                            "bullets": [],
                            "visual_direction": "Use the actual reveal clip.",
                            "image_url": "http://127.0.0.1:8000/static/assets/hook.png",
                            "emphasis": "hook",
                            "claim_refs": ["c1"],
                            "evidence_refs": ["e1"],
                            "source_media": [
                                {
                                    "asset_id": "video-1",
                                    "modality": "video",
                                    "usage": "proof_clip",
                                    "claim_refs": ["c1"],
                                    "evidence_refs": ["e1"],
                                    "start_ms": 12000,
                                    "end_ms": 18000,
                                }
                            ],
                        },
                        {
                            "block_id": "block-2",
                            "label": "Proof",
                            "title": "Why it matters",
                            "body": "Move to the second proof beat. Explain the operator takeaway in one tight frame.",
                            "bullets": [],
                            "visual_direction": "Use a second source-backed moment.",
                            "image_url": "http://127.0.0.1:8000/static/assets/proof.png",
                            "emphasis": "proof",
                            "claim_refs": ["c2"],
                            "evidence_refs": ["e2"],
                            "source_media": [
                                {
                                    "asset_id": "video-1",
                                    "modality": "video",
                                    "usage": "proof_clip",
                                    "claim_refs": ["c1"],
                                    "evidence_refs": ["e1"],
                                    "start_ms": 12000,
                                    "end_ms": 18000,
                                },
                                {
                                    "asset_id": "video-1",
                                    "modality": "video",
                                    "usage": "proof_clip",
                                    "claim_refs": ["c2"],
                                    "evidence_refs": ["e2"],
                                    "start_ms": 26000,
                                    "end_ms": 32000,
                                },
                            ],
                        },
                        {
                            "block_id": "block-3",
                            "label": "Action",
                            "title": "Next move",
                            "body": "Close on the operator action. Keep it direct.",
                            "bullets": [],
                            "visual_direction": "Generated closing frame.",
                            "image_url": "http://127.0.0.1:8000/static/assets/action.png",
                            "emphasis": "action",
                            "claim_refs": ["c3"],
                            "evidence_refs": [],
                            "source_media": [],
                        },
                    ],
                },
                content_signal={
                    "key_claims": [
                        {"claim_id": "c1", "claim_text": "The first reveal shows the demand spike."},
                        {"claim_id": "c2", "claim_text": "The second moment ties the spike to operator action."},
                    ]
                },
                source_manifest={
                    "assets": [
                        {
                            "asset_id": "video-1",
                            "modality": "video",
                            "uri": "http://example.com/reveal.mp4",
                        }
                    ]
                },
            )
        )
    )

    assert result["status"] == "success"
    artifact = QuickArtifactSchema.model_validate(result["artifact"])
    assert artifact.reel is not None
    assert [segment.block_id for segment in artifact.reel.segments] == ["block-1", "block-2", "block-3"]
    assert artifact.reel.segments[0].render_mode == "hybrid"
    assert artifact.reel.segments[0].primary_media is not None
    assert artifact.reel.segments[0].primary_media.start_ms == 12000
    assert artifact.reel.segments[1].primary_media is not None
    assert artifact.reel.segments[1].primary_media.start_ms == 26000
    assert artifact.reel.segments[2].render_mode == "generated_image"
    assert artifact.reel.segments[2].fallback_image_url == "http://127.0.0.1:8000/static/assets/action.png"
    assert artifact.reel.segments[0].caption_text == "Lead with the reveal. Show the chart bend immediately."


def test_build_quick_video_segment_prefers_local_proof_clip_and_generated_visual() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "client": ("testclient", 50000),
        "server": ("127.0.0.1", 8000),
        "scheme": "http",
    }

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(scope, receive)

    artifact = QuickArtifactSchema.model_validate(
        {
            "artifact_id": "artifact-video",
            "title": "Video artifact",
            "subtitle": "Sub",
            "summary": "Summary",
            "visual_style": "hybrid",
            "hero_direction": "Hero",
            "reel": {
                "reel_id": "artifact-video-reel",
                "title": "Video artifact proof reel",
                "summary": "Three segments.",
                "segments": [
                    {
                        "segment_id": "artifact-video-segment-1",
                        "block_id": "block-1",
                        "title": "Proof clip",
                        "render_mode": "hybrid",
                        "caption_text": "Explain the clip, then show the proof.",
                        "claim_refs": ["c1"],
                        "evidence_refs": ["e1"],
                        "primary_media": {
                            "asset_id": "video-1",
                            "modality": "video",
                            "usage": "proof_clip",
                            "claim_refs": ["c1"],
                            "evidence_refs": ["e1"],
                            "start_ms": 1000,
                            "end_ms": 5000,
                        },
                        "fallback_image_url": "http://127.0.0.1:8000/static/assets/generated.png",
                        "start_ms": 1000,
                        "end_ms": 5000,
                        "timing_inferred": False,
                    }
                ],
            },
            "blocks": [],
        }
    )

    with patch("app.services.video_pipeline.generate_audio_and_get_url", return_value="http://127.0.0.1:8000/static/assets/voice.mp3") as audio_mock, patch(
        "app.services.video_pipeline._audio_duration_ms",
        return_value=2400,
    ), patch(
        "app.services.video_pipeline.asset_path_from_reference",
        side_effect=lambda ref: Path("/tmp/demo.mp4") if ref else None,
    ):
        segment = build_quick_video_segment(
            request=request,
            artifact=artifact,
            segment=artifact.reel.segments[0],
            source_manifest={
                "assets": [
                    {
                        "asset_id": "video-1",
                        "modality": "video",
                        "uri": "http://127.0.0.1:8000/static/assets/source.mp4",
                        "duration_ms": 30000,
                    }
                ]
            },
        )

    assert segment.render_mode == "image_plus_clip"
    assert segment.voiceover_url == "http://127.0.0.1:8000/static/assets/voice.mp3"
    assert segment.visual_url == "http://127.0.0.1:8000/static/assets/generated.png"
    assert segment.source_video_url == "http://127.0.0.1:8000/static/assets/source.mp4"
    assert segment.source_start_ms == 1000
    assert segment.source_end_ms == 5000
    assert segment.duration_ms == 6400
    assert audio_mock.call_args.kwargs["playback_rate"] == 1.1


def test_build_quick_video_segment_uses_artifact_block_image_when_reel_fallback_missing() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "client": ("testclient", 50000),
        "server": ("127.0.0.1", 8000),
        "scheme": "http",
    }

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(scope, receive)
    artifact = QuickArtifactSchema.model_validate(
        {
            "artifact_id": "artifact-video",
            "title": "Prompt-only artifact",
            "subtitle": "Sub",
            "summary": "Summary",
            "visual_style": "diagram",
            "hero_direction": "Hero",
            "reel": {
                "reel_id": "artifact-video-reel",
                "title": "Video artifact proof reel",
                "summary": "One segment.",
                "segments": [
                    {
                        "segment_id": "artifact-video-segment-1",
                        "block_id": "block-1",
                        "title": "Generated panel",
                        "render_mode": "generated_image",
                        "caption_text": "Explain the generated visual.",
                        "claim_refs": [],
                        "evidence_refs": [],
                        "fallback_image_url": None,
                        "timing_inferred": False,
                    }
                ],
            },
            "blocks": [
                {
                    "block_id": "block-1",
                    "label": "Hook",
                    "title": "Generated panel",
                    "body": "Explain the generated visual.",
                    "bullets": [],
                    "visual_direction": "Use the generated visual.",
                    "image_url": "http://127.0.0.1:8000/static/assets/generated.png",
                    "emphasis": "hook",
                    "claim_refs": [],
                    "evidence_refs": [],
                    "source_media": [],
                }
            ],
        }
    )

    with patch("app.services.video_pipeline.generate_audio_and_get_url", return_value=""), patch(
        "app.services.video_pipeline.asset_path_from_reference",
        side_effect=lambda ref: Path("/tmp/generated.png") if ref else None,
    ):
        segment = build_quick_video_segment(
            request=request,
            artifact=artifact,
            segment=artifact.reel.segments[0],
            source_manifest=None,
        )

    assert segment.render_mode == "image_only"
    assert segment.visual_url == "http://127.0.0.1:8000/static/assets/generated.png"


def test_generate_quick_video_builds_reel_if_missing_and_attaches_video() -> None:
    agent = GeminiStoryAgent()

    with patch(
        "app.services.gemini_story_agent.build_quick_video",
        return_value=QuickVideoSchema(
            video_id="artifact-video-1",
            video_url="http://127.0.0.1:8000/static/assets/quick_video_demo.mp4",
            duration_ms=12345,
            segments=[],
        ),
    ):
        result = asyncio.run(
            agent.generate_quick_video(
                QuickVideoRequest(
                    artifact={
                        "artifact_id": "artifact-video",
                        "title": "Battery launch brief",
                        "subtitle": "A fast operator update",
                        "summary": "Summarize the reveal and implication.",
                        "visual_style": "hybrid",
                        "hero_direction": "Use the reveal frame as the cover.",
                        "blocks": [
                            {
                                "block_id": "block-1",
                                "label": "Hook",
                                "title": "The reveal",
                                "body": "Lead with the reveal.",
                                "bullets": [],
                                "visual_direction": "Use the actual reveal clip.",
                                "image_url": "http://127.0.0.1:8000/static/assets/hook.png",
                                "emphasis": "hook",
                                "claim_refs": ["c1"],
                                "evidence_refs": ["e1"],
                                "source_media": [
                                    {
                                        "asset_id": "video-1",
                                        "modality": "video",
                                        "usage": "proof_clip",
                                        "claim_refs": ["c1"],
                                        "evidence_refs": ["e1"],
                                        "start_ms": 12000,
                                        "end_ms": 18000,
                                    }
                                ],
                            }
                        ],
                    },
                    source_manifest={
                        "assets": [
                            {
                                "asset_id": "video-1",
                                "modality": "video",
                                "uri": "http://127.0.0.1:8000/static/assets/reveal.mp4",
                            }
                        ]
                    },
                    content_signal={
                        "key_claims": [
                            {"claim_id": "c1", "claim_text": "The reveal shows the demand spike."},
                        ]
                    },
                ),
                request=SimpleNamespace(base_url="http://127.0.0.1:8000/"),
            )
        )

    assert result["status"] == "success"
    artifact = QuickArtifactSchema.model_validate(result["artifact"])
    assert artifact.reel is not None
    assert artifact.video is not None
    assert artifact.video.video_url == "http://127.0.0.1:8000/static/assets/quick_video_demo.mp4"


def test_populate_quick_block_visuals_generates_images_even_for_source_backed_blocks() -> None:
    agent = GeminiStoryAgent()
    artifact = QuickArtifactSchema.model_validate(
        {
            "artifact_id": "artifact-visuals",
            "title": "Visualized artifact",
            "subtitle": "Testing block visuals",
            "summary": "Each block should have a visible visual treatment.",
            "visual_style": "illustration",
            "hero_direction": "Clean hero.",
            "blocks": [
                {
                    "block_id": "block-1",
                    "label": "Hook",
                    "title": "Needs generated image",
                    "body": "This block has no source media.",
                    "bullets": [],
                    "visual_direction": "Strong symbolic opener.",
                    "emphasis": "hook",
                },
                {
                    "block_id": "block-2",
                    "label": "Proof",
                    "title": "Uses source clip",
                    "body": "This block already has source media.",
                    "bullets": [],
                    "visual_direction": "Reuse the clip.",
                    "emphasis": "proof",
                    "source_media": [
                        {
                            "asset_id": "video-1",
                            "modality": "video",
                            "usage": "proof_clip",
                            "claim_refs": ["c1"],
                            "evidence_refs": ["e1"],
                            "start_ms": 12000,
                            "end_ms": 18000,
                        }
                    ],
                },
            ],
        }
    )

    with patch.object(
        GeminiStoryAgent,
        "_generate_quick_block_image",
        new=AsyncMock(return_value="http://127.0.0.1:8000/static/assets/quick_block_demo.png"),
    ) as block_image_mock:
        visualized = asyncio.run(
            agent._populate_quick_block_visuals(
                request=SimpleNamespace(url=SimpleNamespace(scheme="http", netloc="127.0.0.1:8000")),
                topic="Demo topic",
                audience="Operators",
                tone="Practical",
                visual_mode="illustration",
                artifact=artifact,
                content_signal={},
            )
        )

    assert visualized.blocks[0].image_url == "http://127.0.0.1:8000/static/assets/quick_block_demo.png"
    assert visualized.blocks[1].image_url == "http://127.0.0.1:8000/static/assets/quick_block_demo.png"
    assert block_image_mock.await_count == 2


def test_structured_evidence_refs_normalizes_string_video_timecodes() -> None:
    by_claim, _, _ = GeminiStoryAgent._structured_evidence_refs(
        {
            "key_claims": [
                {
                    "claim_id": "c1",
                    "claim_text": "The CEO points to the adoption spike.",
                    "evidence_snippets": [
                        {
                            "evidence_id": "e1",
                            "modality": "video",
                            "asset_id": "video-1",
                            "start_ms": "00:12",
                            "end_ms": "00:18",
                            "transcript_text": "As you can see here, the line bends upward.",
                        }
                    ],
                },
                {
                    "claim_id": "c2",
                    "claim_text": "The second clip uses second-based numerics.",
                    "evidence_snippets": [
                        {
                            "evidence_id": "e2",
                            "modality": "video",
                            "asset_id": "video-1",
                            "start_ms": "24",
                            "end_ms": "31",
                            "transcript_text": "This second segment starts later in the clip.",
                        }
                    ],
                },
            ]
        },
        {
            "assets": [
                {
                    "asset_id": "video-1",
                    "modality": "video",
                    "uri": "http://example.com/video.mp4",
                    "duration_ms": 90000,
                }
            ]
        },
    )

    assert by_claim["c1"][0].start_ms == 12000
    assert by_claim["c1"][0].end_ms == 18000
    assert by_claim["c2"][0].start_ms == 24000
    assert by_claim["c2"][0].end_ms == 31000


def test_structured_evidence_refs_infers_short_proof_window_when_video_end_missing() -> None:
    by_claim, _, _ = GeminiStoryAgent._structured_evidence_refs(
        {
            "key_claims": [
                {
                    "claim_id": "c1",
                    "claim_text": "The keynote moment begins here.",
                    "evidence_snippets": [
                        {
                            "evidence_id": "e1",
                            "modality": "video",
                            "asset_id": "video-1",
                            "start_ms": "00:45",
                            "transcript_text": "Here is the main reveal moment.",
                        }
                    ],
                }
            ]
        },
        {
            "assets": [
                {
                    "asset_id": "video-1",
                    "modality": "video",
                    "uri": "https://www.youtube.com/watch?v=demo",
                }
            ]
        },
    )

    assert by_claim["c1"][0].start_ms == 45000
    assert by_claim["c1"][0].end_ms == 60000
    assert by_claim["c1"][0].timing_inferred is True


def test_transcript_only_video_prompts_include_no_frame_access_guardrail() -> None:
    prompt = GeminiStoryAgent._build_structural_signal_prompt(
        document_text="As you can see here, this chart changes after launch.",
        source_inventory_text="- youtube-1: video | Demo clip",
        transcript_only_video=True,
    )
    assert "without direct frame access" in prompt
    assert "do not invent exact visual details" in prompt


def test_pdf_prompts_discourage_frontmatter_overuse() -> None:
    structural_prompt = GeminiStoryAgent._build_structural_signal_prompt(
        document_text="A roadmap for evaluating moral competence in large language models.",
        source_inventory_text="- asset-pdf-1: pdf_page | paper.pdf | application/pdf",
        transcript_only_video=False,
    )
    one_pass_prompt = GeminiStoryAgent._build_signal_extraction_prompt(
        document_text="A roadmap for evaluating moral competence in large language models.",
        schema_text='{"type":"object"}',
        version="v2",
        source_inventory_text="- asset-pdf-1: pdf_page | paper.pdf | application/pdf",
        transcript_only_video=False,
    )

    assert "prefer later body-page evidence" in structural_prompt
    assert "Avoid anchoring most claims to abstract/frontmatter evidence" in structural_prompt
    assert "do not anchor most claims to the abstract" in one_pass_prompt
    assert "Use frontmatter evidence mainly for opener context" in one_pass_prompt


def test_regenerate_quick_block_preserves_block_id() -> None:
    client = ExtractionFakeClient(
        response_text=json.dumps(
            {
                "block_id": "wrong-id",
                "label": "Proof",
                "title": "Sharper evidence",
                "body": "Use the strongest study result and cut the rest.",
                "bullets": ["Lead with the main metric."],
                "visual_direction": "Single decisive chart.",
                "emphasis": "proof",
            }
        )
    )
    agent = GeminiStoryAgent()
    agent.client = client

    result = asyncio.run(
        agent.regenerate_quick_block(
            QuickBlockOverrideRequest(
                topic="Evaluating moral competence in LLMs",
                audience="Investors",
                tone="Executive",
                visual_mode="diagram",
                artifact={
                    "artifact_id": "artifact-1",
                    "title": "AI Moral Competence",
                    "subtitle": "A fast structured brief",
                    "summary": "Focus the audience on the central distinction.",
                    "visual_style": "diagram",
                    "hero_direction": "Clean editorial cover.",
                    "blocks": [
                        {
                            "block_id": "proof-block",
                            "label": "Proof",
                            "title": "What supports it",
                            "body": "Current evidence is uneven across tasks.",
                            "bullets": ["Benchmarks diverge."],
                            "visual_direction": "Comparison cue.",
                            "emphasis": "proof",
                        }
                    ],
                },
                block_id="proof-block",
                instruction="Make this block more executive and sharper.",
            ),
            request=SimpleNamespace(url=SimpleNamespace(scheme="http", netloc="127.0.0.1:8000")),
        )
    )

    assert result["status"] == "success"
    assert result["block"]["block_id"] == "proof-block"
    assert result["block"]["title"] == "Sharper evidence"


def test_regenerate_quick_block_generates_visual_for_source_backed_block() -> None:
    client = ExtractionFakeClient(
        response_text=json.dumps(
            {
                "block_id": "block-4",
                "label": "Takeaway",
                "title": "Close with a diagram",
                "body": "Summarize the flow in one decisive panel.",
                "bullets": ["Use a schematic instead of raw footage."],
                "visual_direction": "A clean diagram that simplifies the sequence.",
                "emphasis": "action",
                "claim_refs": ["claim-4"],
            }
        )
    )
    agent = GeminiStoryAgent()
    agent.client = client
    agent._generate_quick_block_image = AsyncMock(return_value="http://127.0.0.1:8000/static/assets/override-diagram.png")

    result = asyncio.run(
        agent.regenerate_quick_block(
            QuickBlockOverrideRequest(
                topic="Protein folding",
                audience="Investors",
                tone="Executive",
                visual_mode="diagram",
                artifact={
                    "artifact_id": "artifact-1",
                    "title": "Protein Folding",
                    "subtitle": "A fast structured brief",
                    "summary": "Focus on why the mechanism matters.",
                    "visual_style": "diagram",
                    "hero_direction": "Clean editorial cover.",
                    "blocks": [
                        {
                            "block_id": "block-4",
                            "label": "Takeaway",
                            "title": "What to do with it",
                            "body": "End on the practical implication.",
                            "bullets": ["Keep the close memorable."],
                            "visual_direction": "Closing module with synthesis and one action cue.",
                            "emphasis": "action",
                            "claim_refs": ["claim-4"],
                            "source_media": [
                                SourceMediaRefSchema(
                                    asset_id="video-1",
                                    modality="video",
                                    usage="proof_clip",
                                    claim_refs=["claim-4"],
                                    evidence_refs=["evidence-4"],
                                    start_ms=2000,
                                    end_ms=6000,
                                ).model_dump()
                            ],
                        }
                    ],
                },
                block_id="block-4",
                instruction="I need a diagram here.",
            ),
            request=SimpleNamespace(url=SimpleNamespace(scheme="http", netloc="127.0.0.1:8000")),
        )
    )

    assert result["status"] == "success"
    assert result["block"]["image_url"] == "http://127.0.0.1:8000/static/assets/override-diagram.png"
    assert result["block"]["source_media"][0]["asset_id"] == "video-1"


def test_regenerate_quick_block_surfaces_model_failure() -> None:
    client = ExtractionFakeClient(response_router=lambda prompt, index: (_ for _ in ()).throw(RuntimeError("model exploded")))
    agent = GeminiStoryAgent()
    agent.client = client

    result = asyncio.run(
        agent.regenerate_quick_block(
            QuickBlockOverrideRequest(
                topic="Evaluating moral competence in LLMs",
                audience="Investors",
                tone="Executive",
                visual_mode="diagram",
                artifact={
                    "artifact_id": "artifact-1",
                    "title": "AI Moral Competence",
                    "subtitle": "A fast structured brief",
                    "summary": "Focus the audience on the central distinction.",
                    "visual_style": "diagram",
                    "hero_direction": "Clean editorial cover.",
                    "blocks": [
                        {
                            "block_id": "proof-block",
                            "label": "Proof",
                            "title": "What supports it",
                            "body": "Current evidence is uneven across tasks.",
                            "bullets": ["Benchmarks diverge."],
                            "visual_direction": "Comparison cue.",
                            "emphasis": "proof",
                        }
                    ],
                },
                block_id="proof-block",
                instruction="Make this block more executive and sharper.",
            ),
            request=SimpleNamespace(url=SimpleNamespace(scheme="http", netloc="127.0.0.1:8000")),
        )
    )

    assert result["status"] == "error"
    assert "Block override failed" in result["message"]


def test_regenerate_quick_artifact_preserves_blocks_before_anchor() -> None:
    client = ExtractionFakeClient(
        response_text=json.dumps(
            {
                "artifact_id": "artifact-1",
                "title": "New title",
                "subtitle": "New subtitle",
                "summary": "New summary",
                "visual_style": "diagram",
                "hero_direction": "Sharper cover.",
                "blocks": [
                    {
                        "block_id": "block-1",
                        "label": "Hook",
                        "title": "Rewritten hook",
                        "body": "Rewritten opener.",
                        "bullets": [],
                        "visual_direction": "New opener.",
                        "emphasis": "hook",
                    },
                    {
                        "block_id": "block-2",
                        "label": "Core",
                        "title": "Rewritten core",
                        "body": "Rewritten core block.",
                        "bullets": [],
                        "visual_direction": "New core.",
                        "emphasis": "core",
                    },
                    {
                        "block_id": "block-3",
                        "label": "Proof",
                        "title": "Rewritten proof",
                        "body": "Rewritten proof block.",
                        "bullets": [],
                        "visual_direction": "New proof.",
                        "emphasis": "proof",
                    },
                    {
                        "block_id": "block-4",
                        "label": "Action",
                        "title": "Rewritten action",
                        "body": "Rewritten action block.",
                        "bullets": [],
                        "visual_direction": "New action.",
                        "emphasis": "action",
                    },
                ],
            }
        )
    )
    agent = GeminiStoryAgent()
    agent.client = client

    result = asyncio.run(
        agent.regenerate_quick_artifact(
            QuickArtifactOverrideRequest(
                topic="Evaluating moral competence in LLMs",
                audience="Investors",
                tone="Executive",
                visual_mode="diagram",
                artifact={
                    "artifact_id": "artifact-1",
                    "title": "Original title",
                    "subtitle": "Original subtitle",
                    "summary": "Original summary",
                    "visual_style": "diagram",
                    "hero_direction": "Original cover.",
                    "blocks": [
                        {
                            "block_id": "block-1",
                            "label": "Hook",
                            "title": "Keep me",
                            "body": "Original opener.",
                            "bullets": [],
                            "visual_direction": "Original opener cue.",
                            "emphasis": "hook",
                        },
                        {
                            "block_id": "block-2",
                            "label": "Core",
                            "title": "Change me",
                            "body": "Original core block.",
                            "bullets": [],
                            "visual_direction": "Original core cue.",
                            "emphasis": "core",
                        },
                        {
                            "block_id": "block-3",
                            "label": "Proof",
                            "title": "Change me too",
                            "body": "Original proof block.",
                            "bullets": [],
                            "visual_direction": "Original proof cue.",
                            "emphasis": "proof",
                        },
                        {
                            "block_id": "block-4",
                            "label": "Action",
                            "title": "Change me three",
                            "body": "Original action block.",
                            "bullets": [],
                            "visual_direction": "Original action cue.",
                            "emphasis": "action",
                        },
                    ],
                },
                instruction="Make the rest more academic.",
                anchor_block_id="block-2",
            ),
            request=SimpleNamespace(url=SimpleNamespace(scheme="http", netloc="127.0.0.1:8000")),
        )
    )

    assert result["status"] == "success"
    updated_artifact = QuickArtifactSchema.model_validate(result["artifact"])
    assert updated_artifact.blocks[0].title == "Keep me"
    assert updated_artifact.blocks[1].title == "Rewritten core"
    assert updated_artifact.title == "Original title"


def test_regenerate_quick_artifact_surfaces_model_failure() -> None:
    client = ExtractionFakeClient(response_router=lambda prompt, index: (_ for _ in ()).throw(RuntimeError("model exploded")))
    agent = GeminiStoryAgent()
    agent.client = client

    result = asyncio.run(
        agent.regenerate_quick_artifact(
            QuickArtifactOverrideRequest(
                topic="Evaluating moral competence in LLMs",
                audience="Investors",
                tone="Executive",
                visual_mode="diagram",
                artifact={
                    "artifact_id": "artifact-1",
                    "title": "Original title",
                    "subtitle": "Original subtitle",
                    "summary": "Original summary",
                    "visual_style": "diagram",
                    "hero_direction": "Original cover.",
                    "blocks": [
                        {
                            "block_id": "block-1",
                            "label": "Hook",
                            "title": "Keep me",
                            "body": "Original opener.",
                            "bullets": [],
                            "visual_direction": "Original opener cue.",
                            "emphasis": "hook",
                        },
                        {
                            "block_id": "block-2",
                            "label": "Core",
                            "title": "Change me",
                            "body": "Original core block.",
                            "bullets": [],
                            "visual_direction": "Original core cue.",
                            "emphasis": "core",
                        },
                    ],
                },
                instruction="Make the rest more academic.",
                anchor_block_id="block-2",
            ),
            request=SimpleNamespace(url=SimpleNamespace(scheme="http", netloc="127.0.0.1:8000")),
        )
    )

    assert result["status"] == "error"
    assert "Global override failed" in result["message"]


def test_normalized_scene_id_defaults_when_missing() -> None:
    assert normalized_scene_id("", 2) == "scene-2"
    assert normalized_scene_id(" custom-scene ", 2) == "custom-scene"


def test_evaluate_scene_quality_pass_with_expected_content() -> None:
    scene = ScriptPackScene(
        scene_id="scene-1",
        title="Core concept",
        scene_goal="Explain it",
        narration_focus="quantum tunneling barrier transition",
        visual_prompt="clean diagram",
        claim_refs=["c1"],
        continuity_refs=["previous barrier"],
        acceptance_checks=["50-100 words"],
    )
    text = (
        "Quantum tunneling describes how particles transition through a barrier that would seem "
        "impossible in classical physics. This scene connects the previous barrier setup to the "
        "probability wave behavior and highlights why transition rates change with barrier width."
    )
    result = evaluate_scene_quality(
        scene=scene,
        generated_text=text,
        image_url="http://localhost/image.png",
        must_include=["quantum"],
        must_avoid=["gibberish"],
        continuity_hints=["previous barrier"],
        attempt=1,
    )
    assert result["status"] in {"PASS", "WARN"}
    assert result["scene_id"] == "scene-1"
    assert result["attempt"] == 1


def test_evaluate_scene_quality_allows_shorter_thumbnail_support_copy() -> None:
    scene = ScriptPackScene(
        scene_id="scene-1",
        title="What is the flaw",
        scene_goal="Create an instantly legible hero thumbnail.",
        narration_focus="Show the hook fast.",
        visual_prompt="A bold thumbnail hero frame.",
        claim_refs=["c1"],
        continuity_refs=[],
        acceptance_checks=["Narration is between 18 and 40 words."],
        scene_mode="static",
        layout_template="hero_thumbnail",
    )
    text = "A hidden flaw hides in plain sight, and this frame turns that reveal into one sharp, curiosity-first visual cue."
    result = evaluate_scene_quality(
        scene=scene,
        generated_text=text,
        image_url="http://localhost/image.png",
        must_include=[],
        must_avoid=[],
        continuity_hints=[],
        attempt=1,
    )
    assert result["status"] in {"PASS", "WARN"}
    assert result["word_count"] < 45


def test_evaluate_scene_quality_uses_artifact_type_when_layout_template_is_missing() -> None:
    scene = ScriptPackScene(
        scene_id="scene-1",
        title="Hidden flaw",
        scene_goal="Create a thumbnail.",
        narration_focus="Show the hidden flaw fast.",
        visual_prompt="A bold thumbnail hero frame.",
        claim_refs=["c1"],
        continuity_refs=[],
        acceptance_checks=["Narration is between 18 and 40 words."],
        scene_mode="static",
        layout_template=None,
    )
    text = "A hidden flaw changes the outcome, and this cover turns that reveal into one clear, curiosity-first hook."
    result = evaluate_scene_quality(
        scene=scene,
        generated_text=text,
        image_url="http://localhost/image.png",
        must_include=[],
        must_avoid=[],
        continuity_hints=[],
        attempt=1,
        artifact_type="slide_thumbnail",
    )
    assert result["status"] in {"PASS", "WARN"}
    assert not any("target 50-100" in reason for reason in result["reasons"])


def test_compose_thumbnail_cover_and_get_url_adds_overlay_elements() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    request = Request(scope)

    image = Image.new("RGB", (1280, 720), (24, 32, 72))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    source_url = save_image_and_get_url(
        request=request,
        scene_id="scene-1",
        image_bytes=buffer.getvalue(),
        prefix="unit_thumb_source",
    )

    composed_url = compose_thumbnail_cover_and_get_url(
        request=request,
        scene_id="scene-1",
        source_url=source_url,
        title="Traders are shifting to short-term risk",
        support_text="Traders are shifting to short-term single-stock options, creating concentrated left-tail jump risk.",
        cue_lines=["Short-term options surge", "Left-tail jump risk"],
        prefix="unit_thumb_cover",
    )

    source_path = asset_path_from_url(source_url)
    composed_path = asset_path_from_url(composed_url)
    assert source_path is not None
    assert composed_path is not None
    assert composed_path.exists()

    with Image.open(source_path) as original, Image.open(composed_path) as composed:
        original_rgba = original.convert("RGBA")
        composed_rgba = composed.convert("RGBA")
        assert composed_rgba.size == original_rgba.size
        diff = ImageChops.difference(original_rgba.convert("RGB"), composed_rgba.convert("RGB"))
        assert diff.getbbox() is not None


def test_build_sse_event_serializes_payload() -> None:
    event = build_sse_event("status", {"message": "ok"})
    assert event["event"] == "status"
    assert event["data"] == '{"message": "ok"}'


def test_locate_excerpt_in_page_text_returns_line_window_for_matching_query() -> None:
    page_text = "\n".join(
        [
            "Introduction",
            "Large language models are increasingly deployed in sensitive domains.",
            "We propose a roadmap for evaluating moral competence in large language models.",
            "The framework distinguishes surface performance from genuine competence.",
            "Conclusion",
        ]
    )

    result = locate_excerpt_in_page_text(
        page_text=page_text,
        query_text="evaluating moral competence in large language models",
    )

    assert result is not None
    assert result["line_start"] == 3
    assert result["line_end"] == 3
    assert "roadmap for evaluating moral competence" in str(result["matched_excerpt"]).lower()


def test_append_text_part_handles_incremental_chunks() -> None:
    text, delta = append_text_part("", "Hello")
    assert text == "Hello"
    assert delta == "Hello"

    text, delta = append_text_part(text, " world")
    assert text == "Hello world"
    assert delta == " world"


def test_append_text_part_handles_cumulative_chunks_without_duplication() -> None:
    text, delta = append_text_part("", "Hello")
    assert text == "Hello"
    assert delta == "Hello"

    text, delta = append_text_part(text, "Hello world")
    assert text == "Hello world"
    assert delta == " world"

    text, delta = append_text_part(text, "Hello world")
    assert text == "Hello world"
    assert delta == ""


def test_signal_extraction_prompt_versions_are_available() -> None:
    schema = '{"type":"object"}'
    source = "Sample source text."
    v1_prompt = GeminiStoryAgent._build_signal_extraction_prompt(
        document_text=source,
        schema_text=schema,
        version="v1",
    )
    v2_prompt = GeminiStoryAgent._build_signal_extraction_prompt(
        document_text=source,
        schema_text=schema,
        version="v2",
    )
    assert "Analyze the following document" in v1_prompt
    assert "ONE RUN" in v2_prompt
    assert "JSON SCHEMA" in v1_prompt
    assert "JSON SCHEMA" in v2_prompt


def test_extract_signal_uploads_source_assets_and_cleans_up_gemini_files() -> None:
    async def run() -> None:
        asset_path = Path(__file__).resolve().parents[1] / "app" / "static" / "assets" / "unit_extract_audio.mp3"
        asset_path.write_bytes(b"fake-audio")

        try:
            structural_payload = {
                "version": "v1.0",
                "source": {
                    "source_id": "src-1",
                    "source_type": "transcript",
                    "language": "en",
                    "input_length_tokens": 32,
                },
                "thesis": {
                    "one_liner": "Audio evidence can ground key claims.",
                    "expanded_summary": "The uploaded audio provides direct grounding for the extracted claims.",
                },
                "key_claims": [
                    {
                        "claim_id": "c1",
                        "claim_text": "Uploaded audio grounds the main claim.",
                        "supporting_points": ["The speaker states the key result directly."],
                        "evidence_snippets": [
                            {
                                "evidence_id": "e1",
                                "type": "audio",
                                "asset_id": "asset-audio-1",
                                "start_ms": 1000,
                                "end_ms": 4000,
                                "transcript_text": "The test result drops power use by forty percent.",
                            }
                        ],
                        "confidence": 0.94,
                    }
                ],
                "concepts": [
                    {
                        "concept_id": "k1",
                        "label": "power efficiency",
                        "definition": "Lower energy use under the new design.",
                        "importance": 5,
                    }
                ],
                "open_questions": [],
                "signal_quality": {
                    "coverage_score": 0.9,
                    "ambiguity_score": 0.2,
                    "hallucination_risk": 0.1,
                },
            }
            creative_payload = {
                "narrative_beats": [
                    {"beat_id": "b1", "role": "hook", "message": "The result is measured directly.", "claim_refs": ["c1"]},
                    {"beat_id": "b2", "role": "mechanism", "message": "The audio states the result.", "claim_refs": ["c1"]},
                    {"beat_id": "b3", "role": "takeaway", "message": "Use the quote as proof.", "claim_refs": ["c1"]},
                ],
                "visual_candidates": [
                    {
                        "candidate_id": "v1",
                        "purpose": "Show the measured change.",
                        "recommended_structure": "comparison",
                        "claim_refs": ["c1"],
                    }
                ],
            }

            def response_router(prompt: str, call_count: int) -> str:
                if "recover clean reading-order source text" in prompt:
                    return json.dumps(
                        {
                            "normalized_source_text": "The test result drops power use by forty percent.",
                            "source_text_origin": "audio_transcript",
                        }
                    )
                if "structural truth layer" in prompt:
                    return json.dumps(structural_payload)
                if "creative structuring layer" in prompt:
                    return json.dumps(creative_payload)
                raise AssertionError(f"Unexpected extraction prompt: {prompt[:120]}")

            agent = object.__new__(GeminiStoryAgent)
            agent.client = ExtractionFakeClient(response_router=response_router)

            result = await agent.extract_signal(
                SignalExtractionRequest(
                    input_text="",
                    source_manifest={
                        "assets": [
                            {
                                "asset_id": "asset-audio-1",
                                "modality": "audio",
                                "uri": str(asset_path),
                                "mime_type": "audio/mpeg",
                                "title": "unit_extract_audio.mp3",
                            }
                        ]
                    },
                )
            )

            assert result["status"] == "success"
            uploaded = agent.client.files.upload_calls
            deleted = agent.client.files.deleted_names
            assert len(uploaded) == 1
            assert uploaded[0][0].endswith("unit_extract_audio.mp3")
            assert uploaded[0][1] == "audio/mpeg"
            assert deleted == ["files/1"]
            assert result["normalized_source_text"] == "The test result drops power use by forty percent."
            assert result["source_text_origin"] == "audio_transcript"
            assert result["content_signal"]["narrative_beats"][0]["claim_refs"] == ["c1"]
            assert result["trace"]["checkpoints"][-1]["details"]["uploaded_asset_count"] == 1
            contents = agent.client.models.contents[0]
            assert isinstance(contents, list)
            assert any(
                isinstance(item, str) and "SOURCE ASSET INVENTORY" in item and "asset-audio-1" in item
                for item in contents
            )
            part = next(item for item in contents if not isinstance(item, str))
            assert part.model_dump()["file_data"]["file_uri"] == "gs://demo/uploaded-1"
            assert any(
                isinstance(item, str) and "structural truth layer" in item
                for item in agent.client.models.contents[1]
            )
        finally:
            asset_path.unlink(missing_ok=True)

    asyncio.run(run())


def test_extract_signal_prefers_manifest_embedded_text_before_gemini_recovery() -> None:
    async def run() -> None:
        asset_path = Path(__file__).resolve().parents[1] / "app" / "static" / "assets" / "unit_extract_pdf.pdf"
        asset_path.write_bytes(b"%PDF-1.4 fake")

        try:
            structural_payload = {
                "version": "v1.0",
                "source": {
                    "source_id": "src-1",
                    "source_type": "document",
                    "language": "en",
                    "input_length_tokens": 32,
                },
                "thesis": {
                    "one_liner": "Recovered PDF text should drive the signal.",
                    "expanded_summary": "The embedded normalized text stays available for planning.",
                },
                "key_claims": [
                    {
                        "claim_id": "c1",
                        "claim_text": "The PDF argues for a roadmap.",
                        "supporting_points": ["The source text states the roadmap directly."],
                        "evidence_snippets": [
                            {
                                "evidence_id": "e1",
                                "type": "pdf_page",
                                "asset_id": "asset-pdf-1",
                                "page_index": 1,
                                "transcript_text": "A roadmap for evaluating moral competence in large language models.",
                            }
                        ],
                        "confidence": 0.92,
                    }
                ],
                "concepts": [],
                "open_questions": [],
                "signal_quality": {
                    "coverage_score": 0.9,
                    "ambiguity_score": 0.2,
                    "hallucination_risk": 0.1,
                },
            }
            creative_payload = {
                "narrative_beats": [
                    {"beat_id": "b1", "role": "hook", "message": "The roadmap reframes evaluation.", "claim_refs": ["c1"]},
                    {"beat_id": "b2", "role": "mechanism", "message": "The source defines moral competence carefully.", "claim_refs": ["c1"]},
                    {"beat_id": "b3", "role": "takeaway", "message": "Use the roadmap as the organizing frame.", "claim_refs": ["c1"]},
                ],
                "visual_candidates": [
                    {
                        "candidate_id": "v1",
                        "purpose": "Show the roadmap structure.",
                        "recommended_structure": "process",
                        "claim_refs": ["c1"],
                    }
                ],
            }

            def response_router(prompt: str, call_count: int) -> str:
                if "recover clean reading-order source text" in prompt:
                    raise AssertionError("Gemini source-text recovery should be skipped when manifest text exists.")
                if "structural truth layer" in prompt:
                    return json.dumps(structural_payload)
                if "creative structuring layer" in prompt:
                    return json.dumps(creative_payload)
                raise AssertionError(f"Unexpected extraction prompt: {prompt[:120]}")

            agent = object.__new__(GeminiStoryAgent)
            agent.client = ExtractionFakeClient(response_router=response_router)

            result = await agent.extract_signal(
                SignalExtractionRequest(
                    input_text="",
                    source_manifest={
                        "assets": [
                            {
                                "asset_id": "asset-pdf-1",
                                "modality": "pdf_page",
                                "uri": str(asset_path),
                                "mime_type": "application/pdf",
                                "title": "unit_extract_pdf.pdf",
                                "metadata": {
                                    "normalized_text": "A roadmap for evaluating moral competence in large language models.",
                                },
                            }
                        ]
                    },
                )
            )

            assert result["status"] == "success"
            assert result["normalized_source_text"] == "A roadmap for evaluating moral competence in large language models."
            assert result["source_text_origin"] == "asset_embedded_text"
            assert len(agent.client.files.upload_calls) == 0
            assert agent.client.files.deleted_names == []
            assert len(agent.client.models.contents) == 2
            assert result["trace"]["checkpoints"][-1]["details"]["uploaded_asset_count"] == 0
            assert all(
                "recover clean reading-order source text" not in (
                    item[0] if isinstance(item, list) and item and isinstance(item[0], str) else str(item)
                )
                for item in agent.client.models.contents
            )
        finally:
            asset_path.unlink(missing_ok=True)

    asyncio.run(run())


def test_artifact_scene_budget_respects_static_caps_and_sequential_duration() -> None:
    dense_signal = {
        "key_claims": [{"claim_id": f"c{i}"} for i in range(1, 8)],
        "narrative_beats": [{"beat_id": f"b{i}"} for i in range(1, 6)],
    }

    comparison_policy = GeminiStoryAgent._resolve_artifact_policy(
        render_profile={"artifact_type": "comparison_one_pager"},
        artifact_scope=["story_cards", "social_caption"],
    )
    comparison_count, _ = GeminiStoryAgent._derive_scene_count(
        artifact_policy=comparison_policy,
        content_signal=dense_signal,
        render_profile={"artifact_type": "comparison_one_pager", "output_controls": {"target_duration_sec": 180}},
        audience_level="advanced",
    )
    assert comparison_count == 1

    thumbnail_policy = GeminiStoryAgent._resolve_artifact_policy(
        render_profile={"artifact_type": "slide_thumbnail"},
        artifact_scope=["thumbnail", "social_caption"],
    )
    thumbnail_count, _ = GeminiStoryAgent._derive_scene_count(
        artifact_policy=thumbnail_policy,
        content_signal=dense_signal,
        render_profile={"artifact_type": "slide_thumbnail", "output_controls": {"target_duration_sec": 180}},
        audience_level="advanced",
    )
    assert thumbnail_count == 1

    storyboard_policy = GeminiStoryAgent._resolve_artifact_policy(
        render_profile={"artifact_type": "storyboard_grid", "density": "standard"},
        artifact_scope=["storyboard", "voiceover", "social_caption"],
    )
    storyboard_count, reason = GeminiStoryAgent._derive_scene_count(
        artifact_policy=storyboard_policy,
        content_signal=dense_signal,
        render_profile={
            "artifact_type": "storyboard_grid",
            "density": "standard",
            "output_controls": {"target_duration_sec": 90},
        },
        audience_level="beginner",
    )
    assert storyboard_count == 7
    assert "target_duration_sec=90" in reason


def test_planner_source_text_prefers_normalized_source_text_when_raw_text_is_missing() -> None:
    planner_source = GeminiStoryAgent._planner_source_text(
        source_text="",
        normalized_source_text="Recovered PDF text with concrete wording.",
        content_signal={"thesis": {"one_liner": "Fallback thesis"}},
    )

    assert planner_source == "Recovered PDF text with concrete wording."


def test_generate_script_pack_advanced_comparison_one_pager_returns_single_static_scene() -> None:
    async def run() -> None:
        planned_outline = {
            "scenes": [
                {
                    "scene_id": "scene-1",
                    "title": "Opening Board",
                    "narration_focus": "Guide the viewer through the modules.",
                    "visual_prompt": "A dense editorial one-pager board.",
                    "claim_refs": ["c1", "c2"],
                },
                {
                    "scene_id": "scene-2",
                    "title": "Second Beat",
                    "narration_focus": "This should be clipped away.",
                    "visual_prompt": "Unused scene.",
                    "claim_refs": ["c3"],
                },
            ]
        }
        salience_payload = {
            "items": [
                {
                    "candidate_id": "c1",
                    "candidate_type": "key_claim",
                    "content": "Solar is modular.",
                    "rating": "CRITICAL",
                    "downstream_impact": "The comparison loses one side of the tradeoff.",
                    "evidence_quote": "solar is modular",
                    "overlap_with": [],
                }
            ]
        }
        forward_pull_payload = {
            "bait": {"content": "Two energy paths look similar at first.", "evidence_quote": "solar vs wind"},
            "hook": {"question": "Which tradeoff matters most?", "evidence_quote": "tradeoffs differ"},
            "threats": [],
            "rewards": [],
            "payloads": [{"theme_or_engine": "Decision-quality comparison", "supporting_instances": ["cost profiles differ"]}],
        }
        agent = object.__new__(GeminiStoryAgent)
        agent.client = RoutingFakeClient(
            outline_payload=planned_outline,
            salience_payload=salience_payload,
            forward_pull_payload=forward_pull_payload,
        )

        result = await agent.generate_script_pack_advanced(
            ScriptPackRequest(
                source_text="Solar and wind differ in modularity, output, and cost profiles.",
                content_signal={
                    "thesis": {"one_liner": "Solar vs wind tradeoffs"},
                    "key_claims": [
                        {"claim_id": "c1", "claim_text": "Solar is modular."},
                        {"claim_id": "c2", "claim_text": "Wind has higher output."},
                        {"claim_id": "c3", "claim_text": "Cost profiles differ."},
                    ],
                    "concepts": [
                        {"concept_id": "k1", "label": "modularity"},
                        {"concept_id": "k2", "label": "output"},
                    ],
                    "narrative_beats": [{"beat_id": "b1", "message": "Compare tradeoffs"}],
                    "visual_candidates": [
                        {
                            "candidate_id": "v1",
                            "recommended_structure": "modular_poster",
                            "claim_refs": ["c1", "c2"],
                        }
                    ],
                },
                render_profile={
                    "artifact_type": "comparison_one_pager",
                    "density": "detailed",
                    "audience": {"persona": "Operators", "level": "advanced"},
                    "output_controls": {"target_duration_sec": 180},
                },
                artifact_scope=["story_cards", "social_caption"],
            )
        )

        assert result["status"] == "success"
        script_pack = result["script_pack"]
        planner_qa = result["planner_qa_summary"]
        assert script_pack["artifact_type"] == "comparison_one_pager"
        assert script_pack["planning_mode"] == "static"
        assert script_pack["script_shape"] == "one_pager_board"
        assert script_pack["scene_count"] == 1
        assert len(script_pack["scenes"]) == 1
        assert script_pack["scenes"][0]["scene_mode"] == "static"
        assert script_pack["scenes"][0]["layout_template"] == "modular_poster"
        assert script_pack["scenes"][0]["title"] == "Which tradeoff matters most?"
        assert "synthesis panel" in script_pack["scenes"][0]["visual_hierarchy"]
        assert len(script_pack["scenes"][0]["modules"]) >= 1
        assert "one dense composed scene" in script_pack["scene_budget_reason"].lower()
        assert planner_qa["mode"] == "repaired"
        assert planner_qa["repair_applied"] is True
        assert len(agent.client.models.prompts) == 3
        assert "counterfactual deletion" in agent.client.models.prompts[0]
        assert "Bait-Hook-Threat-Reward-Payload lens" in agent.client.models.prompts[1]
        assert "one-pager board" in agent.client.models.prompts[2].lower()
        assert "visual candidates" in agent.client.models.prompts[2].lower()
        assert "consumption rule: use hook and payload first" in agent.client.models.prompts[2].lower()

    asyncio.run(run())


def test_one_pager_fallback_scene_plan_uses_modular_poster_modules() -> None:
    policy = GeminiStoryAgent._resolve_artifact_policy(
        render_profile={"artifact_type": "comparison_one_pager"},
        artifact_scope=["story_cards", "social_caption"],
    )

    scene = GeminiStoryAgent._fallback_scene_plan(
        idx=1,
        scene_count=1,
        thesis="Heat pump adoption",
        artifact_policy=policy,
        claim_ids=["c1", "c2", "c3"],
    )

    assert scene.layout_template == "modular_poster"
    assert scene.title == "One-Pager Board"
    assert "core modules and takeaway" in scene.narration_focus
    assert len(scene.modules) == 4
    assert scene.modules[0].module_id == "hook-header"
    assert "synthesis panel" in scene.visual_hierarchy


def test_generate_script_pack_advanced_storyboard_runs_both_enrichment_passes() -> None:
    async def run() -> None:
        agent = object.__new__(GeminiStoryAgent)
        agent.client = RoutingFakeClient(
            outline_payload={
                "scenes": [
                    {
                        "scene_id": "scene-1",
                        "title": "Opening",
                        "narration_focus": "Set up the core tension.",
                        "visual_prompt": "A cinematic opening visual.",
                        "claim_refs": [],
                    },
                    {
                        "scene_id": "scene-2",
                        "title": "Mechanism",
                        "narration_focus": "Explain how it works.",
                        "visual_prompt": "A clear process visual.",
                        "claim_refs": [],
                    },
                    {
                        "scene_id": "scene-3",
                        "title": "Stakes",
                        "narration_focus": "Show what is at risk.",
                        "visual_prompt": "A tension-building scene.",
                        "claim_refs": [],
                    },
                    {
                        "scene_id": "scene-4",
                        "title": "Payoff",
                        "narration_focus": "Resolve the main question.",
                        "visual_prompt": "A satisfying final image.",
                        "claim_refs": [],
                    },
                ]
            },
            salience_payload={
                "items": [
                    {
                        "candidate_id": "c1",
                        "candidate_type": "key_claim",
                        "content": "The system stores excess energy.",
                        "rating": "CRITICAL",
                        "downstream_impact": "The causal backbone breaks.",
                        "evidence_quote": "stores excess energy",
                        "overlap_with": [],
                    }
                ]
            },
            forward_pull_payload={
                "bait": {"content": "The grid looks stable until demand spikes.", "evidence_quote": "demand spikes"},
                "hook": {"question": "How does the grid stay balanced?", "evidence_quote": "stay balanced"},
                "threats": [{"stake": "Power reliability drops.", "who_is_at_risk": "homes and hospitals", "evidence_quote": "reliability drops"}],
                "rewards": [{"payoff_signal": "Stored energy fills the gap.", "likely_location": "b3", "evidence_quote": "fills the gap"}],
                "payloads": [{"theme_or_engine": "Resilience through storage", "supporting_instances": ["energy fills the gap"]}],
            },
        )

        result = await agent.generate_script_pack_advanced(
            ScriptPackRequest(
                source_text="When demand spikes, stored energy fills the gap and keeps the grid reliable.",
                content_signal={
                    "thesis": {"one_liner": "Grid storage balances demand spikes"},
                    "key_claims": [
                        {"claim_id": "c1", "claim_text": "The system stores excess energy."},
                        {"claim_id": "c2", "claim_text": "Stored energy is released during demand spikes."},
                        {"claim_id": "c3", "claim_text": "Reliability drops if the gap is not filled."},
                        {"claim_id": "c4", "claim_text": "Storage improves resilience."},
                    ],
                    "narrative_beats": [
                        {"beat_id": "b1", "message": "Demand spikes create a gap."},
                        {"beat_id": "b2", "message": "Storage holds excess energy."},
                    ],
                },
                render_profile={
                    "artifact_type": "storyboard_grid",
                    "density": "standard",
                    "audience": {"persona": "General audience", "level": "beginner"},
                    "output_controls": {"target_duration_sec": 60},
                },
                artifact_scope=["storyboard", "voiceover", "social_caption"],
            )
        )

        assert result["status"] == "success"
        prompts = agent.client.models.prompts
        planner_qa = result["planner_qa_summary"]
        assert len(prompts) == 3
        assert "counterfactual deletion" in prompts[0]
        assert "Bait-Hook-Threat-Reward-Payload lens" in prompts[1]
        assert "SALIENCE MAP:" in prompts[2]
        assert "FORWARD-PULL MAP:" in prompts[2]
        assert "Threats:" in prompts[2]
        assert result["script_pack"]["planning_mode"] == "sequential"
        assert result["script_pack"]["scene_count"] == 4
        assert planner_qa["mode"] == "repaired"
        assert result["script_pack"]["scenes"][0]["scene_role"] == "bait_hook"
        assert "Driving question: How does the grid stay balanced?" in result["script_pack"]["scenes"][0]["narration_focus"]
        assert result["script_pack"]["scenes"][-1]["scene_role"] == "payoff"
        assert "Stored energy fills the gap" in result["script_pack"]["scenes"][-1]["narration_focus"]
        assert any("c1" in scene["claim_refs"] for scene in result["script_pack"]["scenes"])

    asyncio.run(run())


def test_generate_script_pack_advanced_technical_infographic_skips_forward_pull_pass() -> None:
    async def run() -> None:
        agent = object.__new__(GeminiStoryAgent)
        agent.client = RoutingFakeClient(
            outline_payload={
                "scenes": [
                    {
                        "scene_id": "scene-1",
                        "title": "System Overview",
                        "narration_focus": "Explain the mechanism.",
                        "visual_prompt": "A structured technical board.",
                        "claim_refs": ["c1", "c2"],
                    }
                ]
            },
            salience_payload={
                "items": [
                    {
                        "candidate_id": "c1",
                        "candidate_type": "key_claim",
                        "content": "Pressure drives the exchange.",
                        "rating": "CRITICAL",
                        "downstream_impact": "The mechanism stops making sense.",
                        "evidence_quote": "pressure drives exchange",
                        "overlap_with": [],
                    }
                ]
            },
        )

        result = await agent.generate_script_pack_advanced(
            ScriptPackRequest(
                source_text="Pressure drives the exchange across the membrane and sets up the full mechanism.",
                content_signal={
                    "thesis": {"one_liner": "Membrane exchange mechanism"},
                    "key_claims": [
                        {"claim_id": "c1", "claim_text": "Pressure drives the exchange."},
                        {"claim_id": "c2", "claim_text": "The membrane regulates flow."},
                    ],
                    "narrative_beats": [{"beat_id": "b1", "message": "Pressure establishes the gradient."}],
                },
                render_profile={
                    "artifact_type": "technical_infographic",
                    "density": "detailed",
                    "audience": {"persona": "Students", "level": "intermediate"},
                    "output_controls": {"target_duration_sec": 120},
                },
                artifact_scope=["story_cards", "voiceover"],
            )
        )

        assert result["status"] == "success"
        prompts = agent.client.models.prompts
        planner_qa = result["planner_qa_summary"]
        assert len(prompts) == 2
        assert "counterfactual deletion" in prompts[0]
        assert all("Bait-Hook-Threat-Reward-Payload lens" not in prompt for prompt in prompts)
        assert "threat and reward framing should be ignored" in prompts[1].lower()
        assert result["script_pack"]["planning_mode"] == "static"
        assert result["script_pack"]["script_shape"] == "technical_infographic"
        assert planner_qa["mode"] == "direct"

    asyncio.run(run())


def test_generate_script_pack_advanced_thumbnail_repairs_dominant_hook() -> None:
    async def run() -> None:
        agent = object.__new__(GeminiStoryAgent)
        agent.client = RoutingFakeClient(
            outline_payload={
                "scenes": [
                    {
                        "scene_id": "scene-1",
                        "title": "Thumbnail",
                        "narration_focus": "A generic visual idea.",
                        "visual_prompt": "A generic promo image.",
                        "claim_refs": ["c1", "c2", "c3"],
                    }
                ]
            },
            salience_payload={
                "items": [
                    {
                        "candidate_id": "c1",
                        "candidate_type": "key_claim",
                        "content": "One hidden flaw changes everything.",
                        "rating": "CRITICAL",
                        "downstream_impact": "The hook disappears.",
                        "evidence_quote": "hidden flaw changes everything",
                        "overlap_with": [],
                    }
                ]
            },
            forward_pull_payload={
                "bait": {"content": "One hidden flaw changes everything.", "evidence_quote": "hidden flaw"},
                "hook": {"question": "What is the flaw?", "evidence_quote": "what is the flaw"},
                "threats": [],
                "rewards": [],
                "payloads": [{"theme_or_engine": "Reveal the flaw fast", "supporting_instances": ["hidden flaw"]}],
            },
        )

        result = await agent.generate_script_pack_advanced(
            ScriptPackRequest(
                source_text="A hidden flaw in the design changes everything once you see it.",
                content_signal={
                    "thesis": {"one_liner": "A hidden flaw changes the design"},
                    "key_claims": [
                        {"claim_id": "c1", "claim_text": "One hidden flaw changes everything."},
                        {"claim_id": "c2", "claim_text": "The flaw is easy to miss."},
                        {"claim_id": "c3", "claim_text": "Spotting it changes the diagnosis."},
                    ],
                    "narrative_beats": [{"beat_id": "b1", "message": "Reveal the overlooked flaw."}],
                },
                render_profile={
                    "artifact_type": "slide_thumbnail",
                    "density": "standard",
                    "audience": {"persona": "General audience", "level": "beginner"},
                    "output_controls": {"target_duration_sec": 60},
                },
                artifact_scope=["thumbnail", "social_caption"],
            )
        )

        assert result["status"] == "success"
        scene = result["script_pack"]["scenes"][0]
        planner_qa = result["planner_qa_summary"]
        assert scene["title"] == "What is the flaw"
        assert scene["focal_subject"] == "What is the flaw?"
        assert scene["visual_hierarchy"][0] == "What is the flaw?"
        assert len(scene["claim_refs"]) <= 2
        assert planner_qa["mode"] == "repaired"
        assert "single static thumbnail concept" in agent.client.models.prompts[2].lower()
        assert "headline-safe area" in agent.client.models.prompts[2].lower()

    asyncio.run(run())


def test_stream_scene_assets_uses_thumbnail_specific_render_prompt() -> None:
    async def run() -> None:
        agent = object.__new__(GeminiStoryAgent)
        agent.client = CapturingStreamClient()

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "scheme": "http",
        }
        request = Request(scope)

        events = []
        async for event in agent._stream_scene_assets(
            request=request,
            scene_id="scene-1",
            topic="A hidden flaw changes the design",
            audience="General audience (beginner)",
            tone="teach",
            scene_title="One hidden flaw changes everything.",
            narration_focus="Show the hook fast and explain why the frame is compelling.",
            style_guide="Visual Mode: ILLUSTRATION.",
            visual_prompt="A bold hero frame with one subject and strong contrast.",
            image_prefix="test-thumb",
            audio_prefix="test-audio",
            scene_goal="Create an instantly legible hero thumbnail.",
            artifact_type="slide_thumbnail",
            scene_mode="static",
            layout_template="hero_thumbnail",
            focal_subject="One hidden flaw changes everything.",
            visual_hierarchy=["headline-safe hook zone", "hero subject", "supporting context cue"],
            claim_refs=["c1"],
            claim_text_snippets=["One hidden flaw changes everything."],
            crop_safe_regions=["top-left headline zone", "center hero safe area"],
            result_collector={},
        ):
            events.append(event)

        assert events == []
        assert len(agent.client.models.prompts) == 1
        prompt = agent.client.models.prompts[0].lower()
        assert "this output is a single slide thumbnail" in prompt
        assert "source claims:" in prompt
        assert "one hidden flaw changes everything." in prompt
        assert "text-safe zone" in prompt
        assert "do not use generic symbols like compasses" in prompt
        assert "do not create dense infographic or poster layouts" in prompt
        assert "single composed thumbnail frame" in prompt

    asyncio.run(run())


def test_stream_scene_assets_grounds_storyboard_render_prompt_in_claims_and_evidence() -> None:
    async def run() -> None:
        agent = object.__new__(GeminiStoryAgent)
        agent.client = CapturingStreamClient()

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "scheme": "http",
        }
        request = Request(scope)

        async for _event in agent._stream_scene_assets(
            request=request,
            scene_id="scene-1",
            topic="Evaluating moral competence in language models",
            audience="General audience (advanced)",
            tone="teach",
            scene_title="Competence versus mimicry",
            narration_focus="Contrast benchmark mimicry with genuine moral competence.",
            style_guide="Visual Mode: HYBRID.",
            visual_prompt="A grounded research lab scene showing evaluation artifacts and debate.",
            image_prefix="test-storyboard",
            audio_prefix="test-audio",
            scene_goal="Show the concrete tension between benchmark performance and competence.",
            artifact_type="storyboard_grid",
            scene_mode="sequential",
            claim_refs=["c1", "c2"],
            claim_text_snippets=[
                "LLMs can appear morally competent while relying on shallow pattern matching.",
                "Evaluation should distinguish benchmark success from genuine moral reasoning.",
            ],
            evidence_text_snippets=[
                "pdf_page | page 1 | benchmark success can mask shallow reasoning",
                "pdf_page | page 2 | roadmap for evaluating moral competence",
            ],
            result_collector={},
        ):
            pass

        assert len(agent.client.models.prompts) == 1
        prompt = agent.client.models.prompts[0].lower()
        assert "source claims:" in prompt
        assert "source evidence:" in prompt
        assert "specific nouns, measurements, environments, and interactions" in prompt
        assert "avoid generic corporate, cosmic, or metaphor-only imagery" in prompt
        assert "benchmark success can mask shallow reasoning" in prompt

    asyncio.run(run())


def test_generate_script_pack_advanced_replans_once_when_hard_failures_survive_repair() -> None:
    async def run() -> None:
        agent = object.__new__(GeminiStoryAgent)
        agent.client = RoutingFakeClient(
            outline_payload=[
                {
                    "scenes": [
                        {
                            "scene_id": "scene-1",
                            "title": "Opening",
                            "narration_focus": "Generic start.",
                            "visual_prompt": "Generic opener.",
                            "claim_refs": [],
                        },
                        {
                            "scene_id": "scene-2",
                            "title": "Middle",
                            "narration_focus": "Generic middle.",
                            "visual_prompt": "Generic middle.",
                            "claim_refs": [],
                        },
                        {
                            "scene_id": "scene-3",
                            "title": "End",
                            "narration_focus": "Generic ending.",
                            "visual_prompt": "Generic ending.",
                            "claim_refs": [],
                        },
                    ]
                },
                {
                    "scenes": [
                        {
                            "scene_id": "scene-1",
                            "title": "Why does the backup matter?",
                            "narration_focus": "Driving question: Why does the backup matter?",
                            "visual_prompt": "A tense opener about backup power.",
                            "claim_refs": [],
                        },
                        {
                            "scene_id": "scene-2",
                            "title": "Stored Reserve",
                            "narration_focus": "The system stores excess energy for emergencies.",
                            "visual_prompt": "An energy storage visual.",
                            "claim_refs": ["c1"],
                        },
                        {
                            "scene_id": "scene-3",
                            "title": "Reliable Ending",
                            "narration_focus": "Stored energy fills the gap. End on resilience through storage.",
                            "visual_prompt": "A payoff image showing stable power.",
                            "claim_refs": [],
                        },
                    ]
                },
            ],
            salience_payload={
                "items": [
                    {
                        "candidate_id": "c1",
                        "candidate_type": "key_claim",
                        "content": "The system stores excess energy.",
                        "rating": "CRITICAL",
                        "downstream_impact": "The core mechanism disappears.",
                        "evidence_quote": "stores excess energy",
                        "overlap_with": [],
                    }
                ]
            },
            forward_pull_payload={
                "bait": {"content": "Backup power seems invisible until it matters.", "evidence_quote": "until it matters"},
                "hook": {"question": "Why does the backup matter?", "evidence_quote": "backup matter"},
                "threats": [],
                "rewards": [{"payoff_signal": "Stored energy fills the gap.", "likely_location": "b3", "evidence_quote": "fills the gap"}],
                "payloads": [{"theme_or_engine": "Resilience through storage", "supporting_instances": ["reliable backup"]}],
            },
        )

        def no_op_repair(*, script_pack, context):  # noqa: ANN001
            return script_pack

        agent._repair_script_pack_from_enrichments = no_op_repair  # type: ignore[method-assign]

        result = await agent.generate_script_pack_advanced(
            ScriptPackRequest(
                source_text="The system stores excess energy so backup power works when it matters most.",
                content_signal={
                    "thesis": {"one_liner": "Stored energy enables reliable backup"},
                    "key_claims": [{"claim_id": "c1", "claim_text": "The system stores excess energy."}],
                    "narrative_beats": [{"beat_id": "b1", "message": "Backup matters during outages."}],
                },
                render_profile={
                    "artifact_type": "storyboard_grid",
                    "density": "simple",
                    "audience": {"persona": "General audience", "level": "beginner"},
                    "output_controls": {"target_duration_sec": 40},
                },
                artifact_scope=["storyboard", "voiceover", "social_caption"],
            )
        )

        assert result["status"] == "success"
        planner_qa = result["planner_qa_summary"]
        assert agent.client.models.outline_call_count == 2
        outline_prompts = [
            prompt for prompt in agent.client.models.prompts
            if "counterfactual deletion" not in prompt and "Bait-Hook-Threat-Reward-Payload lens" not in prompt
        ]
        assert len(outline_prompts) == 2
        assert "REVISION REQUIRED" in outline_prompts[1]
        assert result["script_pack"]["scenes"][0]["title"] == "Why does the backup matter?"
        assert any("c1" in scene["claim_refs"] for scene in result["script_pack"]["scenes"])
        assert planner_qa["mode"] == "replanned"
        assert planner_qa["replan_attempted"] is True

    asyncio.run(run())


def test_generate_script_pack_advanced_enriches_scenes_with_multimodal_evidence() -> None:
    async def run() -> None:
        agent = object.__new__(GeminiStoryAgent)
        agent.client = RoutingFakeClient(
            outline_payload={
                "scenes": [
                    {
                        "scene_id": "scene-1",
                        "title": "Power Drop",
                        "narration_focus": "Explain the 40% power drop and why the proof matters.",
                        "visual_prompt": "A grounded technical proof visual.",
                        "claim_refs": ["c1"],
                    }
                ]
            }
        )

        result = await agent.generate_script_pack_advanced(
            ScriptPackRequest(
                source_text="The chip redesign lowers power consumption by forty percent.",
                source_manifest={
                    "assets": [
                        {
                            "asset_id": "asset-audio-1",
                            "modality": "audio",
                            "uri": "http://example.com/audio.mp3",
                            "duration_ms": 120000,
                            "metadata": {"speaker": "CEO"},
                        },
                        {
                            "asset_id": "asset-page-1",
                            "modality": "pdf_page",
                            "uri": "http://example.com/deck/page-4.png",
                            "page_index": 4,
                        },
                    ]
                },
                content_signal={
                    "thesis": {"one_liner": "The redesign lowers power draw"},
                    "key_claims": [
                        {
                            "claim_id": "c1",
                            "claim_text": "The new chip architecture reduces power consumption by 40%.",
                            "evidence_snippets": [
                                {
                                    "evidence_id": "e1",
                                    "type": "audio",
                                    "asset_id": "asset-audio-1",
                                    "start_ms": 725000,
                                    "end_ms": 738000,
                                    "transcript_text": "We're seeing a forty percent drop in power.",
                                },
                                {
                                    "evidence_id": "e2",
                                    "type": "pdf_page",
                                    "asset_id": "asset-page-1",
                                    "page_index": 4,
                                    "bbox_norm": [0.1, 0.15, 0.7, 0.75],
                                    "visual_context": "Thermal efficiency chart on the keynote slide.",
                                },
                            ],
                        }
                    ],
                    "narrative_beats": [{"beat_id": "b1", "message": "Power efficiency becomes measurable."}],
                },
                render_profile={
                    "artifact_type": "storyboard_grid",
                    "density": "standard",
                    "audience": {"persona": "Engineers", "level": "intermediate"},
                    "output_controls": {"target_duration_sec": 30},
                },
                artifact_scope=["storyboard", "voiceover"],
            )
        )

        assert result["status"] == "success"
        scene = result["script_pack"]["scenes"][0]
        traceability = result["claim_traceability"]
        assert set(scene["evidence_refs"]) == {"e1", "e2"}
        assert scene["render_strategy"] == "hybrid"
        assert len(scene["source_media"]) == 2
        assert {item["asset_id"] for item in scene["source_media"]} == {"asset-audio-1", "asset-page-1"}
        assert traceability["evidence_total"] == 2
        assert traceability["evidence_referenced"] == 2
        assert set(traceability["scene_evidence_map"]["scene-1"]) == {"e1", "e2"}

    asyncio.run(run())


def test_generate_script_pack_advanced_limits_frontmatter_proof_to_opener_and_diversifies_body_pages() -> None:
    async def run() -> None:
        agent = object.__new__(GeminiStoryAgent)
        agent.client = RoutingFakeClient(
            outline_payload={
                "scenes": [
                    {
                        "scene_id": "scene-1",
                        "title": "Hook",
                        "scene_role": "bait_hook",
                        "narration_focus": "Open with the paper's framing question.",
                        "visual_prompt": "A scientific paper opening visual.",
                        "claim_refs": ["c1"],
                    },
                    {
                        "scene_id": "scene-2",
                        "title": "Body Evidence A",
                        "scene_role": "setup",
                        "narration_focus": "Move into the paper's concrete framework.",
                        "visual_prompt": "A framework diagram from the paper body.",
                        "claim_refs": ["c1"],
                    },
                    {
                        "scene_id": "scene-3",
                        "title": "Body Evidence B",
                        "scene_role": "payoff",
                        "narration_focus": "Land on a later empirical detail.",
                        "visual_prompt": "A later-page evidence visual.",
                        "claim_refs": ["c1"],
                    },
                ]
            }
        )

        result = await agent.generate_script_pack_advanced(
            ScriptPackRequest(
                source_text="",
                normalized_source_text="A roadmap for evaluating moral competence in large language models.",
                source_manifest={
                    "assets": [
                        {
                            "asset_id": "asset-paper-1",
                            "modality": "pdf_page",
                            "uri": "http://example.com/paper.pdf",
                            "mime_type": "application/pdf",
                            "title": "paper.pdf",
                        },
                    ]
                },
                content_signal={
                    "thesis": {"one_liner": "A roadmap for evaluating moral competence in large language models."},
                    "key_claims": [
                        {
                            "claim_id": "c1",
                            "claim_text": "The paper proposes a roadmap for evaluating moral competence.",
                            "evidence_snippets": [
                                {
                                    "evidence_id": "e-abstract",
                                    "type": "pdf_page",
                                    "asset_id": "asset-paper-1",
                                    "page_index": 1,
                                    "quote_text": "Abstract: A roadmap for evaluating moral competence in large language models.",
                                },
                                {
                                    "evidence_id": "e-body-4",
                                    "type": "pdf_page",
                                    "asset_id": "asset-paper-1",
                                    "page_index": 4,
                                    "visual_context": "Framework overview figure in the body of the paper.",
                                },
                                {
                                    "evidence_id": "e-body-6",
                                    "type": "pdf_page",
                                    "asset_id": "asset-paper-1",
                                    "page_index": 6,
                                    "visual_context": "Later-page evaluation criteria table.",
                                },
                            ],
                        }
                    ],
                    "narrative_beats": [
                        {"beat_id": "b1", "role": "hook", "message": "The abstract frames the roadmap."},
                        {"beat_id": "b2", "role": "setup", "message": "The body introduces the framework."},
                        {"beat_id": "b3", "role": "payoff", "message": "Later pages ground the evaluation details."},
                    ],
                },
                render_profile={
                    "artifact_type": "storyboard_grid",
                    "density": "standard",
                    "audience": {"persona": "Researchers", "level": "intermediate"},
                    "output_controls": {"target_duration_sec": 45},
                },
                artifact_scope=["storyboard", "voiceover"],
            )
        )

        assert result["status"] == "success"
        scenes = result["script_pack"]["scenes"]
        assert scenes[0]["source_media"][0]["page_index"] == 1
        assert scenes[1]["source_media"][0]["page_index"] == 4
        assert scenes[2]["source_media"][0]["page_index"] == 6
        assert "e-abstract" in scenes[0]["evidence_refs"]
        assert "e-abstract" not in scenes[1]["evidence_refs"]
        assert "e-abstract" not in scenes[2]["evidence_refs"]

    asyncio.run(run())


def test_generate_stream_advanced_events_emits_source_media_ready_payloads() -> None:
    async def run() -> None:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "scheme": "http",
        }

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": b"", "more_body": False}

        request = Request(scope, receive)

        image = Image.new("RGB", (1280, 720), (24, 32, 72))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        source_image_url = save_image_and_get_url(
            request=request,
            scene_id="scene-source",
            image_bytes=buffer.getvalue(),
            prefix="unit_source_media",
        )

        agent = object.__new__(GeminiStoryAgent)

        async def fake_stream_scene_assets(**kwargs):  # noqa: ANN003
            result_collector = kwargs["result_collector"]
            text = (
                "This scene explains the forty percent power drop with direct source proof, "
                "showing how the keynote audio and slide crop reinforce the same grounded claim "
                "about lower consumption and measurable efficiency gains."
            )
            result_collector["text"] = text
            result_collector["image_url"] = source_image_url
            result_collector["audio_url"] = ""
            result_collector["word_count"] = len(text.split())
            if False:
                yield {}

        agent._stream_scene_assets = fake_stream_scene_assets  # type: ignore[method-assign]

        approved_script_pack = {
            "plan_id": "plan-proof",
            "plan_summary": "Proof-backed storyboard",
            "audience_descriptor": "Engineers",
            "scene_count": 1,
            "artifact_type": "storyboard_grid",
            "planning_mode": "sequential",
            "script_shape": "sequential_storyboard",
            "scenes": [
                {
                    "scene_id": "scene-1",
                    "title": "Power Drop",
                    "scene_goal": "Show the measurable reduction.",
                    "narration_focus": "Explain the 40% power drop and why the proof matters.",
                    "visual_prompt": "A grounded technical proof visual.",
                    "claim_refs": ["c1"],
                    "continuity_refs": [],
                    "acceptance_checks": [],
                }
            ],
        }

        events: list[dict[str, str]] = []
        async for event in agent.generate_stream_advanced_events(
            request=request,
            payload=AdvancedStreamRequest.model_validate(
                {
                    "source_text": "",
                    "source_manifest": {
                        "assets": [
                            {
                                "asset_id": "asset-audio-1",
                                "modality": "audio",
                                "uri": "http://example.com/audio.mp3",
                                "duration_ms": 120000,
                                "metadata": {"speaker": "CEO"},
                            },
                            {
                                "asset_id": "asset-page-1",
                                "modality": "pdf_page",
                                "uri": source_image_url,
                                "page_index": 4,
                            },
                        ]
                    },
                    "content_signal": {
                        "thesis": {"one_liner": "The redesign lowers power draw"},
                        "key_claims": [
                            {
                                "claim_id": "c1",
                                "claim_text": "The new chip architecture reduces power consumption by 40%.",
                                "evidence_snippets": [
                                    {
                                        "evidence_id": "e1",
                                        "type": "audio",
                                        "asset_id": "asset-audio-1",
                                        "start_ms": 725000,
                                        "end_ms": 738000,
                                        "transcript_text": "We're seeing a forty percent drop in power.",
                                    },
                                    {
                                        "evidence_id": "e2",
                                        "type": "pdf_page",
                                        "asset_id": "asset-page-1",
                                        "page_index": 4,
                                        "bbox_norm": [0.1, 0.15, 0.7, 0.75],
                                        "visual_context": "Thermal efficiency chart on the keynote slide.",
                                    },
                                ],
                            }
                        ],
                        "narrative_beats": [{"beat_id": "b1", "message": "Power efficiency becomes measurable."}],
                    },
                    "render_profile": {
                        "artifact_type": "storyboard_grid",
                        "density": "standard",
                        "audience": {"persona": "Engineers", "level": "intermediate"},
                        "output_controls": {"target_duration_sec": 30},
                    },
                    "script_pack": approved_script_pack,
                    "artifact_scope": ["storyboard", "voiceover"],
                }
            ),
        ):
            events.append(event)

        parsed_events = [
            (event["event"], json.loads(event["data"]))
            for event in events
        ]
        queue_event = next(data for name, data in parsed_events if name == "scene_queue_ready")
        scene_start_event = next(data for name, data in parsed_events if name == "scene_start")
        proof_events = [data for name, data in parsed_events if name == "source_media_ready"]
        final_bundle_event = next(data for name, data in parsed_events if name == "final_bundle_ready")

        assert queue_event["scenes"][0]["source_media_count"] == 2
        assert queue_event["scenes"][0]["render_strategy"] == "hybrid"
        assert scene_start_event["render_strategy"] == "hybrid"
        assert set(scene_start_event["evidence_refs"]) == {"e1", "e2"}
        assert len(proof_events) == 2
        assert any(event["modality"] == "audio" and event["url"] == "http://example.com/audio.mp3" for event in proof_events)
        image_proof = next(event for event in proof_events if event["modality"] == "pdf_page")
        assert image_proof["original_url"] == source_image_url
        assert image_proof["url"] != source_image_url
        assert "source_media_crop_scene-1-proof-" in image_proof["url"]
        assert final_bundle_event["claim_traceability"]["evidence_total"] == 2
        assert final_bundle_event["claim_traceability"]["evidence_referenced"] == 2

    asyncio.run(run())


def test_generate_stream_advanced_events_emits_source_media_warning_when_links_cannot_resolve() -> None:
    async def run() -> None:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "scheme": "http",
        }

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": b"", "more_body": False}

        request = Request(scope, receive)

        agent = object.__new__(GeminiStoryAgent)

        async def fake_stream_scene_assets(**kwargs):  # noqa: ANN003
            result_collector = kwargs["result_collector"]
            text = "This scene should have proof, but the proof asset URL cannot be resolved."
            result_collector["text"] = text
            result_collector["image_url"] = ""
            result_collector["audio_url"] = ""
            result_collector["word_count"] = len(text.split())
            if False:
                yield {}

        agent._stream_scene_assets = fake_stream_scene_assets  # type: ignore[method-assign]

        approved_script_pack = {
            "plan_id": "plan-proof-warning",
            "plan_summary": "Proof-backed storyboard",
            "audience_descriptor": "Engineers",
            "scene_count": 1,
            "artifact_type": "storyboard_grid",
            "planning_mode": "sequential",
            "script_shape": "sequential_storyboard",
            "scenes": [
                {
                    "scene_id": "scene-warning",
                    "title": "Missing Proof Link",
                    "scene_goal": "Show proof link diagnostics.",
                    "narration_focus": "Explain that source proof could not be linked.",
                    "visual_prompt": "Diagnostic visual.",
                    "claim_refs": ["c1"],
                    "continuity_refs": [],
                    "acceptance_checks": [],
                }
            ],
        }

        events: list[dict[str, str]] = []
        async for event in agent.generate_stream_advanced_events(
            request=request,
            payload=AdvancedStreamRequest.model_validate(
                {
                    "source_text": "",
                    "source_manifest": {
                        "assets": [
                            {
                                "asset_id": "asset-audio-missing",
                                "modality": "audio",
                                "uri": None,
                                "duration_ms": 120000,
                            },
                        ]
                    },
                    "content_signal": {
                        "thesis": {"one_liner": "Proof should be linked when possible."},
                        "key_claims": [
                            {
                                "claim_id": "c1",
                                "claim_text": "The narrated claim should point back to source media.",
                                "evidence_snippets": [
                                    {
                                        "evidence_id": "e1",
                                        "type": "audio",
                                        "asset_id": "asset-audio-missing",
                                        "start_ms": 1200,
                                        "end_ms": 4200,
                                        "transcript_text": "This is the supporting source clip.",
                                    },
                                ],
                            }
                        ],
                        "narrative_beats": [{"beat_id": "b1", "message": "Explain why the proof link is missing."}],
                    },
                    "render_profile": {
                        "artifact_type": "storyboard_grid",
                        "density": "standard",
                        "audience": {"persona": "Engineers", "level": "intermediate"},
                        "output_controls": {"target_duration_sec": 30},
                    },
                    "script_pack": approved_script_pack,
                    "artifact_scope": ["storyboard", "voiceover"],
                }
            ),
        ):
            events.append(event)

        parsed_events = [
            (event["event"], json.loads(event["data"]))
            for event in events
        ]
        scene_start_event = next(data for name, data in parsed_events if name == "scene_start")
        warning_event = next(data for name, data in parsed_events if name == "source_media_warning")
        proof_events = [data for name, data in parsed_events if name == "source_media_ready"]

        assert scene_start_event["scene_id"] == "scene-warning"
        assert scene_start_event["source_media"] == []
        assert proof_events == []
        assert warning_event["scene_id"] == "scene-warning"
        assert warning_event["asset_ids"] == ["asset-audio-missing"]
        assert warning_event["expected_count"] == 1
        assert "no resolvable proof links" in warning_event["message"].lower()

    asyncio.run(run())


def test_enrich_script_pack_with_source_media_falls_back_to_scene_evidence_refs() -> None:
    script_pack = ScriptPack.model_validate(
        {
            "plan_id": "plan-evidence-fallback",
            "plan_summary": "Fallback proof enrichment",
            "audience_descriptor": "Engineers",
            "scene_count": 1,
            "artifact_type": "storyboard_grid",
            "scenes": [
                {
                    "scene_id": "scene-1",
                    "title": "Evidence First",
                    "scene_goal": "Recover proof links from evidence refs.",
                    "narration_focus": "Use direct evidence refs even when claim refs are sparse.",
                    "visual_prompt": "Technical evidence panel.",
                    "claim_refs": [],
                    "evidence_refs": ["e1"],
                    "continuity_refs": [],
                    "acceptance_checks": [],
                }
            ],
        }
    )

    enriched, scene_evidence_map, evidence_ids = GeminiStoryAgent._enrich_script_pack_with_source_media(
        script_pack=script_pack,
        content_signal={
            "key_claims": [
                {
                    "claim_id": "c1",
                    "claim_text": "The source document contains a verifiable proof excerpt.",
                    "evidence_snippets": [
                        {
                            "evidence_id": "e1",
                            "type": "pdf_page",
                            "asset_id": "asset-paper-1",
                            "page_index": 3,
                            "quote_text": "The exact supporting sentence lives on page three.",
                        }
                    ],
                }
            ]
        },
        source_manifest={
            "assets": [
                {
                    "asset_id": "asset-paper-1",
                    "modality": "pdf_page",
                    "uri": "http://example.com/paper.pdf",
                    "page_index": 3,
                }
            ]
        },
    )

    scene = enriched.scenes[0]
    assert scene.source_media
    assert scene.source_media[0].asset_id == "asset-paper-1"
    assert scene.source_media[0].evidence_refs == ["e1"]
    assert scene_evidence_map["scene-1"] == ["e1"]
    assert evidence_ids == ["e1"]


def test_enrich_script_pack_with_source_media_removes_non_opener_frontmatter_when_body_evidence_exists() -> None:
    script_pack = ScriptPack.model_validate(
        {
            "plan_id": "plan-frontmatter-filter",
            "plan_summary": "Frontmatter should stay on the opener only.",
            "audience_descriptor": "Researchers",
            "scene_count": 2,
            "artifact_type": "storyboard_grid",
            "scenes": [
                {
                    "scene_id": "scene-1",
                    "title": "Hook",
                    "scene_role": "bait_hook",
                    "scene_goal": "Open with the paper framing.",
                    "narration_focus": "Use the abstract only for the opener.",
                    "visual_prompt": "Paper opener.",
                    "claim_refs": ["c1"],
                    "evidence_refs": ["e-abstract"],
                    "source_media": [
                        {
                            "asset_id": "asset-paper-1",
                            "modality": "pdf_page",
                            "usage": "callout",
                            "claim_refs": ["c1"],
                            "evidence_refs": ["e-abstract"],
                            "page_index": 1,
                            "quote_text": "Abstract: The paper introduces the roadmap.",
                        }
                    ],
                    "continuity_refs": [],
                    "acceptance_checks": [],
                },
                {
                    "scene_id": "scene-2",
                    "title": "Body Detail",
                    "scene_role": "payoff",
                    "scene_goal": "Use the later body page, not the abstract.",
                    "narration_focus": "Ground the claim in the body of the paper.",
                    "visual_prompt": "Body-page framework figure.",
                    "claim_refs": ["c1"],
                    "evidence_refs": ["e-abstract", "e-body-4"],
                    "source_media": [
                        {
                            "asset_id": "asset-paper-1",
                            "modality": "pdf_page",
                            "usage": "callout",
                            "claim_refs": ["c1"],
                            "evidence_refs": ["e-abstract"],
                            "page_index": 1,
                            "quote_text": "Abstract: The paper introduces the roadmap.",
                        }
                    ],
                    "continuity_refs": [],
                    "acceptance_checks": [],
                },
            ],
        }
    )

    enriched, scene_evidence_map, evidence_ids = GeminiStoryAgent._enrich_script_pack_with_source_media(
        script_pack=script_pack,
        content_signal={
            "key_claims": [
                {
                    "claim_id": "c1",
                    "claim_text": "The paper proposes a roadmap for evaluating moral competence.",
                    "evidence_snippets": [
                        {
                            "evidence_id": "e-abstract",
                            "type": "pdf_page",
                            "asset_id": "asset-paper-1",
                            "page_index": 1,
                            "quote_text": "Abstract: The paper introduces the roadmap.",
                        },
                        {
                            "evidence_id": "e-body-4",
                            "type": "pdf_page",
                            "asset_id": "asset-paper-1",
                            "page_index": 4,
                            "visual_context": "Framework diagram in the paper body.",
                        },
                    ],
                }
            ]
        },
        source_manifest={
            "assets": [
                {
                    "asset_id": "asset-paper-1",
                    "modality": "pdf_page",
                    "uri": "http://example.com/paper.pdf",
                    "mime_type": "application/pdf",
                    "title": "paper.pdf",
                }
            ]
        },
    )

    assert evidence_ids == ["e-abstract", "e-body-4"]
    assert scene_evidence_map["scene-1"] == ["e-abstract"]
    assert scene_evidence_map["scene-2"] == ["e-body-4"]
    assert any(media.page_index == 1 for media in enriched.scenes[0].source_media)
    assert all(media.page_index != 1 for media in enriched.scenes[1].source_media)
    assert any(media.page_index == 4 for media in enriched.scenes[1].source_media)
    assert "e-abstract" not in enriched.scenes[1].evidence_refs
    assert "e-body-4" in enriched.scenes[1].evidence_refs


def test_enrich_script_pack_with_source_media_merges_duplicate_pdf_refs() -> None:
    script_pack = ScriptPack.model_validate(
        {
            "plan_id": "plan-dedupe",
            "plan_summary": "Deduplicate planner and evidence proof refs",
            "audience_descriptor": "Researchers",
            "scene_count": 1,
            "artifact_type": "storyboard_grid",
            "scenes": [
                {
                    "scene_id": "scene-1",
                    "title": "Competence Shift",
                    "scene_goal": "Keep one merged proof entry per PDF citation.",
                    "narration_focus": "Explain the shift from moral performance to moral competence.",
                    "visual_prompt": "Use the cited paper excerpt as the proof anchor.",
                    "claim_refs": ["c1"],
                    "evidence_refs": [],
                    "continuity_refs": [],
                    "acceptance_checks": [],
                    "source_media": [
                        {
                            "asset_id": "asset-pdf-1",
                            "modality": "pdf_page",
                            "usage": "callout",
                            "claim_refs": ["c1"],
                            "evidence_refs": [],
                            "page_index": 1,
                            "quote_text": "moving beyond evaluating for mere moral performance... to evaluating for moral competence",
                            "visual_context": "Highlighted text emphasizing the shift from performance to competence.",
                        }
                    ],
                    "modules": [
                        {
                            "module_id": "module-proof",
                            "label": "Primary proof",
                            "purpose": "Show the cited passage.",
                            "content_type": "support_panel",
                            "claim_refs": ["c1"],
                            "source_media": [
                                {
                                    "asset_id": "asset-pdf-1",
                                    "modality": "pdf_page",
                                    "usage": "callout",
                                    "claim_refs": ["c1"],
                                    "evidence_refs": ["c1-e1"],
                                    "page_index": 1,
                                    "label": "moving beyond evaluating for mere moral performance... to evaluating for moral competence",
                                    "quote_text": "moving beyond evaluating for mere moral performance... to evaluating for moral competence",
                                },
                                {
                                    "asset_id": "asset-pdf-1",
                                    "modality": "pdf_page",
                                    "usage": "callout",
                                    "claim_refs": ["c1"],
                                    "evidence_refs": ["c1-e1"],
                                    "page_index": 1,
                                    "label": "moving beyond evaluating for mere moral performance... to evaluating for moral competence",
                                    "quote_text": "moving beyond evaluating for mere moral performance... to evaluating for moral competence",
                                },
                            ],
                        }
                    ],
                }
            ],
        }
    )

    enriched, _, _ = GeminiStoryAgent._enrich_script_pack_with_source_media(
        script_pack=script_pack,
        content_signal={
            "key_claims": [
                {
                    "claim_id": "c1",
                    "claim_text": "The paper argues for evaluating moral competence rather than just performance.",
                    "evidence_snippets": [
                        {
                            "evidence_id": "c1-e1",
                            "type": "text",
                            "asset_id": "asset-pdf-1",
                            "page_index": 1,
                            "quote_text": "moving beyond evaluating for mere moral performance... to evaluating for moral competence",
                        }
                    ],
                }
            ]
        },
        source_manifest={
            "assets": [
                {
                    "asset_id": "asset-pdf-1",
                    "modality": "pdf_page",
                    "uri": "http://example.com/paper.pdf",
                    "page_index": 1,
                }
            ]
        },
    )

    scene = enriched.scenes[0]
    assert len(scene.source_media) == 1
    assert scene.source_media[0].asset_id == "asset-pdf-1"
    assert scene.source_media[0].evidence_refs == ["c1-e1"]
    assert scene.source_media[0].visual_context == "Highlighted text emphasizing the shift from performance to competence."
    assert scene.source_media[0].quote_text == "moving beyond evaluating for mere moral performance... to evaluating for moral competence"

    module = scene.modules[0]
    assert len(module.source_media) == 1
    assert module.source_media[0].evidence_refs == ["c1-e1"]


def test_generate_stream_advanced_events_overlaps_later_scenes_after_scene_one() -> None:
    async def run() -> None:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "scheme": "http",
        }

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": b"", "more_body": False}

        request = Request(scope, receive)
        agent = object.__new__(GeminiStoryAgent)

        active_late_scenes = 0
        max_active_late_scenes = 0
        start_order: list[str] = []

        async def fake_stream_scene_assets(**kwargs):  # noqa: ANN003
            nonlocal active_late_scenes, max_active_late_scenes
            scene_id = kwargs["scene_id"]
            result_collector = kwargs["result_collector"]
            start_order.append(scene_id)
            if scene_id != "scene-1":
                active_late_scenes += 1
                max_active_late_scenes = max(max_active_late_scenes, active_late_scenes)
                await asyncio.sleep(0.05)
                active_late_scenes -= 1
            text = (
                f"{scene_id} explains a grounded claim with enough detail to satisfy the "
                "quality checker while keeping the scene concise and coherent for testing."
            )
            result_collector["text"] = text
            result_collector["image_url"] = "http://localhost/image.png"
            result_collector["audio_url"] = ""
            result_collector["word_count"] = len(text.split())
            if False:
                yield {}

        agent._stream_scene_assets = fake_stream_scene_assets  # type: ignore[method-assign]

        approved_script_pack = {
            "plan_id": "plan-concurrency",
            "plan_summary": "Parallelizable storyboard",
            "audience_descriptor": "Operators",
            "scene_count": 3,
            "artifact_type": "storyboard_grid",
            "planning_mode": "sequential",
            "script_shape": "sequential_storyboard",
            "scenes": [
                {
                    "scene_id": "scene-1",
                    "title": "Opening",
                    "scene_goal": "Open the story.",
                    "narration_focus": "Explain the first point.",
                    "visual_prompt": "Grounded opener.",
                    "claim_refs": ["c1"],
                    "continuity_refs": [],
                    "acceptance_checks": [],
                },
                {
                    "scene_id": "scene-2",
                    "title": "Middle",
                    "scene_goal": "Continue the story.",
                    "narration_focus": "Explain the second point.",
                    "visual_prompt": "Grounded middle.",
                    "claim_refs": ["c2"],
                    "continuity_refs": [],
                    "acceptance_checks": [],
                },
                {
                    "scene_id": "scene-3",
                    "title": "Close",
                    "scene_goal": "Close the story.",
                    "narration_focus": "Explain the third point.",
                    "visual_prompt": "Grounded ending.",
                    "claim_refs": ["c3"],
                    "continuity_refs": [],
                    "acceptance_checks": [],
                },
            ],
        }

        events: list[dict[str, str]] = []
        async for event in agent.generate_stream_advanced_events(
            request=request,
            payload=AdvancedStreamRequest.model_validate(
                {
                    "source_text": "A grounded source text",
                    "content_signal": {
                        "thesis": {"one_liner": "A three-part story"},
                        "key_claims": [
                            {"claim_id": "c1", "claim_text": "Opening claim."},
                            {"claim_id": "c2", "claim_text": "Middle claim."},
                            {"claim_id": "c3", "claim_text": "Closing claim."},
                        ],
                        "narrative_beats": [{"beat_id": "b1", "message": "Beat"}],
                    },
                    "render_profile": {
                        "visual_mode": "illustration",
                        "goal": "teach",
                        "audience": {"level": "beginner", "persona": "General audience"},
                    },
                    "artifact_scope": ["storyboard", "voiceover"],
                    "script_pack": approved_script_pack,
                }
            ),
        ):
            events.append(event)

        scene_start_events = [event for event in events if event["event"] == "scene_start"]
        assert [json.loads(event["data"])["scene_id"] for event in scene_start_events] == [
            "scene-1",
            "scene-2",
            "scene-3",
        ]
        assert start_order[0] == "scene-1"
        assert max_active_late_scenes >= 2

    asyncio.run(run())


def test_resolve_source_media_payloads_includes_pdf_line_locator() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    request = Request(scope)

    with patch(
        "app.services.gemini_story_agent.resolve_pdf_proof_locator",
        return_value={
            "line_start": 12,
            "line_end": 13,
            "matched_excerpt": "We propose a roadmap for evaluating moral competence in large language models.",
        },
    ):
        payloads = GeminiStoryAgent._resolve_source_media_payloads(
            request=request,
            scene_id="scene-1",
            source_media=[
                SourceMediaRefSchema(
                    asset_id="asset-paper-1",
                    modality="pdf_page",
                    usage="callout",
                    claim_refs=["c1"],
                    evidence_refs=["e1"],
                    page_index=4,
                    quote_text="evaluating moral competence in large language models",
                    visual_context="Framework paragraph in the paper body.",
                )
            ],
            source_manifest={
                "assets": [
                    {
                        "asset_id": "asset-paper-1",
                        "modality": "pdf_page",
                        "uri": "http://example.com/paper.pdf",
                        "page_index": 4,
                        "title": "paper.pdf",
                    }
                ]
            },
        )

    assert len(payloads) == 1
    assert payloads[0]["page_index"] == 4
    assert payloads[0]["line_start"] == 12
    assert payloads[0]["line_end"] == 13
    assert "moral competence" in payloads[0]["matched_excerpt"].lower()


def test_resolve_source_media_payloads_overwrites_zero_pdf_page_with_locator_match() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    request = Request(scope)

    with patch(
        "app.services.gemini_story_agent.resolve_pdf_proof_locator",
        return_value={
            "page_index": 4,
            "line_start": 12,
            "line_end": 13,
            "matched_excerpt": "We propose a roadmap for evaluating moral competence in large language models.",
        },
    ):
        payloads = GeminiStoryAgent._resolve_source_media_payloads(
            request=request,
            scene_id="scene-1",
            source_media=[
                SourceMediaRefSchema(
                    asset_id="asset-paper-1",
                    modality="pdf_page",
                    usage="callout",
                    claim_refs=["c1"],
                    evidence_refs=["e1"],
                    page_index=0,
                    quote_text="evaluating moral competence in large language models",
                    visual_context="Framework paragraph in the paper body.",
                )
            ],
            source_manifest={
                "assets": [
                    {
                        "asset_id": "asset-paper-1",
                        "modality": "pdf_page",
                        "uri": "http://example.com/paper.pdf",
                        "title": "paper.pdf",
                    }
                ]
            },
        )

    assert len(payloads) == 1
    assert payloads[0]["page_index"] == 4
    assert payloads[0]["line_start"] == 12
    assert payloads[0]["line_end"] == 13
