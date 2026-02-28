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

## MVP (Locked)

In one run, a user can:
1. Provide input (prompt or long document).
2. Define a render profile (audience/style/fidelity/density/palette).
3. Click generate and watch a 6-scene interleaved stream.
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
  - `audience_level` (`beginner`, `intermediate`, `expert`)

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

## Data Contracts

Canonical schemas live in:
- `/Users/rk/Desktop/Gemini Live Agent Challenge/schemas/content_signal.schema.json`
- `/Users/rk/Desktop/Gemini Live Agent Challenge/schemas/render_profile.schema.json`
- `/Users/rk/Desktop/Gemini Live Agent Challenge/schemas/scene_plan.schema.json`

Matching typed models:
- TypeScript: `/Users/rk/Desktop/Gemini Live Agent Challenge/schemas/schema-types.ts`
- Pydantic: `/Users/rk/Desktop/Gemini Live Agent Challenge/schemas/schema-models.py`

## Architecture (MVP)

- Frontend: Next.js timeline UI (Quick Generate + Advanced Studio).
- Backend: FastAPI with SSE streaming endpoints.
- Model integration: Gemini via Google GenAI SDK.
- Cloud deployment: Cloud Run (API) + Cloud Storage (generated assets).

Core pipeline:
1. `extract_signal` -> `content_signal`
2. combine `content_signal + render_profile` -> `scene_plan`
3. stream interleaved scene events
4. optional scene-level regenerate
5. publish final bundle

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

Defer post-MVP:
- full video compositor
- multi-agent orchestration
- auth/collaboration
