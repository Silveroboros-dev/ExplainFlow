import json
import asyncio
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from typing import List
from sse_starlette.sse import EventSourceResponse
from google import genai
from google.genai import types

router = APIRouter()

# Initialize the GenAI client. It automatically picks up GEMINI_API_KEY from the environment
client = genai.Client()

class SignalExtractionRequest(BaseModel):
    input_text: str

class RegenerateSceneRequest(BaseModel):
    scene_id: str
    instruction: str

# Define the structured output schema for the scene plan
class ScenePlanSchema(BaseModel):
    scene_id: str = Field(description="A unique identifier for the scene, e.g., 'scene-1'")
    title: str = Field(description="The title of the scene")
    narration_focus: str = Field(description="Instructions on what the narration should focus on for this scene")
    visual_prompt: str = Field(description="An incredibly detailed, high-quality prompt for an image generator (like Imagen 4). It must specify a clear subject, a cohesive visual style (e.g., 'clean isometric vector illustration', 'cinematic 3D render', 'minimalist infographic'), color palette instructions, and composition. The image MUST be highly relevant to the educational topic, acting as a visual aid. Do NOT include text or labels in the prompt as AI struggles with spelling.")

class OutlineSchema(BaseModel):
    scenes: list[ScenePlanSchema]

@router.post("/extract-signal")
async def extract_signal(request: SignalExtractionRequest):
    try:
        # Load the schema definition to enforce the structure
        with open("../schemas/content_signal.schema.json", "r") as f:
            schema_str = f.read()

        extraction_prompt = f"""
        Analyze the following document and extract the core signal into a highly structured JSON format.
        You MUST strictly adhere to the provided JSON Schema.
        
        DOCUMENT:
        {request.input_text}
        
        JSON SCHEMA:
        {schema_str}
        
        Return ONLY valid JSON matching this schema, without any markdown formatting like ```json.
        """

        response = await client.aio.models.generate_content(
            model='gemini-3.1-pro-preview',
            contents=extraction_prompt,
            config=types.GenerateContentConfig(
                temperature=0.2, # Low temperature for accurate extraction
                response_mime_type="application/json",
            )
        )
        
        signal_data = json.loads(response.text)
        return {"status": "success", "content_signal": signal_data}
        
    except Exception as e:
        print(f"Extraction error: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/generate-stream")
