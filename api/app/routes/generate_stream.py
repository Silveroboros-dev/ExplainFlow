import json
import time
from pathlib import Path

from fastapi import APIRouter, Request
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

router = APIRouter()

client = genai.Client()

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMAS_DIR = REPO_ROOT / "schemas"
ASSET_DIR = Path(__file__).resolve().parents[1] / "static" / "assets"
ASSET_DIR.mkdir(parents=True, exist_ok=True)

class SignalExtractionRequest(BaseModel):
    input_text: str

class RegenerateSceneRequest(BaseModel):
    scene_id: str
    current_text: str
    instruction: str
    visual_mode: str = "illustration"

class ScenePlanSchema(BaseModel):
    scene_id: str = Field(description="A unique identifier for the scene, e.g., 'scene-1'")
    title: str = Field(description="The title of the scene")
    narration_focus: str = Field(description="Instructions on what the narration should focus on for this scene")
    visual_prompt: str = Field(description="A detailed image prompt for the scene visual. It must specify subject, style, composition, and color direction. Keep image text-free.")
    claim_refs: list[str] = Field(default=[], description="List of claim IDs (e.g., 'c1', 'c2') that this scene covers")

class OutlineSchema(BaseModel):
    scenes: list[ScenePlanSchema]

def _load_schema_text(filename: str) -> str:
    return (SCHEMAS_DIR / filename).read_text(encoding="utf-8")

def _style_guide_for_mode(visual_mode: str) -> str:
    if visual_mode == "diagram":
        return "Visuals must be clean, high-detail educational diagrams or historically/scientifically accurate realistic landscapes. Ensure the visual specifically illustrates the scientific or historical concepts mentioned in the text. Avoid image text labels. Prefer extreme accuracy, realism, and clarity."
    if visual_mode == "hybrid":
        return "Visuals must blend 3D subjects with holographic UI overlays, charts, or interface elements in a consistent style."
    return "Visuals must be high-quality cinematic 3D renders or polished vector-style illustrations with consistent palette and character design."

def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")

def _save_image_and_get_url(request: Request, scene_id: str, image_bytes: bytes, prefix: str) -> str:
    ts = int(time.time() * 1000)
    img_filename = f"{prefix}_{scene_id}_{ts}.png"
    img_path = ASSET_DIR / img_filename
    img_path.write_bytes(image_bytes)
    return f"{_base_url(request)}/static/assets/{img_filename}"

def _generate_audio_and_get_url(request: Request, scene_id: str, text: str, prefix: str) -> str:
    narration = text.strip()
    if not narration:
        return ""
    try:
        from gtts import gTTS
    except Exception as exc:
        print(f"Audio generation unavailable (gTTS import failed): {exc}")
        return ""
    try:
        ts = int(time.time() * 1000)
        audio_filename = f"{prefix}_{scene_id}_{ts}.mp3"
        audio_path = ASSET_DIR / audio_filename
        gTTS(text=narration, lang="en", slow=False).save(str(audio_path))
        return f"{_base_url(request)}/static/assets/{audio_filename}"
    except Exception as exc:
        print(f"Audio generation failed: {exc}")
        return ""

