import asyncio
import json
import math
import re
import time
from typing import Any, AsyncIterator

from fastapi import Request
from google.genai import types

from app.config import SCHEMAS_DIR, get_gemini_client
from app.schemas.events import build_sse_event
from app.schemas.requests import (
    AdvancedStreamRequest,
    OutlineSchema,
    RegenerateSceneRequest,
    ScenePlanSchema,
    ScriptPack,
    ScriptPackRequest,
    ScriptPackScene,
    SignalExtractionRequest,
)
from app.services.audio_pipeline import generate_audio_and_get_url
from app.services.image_pipeline import save_image_and_get_url
from app.services.interleaved_parser import (
    evaluate_scene_quality,
    extract_anchor_terms,
    extract_parts_from_chunk,
    extract_parts_from_response,
    normalized_scene_id,
)


class GeminiStoryAgent:
    def __init__(self) -> None:
        self.client = get_gemini_client()

    @staticmethod
    def _load_schema_text(filename: str) -> str:
        return (SCHEMAS_DIR / filename).read_text(encoding="utf-8")

    @staticmethod
    def _style_guide_for_mode(visual_mode: str) -> str:
        if visual_mode == "diagram":
            return (
                "Visuals must be clean, high-detail educational diagrams or "
                "historically/scientifically accurate realistic landscapes. Ensure the visual "
                "specifically illustrates the scientific or historical concepts mentioned in "
                "the text. Avoid image text labels. Prefer extreme accuracy, realism, and clarity."
            )
        if visual_mode == "hybrid":
            return (
                "Visuals must blend 3D subjects with holographic UI overlays, charts, "
                "or interface elements in a consistent style."
            )
        return (
            "Visuals must be high-quality cinematic 3D renders or polished vector-style "
            "illustrations with consistent palette and character design."
        )

    @staticmethod
    def _is_resource_exhausted(exc: Exception) -> bool:
        message = str(exc).lower()
        return (
            "resource_exhausted" in message
            or "quota exceeded" in message
            or "429" in message
            or "rate limit" in message
        )

    @staticmethod
    def _is_daily_quota_exhausted(exc: Exception) -> bool:
        message = str(exc).lower()
        return "perday" in message or "per-day" in message or "requestsperday" in message

    @staticmethod
    def _extract_retry_delay_seconds(exc: Exception, default_seconds: float = 5.0) -> float:
        message = str(exc)
        retry_in_match = re.search(r"retry in ([0-9]+(?:\.[0-9]+)?)s", message, re.IGNORECASE)
        if retry_in_match:
            return max(1.0, min(float(retry_in_match.group(1)), 30.0))

        retry_delay_match = re.search(r"retryDelay': '([0-9]+)s'", message)
        if retry_delay_match:
            return max(1.0, min(float(retry_delay_match.group(1)), 30.0))

        return default_seconds

    @staticmethod
    def _friendly_quota_error_message() -> str:
        return (
            "Gemini generation is temporarily unavailable due to quota or rate limits "
            "(RESOURCE_EXHAUSTED). Wait ~30-60 seconds and retry, or use a billed API key/project."
        )

    @staticmethod
    def _compile_script_pack(
        *,
        plan_id: str,
        thesis: str,
        audience_descriptor: str,
        scenes: list[ScenePlanSchema],
        must_include: list[str],
        must_avoid: list[str],
    ) -> ScriptPack:
        script_scenes: list[ScriptPackScene] = []

        for idx, scene in enumerate(scenes, start=1):
            scene_id = normalized_scene_id(scene.scene_id, idx)
            title = (scene.title or f"Scene {idx}").strip()
            narration_focus = (
                scene.narration_focus
                or f"Explain core point {idx} about {thesis}."
            ).strip()
            visual_prompt = (
                scene.visual_prompt
                or "Generate a precise educational visual that supports the narration."
            ).strip()
            claim_refs = [ref for ref in scene.claim_refs if isinstance(ref, str) and ref.strip()]

            continuity_refs: list[str] = []
            if idx > 1:
                continuity_refs.append(f"Maintain continuity from scene-{idx - 1}.")
            continuity_refs.extend(extract_anchor_terms(title, limit=2))

            acceptance_checks = [
                "Narration is between 50 and 100 words.",
                "Narration is plain spoken prose with no labels or markdown.",
                "Visual and narration align with the stated scene focus.",
            ]
            if must_include:
                acceptance_checks.append(
                    f"Prefer these audience cues: {', '.join(must_include[:4])}."
                )
            if must_avoid:
                acceptance_checks.append(
                    f"Avoid these patterns: {', '.join(must_avoid[:4])}."
                )

            script_scenes.append(
                ScriptPackScene(
                    scene_id=scene_id,
                    title=title,
                    scene_goal=f"Deliver scene {idx} of the explainer clearly for {audience_descriptor}.",
                    narration_focus=narration_focus,
                    visual_prompt=visual_prompt,
                    claim_refs=claim_refs,
                    continuity_refs=continuity_refs,
                    acceptance_checks=acceptance_checks,
                )
            )

        return ScriptPack(
            plan_id=plan_id,
            plan_summary=f"{thesis} explained through {len(script_scenes)} cohesive scenes.",
            audience_descriptor=audience_descriptor,
            scene_count=len(script_scenes),
            scenes=script_scenes,
        )

    async def _stream_scene_assets(
        self,
        request: Request,
        scene_id: str,
        topic: str,
        audience: str,
        tone: str,
        scene_title: str,
        narration_focus: str,
        style_guide: str,
        visual_prompt: str,
        image_prefix: str,
        audio_prefix: str,
        continuity_hints: list[str] | None = None,
        extra_constraints: list[str] | None = None,
        result_collector: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, str]]:
        continuity_block = ""
        if continuity_hints:
            continuity_lines = "\n".join(f"- {hint}" for hint in continuity_hints[-4:])
            continuity_block = f"CONTINUITY MEMORY:\n{continuity_lines}\n\n"

        constraints_block = ""
        if extra_constraints:
            constraints_lines = "\n".join(f"- {constraint}" for constraint in extra_constraints[:8])
            constraints_block = f"ACCEPTANCE CHECKS:\n{constraints_lines}\n\n"

        scene_prompt = (
            f"CONTEXT: We are building an explainer about '{topic}' for a {audience} audience.\n"
            f"TONE: {tone}\n"
            f"SCENE TITLE: {scene_title}\n"
            f"SCENE FOCUS: {narration_focus}\n"
            f"VISUAL STYLE: {style_guide}\n"
            f"VISUAL DIRECTION: {visual_prompt}\n\n"
            f"{continuity_block}"
            f"{constraints_block}"
            "CRITICAL CONTINUITY RULE: All generated images MUST share an identical, cohesive visual style. "
            "Maintain the exact same art direction as previous scenes.\n\n"
            "TASK: Generate the content for THIS SCENE ONLY.\n"
            "STRICT OUTPUT RULES:\n"
            "1) Start immediately with the spoken narration text. NO labels like 'Narration:', "
            "NO scene numbers, NO markdown titles.\n"
            "2) The text must be 50-100 words.\n"
            "3) Immediately after the text, generate the corresponding high-quality inline image. "
            "The image MUST accurately depict the specific scientific or historical details mentioned in the text.\n"
            "4) DO NOT output any other text or conversational filler."
        )

        current_scene_text = ""
        latest_image_url = ""
        audio_url = ""
        max_attempts = 3

        for attempt in range(max_attempts):
            emitted_any_chunk = False
            try:
                response_stream = await self.client.aio.models.generate_content_stream(
                    model="gemini-3-pro-image-preview",
                    contents=scene_prompt,
                    config=types.GenerateContentConfig(temperature=0.7),
                )

                async for chunk in response_stream:
                    if await request.is_disconnected():
                        return

                    text_parts, image_parts = extract_parts_from_chunk(chunk)
                    if not text_parts and not image_parts:
                        continue

                    emitted_any_chunk = True

                    for text in text_parts:
                        current_scene_text += text
                        yield build_sse_event(
                            "story_text_delta",
                            {"scene_id": scene_id, "delta": text},
                        )

                    for image_bytes in image_parts:
                        latest_image_url = save_image_and_get_url(
                            request=request,
                            scene_id=scene_id,
                            image_bytes=image_bytes,
                            prefix=image_prefix,
                        )
                        yield build_sse_event(
                            "diagram_ready",
                            {"scene_id": scene_id, "url": latest_image_url},
                        )
                break
            except Exception as exc:
                is_retryable = (
                    self._is_resource_exhausted(exc)
                    and not self._is_daily_quota_exhausted(exc)
                    and not emitted_any_chunk
                    and attempt < max_attempts - 1
                )
                if not is_retryable:
                    raise

                delay_sec = self._extract_retry_delay_seconds(exc) * (1.0 + 0.5 * attempt)
                yield build_sse_event(
                    "status",
                    {
                        "scene_id": scene_id,
                        "message": f"Rate limit reached. Retrying this scene in {int(round(delay_sec))}s...",
                    },
                )
                await asyncio.sleep(delay_sec)

        if current_scene_text.strip():
            audio_url = generate_audio_and_get_url(
                request=request,
                scene_id=scene_id,
                text=current_scene_text,
                prefix=audio_prefix,
            )
            if audio_url:
                yield build_sse_event("audio_ready", {"scene_id": scene_id, "url": audio_url})

        if result_collector is not None:
            result_collector["text"] = current_scene_text
            result_collector["image_url"] = latest_image_url
            result_collector["audio_url"] = audio_url
            result_collector["word_count"] = len(re.findall(r"\b[\w'-]+\b", current_scene_text))

    async def extract_signal(self, payload: SignalExtractionRequest) -> dict[str, Any]:
        try:
            schema_str = self._load_schema_text("content_signal.schema.json")
            extraction_prompt = (
                "Analyze the following document and extract the core signal into a highly structured JSON format.\n"
                "You MUST strictly adhere to the provided JSON Schema.\n\n"
                f"DOCUMENT:\n{payload.input_text}\n\n"
                f"JSON SCHEMA:\n{schema_str}\n\n"
                "Return ONLY valid JSON matching this schema, without any markdown formatting like ```json."
            )
            response = await self.client.aio.models.generate_content(
                model="gemini-3.1-pro-preview",
                contents=extraction_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                ),
            )
            signal_data = json.loads(response.text)
            return {"status": "success", "content_signal": signal_data}
        except Exception as exc:
            print(f"Extraction error: {exc}")
            return {"status": "error", "message": str(exc)}

    async def generate_stream_events(
        self,
        *,
        request: Request,
        topic: str,
        audience: str,
        tone: str,
        visual_mode: str = "illustration",
    ) -> AsyncIterator[dict[str, str]]:
        style_guide = self._style_guide_for_mode(visual_mode)
        planning_prompt = (
            f"Create a 4-scene outline for a visual explainer about '{topic}'. "
            f"Target audience: {audience}. Tone: {tone or 'clear and engaging'}. "
            "You MUST generate EXACTLY 4 scenes.\n\n"
            f"Visual rule: {style_guide}"
        )

        try:
            plan_response = await self.client.aio.models.generate_content(
                model="gemini-3.1-pro-preview",
                contents=planning_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    response_mime_type="application/json",
                    response_schema=OutlineSchema,
                ),
            )
            parsed_outline = OutlineSchema.model_validate_json(plan_response.text)
            scenes = parsed_outline.scenes[:4]

            while len(scenes) < 4:
                idx = len(scenes) + 1
                scenes.append(
                    ScenePlanSchema(
                        scene_id=f"scene-{idx}",
                        title=f"Scene {idx}",
                        narration_focus=f"Explain key point {idx} about {topic}.",
                        visual_prompt="Generate a visually rich educational image for this scene.",
                    )
                )

            yield build_sse_event(
                "scene_queue_ready",
                {
                    "scenes": [scene.model_dump() for scene in scenes],
                    "optimized_count": len(scenes),
                },
            )

            for idx, scene in enumerate(scenes, start=1):
                if await request.is_disconnected():
                    return

                scene_id = normalized_scene_id(scene.scene_id, idx)
                title = scene.title or f"Scene {idx}"
                narration_focus = scene.narration_focus or f"Explain key point {idx}."
                visual_prompt = scene.visual_prompt or ""

                yield build_sse_event("scene_start", {"scene_id": scene_id, "title": title})

                async for event in self._stream_scene_assets(
                    request=request,
                    scene_id=scene_id,
                    topic=topic,
                    audience=audience,
                    tone=tone,
                    scene_title=title,
                    narration_focus=narration_focus,
                    style_guide=style_guide,
                    visual_prompt=visual_prompt,
                    image_prefix="interleaved",
                    audio_prefix="audio",
                ):
                    yield event

                yield build_sse_event("scene_done", {"scene_id": scene_id})

            yield build_sse_event(
                "final_bundle_ready",
                {
                    "run_id": "interleaved-run-123",
                    "bundle_url": "/api/final-bundle/interleaved-run-123",
                },
            )
        except Exception as exc:
            print(f"Error generating stream: {exc}")
            message = self._friendly_quota_error_message() if self._is_resource_exhausted(exc) else str(exc)
            yield build_sse_event("error", {"error": message})

    async def generate_stream_advanced_events(
        self,
        *,
        request: Request,
        payload: AdvancedStreamRequest,
    ) -> AsyncIterator[dict[str, str]]:
        content_signal = payload.content_signal
        render_profile = payload.render_profile

        approved_script_pack_raw = payload.script_pack
        approved_script_pack: ScriptPack | None = None
        if isinstance(approved_script_pack_raw, dict):
            try:
                approved_script_pack = ScriptPack.model_validate(approved_script_pack_raw)
            except Exception:
                approved_script_pack = None

        visual_mode = render_profile.get("visual_mode", "illustration")
        audience_cfg = render_profile.get("audience", {})
        audience_level = str(audience_cfg.get("level", "beginner")).lower()
        audience_persona = str(audience_cfg.get("persona", "General audience")).strip()
        domain_context = str(audience_cfg.get("domain_context", "")).strip()
        taste_bar = str(audience_cfg.get("taste_bar", "standard")).lower()
        must_include = [
            str(item).strip()
            for item in audience_cfg.get("must_include", [])
            if isinstance(item, str) and str(item).strip()
        ][:8]
        must_avoid = [
            str(item).strip()
            for item in audience_cfg.get("must_avoid", [])
            if isinstance(item, str) and str(item).strip()
        ][:8]
        goal = render_profile.get("goal", "teach")
        style_descriptors = ", ".join(render_profile.get("style", {}).get("descriptors", ["clean", "modern"]))
        palette = render_profile.get("palette", {})

        style_guide = f"Visual Mode: {visual_mode.upper()}.\n"
        style_guide += f"Style Descriptors: {style_descriptors}.\n"
        style_guide += f"Taste Bar: {taste_bar.upper()}.\n"
        if palette.get("mode") == "brand":
            style_guide += (
                "Mandatory Color Palette: "
                f"Primary {palette.get('primary', '#000000')}, "
                f"Secondary {palette.get('secondary', '#FFFFFF')}, "
                f"Accent {palette.get('accent', '#FF0000')}. "
                "Use these specific hex colors prominently.\n"
            )
        else:
            style_guide += "Palette: Auto-select an engaging, educational color palette.\n"

        if visual_mode == "diagram":
            style_guide += (
                "CRITICAL: Do NOT request 2D maps with text labels. "
                "Focus on abstract or photorealistic educational infographics."
            )
        elif visual_mode == "hybrid":
            style_guide += "CRITICAL: Blend 3D objects with floating holographic UI elements or charts."

        thesis = content_signal.get("thesis", {}).get("one_liner", "A generic topic")
        beats = content_signal.get("narrative_beats", [])
        audience_descriptor = f"{audience_persona} ({audience_level})"
        if domain_context:
            audience_descriptor += f" in {domain_context}"

        output_controls = render_profile.get("output_controls", {})
        target_duration = output_controls.get("target_duration_sec", 60)
        density = render_profile.get("density", "standard")
        sec_per_scene = 10 if density == "detailed" else (18 if density == "simple" else 14)

        base_scenes = math.ceil(target_duration / sec_per_scene)
        claims_count = len(content_signal.get("key_claims", []))
        if claims_count > 5:
            base_scenes += 1
        if audience_level == "beginner":
            base_scenes -= 1
        scene_count = max(3, min(base_scenes, 8))

        planning_prompt = (
            f"Given this core thesis: '{thesis}' and these narrative beats: {json.dumps(beats[:10])}, "
            f"create a specific {scene_count}-scene storyboard outline for the audience persona "
            f"'{audience_descriptor}'. Audience taste bar is '{taste_bar}'. "
            "Ensure every scene has a descriptive title and a clear narration focus."
        )
        if must_include:
            planning_prompt += f" Must include: {', '.join(must_include)}."
        if must_avoid:
            planning_prompt += f" Must avoid: {', '.join(must_avoid)}."

        try:
            if approved_script_pack is not None and approved_script_pack.scenes:
                script_pack = approved_script_pack
                yield build_sse_event(
                    "status",
                    {"message": "Using approved script pack. Starting scene generation..."},
                )
            else:
                plan_response = await self.client.aio.models.generate_content(
                    model="gemini-3.1-pro-preview",
                    contents=planning_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                        response_mime_type="application/json",
                        response_schema=OutlineSchema,
                    ),
                )
                parsed_outline = OutlineSchema.model_validate_json(plan_response.text)
                scenes = parsed_outline.scenes[:scene_count]

                while len(scenes) < scene_count:
                    idx = len(scenes) + 1
                    scenes.append(
                        ScenePlanSchema(
                            scene_id=f"scene-{idx}",
                            title=f"Explainer Point {idx}",
                            narration_focus=f"Further detail on {thesis}.",
                            visual_prompt="A relevant educational visual.",
                            claim_refs=[],
                        )
                    )

                script_pack = self._compile_script_pack(
                    plan_id=f"script-pack-{int(time.time())}",
                    thesis=thesis,
                    audience_descriptor=audience_descriptor,
                    scenes=scenes,
                    must_include=must_include,
                    must_avoid=must_avoid,
                )

            yield build_sse_event("script_pack_ready", {"script_pack": script_pack.model_dump()})

            yield build_sse_event(
                "scene_queue_ready",
                {
                    "scenes": [
                        {
                            "scene_id": scene.scene_id,
                            "title": scene.title,
                            "claim_refs": scene.claim_refs,
                            "narration_focus": scene.narration_focus,
                        }
                        for scene in script_pack.scenes
                    ],
                    "optimized_count": script_pack.scene_count,
                },
            )

            continuity_memory: list[str] = []

            for scene in script_pack.scenes:
                if await request.is_disconnected():
                    return

                scene_id = scene.scene_id
                title = scene.title

                yield build_sse_event(
                    "scene_start",
                    {
                        "scene_id": scene_id,
                        "title": title,
                        "claim_refs": scene.claim_refs,
                    },
                )

                retries_used = 0
                qa_result: dict[str, Any] = {
                    "scene_id": scene_id,
                    "status": "WARN",
                    "score": 0.0,
                    "reasons": ["Quality checks not executed."],
                    "attempt": 1,
                    "word_count": 0,
                }
                scene_result: dict[str, Any] = {}
                retry_reason_constraints: list[str] = []

                for attempt_index in range(2):
                    scene_result = {}
                    active_continuity = (continuity_memory[-3:] + scene.continuity_refs)[-6:]
                    attempt_constraints = list(scene.acceptance_checks)
                    if retry_reason_constraints:
                        attempt_constraints.append(
                            f"Fix these QA issues from previous attempt: {'; '.join(retry_reason_constraints[:3])}."
                        )

                    if attempt_index > 0:
                        yield build_sse_event(
                            "scene_retry_reset",
                            {"scene_id": scene_id, "retry_index": attempt_index},
                        )

                    async for event in self._stream_scene_assets(
                        request=request,
                        scene_id=scene_id,
                        topic=thesis,
                        audience=audience_descriptor,
                        tone=goal,
                        scene_title=title,
                        narration_focus=scene.narration_focus,
                        style_guide=style_guide,
                        visual_prompt=scene.visual_prompt,
                        image_prefix="advanced_interleaved",
                        audio_prefix="advanced_audio",
                        continuity_hints=active_continuity,
                        extra_constraints=attempt_constraints,
                        result_collector=scene_result,
                    ):
                        yield event

                    qa_result = evaluate_scene_quality(
                        scene=scene,
                        generated_text=str(scene_result.get("text", "")),
                        image_url=str(scene_result.get("image_url", "")),
                        must_include=must_include,
                        must_avoid=must_avoid,
                        continuity_hints=active_continuity,
                        attempt=attempt_index + 1,
                    )
                    yield build_sse_event("qa_status", qa_result)

                    if qa_result["status"] != "FAIL":
                        break

                    if attempt_index == 0:
                        retry_reason_constraints = list(qa_result["reasons"])
                        retries_used = 1
                        yield build_sse_event(
                            "qa_retry",
                            {
                                "scene_id": scene_id,
                                "retry_index": 1,
                                "reasons": qa_result["reasons"],
                            },
                        )

                continuity_tokens = extract_anchor_terms(str(scene_result.get("text", "")), limit=4)
                if continuity_tokens:
                    continuity_memory.append(f"{title}: {', '.join(continuity_tokens)}")
                    continuity_memory = continuity_memory[-8:]

                yield build_sse_event(
                    "scene_done",
                    {
                        "scene_id": scene_id,
                        "qa_status": qa_result["status"],
                        "auto_retries": retries_used,
                    },
                )

            yield build_sse_event(
                "final_bundle_ready",
                {
                    "run_id": "advanced-run-123",
                    "bundle_url": "/api/final-bundle/advanced-run-123",
                },
            )
        except Exception as exc:
            print(f"Error in advanced stream: {exc}")
            message = self._friendly_quota_error_message() if self._is_resource_exhausted(exc) else str(exc)
            yield build_sse_event("error", {"error": message})

    async def generate_script_pack_advanced(self, payload: ScriptPackRequest) -> dict[str, Any]:
        content_signal = payload.content_signal
        render_profile = payload.render_profile

        audience_cfg = render_profile.get("audience", {})
        audience_level = str(audience_cfg.get("level", "beginner")).lower()
        audience_persona = str(audience_cfg.get("persona", "General audience")).strip()
        domain_context = str(audience_cfg.get("domain_context", "")).strip()
        taste_bar = str(audience_cfg.get("taste_bar", "standard")).lower()
        must_include = [
            str(item).strip()
            for item in audience_cfg.get("must_include", [])
            if isinstance(item, str) and str(item).strip()
        ][:8]
        must_avoid = [
            str(item).strip()
            for item in audience_cfg.get("must_avoid", [])
            if isinstance(item, str) and str(item).strip()
        ][:8]

        thesis = content_signal.get("thesis", {}).get("one_liner", "A generic topic")
        beats = content_signal.get("narrative_beats", [])
        audience_descriptor = f"{audience_persona} ({audience_level})"
        if domain_context:
            audience_descriptor += f" in {domain_context}"

        output_controls = render_profile.get("output_controls", {})
        target_duration = output_controls.get("target_duration_sec", 60)
        density = render_profile.get("density", "standard")
        sec_per_scene = 10 if density == "detailed" else (18 if density == "simple" else 14)

        base_scenes = math.ceil(target_duration / sec_per_scene)
        claims_count = len(content_signal.get("key_claims", []))
        if claims_count > 5:
            base_scenes += 1
        if audience_level == "beginner":
            base_scenes -= 1
        scene_count = max(3, min(base_scenes, 8))

        planning_prompt = (
            f"Given this core thesis: '{thesis}' and these narrative beats: {json.dumps(beats[:10])}, "
            f"create a specific {scene_count}-scene storyboard outline for the audience persona "
            f"'{audience_descriptor}'. Audience taste bar is '{taste_bar}'. "
            "Ensure every scene has a descriptive title and a clear narration focus."
        )
        if must_include:
            planning_prompt += f" Must include: {', '.join(must_include)}."
        if must_avoid:
            planning_prompt += f" Must avoid: {', '.join(must_avoid)}."

        try:
            plan_response = await self.client.aio.models.generate_content(
                model="gemini-3.1-pro-preview",
                contents=planning_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    response_mime_type="application/json",
                    response_schema=OutlineSchema,
                ),
            )
            parsed_outline = OutlineSchema.model_validate_json(plan_response.text)
            scenes = parsed_outline.scenes[:scene_count]

            while len(scenes) < scene_count:
                idx = len(scenes) + 1
                scenes.append(
                    ScenePlanSchema(
                        scene_id=f"scene-{idx}",
                        title=f"Explainer Point {idx}",
                        narration_focus=f"Further detail on {thesis}.",
                        visual_prompt="A relevant educational visual.",
                        claim_refs=[],
                    )
                )

            script_pack = self._compile_script_pack(
                plan_id=f"script-pack-{int(time.time())}",
                thesis=thesis,
                audience_descriptor=audience_descriptor,
                scenes=scenes,
                must_include=must_include,
                must_avoid=must_avoid,
            )
            return {"status": "success", "script_pack": script_pack.model_dump()}
        except Exception as exc:
            print(f"Error generating script pack: {exc}")
            message = self._friendly_quota_error_message() if self._is_resource_exhausted(exc) else str(exc)
            return {"status": "error", "message": message}

    async def regenerate_scene(
        self,
        payload: RegenerateSceneRequest,
        request: Request,
    ) -> dict[str, Any]:
        scene_id = payload.scene_id
        current_text = payload.current_text
        instruction = payload.instruction
        visual_mode = payload.visual_mode

        try:
            style_guide = self._style_guide_for_mode(visual_mode)
            regen_prompt = (
                f"Regenerate scene {scene_id} with this instruction: {instruction}\n\n"
                f"Original text context: {current_text}\n\n"
                "Requirements:\n"
                "1) Return updated narration text first (no labels or markdown).\n"
                "2) Then return one high-quality inline image for that scene. "
                "The image MUST accurately depict any specific scientific or historical details mentioned in the text.\n"
                f"3) Follow this visual style guide: {style_guide}"
            )

            response = await self.client.aio.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=regen_prompt,
                config=types.GenerateContentConfig(temperature=0.7),
            )
            updated_text, image_bytes = extract_parts_from_response(response)

            image_url = ""
            if image_bytes:
                image_url = save_image_and_get_url(
                    request=request,
                    scene_id=scene_id,
                    image_bytes=image_bytes,
                    prefix="regen",
                )

            audio_url = generate_audio_and_get_url(
                request=request,
                scene_id=scene_id,
                text=updated_text,
                prefix="regen_audio",
            )

            return {
                "status": "success",
                "scene_id": scene_id,
                "text": updated_text,
                "imageUrl": image_url,
                "audioUrl": audio_url,
            }
        except Exception as exc:
            print(f"Regeneration error: {exc}")
            return {"status": "error", "message": str(exc)}
