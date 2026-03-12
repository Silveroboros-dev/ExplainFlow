# ExplainFlow Codex Handoff

Last updated: 2026-03-12

## Repo State

- Workspace: `/Users/rk/Desktop/Gemini Live Agent Challenge`
- Active branch: `codex/advanced-qa-pipeline`
- Latest branch commit: `7d7d41b` (`Share advanced route request helpers`)
- Branch status: clean for code changes; only local deployment-file edits remain in `GEMINI.md`, `cloudbuild.yaml`, and `terraform/main.tf`

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

- Completed the first `Advanced Studio` frontend refactor phase.
  - extracted panels / sections / dialogs:
    - `AdvancedSourcePanel.tsx`
    - `AdvancedRenderProfilePanel.tsx`
    - `AdvancedContentSignalPanel.tsx`
    - `AdvancedScriptPackPanel.tsx`
    - `AdvancedGenerationStreamPanel.tsx`
    - `AdvancedGeneratedExplainerSection.tsx`
    - `AdvancedAssistantPanel.tsx`
    - `AdvancedProofDialog.tsx`
    - `AdvancedActionDialog.tsx`
  - moved shared logic into:
    - `web/src/lib/advanced.ts`
    - `web/src/lib/advanced-api.ts`
  - introduced workflow hooks:
    - `useAdvancedWorkflowStorage.ts`
    - `useAdvancedWorkflowSession.ts`
    - `useAdvancedWorkflowActions.ts`
    - `useAdvancedGenerationStream.ts`
    - `useAdvancedAgentChat.ts`
  - reduced `web/src/app/advanced/page.tsx` from about `4057` lines to about `1558` lines
- Preserved `Advanced MP4 Export (Beta)` behavior:
  - exports from existing Advanced scenes only
  - no new Gemini call
  - no scene regeneration
  - current source of truth is the already generated scene asset list
- Simplified workflow couplings that were too implicit:
  - assistant checkpoint-changing actions now require explicit user confirmation
  - bundle image upscale is bundle-local only and blocks conflicting workflow changes while running
  - scene regenerate now uses locked workflow / script / proof context instead of a standalone side door
- Fixed concrete correctness issues uncovered during refactor:
  - stale proof asset URLs now rebase to the current request origin
  - proof links are more reliable across reused / deployed workflows
  - canonical narration is now separate from display / typewriter text, so export and scene regeneration do not depend on preview state
- Removed unused Advanced typing-complete state
- Kept Advanced MP4 calmer-motion / short-overlay behavior and visible export controls intact
- Landed a second backend / workflow optimization phase after the initial frontend refactor:
  - extracted large backend helper domains out of `gemini_story_agent.py`
  - reduced repeated workflow-prep work across script-pack generation and stream start
  - trimmed redundant workflow polling / locking round trips in the Advanced UI
  - reduced routine workflow snapshot payload size

Central files:

- `api/app/routes/assets.py`
- `api/app/routes/workflow.py`
- `api/app/routes/advanced_route_helpers.py`
- `api/app/services/video_pipeline.py`
- `api/app/services/gemini_story_agent.py`
- `api/app/services/story_agent_source_media.py`
- `api/app/services/story_agent_planner.py`
- `api/app/services/story_agent_scene_generation.py`
- `api/app/services/story_agent_advanced_stream.py`
- `api/app/services/story_agent_advanced_qa.py`
- `api/app/services/story_agent_advanced_first_scene.py`
- `api/app/services/story_agent_buffered_scene.py`
- `api/app/services/story_agent_scene_prelude.py`
- `api/app/services/story_agent_extraction.py`
- `api/app/services/story_agent_extraction_runtime.py`
- `api/app/services/story_agent_quick.py`
- `api/app/services/story_agent_quick_artifact.py`
- `api/app/services/story_agent_quick_runtime.py`
- `api/app/services/story_agent_quick_workflows.py`
- `api/app/services/interleaved_parser.py`
- `api/app/schemas/requests.py`
- `api/app/services/workflow_chat_agent.py`
- `web/src/app/advanced/page.tsx`
- `web/src/components/FinalBundle.tsx`
- `web/src/components/SceneCard.tsx`
- `web/src/hooks/useAdvancedGenerationStream.ts`
- `web/src/hooks/useAdvancedWorkflowActions.ts`
- `web/src/hooks/useAdvancedAgentChat.ts`
- `web/src/lib/advanced.ts`

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