async def _stream_scene_assets(
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
):
    scene_prompt = (
        f"CONTEXT: We are building an explainer about '{topic}' for a {audience} audience.\n"
        f"SCENE TITLE: {scene_title}\n"
        f"SCENE FOCUS: {narration_focus}\n"
        f"VISUAL STYLE: {style_guide}\n"
        f"VISUAL DIRECTION: {visual_prompt}\n\n"
        "TASK: Generate the content for THIS SCENE ONLY.\n"
        "STRICT OUTPUT RULES:\n"
        "1) Start immediately with the spoken narration text. NO labels like 'Narration:', NO scene numbers, NO markdown titles.\n"
        "2) The text must be 50-100 words.\n"
        "3) Immediately after the text, generate the corresponding high-quality inline image. The image MUST accurately depict the specific scientific or historical details mentioned in the text.\n"
        "4) DO NOT output any other text or conversational filler."
    )

    response_stream = await client.aio.models.generate_content_stream(
        model="gemini-3-pro-image-preview",
        contents=scene_prompt,
        config=types.GenerateContentConfig(temperature=0.7),
    )

    current_scene_text = ""
    async for chunk in response_stream:
        if await request.is_disconnected():
            return
        
        candidates = getattr(chunk, "candidates", [])
        if not candidates:
            continue
            
        parts = getattr(candidates[0].content, "parts", [])
        for part in parts:
            text = getattr(part, "text", None)
            if text:
                current_scene_text += text
                yield {
                    "event": "story_text_delta",
                    "data": json.dumps({"scene_id": scene_id, "delta": text}),
                }
            
            inline_data = getattr(part, "inline_data", None)
            binary = getattr(inline_data, "data", None) if inline_data else None
            if binary:
                image_url = _save_image_and_get_url(
                    request=request,
                    scene_id=scene_id,
                    image_bytes=binary,
                    prefix=image_prefix,
                )
                yield {
                    "event": "diagram_ready",
                    "data": json.dumps({"scene_id": scene_id, "url": image_url}),
                }

    if current_scene_text.strip():
        audio_url = _generate_audio_and_get_url(
            request=request,
            scene_id=scene_id,
            text=current_scene_text,
            prefix=audio_prefix,
        )
        if audio_url:
            yield {
                "event": "audio_ready",
                "data": json.dumps({"scene_id": scene_id, "url": audio_url}),
            }

def _normalized_scene_id(raw: str, default_idx: int) -> str:
    candidate = (raw or "").strip()
    if not candidate:
        return f"scene-{default_idx}"
    return candidate

@router.post("/extract-signal")
async def extract_signal(request: SignalExtractionRequest):
    try:
        schema_str = _load_schema_text("content_signal.schema.json")
        extraction_prompt = f"Analyze the following document and extract the core signal into a highly structured JSON format.\nYou MUST strictly adhere to the provided JSON Schema.\n\nDOCUMENT:\n{request.input_text}\n\nJSON SCHEMA:\n{schema_str}\n\nReturn ONLY valid JSON matching this schema, without any markdown formatting like ```json."
        response = await client.aio.models.generate_content(
            model="gemini-3.1-pro-preview",
            contents=extraction_prompt,
            config=types.GenerateContentConfig(temperature=0.2, response_mime_type="application/json"),
        )
        signal_data = json.loads(response.text)
        return {"status": "success", "content_signal": signal_data}
    except Exception as exc:
        print(f"Extraction error: {exc}")
        return {"status": "error", "message": str(exc)}

@router.get("/generate-stream")
async def generate_stream(
    request: Request,
    topic: str,
    audience: str,
    tone: str,
    visual_mode: str = "illustration",
):
    async def event_generator():
        style_guide = _style_guide_for_mode(visual_mode)
        planning_prompt = f"Create a 4-scene outline for a visual explainer about '{topic}'. Target audience: {audience}. Tone: {tone or 'clear and engaging'}. You MUST generate EXACTLY 4 scenes.\n\nVisual rule: {style_guide}"
        try:
            plan_response = await client.aio.models.generate_content(
                model="gemini-3.1-pro-preview",
                contents=planning_prompt,
                config=types.GenerateContentConfig(temperature=0.7, response_mime_type="application/json", response_schema=OutlineSchema),
            )
            parsed_outline = OutlineSchema.model_validate_json(plan_response.text)
            scenes = parsed_outline.scenes[:4]

            while len(scenes) < 4:
                idx = len(scenes) + 1
                scenes.append(ScenePlanSchema(scene_id=f"scene-{idx}", title=f"Scene {idx}", narration_focus=f"Explain key point {idx} about {topic}.", visual_prompt="Generate a visually rich educational image for this scene."))

            # Emit the queue instantly
            yield {
                "event": "scene_queue_ready",
                "data": json.dumps({"scenes": [s.model_dump() for s in scenes], "optimized_count": len(scenes)})
            }

            for idx, scene in enumerate(scenes, start=1):
                if await request.is_disconnected(): return
                scene_id = _normalized_scene_id(scene.scene_id, idx)
                title = scene.title or f"Scene {idx}"
                narration_focus = scene.narration_focus or f"Explain key point {idx}."
                visual_prompt = scene.visual_prompt or ""

                yield {"event": "scene_start", "data": json.dumps({"scene_id": scene_id, "title": title})}

                async for event in _stream_scene_assets(
                    request=request, scene_id=scene_id, topic=topic, audience=audience, tone=tone, scene_title=title,
                    narration_focus=narration_focus, style_guide=style_guide, visual_prompt=visual_prompt,
                    image_prefix="interleaved", audio_prefix="audio"
                ):
                    yield event

                yield {"event": "scene_done", "data": json.dumps({"scene_id": scene_id})}

            yield {"event": "final_bundle_ready", "data": json.dumps({"run_id": "interleaved-run-123", "bundle_url": "/api/final-bundle/interleaved-run-123"})}
        except Exception as exc:
            print(f"Error generating stream: {exc}")
            yield {"event": "error", "data": json.dumps({"error": str(exc)})}
    return EventSourceResponse(event_generator())

