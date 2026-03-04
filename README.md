# ExplainFlow

ExplainFlow turns one idea into a complete visual narrative pipeline from core signal extraction to final media bundle.

## Product

ExplainFlow is a Creative Storyteller agent that converts either:
- a short prompt, or
- a long document

into a live, controllable explainer stream with scene-by-scene narration, visuals, and captions.

The product focus is not just generation. It is directed generation:
- users can define output style and quality,
- regenerate a single scene without rerunning everything,
- and trace each scene back to extracted claims.

Pipeline versions in this repo:
- **Legacy (v1):** extraction -> planning -> per-scene interleaved generation.
- **Current (v2):** adds script-pack compilation, continuity memory, and automatic QA with one retry on failure.

## How to Run Locally

To run this system on another machine, follow these steps to start both the Python backend and the Next.js frontend.

### Prerequisites
- Python 3.10+
- Node.js 18+ and `npm`
- A Google GenAI API Key (with access to `gemini-3.1-pro-preview` and `gemini-3-pro-image-preview`)

### 1. Set up the Backend (FastAPI)
The backend handles the AI extraction, the multimodal streaming logic, and static asset serving.

```bash
cd api

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`

# Install dependencies
pip install -r requirements.txt

# Create your environment file
echo "GEMINI_API_KEY=your_api_key_here" > .env

# Start the FastAPI server
uvicorn app.main:app --reload --port 8000
```
*The backend will now be running at `http://localhost:8000`. It will save generated images and audio to `api/app/static/assets`.*

### 2. Set up the Frontend (Next.js)
The frontend handles the UI, the Server-Sent Events (SSE) parsing, and the Scene Inspector.

```bash
cd web

# Install dependencies
npm install

# Start the development server
npm run dev
```
*The frontend will now be running at `http://localhost:3000`.*

### 3. Usage
1. Open `http://localhost:3000/quick` for the prompt-based generator.
2. Open `http://localhost:3000/advanced` to test the long-document extraction and traceability features.

## MVP (Locked)

In one run, a user can:
1. Provide input (prompt or long document).
2. Define a render profile (audience/style/fidelity/density/palette).
3. Click generate and watch a dynamic-scene interleaved stream (typically 3-8 scenes).
4. Regenerate one specific scene with a targeted edit instruction.
5. Export a final explainer bundle.

## Main Features

1. Quick Generate
- Input: `topic`, `audience`, `tone`, `duration`.
- One-click generation for judge-friendly conventional UX.

2. Advanced Studio
- Long-document input.
- Explicit render profile controls:
  - `visual_mode` (`diagram`, `illustration`, `hybrid`)
  - `style` descriptors
  - `fidelity` (`low`, `medium`, `high`)
  - `density` (`simple`, `standard`, `detailed`)
  - `palette` (auto/brand/custom)
  - `audience` object:
    - `level` (`beginner`, `intermediate`, `expert`)
    - `persona` (open-ended, e.g. "Product manager")
    - `taste_bar` (`standard`, `high`, `very_high`)
    - optional `domain_context`, `must_include`, `must_avoid`

3. Signal Extraction Layer
- Extract once into `content_signal`:
  - thesis
  - key claims
  - concepts
  - visual candidates
  - narrative beats

4. Live Interleaved Scene Stream
- Event-driven timeline renders text, visual, caption, and audio artifacts per scene.

5. Scene-Level Regeneration
- Regenerate scene `N` only.
- Keep prior extraction and unaffected scenes intact for speed and control.

6. Source Traceability
- Each scene surfaces `claim_refs` and supporting snippets from `content_signal`.

7. Final Bundle
- Transcript
- Scene manifest (image/audio assets)
- Social caption pack

8. Script Pack Transparency (Current v2)
- Planner output is compiled into a runtime `script_pack` with:
  - normalized scene IDs
  - scene goals
  - continuity references
  - acceptance checks
- The `script_pack` is streamed to UI before generation completes.

9. Scene QA Gate + Auto Retry (Current v2)
- Each scene is auto-evaluated (`PASS`, `WARN`, `FAIL`) on:
  - narration/image presence
  - length/structure
  - focus alignment
  - `must_include` / `must_avoid` alignment
  - continuity strength
- One automatic retry is executed on first `FAIL`, then surfaced in UI.

## Data Contracts

Canonical schemas live in:
- `/Users/rk/Desktop/Gemini Live Agent Challenge/schemas/content_signal.schema.json`
- `/Users/rk/Desktop/Gemini Live Agent Challenge/schemas/render_profile.schema.json`
- `/Users/rk/Desktop/Gemini Live Agent Challenge/schemas/scene_plan.schema.json`

