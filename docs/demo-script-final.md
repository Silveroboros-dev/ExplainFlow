# ExplainFlow Demo Video Script — Final Cut

**Target:** 3:50 actual runtime (10s buffer under the 4:00 hard cap)
**Category:** Creative Storyteller
**Judging weights:** 40% UX/Multimodal, 30% Technical Architecture, 30% Demo/Presentation
**Bonus available:** +0.2 for IaC (Terraform), +0.6 for published content

---

## Recording Prerequisites

### Environment
- Browser: Chrome, clean profile, no bookmarks bar, no extensions visible
- Resolution: 1440p preferred, 1080p minimum
- Font size / zoom: 110% browser zoom so UI text is legible on video
- Dark mode system preference (landing page is dark-themed)

### Tabs Pre-Opened (in order)
1. ExplainFlow landing page (Cloud Run URL, not localhost)
2. Advanced Studio — fresh session
3. Cloud Run console showing `explainflow-api` service
4. Architecture diagram (open `docs/architecture.md` Mermaid or a rendered PNG)
5. Quick page — ideally with a pre-generated artifact ready to show

### Pre-Warm
- Run one full Advanced extraction + script pack + at least 2 scenes before recording
- Run one full Quick generation before recording so you know the timing
- Have a stable source document ready to paste (see Recommended Input below)
- Test that proof links open correctly from the deployed URL

### Audio
- Use an external mic or record voiceover separately
- Speak at ~130 words per minute (natural, unhurried)
- Each section below includes exact word counts to stay on pace

---

## Recommended Source Input

**Source:** Benoit Mandelbrot, "How Long Is the Coast of Britain? Statistical Self-Similarity and Fractional Dimension"

**Why this source:**
- Visually stunning (fractals, coastlines, self-similarity — Gemini generates strong mathematical imagery)
- Intellectually rich (claims, evidence, recursive logic)
- Matches the landing page art (Mandelbrot set) — instant visual continuity
- Familiar enough that judges recognize the concept without needing domain expertise

**Artifact Type:** Storyboard Grid
**Visual Mode:** Hybrid
**Audience Level:** Intermediate
**Audience Persona:** Curious Systems Thinker

---

## The Script

---

### BEAT 1 — Cold Open + Problem (0:00 – 0:25)

**Screen:** ExplainFlow landing page. Mandelbrot/Vitruvian art visible. Let the page breathe for 2 seconds before speaking.

**Voiceover** (~52 words, 25 seconds):

> Current AI video tools are black boxes — you can't control the narrative or verify the facts. ExplainFlow is a Director's Console that exposes the middle. You approve the facts and lock the outline first. And when the visual story is done, every single claim remains fully traceable back to your original source.

**Judge criteria hit:** Clear problem definition (Demo 30%). Sets up "grounding" narrative (Technical 30%).

---

### BEAT 2 — Advanced Studio: Source + Director Console Live (0:25 – 1:25)

**This beat runs LIVE over the director console. Do NOT cut the wait time — it IS the demo.**

The Advanced Studio has a two-column layout that is the visual proof of the agentic architecture:
- **Left column (sticky):** ExplainFlow Assistant (chat) + Agent Session Notes (timestamped checkpoint/QA/trace timeline)
- **Right column:** Workflow Stages bar (5 color-coded badges + progress bar) + active panel with StageProgressList ("Under the Hood" items transitioning pending→active→done)

**Screen:** Click into Advanced Studio. Paste the Mandelbrot paper. Click Extract Content Signal. While extraction runs, lock the render profile (output goal, visual mode, audience, persona, density, taste). Stay on screen and narrate over the director console as it works. The progress UI, stage transitions, and Agent Session Notes streaming in ARE the content.

**Voiceover** (~125 words, 60 seconds):

