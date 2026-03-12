# ExplainFlow Codex Handoff

Last updated: 2026-03-12

## Repo State

- Workspace: `/Users/rk/Desktop/Gemini Live Agent Challenge`
- Active branch: `codex/advanced-qa-pipeline`
- Latest branch commit: `4e9a7ba` (`Refactor Quick source form`)
- Branch status: clean and pushed to `fork/codex/advanced-qa-pipeline`

Do not commit editor state or generated runtime assets unless explicitly requested.

## Current Product Shape

ExplainFlow now has two clear product surfaces inside the same checkpoint-driven agentic workflow:

1. `Advanced Studio`
2. `Quick`

### Advanced Studio

Checkpointed workflow:

1. `Source Material`
2. `Render Profile`
3. `Content Signal`
4. `Script Pack`
5. `Generate Stream`
6. `Final Bundle / Export`

Key properties:

- source-first extraction
- artifact-aware planning
- explicit workflow checkpoints
- staged agent harness around planning and generation
- planner QA before streaming
- scene-level QA during streaming
- proof-linked generation and source traceability
- export from already generated scenes, not rerun generation

### Quick

Quick is now a layered derived workflow:

1. `Artifact`
2. `Proof Reel`
3. `Proof Playlist`
4. `MP4`

Key properties:

- HTML-first artifact generation
- deterministic reel built from Quick blocks
- selectable playback controls per reel segment
- MP4 export from derived reel data
- lighter derived flow that does not reuse every Advanced checkpoint

## What Was Completed Recently

### Advanced

- Added `Advanced MP4 Export (Beta)`
  - exports from existing Advanced scenes only
  - no new Gemini call
  - no scene regeneration
  - current source of truth is the already generated scene asset list
- Added dedicated download flow for Advanced MP4
- Tightened standard Advanced scene narration budget
- Added short overlay text for Advanced MP4
- Replaced jittery motion with calmer scene motion in Advanced MP4
- Fixed export button visibility so export remains accessible once scenes exist

Central files:

- `api/app/routes/assets.py`
- `api/app/services/video_pipeline.py`
- `api/app/services/gemini_story_agent.py`
- `api/app/services/interleaved_parser.py`
- `api/app/schemas/requests.py`
- `web/src/components/FinalBundle.tsx`

### Quick

- Added `Proof Reel`
- Added Quick MP4 generation and download
- Added `Proof Playlist`
- Added per-segment presentation controls:
  - `Auto`
  - `Source`
  - `Image`
- Added `Unmute Local Source Clips`
- Playlist `hybrid` behavior now plays:
  - source clip first
  - generated frame second

Central files:

- `api/app/routes/generate_stream.py`
- `api/app/routes/assets.py`
- `api/app/services/video_pipeline.py`
- `api/app/services/gemini_story_agent.py`
- `web/src/app/quick/page.tsx`
- `web/src/components/ProofPlaylistPlayer.tsx`

### Docs / Architecture

- `docs/architecture.md` was refreshed with:
  - clearer section ordering
  - upgraded sequence diagram
  - data contract transformation diagram
- `README.md` now has:
  - top-level workflow overview
  - Mermaid diagrams
  - stronger differentiator framing
- `docs/demo-script.md` was updated with:
  - judge-facing talking points
  - agent-harness wording
  - Quick adaptability note
- `docs/refactor-plan.md` was added

## Current Refactor Status

Quick frontend refactor started and is already in two rollback-safe checkpoints:

1. `81f2552` `Refactor Quick artifact and reel views`
2. `4e9a7ba` `Refactor Quick source form`

Current result:

- `web/src/app/quick/page.tsx` reduced to about `1308` lines
- extracted:
  - `web/src/components/QuickSourceForm.tsx`
  - `web/src/components/QuickArtifactSummary.tsx`
  - `web/src/components/QuickArtifactView.tsx`
  - `web/src/components/QuickReelView.tsx`
  - `web/src/lib/quick.ts`

