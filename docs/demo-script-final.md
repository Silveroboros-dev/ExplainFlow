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
2. Quick page — ideally with a pre-generated artifact ready to show
3. Advanced Studio — fresh session
4. Cloud Run console showing `explainflow-api` service
5. Architecture diagram (open `docs/architecture.md` Mermaid or a rendered PNG)

### Pre-Warm
- Run one full Quick generation before recording so you know the timing
- Run one full Advanced extraction + script pack + at least 2 scenes before recording
- Have a stable source document ready to paste (see Recommended Input below)
- Test that proof links open correctly from the deployed URL

### Audio
- Use an external mic or record voiceover separately
- Speak at ~140 words per minute (natural, unhurried)
- Each section below includes exact word counts to stay on pace

---

## Recommended Source Input

**Topic:** "The Mechanics of SpaceX Starship Orbital Launch"

**Why this topic:**
- Technically rich (claims, evidence, causal chains)
- Visually interesting (Gemini generates strong aerospace imagery)
- Familiar enough that judges immediately understand the content
- Has natural narrative structure (stages, risks, payoffs)

**Alternative:** "How CRISPR Gene Editing Works" or "The Race to Commercial Fusion Energy"

**Persona:** Aerospace Investor (or Venture Capitalist)
**Taste Bar:** Very High
**Art Direction:** Hybrid

---

## The Script

---

### BEAT 1 — Cold Open + Problem (0:00 – 0:25)

**Screen:** ExplainFlow landing page. Mandelbrot/Vitruvian art visible. Let the page breathe for 2 seconds before speaking.

**Voiceover** (~55 words, 25 seconds):

> Every AI content tool today works the same way. You paste something in, you get something out, and you have no idea where the claims came from, no way to fix one part without redoing everything, and no proof that the output is grounded in reality.
>
> We built ExplainFlow to change that. It is a production studio, not a black box.

**Judge criteria hit:** Clear problem definition (Demo 30%). Sets up "grounding" narrative (Technical 30%).

---

### BEAT 2 — Quick Path: Prove Speed (0:25 – 1:00)

**Screen:** Click into Quick. Paste a topic, click generate, then **CUT** — skip the ~60s generation wait entirely. Resume recording when the artifact is ready. Show the four-block artifact with claim references visible. Switch to Proof Reel tab. Flash the MP4 export button.

**Voiceover** (~75 words, 35 seconds):

> Let me show you the fast path first. I give ExplainFlow a topic, pick my audience, and it generates a grounded explainer artifact. Each block carries claim references back to the source material.
>
> From there, I can derive a Proof Reel — each segment links generated visuals to cited source evidence — and export the whole thing as a narrated MP4.
>
> That is Quick mode: one input to a complete, proof-aware media package. But the real depth is in the Advanced Studio.

**Screen actions (timed):**
- 0:25 — click Quick
- 0:28 — show source input / topic, click generate
- **CUT** — stop recording, wait for generation (~60s), resume when artifact appears
- 0:33 — show generated artifact blocks (scroll slowly)
- 0:42 — point at claim ref badges on blocks
- 0:45 — switch to Proof Reel tab
- 0:50 — briefly show a reel segment playing
- 0:55 — flash MP4 export button
- 0:58 — pause, then navigate to Advanced

**Judge criteria hit:** Multimodal output breadth — text, image, audio, video export (UX 40%). Shows "rich, mixed-media responses" per Creative Storyteller rubric.

---

### BEAT 3 — Advanced Studio: Source + Director Console Live (1:00 – 1:50)

**This beat runs LIVE over the director console. Do NOT cut the wait time — it IS the demo.**

The Advanced Studio has a two-column layout that is the visual proof of the agentic architecture:
- **Left column (sticky):** ExplainFlow Assistant (chat) + Agent Session Notes (timestamped checkpoint/QA/trace timeline)
- **Right column:** Workflow Stages bar (5 color-coded badges + progress bar) + active panel with StageProgressList ("Under the Hood" items transitioning pending→active→done)

**Screen:** Paste the Starship document. Set persona and taste bar. Click Extract Content Signal. Stay on screen and narrate over the director console as it works. The progress UI, stage transitions, and Agent Session Notes streaming in ARE the content.

**Voiceover** (~105 words, 50 seconds):

> In the Advanced Studio, I paste a technical brief and define my audience and quality bar. Watch what happens when I start extraction.
>
> On the left, the Agent Session Notes are filling with timestamped decisions. On the right, the progress list shows each extraction stage transitioning from pending to active to done — source validation, schema check, structuring thesis and claims.
>
> This is not a spinner. This is a live director console showing the agent harness at work. Every checkpoint is logged. Every stage is traceable.
>
> And now the signal arrives — a structured thesis, key claims with evidence chains, and narrative beats. This gets locked as a checkpoint before any generation happens.