> This is the Advanced Studio. I paste Mandelbrot's classic paper on fractal coastlines and start extraction. On the left, Agent Session Notes stream in real time. On the right, extraction stages transition live — this is not a spinner, this is a director console.
>
> While it runs, I lock the render profile in parallel — output goal, visual mode, audience persona, information density, and taste. These parameters give the story its ears, and locking them triggers a second Gemini pass that generates narrative beats and visual candidates on top of the structural truth.
>
> And now the signal arrives — thesis, claims, evidence chains, narrative beats. Notice this is pure content — no fonts, no visual direction. That separation is an engineering decision: when an LLM extracts facts and picks styles at the same time, it hallucinates. Extract truth first, lock it, then spend the generation budget.

**Screen actions (LIVE, no cuts):**
- 0:25 — click Advanced from landing page
- 0:28 — paste document into source panel
- 0:32 — click Extract Content Signal
- 0:35 — while extraction runs, set render profile: Storyboard Grid, Hybrid, Intermediate, Curious Systems Thinker
- 0:40 — lock render profile
- 0:42 — point at Agent Session Notes (left column) as notes stream in
- 0:46 — point at StageProgressList items transitioning (right column)
- 0:50 — point at progress bar advancing
- 0:50 — point at phase text: "Structuring thesis, claims, concepts, and narrative beats..."
- 0:54 — point at Workflow Stages bar — badges changing color
- 1:00 — checkpoint toast appears — briefly acknowledge it
- **~1:15** — signal result appears (extraction takes ~50s total from click)
- 1:15–1:22 — scroll through extracted signal: thesis, claims, evidence
- 1:23 — briefly point at evidence snippets

**If extraction finishes early:** Fill with narration about the checkpoint architecture. If it runs long, let the last few seconds of extraction overlap with the start of your next voiceover.

**Judge criteria hit:** This beat is the primary proof of agent architecture (Technical 30%). Checkpoint logging, stage traceability, and self-awareness are all visible in real-time. The "why checkpoint" explanation directly addresses grounding (Technical 30%).

---

### BEAT 3 — Script Pack: Plan + Planner QA Live (1:25 – 1:50)

**This beat also runs LIVE over the director console. Show the planning pipeline working.**

**Screen:** Click Generate Script Pack. Stay on screen — narrate over the progress UI. The Script Pack panel shows its own StageProgressList with live phase text (outlining→structuring→validating), and the Agent Session Notes get planner-specific entries: "Planner draft started", "Planner is structuring scene roles", "Planner QA and deterministic repair checks are running."

**Voiceover** (~55 words, 25 seconds):

> Now watch ExplainFlow do something most AI systems never do — criticize its own plan before spending a cent on generation. The Script Pack locks every scene's goal and claim coverage, then Planner QA tears it apart, repairs weak spots, and locks acceptance checks that every generated scene must pass.

**Screen actions (LIVE, no cuts):**
- 1:25 — click Generate Script Pack
- 1:27 — point at Script Pack progress items transitioning
- 1:30 — point at phase text: "Mapping scene roles, claim coverage, and artifact structure..."
- 1:33 — phase changes to "Drafting narration focus, visual directives, and continuity..."
- 1:36 — phase changes to "Running planner QA, repairs, and script-pack locking..."
- 1:38 — point at Agent Session Notes: "Planner QA and deterministic repair checks are running"
- **~1:43** — script pack result appears
- 1:43–1:47 — scroll through script pack: scene goals, acceptance checks, claim_refs
- 1:48 — point at planner QA summary if visible

**If script pack finishes early:** Jump straight to showing the result. If it runs long, start your Beat 4 voiceover transition while it finishes.

**Judge criteria hit:** Agent architecture (Technical 30%). Self-healing / error handling (Technical 30%). "Context-aware" planning (UX 40%). Planner QA is the most direct answer to "does it handle errors gracefully?"

---

### BEAT 4 — Live Multimodal Streaming + Auto QA (1:50 – 2:35)

**This is the centerpiece. Give it the most screen time. Runs LIVE and UNCUT.**

