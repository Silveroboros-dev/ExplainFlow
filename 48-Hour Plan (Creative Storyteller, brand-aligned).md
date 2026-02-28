
Project angle: **“Explainer Director”** that turns one idea into a mixed-media explainer stream (text + schema/diagram image + voiceover + captions).
- Add a first-run intake step for visual/style controls.
- Split pipeline into:
    - content_signal (style-agnostic extraction from long input)
    - render_profile (user taste/settings)
    - scene_plan (style-conditioned output from the two above)
 - Cache content_signal so style changes regenerate only scenes/media, not full extraction.


1. Hour 0-2: Scope lock + define schemas for content_signal, render_profile, scene_plan.
2. Hour 2-5: Build intake UI (7 questions), defaults, and preset save/load.
3. Hour 5-9: Backend SSE skeleton + event contract.
4. Hour 9-13: Implement long-doc extraction to content_signal JSON (single pass).
5. Hour 13-17: Scene planner that combines content_signal + render_profile.
6. Hour 17-22: Live UI timeline rendering scene events.
7. Hour 22-27: Generate visuals per scene using render_profile.
8. Hour 27-31: Generate narration/audio per scene.
9. Hour 31-35: Final bundle page (transcript, visuals, audio, captions).
10. Hour 35-39: Cloud Run + Cloud Storage deployment and proof capture.
11. Hour 39-44: Reliability (retries, fallbacks, sample input, style re-run).
12. Hour 44-48: Record 4-minute demo + backup take.
    

**MVP Intake Questions (first run)**

1. Output goal (teach/persuade/summarize/pitch)?
2. Audience level (beginner/intermediate/expert)?
3. Visual mode (diagram/illustration/hybrid)?
4. Style direction (3 words + optional reference)?
5. Fidelity (low/medium/high)?
6. Density (simple/standard/detailed)?
7. Palette/brand constraints (colors, no-go styles)?

---
**Updated 4-Minute Demo Script (Aligned to New Plan)**

1. **0:00-0:20 | Hook**
    - On screen: Landing page + one sentence value prop.
    - Say: “This agent turns long, dense ideas into visual explainers people can understand fast.”
2. **0:20-0:50 | Long Input + Render Profile Intake**
    - On screen: Paste a long document (or upload), then answer 7 render-profile questions.
    - Say: “I provide source content plus style controls like visual mode, fidelity, density, palette, and audience level.”
3. **0:50-1:20 | Signal Extraction (content_signal)**
    - On screen: JSON preview pane with thesis, key_claims, visual_candidates, narrative_beats.
    - Say: “First, it extracts a style-agnostic signal pack once. This keeps quality stable and iterations fast.”
4. **1:20-2:25 | Scene Planning + Live Interleaved Stream**
    - On screen: scene_plan created, then live timeline events: text, diagram/image, audio, captions.
    - Say: “Then it combines content_signal + render_profile to produce a style-conditioned scene plan and streams mixed output live.”
5. **2:25-2:55 | Key Differentiator: Style Re-run Without Re-extract**
    - On screen: Change profile (for example diagram -> hybrid, fidelity medium -> high), click regenerate.
    - Say: “Now I can change style without reprocessing the full document. Only scene/media rendering is recomputed.”
6. **2:55-3:25 | Final Bundle**
    - On screen: Transcript, scene gallery, audio clips, caption pack, asset manifest.
    - Say: “This is the final explainer package ready for presentation or social adaptation.”
7. **3:25-3:45 | Architecture Slide**
    - On screen: Next.js UI -> FastAPI SSE -> Gemini mixed output -> Cloud Storage -> Cloud Run.
    - Say: “The pipeline is event-driven and deployed on Google Cloud with Gemini interleaved output.”
8. **3:45-4:00 | GCP Proof + Close**
    - On screen: Cloud Run service, logs, Storage bucket artifacts.
    - Say: “This demonstrates end-to-end cloud deployment and a repeatable visual storytelling workflow.”

**Demo-safe fallback line**

- “If generation latency appears, I’ll switch to the prepared sample input to keep the flow under 4 minutes.”

**Revised 4-minute script (judge-friendly)**

1. **0:00-0:20 Hook**  
    Say: “This turns complex ideas into visual explainers in one live stream.”
    
2. **0:20-0:45 Conventional UX first**  
    On screen:  
    Enter prompt: "Explain [topic] for [audience], tone [x], duration [y]."  
    Click Generate.  
    Say: “You can use it like a normal prompt-based tool.”
    
3. **0:45-1:35 Live interleaved output**  
    Show scene cards, narration text, visuals, audio, captions arriving live.  
    Say: “Mixed output is generated as one cohesive stream.”
    
4. **1:35-2:10 Advanced mode reveal**  
    Switch to long-document input + render-profile questions (style, fidelity, density, palette, audience).  
    Say: “For serious use, I can ingest long source material and control visual taste.”
    
5. **2:10-2:40 Signal extraction architecture**  
    Show content_signal JSON briefly.  
    Say: “I extract core signal once, then render from it.”
    
6. **2:40-3:05 Style re-run without re-extract**  
    Change style settings and regenerate visuals/scenes only.  
    Say: “This is fast iteration without full reprocessing.”
    
7. **3:05-3:35 Final bundle**  
    Show transcript, storyboard, audio clips, caption pack, manifest.
    
8. **3:35-4:00 Cloud proof + close**  
    Show Cloud Run + Cloud Storage proof.  
    Say: “Simple for first use, controllable for expert use, deployed end-to-end on Google Cloud.”
    

If you want, I can also rewrite your UI labels so this split is explicit: Quick Generate and Advanced Studio.

**4-Minute Demo Script (personal-brand focused)**

1. **0:00-0:20 | Hook**  
    “People don’t always want to read dense text. This agent turns complex ideas into visual-first explainers in one live stream.”
    
2. **0:20-0:45 | Problem + category fit**  
    “This is a Creative Storyteller agent using Gemini interleaved output, hosted on Google Cloud.”
    
3. **0:45-1:10 | Input moment**  
    Enter prompt: “Explain [your topic] for [audience], tone [x], duration [y].”  
    Click Generate.
    
4. **1:10-2:25 | Live interleaved output**  
    Narrate while events appear: text chunks, scene cards, diagram image, then voiceover clips.  
    Callout: “This is one cohesive mixed-media stream, not separate tools stitched manually.”
    
5. **2:25-3:00 | Final bundle page**  
    Show transcript, 6-scene storyboard, audio tracks, caption pack.  
    Say: “Now I can publish the same idea in multiple formats without rewriting.”
    
6. **3:00-3:25 | Architecture quick slide**  
    Show diagram: Web UI -> FastAPI stream -> Gemini -> Cloud Storage -> Cloud Run.  
    Say: “Streaming architecture keeps experience live and interruption-tolerant.”
    
7. **3:25-3:45 | GCP proof**  
    Show Cloud Run service + bucket assets + deployed endpoint logs/screens.
    
8. **3:45-4:00 | Close**  
    “My focus is helping people communicate ideas clearly through visuals and narrative. This agent makes that repeatable.”