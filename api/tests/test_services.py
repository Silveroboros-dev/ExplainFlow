import asyncio
import json
import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from fastapi import Request
from PIL import Image, ImageChops

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.schemas.events import build_sse_event
from app.schemas.requests import (
    AdvancedStreamRequest,
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
            assert len(agent.client.files.upload_calls) == 1
            assert agent.client.files.deleted_names == ["files/1"]
            assert len(agent.client.models.contents) == 2
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