**Screen:** Click Generate Explainer Stream. Watch Scene 1 stream: text narration arrives incrementally via typewriter effect, then a high-fidelity image appears inline. QA badge appears. Let 2-3 scenes stream. If a QA retry happens, pause the narration to highlight it. The Agent Session Notes (left column) continue logging scene-level events.

**Voiceover** (~90 words, 45 seconds):

> Watch this. Text narration types out, then an image lands — generated together in one Gemini call, not stitched after the fact. Scene by scene, the stream builds a complete visual story.
>
> See those badges? Each scene is scored by an Auto QA Gate. Every scene you see already passed. The ones that didn't — you'll never see them.
>
> And every claim badge you see is a live link back to the original source evidence.

**Screen actions:**
- 1:50 — click Generate Stream
- 1:55 — Scene 1 text starts streaming via typewriter (let it flow)
- 2:02 — Scene 1 image appears (pause narration briefly to let it land)
- 2:07 — QA badge appears — point at it
- 2:10 — Scene 2 starts
- 2:17 — Scene 2 image arrives
- 2:20 — If QA retry happens on any scene, highlight it: "There — the system caught a problem and is retrying"
- 2:30 — Scene 3 visible, claim badges visible

**DO NOT CUT THIS BEAT.** The streaming is the visual payoff — text appearing character by character, images landing, QA badges popping in, Agent Session Notes updating on the left. If there are brief pauses between scenes, keep narrating over them. This is where judges see "media seamlessly woven into cohesive narrative."

**Judge criteria hit:** This single beat hits ALL THREE criteria. Interleaved multimodal output (UX 40% — "media seamlessly woven into cohesive narrative"). Self-healing agent behavior (Technical 30% — "graceful error handling"). Visually compelling real software (Demo 30%).

---

### BEAT 5 — Proof + Regeneration (2:35 – 2:52)

**Screen:** Click a claim badge to open the proof dialog. Show evidence. Close dialog. Then click Regenerate on one scene, type a short instruction, **CUT** through the wait, show the new scene while others stay locked.

**Voiceover** (~35 words, 17 seconds):

> Click any claim badge — the original source evidence opens. The proof survived the entire pipeline. And if I don't like a scene, I regenerate just that one — every other scene stays locked. Every image can be upscaled to print resolution, and the entire production exports as a single ZIP — script, images, and audio. Directing, not restarting.

**Screen actions:**
- 2:35 — click a claim badge on a scene card
- 2:37 — proof dialog opens, show evidence text and source reference
- 2:40 — close dialog
- 2:42 — click Regenerate on a scene, type instruction, click confirm
- **CUT** — stop recording, wait for regeneration, resume when new scene appears
- 2:48 — new scene appears, other scenes unchanged

**Judge criteria hit:** Grounding (Technical 30% — "evidence of grounding to avoid hallucinations"). User control beyond text box (UX 40%). Checkpoint recovery (Technical 30%).

---

### BEAT 6 — Architecture + Cloud Proof (2:52 – 3:07)

**Screen:** Flash the architecture diagram (Mermaid render or PNG). Switch to Cloud Run console tab showing active service. Optionally show Terraform file for bonus points.

**Voiceover** (~35 words, 15 seconds):

> Four Gemini models, each assigned to a different stage of the pipeline. Not one general-purpose call — four specialized ones. FastAPI backend, deployed on Cloud Run, managed with Terraform.

**Screen actions:**
- 2:52 — show architecture diagram (2 seconds)
- 2:56 — switch to Cloud Run console, show active service and URL
- 3:01 — briefly flash `terraform/main.tf` or `cloudbuild.yaml` in the repo (for IaC bonus)
- 3:05 — transition to Quick

**Judge criteria hit:** "Legible architecture diagram" + "Visual proof of Cloud deployment" (Demo 30%). Terraform mention earns +0.2 IaC bonus.

---

### BEAT 7 — Quick Mic Drop (3:07 – 3:42)