Quick frontend refactor was intentionally stopped in two rollback-safe checkpoints:

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

Advanced frontend refactor phase 1 is now complete in a long sequence of small rollback-safe checkpoints.

Current result:

- `web/src/app/advanced/page.tsx` reduced to about `1558` lines
- extracted components:
  - `web/src/components/AdvancedSourcePanel.tsx`
  - `web/src/components/AdvancedRenderProfilePanel.tsx`
  - `web/src/components/AdvancedContentSignalPanel.tsx`
  - `web/src/components/AdvancedScriptPackPanel.tsx`
  - `web/src/components/AdvancedGenerationStreamPanel.tsx`
  - `web/src/components/AdvancedGeneratedExplainerSection.tsx`
  - `web/src/components/AdvancedAssistantPanel.tsx`
  - `web/src/components/AdvancedProofDialog.tsx`
  - `web/src/components/AdvancedActionDialog.tsx`
- extracted shared modules:
  - `web/src/lib/advanced.ts`
  - `web/src/lib/advanced-api.ts`
- extracted hooks:
  - `web/src/hooks/useAdvancedWorkflowStorage.ts`
  - `web/src/hooks/useAdvancedWorkflowSession.ts`
  - `web/src/hooks/useAdvancedWorkflowActions.ts`
  - `web/src/hooks/useAdvancedGenerationStream.ts`
  - `web/src/hooks/useAdvancedAgentChat.ts`
- important stability / coupling checkpoints landed after the structural refactor:
  - `283f45c` `Fix stale proof asset URLs`
  - `1c4cf4b` `Add Advanced assistant action confirmations`
  - `3e88d1a` `Simplify Advanced bundle upscale flow`
  - `747ae4f` `Make Advanced scene override workflow-aware`
  - `c361803` `Fix Advanced scene narration state`
  - `2302c18` `Separate Advanced display and narration text`
- backend / workflow optimization checkpoints after that:
  - `d2b8abe` `Refactor story agent backend helpers`
  - `41dac1e` `Optimize workflow media hot paths`
  - `91d694e` `Refactor Quick backend artifact helpers`
  - `07ab489` `Refactor Quick backend workflows`
  - `72377a7` `Overlap Quick scene streaming after opener`
  - `11a40f7` `Share buffered scene pass runner`
  - `b47674f` `Share scene prelude event builder`
  - `76f0558` `Refactor Advanced scene QA loop`
  - `01d1e56` `Refactor Advanced first scene streaming`
  - `0766096` `Skip duplicate script-pack proof enrichment`
  - `c22af34` `Avoid duplicate workflow snapshot refresh`
  - `2d6e71d` `Slim workflow snapshot payloads`
  - `6310cf5` `Combine workflow profile locks`
  - `0c6dec7` `Deduplicate script pack prompt prep`
  - `7d7d41b` `Share advanced route request helpers`

## Files Most Central To The Current State

Backend:

- `api/app/services/gemini_story_agent.py`
- `api/app/services/story_agent_source_media.py`
- `api/app/services/story_agent_planner.py`
- `api/app/services/story_agent_scene_generation.py`
- `api/app/services/story_agent_advanced_stream.py`
- `api/app/services/story_agent_advanced_qa.py`
- `api/app/services/story_agent_advanced_first_scene.py`
- `api/app/services/story_agent_buffered_scene.py`
- `api/app/services/story_agent_scene_prelude.py`
- `api/app/services/story_agent_extraction.py`
- `api/app/services/story_agent_extraction_runtime.py`
- `api/app/services/story_agent_quick.py`
- `api/app/services/story_agent_quick_artifact.py`
- `api/app/services/story_agent_quick_runtime.py`
- `api/app/services/story_agent_quick_workflows.py`
- `api/app/services/video_pipeline.py`
- `api/app/services/source_ingest.py`
- `api/app/services/interleaved_parser.py`
- `api/app/services/agent_coordinator.py`
- `api/app/services/workflow_chat_agent.py`
- `api/app/routes/assets.py`
- `api/app/routes/generate_stream.py`
- `api/app/routes/advanced_route_helpers.py`
- `api/app/routes/workflow.py`
- `api/app/schemas/requests.py`

