# ExplainFlow Demo Script (<= 4 Minutes)

## Goal

Show a clear story in 4 minutes:
1. High-impact, modern visual branding.
2. Advanced Studio: Script Pack Compilation & Review.
3. Live multimodal streaming (The "Nano Banana" Pattern).
4. **Auto QA Gate & Correction Retries** (The "Self-Healing Director").
5. Deployed GCP architecture proof.

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

### 2:30 - 3:15 | Directed Iteration (Regenerate)

**On screen**
- Select one generated scene and click `Regenerate`.
- Input: "Make the visual more abstract and focus on the software moat."

**Say**
- "Even with Auto QA, we keep the human in the loop. I can use directed iteration to refine specific scenes while the rest of the production remains locked and stable."

### 3:15 - 3:45 | Architecture & GCP Proof

**On screen**
- Show the Architecture diagram (Mermaid).
- Switch to Cloud Run console showing the `explainflow-api` service.

**Say**
- "This self-healing pipeline runs on FastAPI and Google Cloud Run. We've optimized the request timeouts to 300 seconds to handle the deep 'thinking' time required for high-tier multimodal generation."

### 3:45 - 4:00 | Close

**On screen**
- Return to the beautiful Mandelbrot Landing Page.

**Say**
- "ExplainFlow turns AI into a repeatable, controllable production studio. It’s not just a storyteller; it’s a director. Thank you."

## Recommended Inputs for Demo

- **Topic**: "The mechanics of Starship orbital launch"
- **Advanced Persona**: "Aerospace Investor"
- **Taste Bar**: "Very High"
- **Visual Mode**: `Hybrid` (to show 3D + UI overlays)