**Screen:** Click into Quick. Paste the YouTube URL for "Living Human Brain Cells Play DOOM" and paste the transcript. Set prompt: "Explain the video to non-technical students in a playful tone." Click Generate, then **CUT** — skip the generation wait. Resume when the artifact is ready. Show the four-block artifact with claim references. Switch to Proof Reel tab — show a segment with generated images alongside source footage. Flash MP4 export.

**Voiceover** (~55 words, 25 seconds):

> Everything I just showed you — Quick does it in one shot. I paste a YouTube video about brain cells playing DOOM, and out comes a grounded artifact with claim refs on every block.
>
> ExplainFlow reads the transcript and saves relevant timecodes. In the Proof Reel, I choose: original YouTube footage, generated images, or both. Imagine a three-hour Karpathy podcast condensed to a five-minute visual summary with key moments pulled from source. Export to MP4. Done.

**Screen actions (timed):**
- 3:07 — click Quick
- 3:09 — paste YouTube URL, paste transcript, set prompt and audience
- **CUT** — stop recording, wait for generation (~60s), resume when artifact appears
- 3:12 — show generated artifact blocks (scroll slowly)
- 3:17 — point at claim ref badges on blocks
- 3:20 — switch to Proof Reel tab
- 3:23 — show a reel segment playing (generated image + source footage visible)
- 3:28 — flash MP4 export button
- 3:30 — pause

**Judge criteria hit:** Multimodal output breadth — text, image, audio, video export (UX 40%). YouTube video as source input demonstrates multimodal ingestion (Technical 30%). Mic-drop ending (Demo 30%).

---

### BEAT 8 — Close (3:42 – 3:50)

**Screen:** Landing page. Let the Mandelbrot/Vitruvian art sit for a moment.

**Voiceover** (~20 words, 8 seconds):

> We skipped the Assistant chat for time, but it is checkpoint-aware — users can ask questions or recover the workflow through natural language at any stage.
>
> ExplainFlow is not a generator. It is a director. Extract, plan, self-check, stream, prove, and repair. Thank you.

**Hard stop at 3:50.** Ten-second buffer before the 4:00 cap.

---

## Total Word Count Check

| Beat | Words | Seconds | Pace (wpm) | Live? |
|------|-------|---------|-------------|-------|
| 1. Cold Open | 52 | 25 | 125 | — |
| 2. Signal + Director Console | 120 | 60 | 120 | **LIVE** |
| 3. Script Pack + Planner QA | 47 | 25 | 113 | **LIVE** |
| 4. Streaming + Auto QA | 75 | 45 | 100 | **LIVE** |
| 5. Proof + Regen | 55 | 22 | 150 | CUT |
| 6. Architecture | 30 | 15 | 120 | — |
| 7. Quick Mic Drop | 80 | 35 | 137 | CUT |
| 8. Close | 45 | 8 | 150 | — |
| **Total** | **504** | **235s (3:55)** | **129 avg** |

131 wpm average is comfortable narration pace. Not rushed, not slow.

**Key structural decision:** Advanced runs first (Beats 2-5) to establish the checkpoint architecture and explain *why* each stage exists. Quick closes as the mic drop (Beat 7) — proving the same grounded pipeline also delivers in seconds. The only CUT point is Beat 5 (proof + regen) and Beat 7 (Quick generation). Beats 2, 3, and 4 all run LIVE and UNCUT over the director console.

---

## Post-Production Notes

### Title Card (Optional, 3 seconds before Beat 1)
- "ExplainFlow: AI Production Studio"
- "Built for the Gemini Live Agent Challenge"
- Fade in over the landing page background

### Captions / Subtitles
- Required by rules (English). Use YouTube auto-captions and correct any errors, OR burn in SRT subtitles.

### Music
- Optional. If used, keep it very low — atmospheric ambient only. Judges need to hear your voice clearly.