Behavior was manually re-verified after each extraction.

## Files Most Central To The Current State

Backend:

- `api/app/services/gemini_story_agent.py`
- `api/app/services/video_pipeline.py`
- `api/app/services/source_ingest.py`
- `api/app/services/interleaved_parser.py`
- `api/app/services/agent_coordinator.py`
- `api/app/services/workflow_chat_agent.py`
- `api/app/routes/assets.py`
- `api/app/routes/generate_stream.py`
- `api/app/routes/workflow.py`
- `api/app/schemas/requests.py`

Frontend:

- `web/src/app/advanced/page.tsx`
- `web/src/app/quick/page.tsx`
- `web/src/components/FinalBundle.tsx`
- `web/src/components/ProofPlaylistPlayer.tsx`
- `web/src/components/QuickSourceForm.tsx`
- `web/src/components/QuickArtifactSummary.tsx`
- `web/src/components/QuickArtifactView.tsx`
- `web/src/components/QuickReelView.tsx`
- `web/src/components/SceneCard.tsx`
- `web/src/lib/quick.ts`

Docs:

- `README.md`
- `docs/architecture.md`
- `docs/demo-script.md`
- `docs/refactor-plan.md`
- `docs/signal-extraction-research.md`

## Known Working Assumptions

- Best extraction quality today:
  - text-only
  - digital PDF via embedded text / `pypdf`
  - text plus uploaded assets
  - transcript-backed source video
- Quick audience and visual style both materially influence output
- Quick YouTube handling is transcript-backed context, not a dedicated backend `youtube_url` contract
- Quick MP4 uses generated visuals and local proof intercuts when available
- Advanced MP4 is intentionally image + audio only for now
- Proof links for PDF work best through separate-tab viewing in deployed environments

## Important Guardrails

Do not refactor away these behaviors:

- Advanced MP4 must export from existing scenes only
- Quick and Advanced MP4 are intentionally different flows
- Quick playlist `hybrid` default is `source clip -> generated frame`
- attachment-style MP4 download routes are required for deployed behavior
- visible-but-disabled export controls are preferable to disappearing controls
- proof/checkpoint semantics matter more than cosmetic simplification

Detailed version lives in `docs/refactor-plan.md`.

## Things Still Not Done

These are real next-step items, not regressions.

1. First small `Advanced` frontend extraction
- Quick refactor started cleanly.
- Advanced is still the larger technical-debt surface.
- Best next slice is a small component extraction, not a rewrite.

2. Better scanned-PDF OCR fallback
- digital PDFs are much better now
- scanned/image-heavy PDFs still need stronger OCR

3. URL + PDF reconciliation
- optional source URL ingest still needs a stronger story

4. Proof precision beyond current PDF excerpt matching
- page/excerpt linkage is better
- true line-deep linking is still limited

5. Deeper post-demo refactor
- backend `gemini_story_agent.py` is still a god object
- Advanced page is still very large

## Recommended Next Priority

If continuing product work:

1. deploy and rehearse current `main`
2. fix only concrete demo bugs
3. stop feature churn

If continuing refactor work on this branch:

1. stop Quick here
2. start the first small `Advanced` extraction
3. keep changes rollback-safe and behavior-preserving

Do not mix a large refactor with new product features.

## Fast Restart Context

If the Codex app updates or runtime state is lost:

1. read this file
2. inspect `docs/refactor-plan.md`
3. inspect `web/src/app/quick/page.tsx`
4. inspect `web/src/app/advanced/page.tsx`
5. choose one path:
   - deploy/rehearse
   - or continue the first small Advanced refactor

## Short Mission For The Next Session

Continue from a stable base.

Most likely next move:

- keep Quick frozen at the current good state
- begin the first small Advanced extraction without changing behavior

Fallback if demo needs dominate:

- stop refactoring
- deploy current `main`
- do a final cloud smoke pass on:
  - Advanced extraction -> script pack -> stream -> MP4 export
  - Quick artifact -> reel -> playlist -> MP4
