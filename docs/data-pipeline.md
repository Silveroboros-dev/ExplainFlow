# ExplainFlow Data Pipeline

This document traces the full data lifecycle: how source material becomes a grounded signal, how the signal becomes a production plan, how scenes are generated and validated, how proof stays attached to the output, and how the final result is exported.

For the system-level architecture (services, models, infrastructure), see [`architecture.md`](./architecture.md).

---

## 1. Source Intake

ExplainFlow accepts three kinds of input:

- **Pasted text** — articles, briefs, transcripts, or any prose document
- **Uploaded media** — images, audio, video, and PDFs, each tracked as a `SourceAssetSchema` with metadata (modality, duration, page count, dimensions, transcript/OCR text)
- **Source manifest** — a structured inventory of uploaded assets that travels with the workflow

Before extraction begins, two preprocessing steps may run:

**Transcript normalization.** If the source is an unpunctuated video transcript (detected by low punctuation density or single-line runs over 220 characters), ExplainFlow normalizes it into clean prose using `gemini-3.1-flash-lite-preview`. This prevents the extraction model from hallucinating structure where none exists.

**Asset recovery.** If no pasted text is provided, ExplainFlow attempts to recover readable text from the uploaded assets — first from embedded transcript/OCR fields, then by calling Gemini with the raw asset files. The recovered text becomes the extraction input.

---

## 2. Signal Extraction

Signal extraction is a two-pass process. The first pass extracts grounded facts. The second adds narrative structure. Neither pass is allowed to invent claims.

### Structural Pass

Model: `gemini-3.1-pro-preview` at temperature 0.2.

Extracts:

| Field | Description |
|-------|-------------|
| `thesis` | One-liner core claim (10–220 chars) and expanded summary (2–3 paragraphs) |
| `key_claims` | Atomic, source-grounded assertions. Each carries a `claim_id` (e.g. `c1`), `claim_text`, `supporting_points`, `confidence` (0–1), and `evidence_snippets` |
| `concepts` | Key terms with `concept_id` (e.g. `k1`), `label`, `definition`, and `importance` (1–5) |
| `open_questions` | Unresolved areas the source does not fully answer |
| `signal_quality` | Self-assessed `coverage_score`, `ambiguity_score`, and `hallucination_risk` (all 0–1) |

This pass explicitly does **not** produce narrative beats or visual candidates.

### Evidence Snippets

Each key claim can carry two types of evidence:

**Text evidence** — a quoted string with an optional citation. Used when the source is pasted text.

**Asset-backed evidence** — a structured reference to an uploaded asset. Includes:
- `asset_id` pointing to a specific uploaded file
- `modality` (text, audio, video, image, pdf_page)
- `start_ms` / `end_ms` for audio/video timecodes
- `page_index` for PDFs (1-indexed)
- `bbox_norm` for image/PDF region crops (normalized [left, top, right, bottom])
- `quote_text`, `transcript_text`, `visual_context` for the backing content
- `confidence` for evidence quality

Grounding rules enforced at extraction time:
- Every claim must be source-grounded
- Evidence snippets must cite specific locations (page, timestamp, region)
- PDF evidence prefers body pages over abstract/frontmatter
- Confidence is lowered when support is weak
- No invented facts, beats, or visuals

### Creative Pass

Model: `gemini-3.1-pro-preview` at temperature 0.4.

Receives the structural signal as context and adds:

| Field | Description |
|-------|-------------|
| `narrative_beats` | 3–8 sequenced beats, each with a `beat_id` (e.g. `b1`), `role` (hook, context, problem, mechanism, example, takeaway, cta), `message`, and `claim_refs` back to structural claims |
| `visual_candidates` | Practical visualization structures, each with a `candidate_id` (e.g. `v1`), `purpose`, `recommended_structure` (flowchart, timeline, comparison, matrix, process, architecture, concept_map, table), `data_points`, and `claim_refs` |

The creative pass is constrained to reference only claim IDs from the structural output. If it fails, ExplainFlow falls back to the structural model.

### Merge

The two passes are merged and cross-validated. All `claim_refs` in beats and visual candidates are checked against existing claim IDs. If two-pass extraction fails entirely, a single-pass fallback runs.

---

## 3. Script Pack Planning

The script pack is the production manifest built before any generation happens. It maps the locked signal and render profile into a scene-by-scene plan.

### Inputs

- **Content signal** — thesis, claims, beats, visual candidates from extraction
- **Render profile** — audience persona, audience level, visual mode, density, taste bar, must-include/must-avoid constraints
- **Artifact scope** — which output types to produce (story cards, voiceover, storyboard, etc.)

### Precompute Enrichments

Two analyses run in parallel on `gemini-3.1-flash-lite-preview` before planning:

**Salience analysis** — rates each concept and claim as CRITICAL, IMPORTANT, or FLAVOUR based on downstream impact. Guides the planner toward what matters most.

**Forward-pull analysis** — models narrative momentum: bait (what hooks the audience), threats (what creates tension), rewards (what pays off), and payloads (what delivers the core insight). Guides pacing.

### Scene Count

Scene count is derived from the artifact policy, signal complexity (number of beats and claims), render profile, and audience level. Typical range: 3–8 scenes.

### Draft Generation