Matching typed models:
- TypeScript: `/Users/rk/Desktop/Gemini Live Agent Challenge/schemas/schema-types.ts`
- Pydantic: `/Users/rk/Desktop/Gemini Live Agent Challenge/schemas/schema-models.py`

## Architecture (Compare)

### Legacy (v1)

- Frontend: Next.js timeline UI (Quick Generate + Advanced Studio).
- Backend: FastAPI with SSE streaming endpoints.
- Model integration: Gemini via Google GenAI SDK.
- Cloud deployment: Cloud Run (API) + Cloud Storage (generated assets).

Core pipeline:
1. `extract_signal` -> `content_signal`
2. combine `content_signal + render_profile` -> outline/scene plan
3. per-scene interleaved generation stream
4. optional scene-level regenerate
5. publish final bundle

### Current (v2)

- Adds `script_pack` compile stage between planning and generation.
- Adds continuity memory carried across scenes.
- Adds scene-level QA gate and one automatic retry on first failure.
- Adds UI transparency for `script_pack` and QA outcomes.

Core pipeline:
1. `extract_signal` -> `content_signal`
2. `content_signal + render_profile` -> dynamic scene planning
3. compile `script_pack` (`continuity_refs`, `acceptance_checks`)
4. scene loop:
   - interleaved generation (text + image)
   - audio generation
   - QA evaluate (`PASS|WARN|FAIL`)
   - one retry if first attempt is `FAIL`
5. scene done + final bundle

For detailed diagrams and sequence flows, see:
- `/Users/rk/Desktop/Gemini Live Agent Challenge/docs/architecture.md`

## Implementation Plan (48 Hours)

1. Contract freeze
- Lock schemas and event contracts.

2. Backend scaffolding
- Implement endpoints:
  - `POST /extract-signal`
  - `POST /generate-stream`
  - `POST /regenerate-scene`
  - `GET /final-bundle/{run_id}`

3. Frontend scaffolding
- Build Quick Generate and Advanced Studio entry paths.
- Build timeline UI and scene cards.

4. Extraction and planning
- Wire long-input extraction to `content_signal`.
- Build planner to create `scene_plan` from `content_signal + render_profile`.

5. Streaming generation
- Emit and render events:
  - `scene_start`
  - `story_text_delta`
  - `diagram_ready`
  - `caption_ready`
  - `audio_ready`
  - `scene_done`
  - `final_bundle_ready`

6. Scene-level regenerate + traceability
- Add per-scene targeted regeneration.
- Add claim/snippet trace panel per scene.

7. Cloud deploy and proof
- Deploy backend to Cloud Run.
- Store generated assets in Cloud Storage.
- Capture proof artifacts for submission.

8. Demo hardening
- Add sample input fallback, retries, and graceful loading states.
- Record <= 4 minute demo plus backup take.

## SSE Event Contract (Compare)

### Legacy (v1)
- `scene_queue_ready`
- `scene_start`
- `story_text_delta`
- `diagram_ready`
- `audio_ready`
- `scene_done`
- `final_bundle_ready`

### Current (v2)
- `script_pack_ready`
- `scene_queue_ready`
- `scene_start`
- `story_text_delta`
- `diagram_ready`
- `audio_ready`
- `qa_status`
- `qa_retry`
- `scene_retry_reset`
- `scene_done`
- `final_bundle_ready`
- `error`

## Demo Flow (4 Minutes)

1. Quick Generate: enter prompt and click generate.
2. Live stream: show interleaved scene output.
3. Advanced mode: show long-doc + render profile controls.
4. Regenerate one scene with a style/complexity tweak.
5. Final bundle: transcript + assets + captions.
6. Cloud proof: Cloud Run + Storage.

## Scope Guardrails

Keep for MVP:
- single orchestrator service
- scene-level regeneration
- source traceability

## TODO / Post-MVP Enhancements

- [ ] **Credit Protection**: Add a simple "Access PIN" field on the landing page (e.g., `GEMINI_JUDGE_2026`) to gate the "Generate" button and prevent unauthorized API usage during the public demo phase.
- [ ] **Optional HD Upscale Pass (Vertex AI)**: After scene approval, upscale approved images with `imagen-4.0-upscale-preview` (`x2`/`x3`/`x4`) for final-bundle quality without re-generating composition.
- [ ] **Multimodal Ingestion**: Support PDF and Markdown uploads. Use Gemini's multimodal vision to extract logic directly from charts and diagrams in the source material, ensuring "Visual-to-Visual" continuity in the generated output.
- [ ] **Full Video Compositor**: Automate the stitching of generated images and audio into a final `.mp4` file.
- [ ] **Multi-Agent Orchestration**: Introduce specialized agents for fact-checking and automated visual critique.