Frontend:

- `web/src/app/advanced/page.tsx`
- `web/src/app/quick/page.tsx`
- `web/src/lib/advanced.ts`
- `web/src/lib/advanced-api.ts`
- `web/src/hooks/useAdvancedWorkflowSession.ts`
- `web/src/hooks/useAdvancedWorkflowActions.ts`
- `web/src/hooks/useAdvancedGenerationStream.ts`
- `web/src/hooks/useAdvancedAgentChat.ts`
- `web/src/components/FinalBundle.tsx`
- `web/src/components/AdvancedGeneratedExplainerSection.tsx`
- `web/src/components/AdvancedSourcePanel.tsx`
- `web/src/components/AdvancedRenderProfilePanel.tsx`
- `web/src/components/AdvancedContentSignalPanel.tsx`
- `web/src/components/AdvancedScriptPackPanel.tsx`
- `web/src/components/AdvancedGenerationStreamPanel.tsx`
- `web/src/components/AdvancedAssistantPanel.tsx`
- `web/src/components/AdvancedProofDialog.tsx`
- `web/src/components/AdvancedActionDialog.tsx`
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

1. Targeted `Advanced` rehearsal / smoke pass after refactor phase 1
- verify the full path:
  - source -> extraction -> render profile -> signal confirm -> script pack -> stream
  - proof viewer / proof links
  - scene override
  - bundle export / Advanced MP4 export
- this branch has many correctness fixes, but there is not yet one documented end-to-end rehearsal pass after all of them landed

2. Better scanned-PDF OCR fallback
- digital PDFs are much better now
- scanned/image-heavy PDFs still need stronger OCR

3. URL + PDF reconciliation
- optional source URL ingest still needs a stronger story

4. Proof precision beyond current PDF excerpt matching
- page/excerpt linkage is better
- true line-deep linking is still limited

5. Deeper post-demo refactor
- backend `gemini_story_agent.py` is much smaller now, but still the top-level orchestrator shell
- Advanced page is much smaller, but still acts as the coordinator shell
- proof-viewer image lint cleanup is still unaddressed
- there has not yet been a full post-refactor rehearsal pass documenting the whole Advanced workflow
- `AgentCoordinator` request builders still deep-copy large payloads defensively; that is the next higher-risk optimization seam if performance work continues

## Recommended Next Priority

If continuing product work:

1. deploy and rehearse current `main`
2. fix only concrete demo bugs
3. stop feature churn

If continuing refactor work on this branch:

1. stop Quick here
2. pause large frontend reshaping and run a targeted Advanced rehearsal / smoke pass
3. only then choose the next narrow seam:
   - `AgentCoordinator` request-builder copy pressure
   - OCR / ingest improvements
   - proof-link / proof-viewer precision
4. keep changes rollback-safe and behavior-preserving

Do not mix a large refactor with new product features.

## Fast Restart Context

If the Codex app updates or runtime state is lost:

1. read this file
2. inspect `docs/refactor-plan.md`
3. inspect `web/src/app/quick/page.tsx`
4. inspect `web/src/app/advanced/page.tsx`
5. choose one path:
   - deploy/rehearse
   - or continue a narrow post-phase-1 Advanced cleanup only if a concrete bug / seam is already identified

## Short Mission For The Next Session

Continue from a stable base.

Most likely next move:

- keep Quick frozen at the current good state
- update / reread this handoff
- run a targeted Advanced smoke pass on:
  - source -> extraction -> render profile -> signal confirm -> script pack -> stream
  - proof viewer / proof links
  - scene override
  - bundle export / Advanced MP4 export

Fallback if demo needs dominate:

- stop refactoring
- deploy current `main`
- do a final cloud smoke pass on:
  - Advanced extraction -> script pack -> stream -> MP4 export
  - Quick artifact -> reel -> playlist -> MP4