@router.post("/generate-stream-advanced")
async def generate_stream_advanced(request: Request):
    body = await request.json()
    content_signal = body.get("content_signal", {})
    render_profile = body.get("render_profile", {})
    
    # Extract exact settings from the strict Render Profile
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
    
    # Formulate style rules directly from the strict schema
    style_guide = f"Visual Mode: {visual_mode.upper()}.\n"
    style_guide += f"Style Descriptors: {style_descriptors}.\n"
    style_guide += f"Taste Bar: {taste_bar.upper()}.\n"
    if palette.get("mode") == "brand":
        style_guide += f"Mandatory Color Palette: Primary {palette.get('primary', '#000000')}, Secondary {palette.get('secondary', '#FFFFFF')}, Accent {palette.get('accent', '#FF0000')}. Use these specific hex colors prominently.\n"
    else:
        style_guide += "Palette: Auto-select an engaging, educational color palette.\n"
        
    if visual_mode == "diagram":
        style_guide += "CRITICAL: Do NOT request 2D maps with text labels. Focus on abstract or photorealistic educational infographics."
    elif visual_mode == "hybrid":
        style_guide += "CRITICAL: Blend 3D objects with floating holographic UI elements or charts."

    async def event_generator():
        thesis = content_signal.get("thesis", {}).get("one_liner", "A generic topic")
        beats = content_signal.get("narrative_beats", [])
        visual_candidates = content_signal.get("visual_candidates", [])
        audience_descriptor = f"{audience_persona} ({audience_level})"
        if domain_context:
            audience_descriptor += f" in {domain_context}"

        # --- Dynamic Scene Count Policy ---
        output_controls = render_profile.get("output_controls", {})
        target_duration = output_controls.get("target_duration_sec", 60)
        density = render_profile.get("density", "standard")
        sec_per_scene = 10 if density == "detailed" else (18 if density == "simple" else 14)
        
        import math
        base_scenes = math.ceil(target_duration / sec_per_scene)
        claims_count = len(content_signal.get("key_claims", []))
        if claims_count > 5: base_scenes += 1
        if audience_level == "beginner": base_scenes -= 1
        scene_count = max(3, min(base_scenes, 8))

        # --- RE-PLANNING PHASE (Advanced) ---
        # We ask Gemini to map the extracted signal into the calculated number of scenes
        planning_prompt = (
            f"Given this core thesis: '{thesis}' and these narrative beats: {json.dumps(beats[:10])}, "
            f"create a specific {scene_count}-scene storyboard outline for the audience persona '{audience_descriptor}'. "
            f"Audience taste bar is '{taste_bar}'. Ensure every scene has a descriptive title and a clear narration focus."
        )
        if must_include:
            planning_prompt += f" Must include: {', '.join(must_include)}."
        if must_avoid:
            planning_prompt += f" Must avoid: {', '.join(must_avoid)}."
        
        try:
            plan_response = await client.aio.models.generate_content(
                model='gemini-3.1-pro-preview',
                contents=planning_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    response_mime_type="application/json",
                    response_schema=OutlineSchema,
                )
            )
            parsed_outline = OutlineSchema.model_validate_json(plan_response.text)
            scenes = parsed_outline.scenes[:scene_count]
            
            while len(scenes) < scene_count:
                idx = len(scenes) + 1
                scenes.append(ScenePlanSchema(
                    scene_id=f"scene-{idx}",
                    title=f"Explainer Point {idx}",
                    narration_focus=f"Further detail on {thesis}.",
                    visual_prompt="A relevant educational visual.",
                    claim_refs=[]
                ))
            
            # 1. Emit the entire queue instantly
            yield {
                "event": "scene_queue_ready",
                "data": json.dumps({"scenes": [s.model_dump() for s in scenes], "optimized_count": len(scenes)})
            }
            
            for idx, scene in enumerate(scenes, start=1):
                if await request.is_disconnected(): return
                scene_id = scene.scene_id
                title = scene.title
                narration_focus = scene.narration_focus

                # Emit scene_start with the traced claim_refs
                yield {"event": "scene_start", "data": json.dumps({"scene_id": scene_id, "title": title, "claim_refs": scene.claim_refs})}

                async for event in _stream_scene_assets(
                    request=request, scene_id=scene_id, topic=thesis, audience=audience_descriptor, tone=goal, scene_title=title,
                    narration_focus=narration_focus, style_guide=style_guide, visual_prompt=scene.visual_prompt,
                    image_prefix="advanced_interleaved", audio_prefix="advanced_audio"
                ):
                    yield event

                yield {"event": "scene_done", "data": json.dumps({"scene_id": scene_id})}

            yield {"event": "final_bundle_ready", "data": json.dumps({"run_id": "advanced-run-123", "bundle_url": "/api/final-bundle/advanced-run-123"})}
        except Exception as exc:
            print(f"Error in advanced stream: {exc}")
            yield {"event": "error", "data": json.dumps({"error": str(exc)})}
    return EventSourceResponse(event_generator())