Model: `gemini-3.1-pro-preview` at temperature 0.7.

Generates an outline with per-scene fields:

| Field | Description |
|-------|-------------|
| `scene_id` | Unique identifier (e.g. `scene-1`) |
| `title` | Scene title |
| `scene_goal` | What this scene must accomplish |
| `scene_role` | Narrative function: hook, core, proof, climax, or resolution |
| `narration_focus` | What the narration should cover |
| `visual_prompt` | Detailed image prompt (subject, style, composition, color) |
| `claim_refs` | Which signal claims this scene covers |
| `continuity_refs` | Links to previous scenes for visual/narrative continuity |
| `acceptance_checks` | QA criteria the scene must pass (vocabulary level, evidence grounding, claim coverage, etc.) |
| `render_strategy` | `generated`, `source_media`, or `hybrid` |

Additional layout fields per scene: `composition_goal`, `layout_template`, `focal_subject`, `visual_hierarchy`, `modules` (support panels with their own claim/evidence refs), `comparison_axes`, `flow_steps`, `crop_safe_regions`.

### Planner QA

After the draft is generated, a local Python validation loop runs (this is not a Gemini call):

1. **Validate** — checks claim coverage, salience alignment, and forward-pull narrative flow. Returns hard issues and warnings.
2. **Repair** — auto-fixes missing claim coverage, weak evidence hooks, and pacing issues by modifying scenes in place.
3. **Constrained replan** — if hard issues remain after repair, a new outline is generated with explicit repair directives at temperature 0.4, then validated again.

The result is a `PlannerQaSummary`:
- `mode`: `direct` (no repair needed), `repaired`, or `replanned`
- `initial_hard_issue_count` / `final_warning_count`
- `repair_applied` / `replan_attempted`

---

## 4. Source Media Enrichment

After planning, evidence from the signal is attached to script pack scenes as proof media.

For each scene, the system:
1. Collects evidence refs from the scene's `claim_refs`
2. Scores each piece of evidence by modality preference (image and audio score highest), bbox precision (+22 points for region crops), body-page preference (+10 for pages past frontmatter), and reuse penalty (−18 to −28 for evidence already used in other scenes)
3. Selects up to 3 top-scoring evidence items per scene
4. Converts each into a `SourceMediaRefSchema` with usage type: `proof_clip` (audio/video), `region_crop` (image/PDF with bbox), or `callout` (inline reference)

When proof media is attached, the scene's `render_strategy` is promoted from `generated` to `hybrid`.

---

## 5. Scene Generation and QA

### Interleaved Streaming

Model: `gemini-3-pro-image-preview`.

Each scene is generated as an interleaved text+image stream:
- **Text** arrives incrementally and is displayed via typewriter effect
- **Image** arrives inline as generated bytes, stored and served as a URL
- **Audio** is generated after text using gTTS, with optional playback rate adjustment

SSE events emitted during streaming: `scene_start`, `story_text_delta`, `diagram_ready`, `audio_ready`, `qa_status`, `scene_done`, `final_bundle_ready`.

### Auto QA Gate

Every scene passes through a QA gate before finalization. The gate scores against the scene's `acceptance_checks`:
- Vocabulary level (matches audience)
- Claim coverage (all `claim_refs` mentioned)
- Evidence grounding (citations present)
- Continuity (aligns with prior scenes)
- Engagement (especially for hook scenes)

If a scene fails QA, the failure reasons are fed back as additional constraints and the scene is regenerated (max 2 attempts: initial + 1 retry). The UI surfaces both `qa_status` and `qa_retry` events in real-time.

### Scene Regeneration

Any individual scene can be regenerated with a custom instruction after the stream completes. The regeneration uses the same model and QA loop but scoped to a single scene — all other scenes remain stable.

---

## 6. Proof Links

Proof is not retrofitted. It is carried from extraction through planning into the final output:

1. **Extraction** produces `key_claims` with `evidence_snippets` (text quotes, asset references with timestamps/regions)
2. **Script pack** maps `claim_refs` and `evidence_refs` to each scene, attaches `source_media` with exact asset locations
3. **Scene output** carries the same `claim_refs`, `evidence_refs`, and `source_media` into the rendered result
4. **Proof viewer** — clicking a claim badge on any scene card opens the evidence metadata, source quote, and backing asset

Source media types in the proof viewer:
- **proof_clip** — audio/video segment with `start_ms`/`end_ms`
- **region_crop** — image or PDF region bounded by `bbox_norm`
- **callout** — inline reference to a specific source location

---

## 7. Export

### Final Bundle ZIP

Contains:
- `script.txt` — collated narration text from all scenes
- `images/` — scene images (numbered by scene order)
- `audio/` — scene voiceover MP3s (numbered by scene order)

### Advanced MP4

Concatenated video built from scene assets:
- Each scene: image with pan/zoom motion + title overlay + voiceover audio
- Scenes joined with crossfade transitions
- Output: 1280×720, 24 fps, H.264 + AAC

### High-Fidelity Upscale

Scene images can be upscaled 2× before export. Text and audio are preserved while images are replaced with higher-resolution versions.

### Storage

Storage is hybrid:
- **Google Cloud Storage** — scene images and source assets (when a bucket is configured)
- **Local static assets** — audio, video, and final bundles are served from the API's local asset directory
