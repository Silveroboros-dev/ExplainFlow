# Refactor Plan

Goal: reduce change risk and maintenance drag without redesigning the product.

## Principles

- Preserve behavior while improving structure.
- Split by responsibility, not by file size alone.
- Keep each phase mergeable and smoke-testable.
- Do not mix refactoring with model-routing experiments or feature redesign.

## Do Not Refactor Away

These behaviors may look uneven in code, but they are intentional product decisions and must survive any cleanup pass.

- `Advanced MP4` must export from already generated scene assets without rerunning generation.
- `Quick MP4` and `Advanced MP4` may share composition helpers, but they do not need to share the same user flow.
- `Quick` playlist `hybrid` behavior in `Auto` mode should remain `source clip -> generated frame`.
- deployed MP4 downloads must continue to use explicit attachment-style routes instead of relying on static asset navigation alone.
- export controls that are important for orientation should prefer visible-but-disabled over disappearing entirely.
- proof-linked behaviors and checkpoint semantics take priority over cosmetic simplification.

Before refactoring any of the paths above, add or update a focused test that proves the behavior still exists.

## Phase 1: Frontend Decomposition

Estimated time: 3-5 days

### Quick

Refactor [/Users/rk/Desktop/Gemini Live Agent Challenge/web/src/app/quick/page.tsx](/Users/rk/Desktop/Gemini%20Live%20Agent%20Challenge/web/src/app/quick/page.tsx).

Targets:
- `QuickSourceForm`
- `QuickArtifactView`
- `QuickReelView`
- `QuickVideoPanel`
- `useQuickPlaylist`
- `useQuickWorkflow`

Objectives:
- keep the page component as orchestration only
- isolate API calls from presentation
- isolate playlist and reel control state from artifact rendering

### Advanced

Refactor [/Users/rk/Desktop/Gemini Live Agent Challenge/web/src/app/advanced/page.tsx](/Users/rk/Desktop/Gemini%20Live%20Agent%20Challenge/web/src/app/advanced/page.tsx).

Targets:
- `AdvancedSourcePanel`
- `AdvancedCheckpointPanel`
- `AdvancedSceneStream`
- `AdvancedFinalBundlePanel`
- `useAdvancedWorkflow`
- `useAdvancedProofing`

Objectives:
- isolate SSE and checkpoint logic
- isolate proof dialog and export behavior
- reduce coupling between assistant UI, scene streaming, and export state

### Shared frontend cleanup

Targets:
- centralize API base handling
- centralize YouTube and local media helpers
- centralize download helpers

## Phase 2: Backend Service Split

Estimated time: 4-6 days

Refactor [/Users/rk/Desktop/Gemini Live Agent Challenge/api/app/services/gemini_story_agent.py](/Users/rk/Desktop/Gemini%20Live%20Agent%20Challenge/api/app/services/gemini_story_agent.py) into smaller units.

Suggested modules:
- `signal_extraction_service.py`
- `script_pack_planner.py`
- `scene_generation_service.py`
- `proof_resolution_service.py`
- `quick_artifact_service.py`

Objectives:
- keep `GeminiStoryAgent` as a facade/coordinator
- move complex logic into smaller testable modules
- reduce the blast radius of planner and proofing changes

Keep [/Users/rk/Desktop/Gemini Live Agent Challenge/api/app/services/video_pipeline.py](/Users/rk/Desktop/Gemini%20Live%20Agent%20Challenge/api/app/services/video_pipeline.py) as the single video composition module.

## Phase 3: Contracts and Workflow Hardening

Estimated time: 2-3 days

Targets:
- [/Users/rk/Desktop/Gemini Live Agent Challenge/api/app/schemas/requests.py](/Users/rk/Desktop/Gemini%20Live%20Agent%20Challenge/api/app/schemas/requests.py)
- [/Users/rk/Desktop/Gemini Live Agent Challenge/api/app/routes/workflow.py](/Users/rk/Desktop/Gemini%20Live%20Agent%20Challenge/api/app/routes/workflow.py)
- [/Users/rk/Desktop/Gemini Live Agent Challenge/api/app/routes/generate_stream.py](/Users/rk/Desktop/Gemini%20Live%20Agent%20Challenge/api/app/routes/generate_stream.py)
- [/Users/rk/Desktop/Gemini Live Agent Challenge/api/app/routes/assets.py](/Users/rk/Desktop/Gemini%20Live%20Agent%20Challenge/api/app/routes/assets.py)

Objectives:
- keep export contracts explicit
- distinguish narration-oriented text from overlay-oriented text where needed
- normalize error response shapes
- keep checkpoint semantics explicit across workflow routes

Also centralize model defaults in one config surface instead of scattering hardcoded IDs across service code.

## Phase 4: Testing and Observability

Estimated time: 2-3 days

Targets:
- extraction quality gates
- planner QA and replan behavior
- scene word-budget enforcement
- proof resolution
- Quick reel, playlist, and MP4 export
- Advanced MP4 export

Objectives:
- expand focused tests rather than only broad integration paths
- replace critical-path `print()` calls with lightweight structured logging
- log checkpoint transitions, planner mode, and export timings

## Recommended Order

1. Quick frontend split
2. Advanced frontend split
3. backend service split
4. contract cleanup
5. testing and logging pass

## Success Criteria

- [/Users/rk/Desktop/Gemini Live Agent Challenge/web/src/app/advanced/page.tsx](/Users/rk/Desktop/Gemini%20Live%20Agent%20Challenge/web/src/app/advanced/page.tsx) reduced below 1500 lines
- [/Users/rk/Desktop/Gemini Live Agent Challenge/web/src/app/quick/page.tsx](/Users/rk/Desktop/Gemini%20Live%20Agent%20Challenge/web/src/app/quick/page.tsx) reduced below 1200 lines
- [/Users/rk/Desktop/Gemini Live Agent Challenge/api/app/services/gemini_story_agent.py](/Users/rk/Desktop/Gemini%20Live%20Agent%20Challenge/api/app/services/gemini_story_agent.py) becomes a coordinator instead of a god object
- no user-visible regressions during the refactor sequence

## Out of Scope

- redesigning the product workflow
- changing the checkpoint model
- introducing new major features during refactor
- changing model-routing strategy as part of structure cleanup
