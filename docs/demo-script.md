# ExplainFlow Demo Script (<= 4 Minutes)

## Goal

Show a clear story in 4 minutes:
1. High-impact, modern visual branding.
2. Advanced Studio: Script Pack Compilation & Review.
3. Live multimodal streaming (The "Nano Banana" Pattern).
4. **Auto QA Gate & Correction Retries** (The "Self-Healing Director").
5. Proof-linked generation and checkpointed recovery.
6. Deployed GCP architecture proof.

## What Judges Should Hear Explicitly

Do not try to explain every subsystem in the video. Instead, make sure the narration lands these product-level ideas:

- ExplainFlow is **not** a one-shot generator.
- ExplainFlow uses an **agent harness**, not just one prompt and one response.
- The `Script Pack` is a checkpointed production manifest, not just intermediate JSON.
- Scenes are **proof-linked** back to source claims and evidence.
- The workflow agent is state-aware and can help the user recover or continue instead of restarting.
- Quick is a fast derived path: `artifact -> Proof Reel -> MP4`.

If the recording is running long, cut detail before you cut these points.

## Demo Setup (Before Recording)

- **Landing Page**: Start at the root URL showing the new Mandelbrot/Vitruvian UI.
- **Sample Document**: Have a long technical brief (e.g., "The Future of Quantum Computing") ready to paste.
- **API URL**: Ensure `NEXT_PUBLIC_API_URL` is pointing to the Cloud Run endpoint.
- **Tabs**: Keep Cloud Run console and the Architecture diagram ready.

## Live Script With Timing

### 0:00 - 0:25 | Hook & The "Director" Concept

**On screen**
- ExplainFlow landing page (Mandelbrot/Vitruvian theme).

**Say**
- "This is ExplainFlow. It’s an 'Explainer Director' that turns complex ideas into visual narrative pipelines."
- "Unlike one-shot static generators, we use a specialized 'Director's Console' to plan, generate, and self-correct mixed-media stories."

### 0:25 - 1:15 | Advanced Studio: Script Pack & Approval

**On screen**
- Navigate to `Advanced Studio`.
- Paste the Quantum Computing document.
- Set Persona: "Venture Capitalist", Taste Bar: "Very High".
- Click `Extract Content Signal`.
- Click `Generate Script Pack`.
- **Scroll through the Script Pack JSON.**

**Say**
- "In the Advanced Studio, we don't just generate; we plan. After extracting the core claims, we generate a Script Pack."
- "This is our production manifest. It includes continuity references and strict 'acceptance checks' for every scene, ensuring the story remains coherent from start to finish."
- "This checkpoint is important: instead of streaming immediately from the extracted signal, we stop here so the system can validate pacing, coverage, and proof before expensive generation begins."
- "That self-checking behavior is part of our agent harness: the system checks the plan before generation, not only after something goes wrong."

### 1:15 - 2:30 | Multimodal Interleaving & Auto QA

**On screen**
- Click `Generate Explainer Stream`.
- Watch Scene 1 stream (Text then Image).
- **Point out the "QA PASS" badge when it appears.**
- If a "QA FAIL" or "Correction Retry" occurs, highlight it immediately.

**Say**
- "Notice the interleaving. Our 'Nano Banana' orchestration emits narration followed immediately by high-fidelity image bytes."
- "But watch the badges. Every scene passes through an 'Auto QA Gate'. The system scores its own output against our acceptance checks."
- "If the director detects narrative drift or technical errors, it automatically triggers a 'Correction Retry' to fix the scene in real-time."
- "And this is not just pretty generation: each scene keeps claim refs, evidence refs, and linked source proof so the user can inspect where the story came from."
- "So the agent harness is active at both levels: first it self-checks the plan, then it self-checks each scene as the stream runs."

### 2:30 - 2:55 | Proof-Linked Review

**On screen**
- Open one scene's proof link.
- Show the source proof view or the PDF source opening in a new tab.

**Say**
- "This is one of the most important product decisions in ExplainFlow: every scene can stay grounded."
- "We carry proof from extraction into planning and then into the final scene cards, so the user can inspect the exact source support instead of trusting a black box."

### 2:55 - 3:20 | Directed Iteration (Regenerate)

**On screen**
- Select one generated scene and click `Regenerate`.
- Input: "Make the visual more abstract and focus on the software moat."

**Say**
- "Even with Auto QA, we keep the human in the loop. I can use directed iteration to refine specific scenes while the rest of the production remains locked and stable."

### 3:20 - 3:45 | Architecture & GCP Proof

**On screen**
- Show the Architecture diagram (Mermaid).
- Switch to Cloud Run console showing the `explainflow-api` service.

**Say**
- "This self-healing pipeline runs on FastAPI and Google Cloud Run. We've optimized the request timeouts to 300 seconds to handle the deep 'thinking' time required for high-tier multimodal generation."
- "The important architecture idea is that the workflow is staged, recoverable, and controllable. Users are not forced to rerun the whole pipeline every time something changes."

### 3:45 - 4:00 | Close

**On screen**
- Return to the beautiful Mandelbrot Landing Page.

**Say**
- "ExplainFlow turns AI into a repeatable, controllable production studio. It’s not just a storyteller; it’s a director. Thank you."

## Optional Quick Swap-In (30-40 Seconds)

If Quick is more stable or more visually impressive in the live build, replace the Directed Iteration section with this:

**On screen**
- Open `/quick`
- generate a Quick artifact
- switch to `Proof Reel`
- show `Generate MP4`

**Say**
- "We also built a fast path called Quick."
- "Instead of running the full staged studio, Quick derives three layers from the same grounded blocks: an artifact, a Proof Reel, and then an MP4."
- "Quick is not one fixed template. It adapts both to how the user wants the explanation framed and how they want it visually presented."
- "And for the MP4, Quick now reuses the same buffered scene orchestration pattern we developed in Advanced, so the narration lands as one connected flow instead of isolated stitched clips."
- "That gives us a much faster publish path while preserving source-aware structure."

## Recommended Inputs for Demo

- **Topic**: "The mechanics of Starship orbital launch"
- **Advanced Persona**: "Aerospace Investor"
- **Taste Bar**: "Very High"
- **Visual Mode**: `Hybrid` (to show 3D + UI overlays)

## Hackathon Pitch Summary

Use this as the short architecture explanation if a judge asks what is different about ExplainFlow:

> "Most AI demo tools are still one-shot wrappers around a single prompt. ExplainFlow is a staged agentic workflow. We split signal extraction into structural and creative passes, run artifact-aware planning with validation and repair, and then generate scenes as discrete units so they can be retried, regenerated, and proof-linked back to the source. For live performance, we use bounded scene concurrency with ordered SSE flush: Scene 1 is generated serially for immediate time-to-first-byte, then later scenes run in small parallel batches while the user is already reading, but we buffer and flush them in order so continuity, QA retries, and UI rendering stay stable. That lets us hide latency without giving up scene-level control."

Alternative live version:

> "ExplainFlow is not a one-shot generator. It is a controllable production pipeline: extract, plan, validate, stream, and repair. We generate the opener first so the user sees output immediately, then we parallelize later scenes in bounded batches and flush them in order. That gives us source grounding, regeneration, and live-demo speed at the same time."

Shorter fallback version:

> "ExplainFlow is not a one-shot generator. It uses an agent harness to extract, plan, self-check, stream, and repair. That gives us better source grounding, better regeneration, and better live-demo resilience than static notebook-style tools."