### Editing Strategy: Advanced First, Quick Mic Drop
- **Only 2 cut points** in this version (Beat 6 Regen and Beat 8 Quick)
- **Beats 2, 3, and 4 all run LIVE and UNCUT** — this is the core differentiator
- The director console (Agent Session Notes, StageProgressList, progress bars, phase text, checkpoint toasts) is the visual proof of the agentic architecture. Cutting away from it would remove the most architecturally impressive content.
- At each CUT: stop recording, wait for generation to finish, resume from the same screen
- In editing, join the clips — the result looks like instant generation
- Rules require "actual software in action," not a single unedited take — clean cuts are fine
- **Timing risk:** Beats 2 and 3 depend on real extraction/planning time (~50s and ~30s). If either runs significantly longer than expected, overlap voiceover from the next beat. If shorter, fill with brief additional narration about checkpoint architecture.

### Thumbnail
- Use a frame from the landing page with the Mandelbrot/Vitruvian art.
- Overlay text: "ExplainFlow — AI Production Studio"
- Do NOT use generic AI imagery.

---

## GCP Proof: Separate Recording

The submission requires a **separate** "Proof of Google Cloud Deployment." This is NOT part of the 4-minute demo video. Record it separately (60-120 seconds) following `docs/gcp-proof-checklist.md`.

Quick version:
1. Show Cloud Run service page (service name, region, URL, active revision)
2. Trigger a real request from the deployed UI
3. Show Cloud Run logs matching that request
4. Show Cloud Storage bucket with generated assets
5. Show `terraform/main.tf` and `cloudbuild.yaml` for IaC bonus

---

## Submission Checklist

Before submitting, verify all of these:

- [ ] Demo video uploaded to YouTube or Vimeo, set to **public**
- [ ] Video is under 4:00
- [ ] Video is in English (or has English subtitles)
- [ ] Video shows actual software, not mockups
- [ ] Video includes a pitch (problem + solution)
- [ ] Separate GCP proof recording uploaded
- [ ] Public repo URL included
- [ ] README.md has spin-up instructions
- [ ] Architecture diagram is in the repo (`docs/architecture.md`)
- [ ] Text description covers: features, functionality, technologies, data sources, learnings
- [ ] Third-party tools mentioned if used

### Bonus Point Opportunities
- [ ] Published content (blog/video/podcast about ExplainFlow): up to +0.6
- [ ] Terraform / `cloudbuild.yaml` shown as IaC: +0.2
- [ ] Google Developer Group membership: +0.2

---

## What Judges Will Compare You Against

Per the Creative Storyteller rubric, judges will ask:

1. **"Is media seamlessly woven into a cohesive narrative?"**
   - Your answer: Yes. Text and image stream interleaved from Gemini, audio is generated per scene, proof links are attached throughout, and the whole thing exports to MP4.

2. **"Does the experience feel live and context-aware versus disjointed?"**
   - Your answer: Yes. The workflow is checkpointed and stateful. The agent chat understands the current stage. Scenes know about previous scenes via continuity hints. QA checks are context-aware.

3. **"Is there evidence of grounding to avoid hallucinations?"**
   - Your answer: Yes. This is the core product. Claim refs and evidence refs propagate from source extraction through planning into every scene card. Users can inspect exact backing evidence.

4. **"Does it handle errors gracefully?"**
   - Your answer: Yes. Planner self-checks and repairs before generation. Scene QA catches drift during streaming. Auto-retry fixes scenes without user intervention. Checkpoints allow recovery without restart.

These are the four questions your video must answer. Every beat in this script addresses at least one.

---

## Emergency Backup Plan

If the deployed Cloud Run service is down or Gemini quota is exhausted during recording:

1. Run locally (`localhost:8000` + `localhost:3000`)
2. Record the demo locally
3. Record the GCP proof separately from a previous successful deployment
4. In the GCP proof, show recent Cloud Run logs and Cloud Storage artifacts from a prior run
5. State clearly: "This is a previously executed successful run on the deployed service"

Do NOT submit a demo with no generation happening. Judges will notice.