async def generate_stream(request: Request, topic: str, audience: str, tone: str, visual_mode: str = "illustration"):
    async def event_generator():
        # 1. Extract the structure (Planning phase)
        # Adapt visual mode into concrete style guidelines
        style_guide = ""
        if visual_mode == "diagram":
            style_guide = "All visual prompts MUST be for clean, highly detailed, photorealistic infographics or accurate geographical/historical landscapes. Do NOT request 2D maps with text labels as AI struggles with spelling. Instead, request 'a photorealistic satellite view of the Yucatan peninsula' or 'an accurate 3D cross-section of a crater'. Focus on high-fidelity, educational realism."
        elif visual_mode == "illustration":
            style_guide = "All visual prompts MUST be for beautiful, cinematic 3D renders or high-quality vector illustrations. Focus on stylized characters, expressive lighting, and engaging scenes."
        elif visual_mode == "hybrid":
            style_guide = "All visual prompts MUST blend 3D objects or characters with floating holographic UI elements, charts, or graphical overlays."

        planning_prompt = f"Create a 4-scene outline for a visual explainer about '{topic}'. The target audience is {audience}. The tone should be {tone}. You MUST generate EXACTLY 4 scenes, no more, no less.\n\nCRITICAL VISUAL RULE:\n{style_guide}"
        
        try:
            # We use the async client to generate the structural plan first
            plan_response = await client.aio.models.generate_content(
                model='gemini-3.1-pro-preview',
                contents=planning_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    response_mime_type="application/json",
                    response_schema=OutlineSchema,
                )
            )
            
            outline = json.loads(plan_response.text)
            scenes = outline.get("scenes", [])
            
            # 2. Generate Interleaved Content (Nano Banana Pro)
            # We ask the model to generate the whole explainer as a single interleaved stream
            # based on the planned scenes.
            
            scenes_data = "\n".join([f"- Scene {i+1}: {s['title']} ({s['narration_focus']})" for i, s in enumerate(scenes)])
            
            gen_prompt = f"Create a 4-scene visual explainer about '{topic}' for a {audience} audience with a {tone} tone.\n\n"
            gen_prompt += f"Follow this plan:\n{scenes_data}\n\n"
            gen_prompt += "For each scene, you MUST:\n"
            gen_prompt += "1. Output the EXACT narration text to be spoken. DO NOT include 'Scene X', scene titles, or any labels. Start directly with the speech.\n"
            gen_prompt += "2. Then, generate a high-quality, relevant image for that scene.\n\n"
            gen_prompt += f"Visual Style Guide: {style_guide}"

            response_stream = await client.aio.models.generate_content_stream(
                model='gemini-3-pro-image-preview',
                contents=gen_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                )
            )
            
            scene_idx = 0
            current_scene = scenes[scene_idx]
            current_scene_id = current_scene["scene_id"]
            current_scene_text = ""
            
            # Start the first scene immediately with the planned title
            yield {
                "event": "scene_start",
                "data": json.dumps({"scene_id": current_scene_id, "title": current_scene["title"]})
            }

            async for chunk in response_stream:
                if await request.is_disconnected():
                    return
                
                for part in chunk.candidates[0].content.parts:
                    # Handle Text Part (Narration)
                    if part.text:
                        current_scene_text += part.text
                        yield {
                            "event": "story_text_delta",
                            "data": json.dumps({"scene_id": current_scene_id, "delta": part.text})
                        }
                    
                    # Handle Image Part (Generated by Nano Banana Pro)
                    if part.inline_data:
                        # 1. Handle Image
                        import time
                        timestamp = int(time.time())
                        img_filename = f"interleaved_{current_scene_id}_{timestamp}.png"
                        img_filepath = f"app/static/assets/{img_filename}"
                        
                        with open(img_filepath, 'wb') as f:
                            f.write(part.inline_data.data)
                        
                        image_url = f"http://localhost:8000/static/assets/{img_filename}"
                        
                        yield {
                            "event": "diagram_ready",
                            "data": json.dumps({"scene_id": current_scene_id, "url": image_url})
                        }
                        
                        # 2. Handle Audio Generation for accumulated text
                        if current_scene_text.strip():
                            try:
                                from gtts import gTTS
                                tts = gTTS(text=current_scene_text, lang='en', slow=False)
                                audio_filename = f"audio_{current_scene_id}_{timestamp}.mp3"
                                audio_filepath = f"app/static/assets/{audio_filename}"
                                tts.save(audio_filepath)
                                
                                audio_url = f"http://localhost:8000/static/assets/{audio_filename}"
                                yield {
                                    "event": "audio_ready",
                                    "data": json.dumps({"scene_id": current_scene_id, "url": audio_url})
                                }
                            except Exception as e:
                                print(f"Audio generation failed: {e}")
                        
                        # 3. Finish Scene
                        yield {
                            "event": "scene_done",
                            "data": json.dumps({"scene_id": current_scene_id})
                        }
                        
                        # Reset and prepare for next scene from the PLAN
                        current_scene_text = ""
                        scene_idx += 1
                        if scene_idx < len(scenes):
                            current_scene = scenes[scene_idx]
                            current_scene_id = current_scene["scene_id"]
                            yield {
                                "event": "scene_start",
                                "data": json.dumps({"scene_id": current_scene_id, "title": current_scene["title"]})
                            }

            yield {
                "event": "final_bundle_ready",
                "data": json.dumps({"run_id": "interleaved-run-123", "bundle_url": "/api/final-bundle/interleaved-run-123"})
            }
            
            yield {
                "event": "final_bundle_ready",
                "data": json.dumps({"run_id": "live-run-123", "bundle_url": "/api/final-bundle/live-run-123"})
            }
            
        except Exception as e:
            print(f"Error generating stream: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }

    return EventSourceResponse(event_generator())

@router.post("/generate-stream-advanced")
async def generate_stream_advanced(request: Request):
    """
    A POST endpoint for streaming generation that accepts a full JSON body
    including the extracted content_signal.
    (We use POST because SSE via standard EventSource doesn't easily support POST with body in the browser,
    but we can read the body, cache the parameters, and redirect to a GET stream, 
    or use the fetch API with a custom SSE parser on the frontend).
    
    For simplicity in this MVP, we will accept a large JSON body in a POST,
    and return an EventSourceResponse directly (FastAPI supports this even for POSTs).
    """
    body = await request.json()
    content_signal = body.get("content_signal", {})
    visual_mode = body.get("visual_mode", "illustration")
    audience = body.get("audience", "Beginner")
    
    async def event_generator():
        # 1. Extract the structure based on the content_signal
        style_guide = ""
        if visual_mode == "diagram":
            style_guide = "All visual prompts MUST be for clean, highly detailed, photorealistic infographics or accurate geographical/historical landscapes. Do NOT request 2D maps with text labels. Focus on high-fidelity, educational realism."
        elif visual_mode == "illustration":
            style_guide = "All visual prompts MUST be for beautiful, cinematic 3D renders or high-quality vector illustrations. Focus on stylized characters, expressive lighting, and engaging scenes."
        elif visual_mode == "hybrid":
            style_guide = "All visual prompts MUST blend 3D objects or characters with floating holographic UI elements, charts, or graphical overlays."

        # Summarize the content signal for the prompt to avoid token bloat
        thesis = content_signal.get("thesis", {}).get("one_liner", "A generic topic")
        beats = content_signal.get("narrative_beats", [])
        beats_summary = "\n".join([f"- Scene {i+1}: {b.get('role')} - {b.get('message')}" for i, b in enumerate(beats[:4])]) # Limit to 4 for now

        gen_prompt = f"Create a 4-scene visual explainer based on the following extracted signal.\n"
        gen_prompt += f"Core Thesis: {thesis}\n"
        gen_prompt += f"Target Audience: {audience}\n\n"
        gen_prompt += f"Narrative Beats to follow:\n{beats_summary}\n\n"
        gen_prompt += "For each scene, you MUST:\n"
        gen_prompt += "1. Output the EXACT narration text to be spoken. DO NOT include 'Scene X', scene titles, or any labels. Start directly with the speech.\n"
        gen_prompt += "2. Then, generate a high-quality, relevant image for that scene.\n\n"
        gen_prompt += f"Visual Style Guide: {style_guide}"

        try:
            response_stream = await client.aio.models.generate_content_stream(
                model='gemini-3-pro-image-preview',
                contents=gen_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                )
            )
            
            scene_idx = 0
            current_beat = beats[scene_idx] if beats else {}
            current_scene_id = f"scene-{scene_idx + 1}"
            current_scene_text = ""
            
            # Start the first scene immediately
            yield {
                "event": "scene_start",
                "data": json.dumps({"scene_id": current_scene_id, "title": current_beat.get('role', 'Intro').capitalize()})
            }

            async for chunk in response_stream:
                if await request.is_disconnected():
                    return
                
                for part in chunk.candidates[0].content.parts:
                    if part.text:
                        current_scene_text += part.text
                        yield {
                            "event": "story_text_delta",
                            "data": json.dumps({"scene_id": current_scene_id, "delta": part.text})
                        }
                    
                    if part.inline_data:
                        import time
                        timestamp = int(time.time())
                        img_filename = f"interleaved_{current_scene_id}_{timestamp}.png"
                        img_filepath = f"app/static/assets/{img_filename}"
                        
                        with open(img_filepath, 'wb') as f:
                            f.write(part.inline_data.data)
                        
                        image_url = f"http://localhost:8000/static/assets/{img_filename}"
                        
                        yield {
                            "event": "diagram_ready",
                            "data": json.dumps({"scene_id": current_scene_id, "url": image_url})
                        }
                        
                        if current_scene_text.strip():
                            try:
                                from gtts import gTTS
                                tts = gTTS(text=current_scene_text, lang='en', slow=False)
                                audio_filename = f"audio_{current_scene_id}_{timestamp}.mp3"
                                audio_filepath = f"app/static/assets/{audio_filename}"
                                tts.save(audio_filepath)
                                
                                audio_url = f"http://localhost:8000/static/assets/{audio_filename}"
                                yield {
                                    "event": "audio_ready",
                                    "data": json.dumps({"scene_id": current_scene_id, "url": audio_url})
                                }
                            except Exception as e:
                                print(f"Audio generation failed: {e}")
                        
                        yield {
                            "event": "scene_done",
                            "data": json.dumps({"scene_id": current_scene_id})
                        }
                        
                        current_scene_text = ""
                        scene_idx += 1
                        if scene_idx < 4 and scene_idx < len(beats):
                            current_beat = beats[scene_idx]
                            current_scene_id = f"scene-{scene_idx + 1}"
                            yield {
                                "event": "scene_start",
                                "data": json.dumps({"scene_id": current_scene_id, "title": current_beat.get('role', f'Scene {scene_idx+1}').capitalize()})
                            }

            yield {
                "event": "final_bundle_ready",
                "data": json.dumps({"run_id": "advanced-run-123", "bundle_url": "/api/final-bundle/advanced-run-123"})
            }
        except Exception as e:
            print(f"Error in advanced stream: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }

    return EventSourceResponse(event_generator())
