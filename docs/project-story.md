# ExplainFlow Project Story

## Inspiration

Most AI storytelling demos still behave like one-shot wrappers around a single prompt. That makes them fast to show, but hard to control, hard to trust, and difficult to repair when something goes wrong. ExplainFlow came from the idea that explainers should behave more like a directed production pipeline: ingest source material, extract structure, plan scenes, generate incrementally, self-check, and keep proof attached to the output.

## What it does

ExplainFlow turns source material into grounded visual explainers through two product modes:

- `Advanced Studio` is a staged workflow for source ingestion, signal extraction, render-profile locking, script-pack planning, live scene streaming, QA retries, proof-linked review, and final bundle / MP4 export.
- `Quick` is a faster path that derives an artifact, proof reel, playlist, and MP4 from the same grounded inputs while preserving source-aware structure.

Across both modes, ExplainFlow keeps claims and evidence connected to scenes so users can inspect where the story came from instead of trusting a black box.

## How we built it

We built ExplainFlow as a staged agentic system on FastAPI, Next.js, and Google Cloud Run.

- On the backend, the workflow is split into extraction, planning, validation, streaming, and repair phases instead of one giant generation call.
- On the frontend, Advanced Studio is organized as checkpointed workflow stages with explicit control over source, render profile, signal, script pack, and stream generation.
- We added scene-level regeneration, proof-linked source review, planner QA, stream-time QA retries, and final bundle / MP4 export from already generated scenes.
- We also refactored the system substantially during the hackathon so that major UI panels, hooks, and backend workflow helpers became easier to reason about and control.

## Challenges we ran into

One of the hardest parts of the hackathon was getting into the TypeScript page logic fast enough to take exact control over behavior, not just styling. ExplainFlow’s Advanced Studio is a stateful workflow UI, so changing things like stage transitions, progress reporting, session notes, CTA placement, and regeneration behavior required understanding the real state graph and orchestration flow rather than treating the frontend like a static shell.

Another challenge was balancing speed with control. We wanted live-demo responsiveness, but we also needed source grounding, planner validation, scene-level retries, and proof-linked outputs. That meant tightening orchestration and reducing logic entanglement instead of just making faster but less trustworthy calls.

## Accomplishments that we're proud of

- Built a staged explainer workflow with explicit checkpoints instead of a one-shot prompt flow.
- Added proof-linked generation so scenes can stay grounded in source claims and evidence.
- Added planner QA and scene-level QA / retry behavior for more reliable outputs.
- Got Quick and Advanced to share useful orchestration patterns without collapsing them into the same product.
- Improved local-video handling, progressive Quick rendering, workflow-aware Advanced scene regeneration, and MP4 export behavior.
- Benchmarked Gemini model paths live and split faster transcript normalization from more complete asset-backed recovery instead of guessing on speed/quality tradeoffs.
- Deployed the system on GCP with working Cloud Run services and an aligned Artifact Registry setup.

## What we learned

- Source-grounded generation becomes much more usable when planning, validation, and generation are separated into explicit stages.
- Users need visible workflow state. Progress, checkpoints, notes, and recoverability matter as much as model quality in a complex agent workflow.
- Refactoring during a hackathon can still be worth it if it directly improves control over behavior, correctness, and demo reliability.
- Shared orchestration is valuable, but product semantics still matter: Quick and Advanced should reuse infrastructure without becoming the same experience.

## What's next for ExplainFlow

- Keep improving the stage-level progress reporting so users see real execution signals instead of decorative activity.
- Continue reducing backend complexity in the story agent and coordinator paths.
- Improve continuity-aware regeneration, especially downstream scene alignment after a scene override.
- Expand delivery formats, including better vertical-video output for source-backed reels.
- Explore future source-video transcription support, but only in a way that preserves trust and does not destabilize the current workflow.
