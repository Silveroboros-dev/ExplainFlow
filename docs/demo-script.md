# ExplainFlow Demo Script (<= 4 Minutes)

## Goal

Show a clear story in 4 minutes:
1. Familiar prompt-first UX.
2. Live interleaved mixed-media generation.
3. Advanced control for long inputs and style profile.
4. Scene-level regeneration without full rerun.
5. Google Cloud deployment proof.

## Demo Setup (Before Recording)

- Keep one reliable sample prompt ready.
- Keep one long-document sample ready.
- Pre-prepare one scene regeneration instruction.
- Keep Cloud Run and Cloud Storage console tabs open for proof.
- Disable noisy notifications.

## Live Script With Timing

### 0:00 - 0:20 | Hook

**On screen**
- ExplainFlow home screen.

**Say**
- "ExplainFlow turns one idea into a complete visual narrative pipeline, from signal extraction to final media bundle."
- "The core value is live, controllable explainers instead of one-shot static outputs."

### 0:20 - 0:45 | Quick Generate (Conventional UX)

**On screen**
- Use Quick Generate form:
  - Topic
  - Audience
  - Tone
  - Duration
- Click `Generate`.

**Say**
- "First, you can use ExplainFlow like a standard prompt tool."
- "I enter a topic, audience, tone, and duration, then generate."

### 0:45 - 1:35 | Live Interleaved Output

**On screen**
- Timeline events appear:
  - `scene_start`
  - `story_text_delta`
  - `diagram_ready`
  - `audio_ready`
  - `caption_ready`
- Scene cards update live.

**Say**
- "Output streams live as scenes, not as a single final blob."
- "Each scene combines narration, visuals, and captions in one flow."

### 1:35 - 2:05 | Advanced Studio (Long Input + Style Controls)

**On screen**
- Switch to Advanced Studio.
- Paste long document.
- Set render profile:
  - visual mode
  - style descriptors
  - fidelity
  - density
  - palette
  - audience level

**Say**
- "For deeper use cases, I can provide long source content and explicit style controls."
- "This makes output quality and taste predictable across different users."

### 2:05 - 2:35 | Signal Extraction Layer

**On screen**
- Show `content_signal` preview:
  - thesis
  - key claims
  - visual candidates
  - narrative beats

**Say**
- "ExplainFlow extracts a style-agnostic signal pack once."
- "That lets us iterate output style without reprocessing the full document every time."

### 2:35 - 3:00 | Scene-Level Regenerate (Key Differentiator)

**On screen**
- Select one scene.
- Apply targeted instruction, for example:
  - "Make this scene diagram-first and simpler for beginners."
- Trigger `Regenerate Scene`.

**Say**
- "Now I regenerate only one scene with a specific instruction."
- "This is directed iteration, not a full rerun."

### 3:00 - 3:25 | Source Traceability + Final Bundle

**On screen**
- Open trace panel for a scene:
  - claim refs
  - supporting snippet
- Open final bundle:
  - transcript
  - scene manifest
  - caption pack

**Say**
- "Each scene is traceable to extracted claims."
- "Final output is packaged for presentation and publishing."

### 3:25 - 3:50 | Architecture + Cloud Proof

**On screen**
- Show architecture slide briefly.
- Switch to Cloud Run service and Cloud Storage bucket.

**Say**
- "The app uses a Next.js frontend and a FastAPI streaming backend on Cloud Run."
- "Generated assets are stored in Cloud Storage."

### 3:50 - 4:00 | Close

**On screen**
- Return to product screen with final bundle.

**Say**
- "ExplainFlow makes complex ideas easier to communicate through controllable, live visual storytelling."

## Backup Lines (If Latency Hits)

- "I’ll switch to the prepared sample run to keep the flow concise."
- "The same pipeline is running, this is just a cached input for recording reliability."

## Recommended Demo Inputs

### Quick Generate Input

- Topic: "How retrieval-augmented generation improves enterprise search"
- Audience: "Product managers"
- Tone: "Clear and practical"
- Duration: "90 seconds"

### Advanced Studio Input

- A 2-4 page technical brief with multiple claims and examples.
- Render profile example:
  - visual mode: `hybrid`
  - style: `clean`, `editorial`, `high-contrast`
  - fidelity: `high`
  - density: `standard`
  - palette: brand/custom
  - audience level: `intermediate`

## Recording Checklist

1. Keep total runtime under 4:00.
2. Avoid dead air while events stream.
3. Keep architecture section under 25 seconds.
4. Keep cloud proof visible and explicit.
5. Record one backup take immediately after primary take.
