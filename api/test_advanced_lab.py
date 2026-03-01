import os
import asyncio
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Import the schemas from the local project
import sys
sys.path.append(os.path.join(os.getcwd(), 'api'))
from app.routes.generate_stream import OutlineSchema

load_dotenv()

async def test_advanced_lab_logic():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment or .env")
    client = genai.Client(api_key=api_key)
    
    # Test Parameters
    thesis = "Quantum Computing is transitioning from theoretical physics to a strategic infrastructure play."
    beats = [
        {"beat_id": "b1", "description": "The current state of 'Noisy Intermediate-Scale Quantum' (NISQ) hardware."},
        {"beat_id": "b2", "description": "Specific industry verticals where quantum advantage is imminent (e.g., drug discovery)."},
        {"beat_id": "b3", "description": "The investment timeline and risk profiles for early-stage quantum startups."}
    ]
    
    # New Lab Parameters
    audience_descriptor = "Venture Capitalist (Intermediate)"
    taste_bar = "VERY_HIGH"
    must_include = ["ROI timelines", "Quantum Advantage", "Hardware Agnostic Software"]
    must_avoid = ["Complex linear algebra", "Detailed physics equations", "Shor's algorithm derivations"]
    
    print(f"--- TESTING ADVANCED LAB LOGIC ---")
    print(f"Persona: {audience_descriptor}")
    print(f"Taste Bar: {taste_bar}")
    print(f"Must Include: {must_include}")
    print(f"Must Avoid: {must_avoid}\n")

    # Replicate the planning prompt logic from generate_stream_advanced
    planning_prompt = (
        f"Given this core thesis: '{thesis}' and these narrative beats: {json.dumps(beats)}, "
        f"create a specific 4-scene storyboard outline for the audience persona '{audience_descriptor}'. "
        f"Audience taste bar is '{taste_bar}'. Ensure every scene has a descriptive title and a clear narration focus."
    )
    if must_include:
        planning_prompt += f" Must include: {', '.join(must_include)}."
    if must_avoid:
        planning_prompt += f" Must avoid: {', '.join(must_avoid)}."

    print("Step 1: Planning with gemini-3.1-pro-preview...")
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
        plan = json.loads(plan_response.text)
        print("Generated Plan:")
        for i, scene in enumerate(plan['scenes'], 1):
            print(f"  Scene {i}: {scene.get('title')}")
            print(f"    Narration: {scene.get('narration_focus')[:100]}...")
            
        # Step 2: Test one scene with Orchestrated Pattern (Text then Image)
        target_scene = plan['scenes'][0]
        print(f"\nStep 2: Testing Orchestrated Generation for Scene 1...")
        
        style_guide = f"Visual Mode: ILLUSTRATION. Style Descriptors: Cinematic, Modern. Taste Bar: {taste_bar}."
        
        # 2a. Generate Text (Simulating the strict rules for audio immersion)
        text_prompt = (
            f"Generate the spoken narration for Scene 1 about '{thesis}'.\n"
            f"Audience: {audience_descriptor}. Tone: Professional VC.\n"
            f"Focus: {target_scene.get('narration_focus')}\n"
            f"Requirements: 50-70 words. Address {', '.join(must_include)}. Avoid {', '.join(must_avoid)}.\n"
            f"STRICT RULE: NO markdown, NO labels, NO titles. Output ONLY the spoken text."
        )
        
        print("Generating text with gemini-3.1-pro-preview...")
        text_response = await client.aio.models.generate_content(
            model='gemini-3.1-pro-preview',
            contents=text_prompt,
        )
        narration_text = text_response.text.strip()
        print(f"\n[NARRATION]:\n{narration_text}")

        # 2b. Generate Image (Using the narration text as context)
        image_prompt = (
            f"Generate a high-quality illustration for this narration: '{narration_text}'\n"
            f"Style Guide: {style_guide}\n"
            f"Visual Direction: {target_scene.get('visual_prompt')}\n"
            f"Rule: NO text in the image."
        )
        
        print("\nGenerating image with gemini-3-pro-image-preview...")
        image_response = await client.aio.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=image_prompt,
        )
        
        image_found = False
        for candidate in image_response.candidates:
            for part in candidate.content.parts:
                if part.inline_data:
                    print(f"[IMAGE GENERATED]: {len(part.inline_data.data)} bytes")
                    image_found = True
        
        if narration_text and image_found:
            print("\nSUCCESS: Orchestrated Lab logic produced high-fidelity content.")
        else:
            print("\nFAILURE: Missing components.")

    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    asyncio.run(test_advanced_lab_logic())