**Screen actions (LIVE, no cuts):**
- 1:00 — paste document into source panel
- 1:03 — set persona to "Aerospace Investor", taste to "Very High"
- 1:08 — click Extract Content Signal
- 1:10 — point at Agent Session Notes (left column) as first notes appear
- 1:15 — point at StageProgressList items transitioning (right column)
- 1:18 — point at progress bar advancing
- 1:22 — point at phase text: "Structuring thesis, claims, concepts, and narrative beats..."
- 1:25 — point at Workflow Stages bar — badges changing color
- 1:30 — checkpoint toast appears — briefly acknowledge it
- **~1:38** — signal result appears (extraction takes ~50s total from click)
- 1:38–1:45 — scroll through extracted signal: thesis, claims, evidence
- 1:48 — briefly point at evidence snippets

**If extraction finishes early:** Fill with narration about the checkpoint architecture. If it runs long, let the last few seconds of extraction overlap with the start of your next voiceover.

**Judge criteria hit:** This beat is the primary proof of agent architecture (Technical 30%). Checkpoint logging, stage traceability, and self-awareness are all visible in real-time. Also hits grounding (Technical 30%) when the signal arrives.

---

### BEAT 4 — Script Pack: Plan + Planner QA Live (1:50 – 2:15)

**This beat also runs LIVE over the director console. Show the planning pipeline working.**

**Screen:** Click Generate Script Pack. Stay on screen — narrate over the progress UI. The Script Pack panel shows its own StageProgressList with live phase text (outlining→structuring→validating), and the Agent Session Notes get planner-specific entries: "Planner draft started", "Planner is structuring scene roles", "Planner QA and deterministic repair checks are running."

**Voiceover** (~55 words, 25 seconds):

> Before spending any generation budget, ExplainFlow compiles a Script Pack. Watch the stages — outlining, structuring, then validating. That validation step is Planner QA: the system self-checks the plan and repairs weak coverage before generation begins.
>
> The Agent Session Notes on the left are logging every decision. This is not a loading screen — it is an audit trail.

**Screen actions (LIVE, no cuts):**
- 1:50 — click Generate Script Pack
- 1:52 — point at Script Pack progress items transitioning
- 1:55 — point at phase text: "Mapping scene roles, claim coverage, and artifact structure..."
- 1:58 — phase changes to "Drafting narration focus, visual directives, and continuity..."
- 2:00 — phase changes to "Running planner QA, repairs, and script-pack locking..."
- 2:02 — point at Agent Session Notes: "Planner QA and deterministic repair checks are running"
- **~2:08** — script pack result appears
- 2:08–2:12 — scroll through script pack: scene goals, acceptance checks, claim_refs
- 2:13 — point at planner QA summary if visible

**If script pack finishes early:** Jump straight to showing the result. If it runs long, start your Beat 5 voiceover transition while it finishes.

**Judge criteria hit:** Agent architecture (Technical 30%). Self-healing / error handling (Technical 30%). "Context-aware" planning (UX 40%). Planner QA is the most direct answer to "does it handle errors gracefully?"

---

### BEAT 5 — Live Multimodal Streaming + Auto QA (2:15 – 3:00)

**This is the centerpiece. Give it the most screen time. Runs LIVE and UNCUT.**

**Screen:** Click Generate Explainer Stream. Watch Scene 1 stream: text narration arrives incrementally via typewriter effect, then a high-fidelity image appears inline. QA badge appears. Let 2-3 scenes stream. If a QA retry happens, pause the narration to highlight it. The Agent Session Notes (left column) continue logging scene-level events.

**Voiceover** (~90 words, 45 seconds):

> Now watch the stream. Narration text arrives scene by scene, immediately followed by a generated visual — this is Gemini's native interleaved multimodal output, text and image woven together in one stream.
>
> Look at the badges. Every scene passes through an Auto QA Gate — scored against the acceptance checks from the Script Pack. If it detects drift or missing claims, it triggers a Correction Retry in real-time.
>
> And the claim badges on each scene card are live proof links back to the original source evidence.

**Screen actions:**
- 2:15 — click Generate Stream
- 2:20 — Scene 1 text starts streaming via typewriter (let it flow)
- 2:27 — Scene 1 image appears (pause narration briefly to let it land)
- 2:32 — QA badge appears — point at it
- 2:35 — Scene 2 starts
- 2:42 — Scene 2 image arrives
- 2:45 — If QA retry happens on any scene, highlight it: "There — the system caught a problem and is retrying"
- 2:55 — Scene 3 visible, claim badges visible

**DO NOT CUT THIS BEAT.** The streaming is the visual payoff — text appearing character by character, images landing, QA badges popping in, Agent Session Notes updating on the left. If there are brief pauses between scenes, keep narrating over them. This is where judges see "media seamlessly woven into cohesive narrative."

**Judge criteria hit:** This single beat hits ALL THREE criteria. Interleaved multimodal output (UX 40% — "media seamlessly woven into cohesive narrative"). Self-healing agent behavior (Technical 30% — "graceful error handling"). Visually compelling real software (Demo 30%).

---

### BEAT 6 — Proof-Linked Review (3:00 – 3:15)