@router.post("/regenerate-scene")
async def regenerate_scene(payload: RegenerateSceneRequest, request: Request):
    scene_id = payload.scene_id
    current_text = payload.current_text
    instruction = payload.instruction
    visual_mode = payload.visual_mode
    try:
        style_guide = _style_guide_for_mode(visual_mode)
        regen_prompt = (
            f"Regenerate scene {scene_id} with this instruction: {instruction}\n\n"
            f"Original text context: {current_text}\n\n"
            "Requirements:\n"
            "1) Return updated narration text first (no labels or markdown).\n"
            "2) Then return one high-quality inline image for that scene. The image MUST accurately depict any specific scientific or historical details mentioned in the text.\n"
            f"3) Follow this visual style guide: {style_guide}"
        )
        response = await client.aio.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=regen_prompt,
            config=types.GenerateContentConfig(temperature=0.7),
        )
        updated_text = ""
        image_bytes = None
        for candidate in getattr(response, "candidates", []):
            for part in getattr(candidate.content, "parts", []):
                if getattr(part, "text", None): updated_text += part.text
                inline_data = getattr(part, "inline_data", None)
                if inline_data and getattr(inline_data, "data", None):
                    image_bytes = inline_data.data
        image_url = ""
        if image_bytes:
            image_url = _save_image_and_get_url(request=request, scene_id=scene_id, image_bytes=image_bytes, prefix="regen")
        audio_url = _generate_audio_and_get_url(request=request, scene_id=scene_id, text=updated_text, prefix="regen_audio")
        return {"status": "success", "scene_id": scene_id, "text": updated_text, "imageUrl": image_url, "audioUrl": audio_url}
    except Exception as exc:
        print(f"Regeneration error: {exc}")
        return {"status": "error", "message": str(exc)}
