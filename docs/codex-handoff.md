# ExplainFlow Codex Handoff

Last updated: 2026-03-07

## Repo State

- Workspace: `/Users/rk/Desktop/Gemini Live Agent Challenge`
- Active branch: `codex/advanced-qa-pipeline`
- Baseline commit at `HEAD`: `e061684` (`feat: implement Workflow Engine (v2)`)
- Important rule: work in the fork branch only, do not touch `main`

## Product Identity

- Product name: `ExplainFlow`
- Elevator pitch: `ExplainFlow turns one idea into a complete visual narrative pipeline from core signal extraction to final media bundle.`
- Track: `Creative Storyteller`
- Core differentiation:
  - style-agnostic signal extraction from long or short source input
  - explicit render profile and audience/taste controls
  - interleaved scene-by-scene output with text, image, and audio
  - traceability from scenes back to extracted claims/snippets
  - scene-level regeneration instead of full reruns

## Architecture Decisions Locked In

- Keep repo separate and avoid legacy naming/governance wording.
- No shared imports/code from the earlier project.
- Scene generation stays interleaved at the model level.
- For stability, backend orchestrates one multimodal call per scene instead of one giant 4-scene call.
- Signal extraction is style-agnostic and should happen before render-profile-dependent planning.
- `script_pack` is the bridge between locked signal + render profile and stream generation.
- Low-key preview should be the default fast path.
- High-fidelity rerun belongs later, near final bundle / approved output.
- User wants agentic UX, but not multi-agent complexity for its own sake. Single loop + strong harness is preferred.

## Current Workflow Shape

Advanced Studio stages:

1. `Extract Signal`
2. `Render Profile`
3. `Content Signal`
4. `Script Pack`
5. `Generate Stream`

Intended checkpoint logic:

- Extract signal first.
- Lock artifact scope + render profile.
- Confirm signal.
- Generate script pack automatically after signal confirmation.
- Ask user whether script should be explicitly reviewed or used immediately.
- Only block stream generation when checkpoint gates actually require it.

## What Was Being Built Most Recently

Agentic workflow / UX layer is in progress on top of the existing pipeline.

Main areas touched:

- Backend agent/harness work:
  - `api/app/routes/workflow.py`
  - `api/app/schemas/requests.py`
  - `api/app/services/agent_coordinator.py`
  - `api/app/services/gemini_story_agent.py`
  - `api/app/services/interleaved_parser.py`
  - `api/app/services/workflow_chat_agent.py` (new, untracked)
  - `api/tests/test_workflow_agent_route.py` (new, untracked)
  - `api/tests/test_workflow_chat_agent.py` (new, untracked)

- Frontend UX/agent console work:
  - `web/src/app/advanced/page.tsx`
  - `web/src/app/page.tsx`
  - `web/src/app/quick/page.tsx`
  - `web/src/components/AgentActivityPanel.tsx` (new, untracked)

## Latest UI Change

Most recent change before this handoff:

- removed assistant shortcut buttons like `Extract Signal`, `Apply Profile`, `Confirm Signal`, `Generate Stream` from the Advanced Studio assistant panel
- simplified left-column layout to reduce overlap between `ExplainFlow Assistant` and `Agent Session Notes`
- updated the assistant textarea placeholder to encourage natural language input

This change is present in:

- `web/src/app/advanced/page.tsx`

## Known Issues / Open Threads

These are the main unresolved items the next conversation should treat as active context:

1. Assistant/checkpoint correctness
- Assistant sometimes reports the signal or profile as locked before the user has actually confirmed it.
- Workflow chat must reflect real checkpoint state, not inferred or optimistic state.

2. Assistant UX quality
- User does not want a fake assistant feel.
- Preferred direction is a real Gemini-backed orchestration/help agent, not static canned UI behavior.
- Chat messages should not pile up vertically or push the rest of the page around.
- System notes and assistant messages should not duplicate each other.

3. Signal extraction prompt quality
- User thinks current extraction prompt is too thin and too close to raw JSON execution.
- There is a proposal to replace/improve it using a stronger narrative-signal prompt while still keeping extraction as a single run.
- Save/keep `v1` extraction prompt so it can be restored if `v2` underperforms.
- New prompt should align with `Live Director Console.md`.

4. Stream/content quality
- There have been bugs where some scenes duplicate text or lose titles.
- There have been earlier layout issues with scene image fitting.
- These need regression checks after agentic/UI changes.

5. Agentic behavior target
- The desired experience is a strong harness:
  - real guidance
  - traceable checkpoints
  - explicit discussion of artifact choice when useful
  - progress/checkpoint notes during long waits
- Not a multi-agent system unless clearly justified.

## Product/UX Preferences From User

- Keep `ExplainFlow` branding.
- README/demo must not reference the prior project.
- User values visual sophistication and high-taste presentation.
- Open-ended audience persona matters; strict enums alone are insufficient.
- `taste_bar` and persona/domain context are important because a generic audience level is too weak.
- For advanced UX, user prefers stage-aware guidance and visible progress over dead waiting screens.
- Script pack should be accessible before generation, and editable/reviewable when explicitly requested.

## Smoke-Test Status Before Handoff

Most recent smoke test status:

- backend on `127.0.0.1:8000` responded successfully
- frontend on `127.0.0.1:3000` responded successfully
- `/quick` and `/advanced` routes responded
- workflow start and extraction API calls succeeded
- quick stream SSE emitted checkpoints and scene events

This only confirms the stack is runnable. It does not prove the new agentic UX is logically correct.

## Dirty Working Tree Snapshot

Modified:

- `.obsidian/workspace.json`
- `api/app/routes/workflow.py`
- `api/app/schemas/requests.py`
- `api/app/services/__init__.py`
- `api/app/services/agent_coordinator.py`
- `api/app/services/gemini_story_agent.py`
- `api/app/services/interleaved_parser.py`
- `api/tests/test_services.py`
- `web/src/app/advanced/page.tsx`
- `web/src/app/page.tsx`
- `web/src/app/quick/page.tsx`

Untracked:

- `api/app/services/workflow_chat_agent.py`
- `api/tests/test_workflow_agent_route.py`
- `api/tests/test_workflow_chat_agent.py`
- `web/src/components/AgentActivityPanel.tsx`

Notes:

- `.obsidian/workspace.json` is likely local/editor state and should be treated carefully.
- The working tree contains meaningful in-progress agentic rebuild changes; do not reset blindly.

## Best Next Entry Point

If continuing in a new conversation, start from this sequence:

1. read `docs/codex-handoff.md`
2. inspect `web/src/app/advanced/page.tsx`
3. inspect `api/app/routes/workflow.py`
4. inspect `api/app/services/workflow_chat_agent.py`
5. verify current checkpoint state transitions against real UI behavior

## Short Mission For The Next Session

Bring the agentic layer from "present but unreliable" to "stateful and credible":

- align assistant messages with real workflow checkpoints
- improve extraction prompt quality without breaking single-run extraction
- keep workflow logic intact unless a real bug forces change
- preserve the ExplainFlow UX direction while removing fake-assistant behavior