**Screen:** Click "View Source Proof" on a scene card claim badge. Show the proof dialog opening: evidence metadata, source quote, and backing asset.

**Voiceover** (~40 words, 15 seconds):

> Here is what makes ExplainFlow fundamentally different. I click any claim badge and the exact backing evidence opens. This is not retroactive citation. The proof was carried from extraction through planning into the final scene. Every claim is traceable.

**Screen actions:**
- 3:00 — click a claim badge on a scene card
- 3:03 — proof dialog opens, show evidence text and source reference
- 3:08 — scroll through evidence metadata
- 3:12 — close dialog

**Judge criteria hit:** Grounding (Technical 30% — "evidence of grounding to avoid hallucinations"). This is the differentiator most competitors will not have.

---

### BEAT 7 — Directed Scene Regeneration (3:15 – 3:27)

**Screen:** Click Regenerate on one scene. Type a short instruction. **CUT** through the regeneration wait. Show the new scene while other scenes remain locked.

**Voiceover** (~30 words, 12 seconds):

> Because the workflow is checkpointed, I can regenerate any single scene with a custom direction while every other scene stays stable. I am directing, not restarting.

**Screen actions:**
- 3:15 — click Regenerate on Scene 2
- 3:18 — type instruction, click confirm
- **CUT** — stop recording, wait for regeneration, resume when new scene appears
- 3:22 — new scene appears, other scenes unchanged

**Judge criteria hit:** User control beyond text box (UX 40%). Checkpoint recovery (Technical 30%).

---

### BEAT 8 — Architecture + Cloud Proof (3:27 – 3:42)

**Screen:** Flash the architecture diagram (Mermaid render or PNG). Switch to Cloud Run console tab showing active service. Optionally show Terraform file for bonus points.

**Voiceover** (~35 words, 15 seconds):

> The system runs on FastAPI and Google Cloud Run with 300-second streaming timeouts. Gemini 3.1 Pro handles extraction and planning, Gemini 3 Pro Image handles interleaved generation, and infrastructure is managed with Terraform.

**Screen actions:**
- 3:27 — show architecture diagram (2 seconds)
- 3:31 — switch to Cloud Run console, show active service and URL
- 3:36 — briefly flash `terraform/main.tf` or `cloudbuild.yaml` in the repo (for IaC bonus)
- 3:40 — transition back to landing page

**Judge criteria hit:** "Legible architecture diagram" + "Visual proof of Cloud deployment" (Demo 30%). Terraform mention earns +0.2 IaC bonus.

---

### BEAT 9 — Close (3:42 – 3:50)

**Screen:** Landing page. Let the Mandelbrot/Vitruvian art sit for a moment.

**Voiceover** (~20 words, 8 seconds):

> ExplainFlow is not a generator. It is a director. Extract, plan, self-check, stream, prove, and repair. Thank you.

**Hard stop at 3:50.** Ten-second buffer before the 4:00 cap.

---

## Total Word Count Check

| Beat | Words | Seconds | Pace (wpm) | Live? |
|------|-------|---------|-------------|-------|
| 1. Cold Open | 55 | 25 | 132 | — |
| 2. Quick | 75 | 35 | 129 | CUT |
| 3. Signal + Director Console | 105 | 50 | 126 | **LIVE** |
| 4. Script Pack + Planner QA | 55 | 25 | 132 | **LIVE** |
| 5. Streaming | 90 | 45 | 120 | **LIVE** |
| 6. Proof | 40 | 15 | 160 | — |
| 7. Regen | 30 | 12 | 150 | CUT |
| 8. Architecture | 35 | 15 | 140 | — |
| 9. Close | 20 | 8 | 150 | — |
| **Total** | **505** | **230s (3:50)** | **132 avg** |

132 wpm average is comfortable narration pace. Not rushed, not slow.

**Key change from earlier drafts:** Beats 3, 4, and 5 all run LIVE over the director console. The only CUT points are in Beat 2 (Quick, no progress UI) and Beat 7 (scene regeneration). The live director console — progress lists, Agent Session Notes, phase text, checkpoint toasts — is the primary visual proof of the agentic architecture, which is 30% of the judging weight.

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

### Editing Strategy: Live Director Console, Minimal Cuts
- **Only 2 cut points** in this version (Beat 2 Quick and Beat 7 Regen)
- **Beats 3, 4, and 5 all run LIVE and UNCUT** — this is the core differentiator
- The director console (Agent Session Notes, StageProgressList, progress bars, phase text, checkpoint toasts) is the visual proof of the agentic architecture. Cutting away from it would remove the most architecturally impressive content.
- At each CUT: stop recording, wait for generation to finish, resume from the same screen
- In editing, join the clips — the result looks like instant generation
- Rules require "actual software in action," not a single unedited take — clean cuts are fine
- **Timing risk:** Beats 3 and 4 depend on real extraction/planning time (~50s and ~30s). If either runs significantly longer than expected, overlap voiceover from the next beat. If shorter, fill with brief additional narration about checkpoint architecture.

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
