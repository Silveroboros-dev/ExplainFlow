# ExplainFlow Codex Handoff

Last updated: 2026-03-08

## Repo State

- Workspace: `/Users/rk/Desktop/Gemini Live Agent Challenge`
- Active branch: `codex/advanced-qa-pipeline`
- Current baseline before the next commit: `a4d8829` (`docs: finalize Workflow v3 studio documentation`)
- Important local-only files still present:
  - `.obsidian/workspace.json`
  - generated assets under `api/app/static/assets/`

Do not commit editor state or generated runtime assets unless explicitly requested.

## Current Product Shape

ExplainFlow is now a staged workflow product with:

1. `Source Material`
2. `Render Profile`
3. `Content Signal`
4. `Script Pack`
5. `Generate Stream`

Core product direction remains:

- source-first extraction
- artifact-aware planning
- interleaved text + image + audio generation
- explicit workflow checkpoints
- proof/traceability back to source evidence
- high-control advanced mode without fake-agent behavior

## What Was Completed In This Sprint

### Backend / pipeline

- Added multimodal ingest plumbing for `pdf`, `image`, and `audio`
  - `api/app/routes/assets.py`
  - `api/app/services/source_ingest.py`
  - `api/app/schemas/requests.py`
  - `schemas/content_signal.schema.json`
- Added `source_manifest`, `evidence_refs`, `source_media`, and `render_strategy`
- Added proof-viewer event support via `source_media_ready`
  - `api/app/schemas/events.py`
  - `api/app/services/gemini_story_agent.py`
- Split signal extraction into two passes:
  - structural truth layer
  - creative structuring layer
- Added local `pypdf` fast path for digital PDFs
  - Gemini remains fallback
- Preserved `normalized_source_text` through workflow state
  - `api/app/services/agent_coordinator.py`
  - `api/app/routes/workflow.py`
  - `api/app/routes/generate_stream.py`
- Improved storyboard grounding by feeding claims/evidence into scene rendering
- Fixed early-proof selection so later scenes prefer body evidence over abstract/frontmatter
- Added PDF proof excerpt + approximate line-range matching in the proof viewer flow

### Workflow / agent behavior

- Fixed render-profile lock survival across extraction completion
- Fixed script-pack approval flow so first approval auto-starts stream
- Fixed workflow chat so explanatory questions do not bounce the user backward incorrectly
- Added planner QA summaries through backend + UI

### Artifact quality

- `comparison_one_pager` now behaves as generic `one_pager`
- one-pager planning/rendering was rewritten toward modular poster boards
- `slide_thumbnail` was tightened:
  - better grounding
  - no audio player in thumbnail cards
  - deterministic cover overlay/title treatment
  - shorter support copy
- high-fidelity bundle action now upscales current images instead of regenerating new ones
- final bundle export is a single zip

### Frontend / UX

- Landing page:
  - only Vitruvian + Mandelbrot hero objects flow now
  - those two tiles are larger and animated
- Advanced Studio:
  - Render Profile uses tile-based selection for:
    - artifact type
    - visual mode
    - audience level
    - density
    - taste bar
  - Source Material module was restyled
  - Source Assets uploader now uses a hidden file input + styled button
  - stage action rows now use the same card-style primary/secondary actions
  - ExplainFlow Assistant and Agent Session Notes were brought into the same inner-surface language
- Quick page:
  - audience + visual mode now use tile selectors
  - tone preset chips were added

## Files Most Central To The Current State

Backend:

- `api/app/services/gemini_story_agent.py`
- `api/app/services/source_ingest.py`
- `api/app/services/agent_coordinator.py`
- `api/app/services/image_pipeline.py`
- `api/app/services/interleaved_parser.py`
- `api/app/services/workflow_chat_agent.py`
- `api/app/schemas/requests.py`
- `api/app/schemas/events.py`

Frontend:

- `web/src/app/advanced/page.tsx`
- `web/src/app/quick/page.tsx`
- `web/src/app/page.tsx`
- `web/src/components/AgentActivityPanel.tsx`
- `web/src/components/SceneCard.tsx`

Docs:

- `docs/architecture.md`

## Known Working Assumptions

- Best extraction quality today:
  - pasted source text
  - or digital PDF via `pypdf` fast path
  - or both text + uploaded assets
- Proof precision today:
  - audio: timestamp-level
  - PDF: page + matched excerpt + approximate line range
  - image/page-image: strongest when region crop exists
- Advanced UI now assumes staged workflow is the primary UX

## Things Still Not Done

These are not sprint regressions; they are next-step roadmap items.

1. Finish model tiering on GCP
- Structural extraction, source-text recovery, and planning precompute now default to Flash-class models locally/by default.
- Creative extraction, main planning, and scene generation still stay on Pro-class models.
- The remaining deployment task is to confirm final GCP env defaults and quota behavior in production.

2. Better scanned-PDF OCR fallback
- Digital PDFs are much better now because of `pypdf`.
- Scanned/image-heavy PDFs still need a stronger OCR path.

3. URL + PDF reconciliation
- Optional source URL ingestion should be added.
- Preferred future behavior:
  - use clean HTML/article text when it matches the uploaded PDF
  - keep PDF for proof linkage

4. Proof precision beyond current PDF excerpt matching
- We now show page + excerpt + line range.
- Native PDF viewer still cannot deep-link to a line.

5. Video ingest and Live API mode
- not part of this sprint

## Manual QA To Run Next

Planned for the next morning:

1. Advanced Studio full path
- upload PDF only
- extract signal
- lock profile
- confirm signal
- inspect script pack
- auto-start stream from first script approval

2. Proof viewer checks
- make sure early scenes do not all cite the abstract
- verify PDF proof opens correct page
- verify excerpt + line range are shown when available

3. Artifact quality checks
- `storyboard_grid`
- `one_pager`
- `slide_thumbnail`

4. UI consistency checks
- Source Material actions remain visible even when disabled
- Assistant / Session Notes / stage windows feel visually coherent

## Recommended Next Priority After QA

If tomorrow’s manual pass is clean, the next most valuable tasks are:

1. validate model tiering / bounded scene concurrency on GCP
2. add source URL + PDF ingest path
3. improve scanned-PDF OCR fallback

## Commit Hygiene Notes

When committing this sprint:

- include product code + docs changes
- exclude:
  - `.obsidian/workspace.json`
  - `api/app/static/assets/*`

## Fast Restart Context

If resuming in a new session, start here:

1. read this file
2. inspect `api/app/services/gemini_story_agent.py`
3. inspect `web/src/app/advanced/page.tsx`
4. run the planned manual QA path

## Short Mission For The Next Session

Validate the shipped multimodal workflow and UI polish in real use, then either:

- close the sprint and merge forward, or
- address the first concrete QA regressions only, without reopening architecture churn.
