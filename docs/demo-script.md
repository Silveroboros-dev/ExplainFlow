# ExplainFlow Demo Script (<= 4 Minutes)

## Goal

Show a clear story in 4 minutes:
1. High-impact, modern visual branding.
2. Live multimodal streaming (The "Nano Banana" Pattern).
3. Advanced Studio for professional persona-driven generation.
4. Directed iteration through scene-level regeneration.
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
- "Unlike one-shot static generators, we stream interleaved text, cinematic visuals, and professional audio in real-time."

### 0:25 - 0:50 | Quick Generate (Conventional UX)

**On screen**
- Click `Start Creating` -> Quick Generate.
- Enter Topic: "How Photosynthesis powers life".
- Click `Generate`.

**Say**
- "For rapid ideas, the Quick Generate path turns a simple prompt into a 4-scene storyboard instantly."
- "You'll see the scenes queue up immediately as the backend begins the orchestration."

### 0:50 - 1:30 | Multimodal Interleaving (The "Nano Banana")

**On screen**
- Watch Scene 1 and 2 stream:
  - Text deltas appear first.
  - High-quality 3D visual appears *immediately* after.
  - Audio badge turns green.

**Say**
- "Notice the interleaving. Using our 'Nano Banana' orchestration, the model emits narration text followed immediately by high-fidelity image bytes."
- "There’s no waiting for a massive final blob; the story comes to life scene by scene."

### 1:30 - 2:15 | Advanced Studio (The "Lab" Logic)

**On screen**
- Navigate to `Advanced Studio`.
- Paste the Quantum Computing document.
- **Crucial**: Set Persona to "Venture Capitalist" and Taste Bar to "Very High".
- Add Must Include: "ROI timelines".
- Add Must Avoid: "Complex math".
- Click `Extract Content Signal`.

**Say**
- "In the Advanced Studio, we take control. I can ingest long-form technical documents and define a strict Persona."
- "We’re targeting a Venture Capitalist here, with a 'Very High' taste bar for visuals and a rule to avoid complex math."

### 2:15 - 2:45 | Signal Extraction & Traceability

**On screen**
- Show the JSON Signal (Thesis, Claims, Beats).
- Point to `claim_refs` in the JSON.

**Say**
- "Before generating a single pixel, we extract a style-agnostic Content Signal."
- "This locks the logic, claims, and narrative beats, ensuring every scene is grounded in the source document."

### 2:45 - 3:15 | Directed Iteration (Regenerate)

**On screen**
- Click `Generate Explainer Stream`.
- Select one generated scene and click `Regenerate`.
- Input: "Make the visual more abstract and focus on the software moat."

**Say**
- "If a scene isn't perfect, I don't rerun the whole app. I use directed iteration."
- "I’m asking the Director to refine just this scene’s visual focus while maintaining the overall narrative consistency."

### 3:15 - 3:45 | Architecture & GCP Proof

**On screen**
- Show the Architecture diagram (Mermaid).
- Switch to Cloud Run console showing the `explainflow-api` service.

**Say**
- "Under the hood, we’re running a FastAPI backend on Google Cloud Run with a 300-second timeout to handle high-tier multimodal 'thinking' time."
- "This architecture is built for the high-latency requirements of the most advanced Gemini models."

### 3:45 - 4:00 | Close

**On screen**
- Return to the beautiful Mandelbrot Landing Page.

**Say**
- "ExplainFlow turns the complexity of AI into a repeatable, controllable director’s console. Communicate your ideas clearly, one scene at a time."

## Recommended Inputs for Demo

- **Topic**: "The mechanics of Starship orbital launch"
- **Advanced Persona**: "Aerospace Investor"
- **Taste Bar**: "Very High"
- **Visual Mode**: `Hybrid` (to show 3D + UI overlays)
