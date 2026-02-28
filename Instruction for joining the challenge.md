
**Rules That Matter (architecture-impacting)**
- Submission deadline: **March 16, 2026, 5:00 PM PT** (banner + rules).
- Must be a **new project created during the contest period** (not an extension of an old one).
- Must use:
  - a **Gemini model**
  - **Google GenAI SDK or ADK**
  - **at least one Google Cloud service**
  - and for **Creative Storyteller** specifically: **Gemini interleaved/mixed output** with agent hosted on Google Cloud.
- Submission must include:
  - public repo + README spin-up instructions
  - architecture diagram
  - demo video (<= 4 min, real software, not mockups)
  - proof of Google Cloud deployment (separate recording or code proof)
- Judges may choose to score from **text/images/video only**, so demo quality matters a lot.
- Judging weights: **40% UX/multimodal**, **30% technical architecture**, **30% demo/presentation**.

**Minimal Starter Repo (fastest path)**
Use a fresh repo, something like `gemini-story-director`.

```text
gemini-story-director/
├─ README.md
├─ docs/
│  ├─ architecture.md
│  ├─ architecture.png
│  ├─ demo-script.md
│  └─ gcp-proof-checklist.md
├─ web/                         # Next.js UI (streaming interleaved output)
│  ├─ app/
│  ├─ components/
│  ├─ lib/
│  └─ package.json
├─ api/                         # FastAPI or Node backend (pick one)
│  ├─ app/
│  │  ├─ main.py                # or server.ts
│  │  ├─ routes/
│  │  │  ├─ generate_stream.py  # SSE/WebSocket stream
│  │  │  ├─ sessions.py
│  │  │  └─ assets.py
│  │  ├─ services/
│  │  │  ├─ gemini_story_agent.py
│  │  │  ├─ interleaved_parser.py
│  │  │  ├─ image_pipeline.py
│  │  │  ├─ audio_pipeline.py
│  │  │  └─ storyboard_compiler.py  # optional MP4 export
│  │  ├─ schemas/
│  │  │  ├─ events.py
│  │  │  └─ requests.py
│  │  └─ config.py
│  ├─ requirements.txt          # or package.json
│  └─ Dockerfile
├─ shared/
│  ├─ prompts/
│  │  ├─ creative_director_system.txt
│  │  └─ storyboard_format.txt
│  └─ samples/
│     ├─ sample_brief_1.md
│     └─ sample_assets/
├─ infra/
│  ├─ cloudrun/
│  │  ├─ service.yaml
│  │  └─ deploy.sh
│  └─ firebase/                 # optional, if hosting UI on Firebase
└─ scripts/
   ├─ smoke_test.sh
   └─ record_gcp_proof_checklist.md
```

**Recommended Stack (weekend-safe)**
- `web`: Next.js (fast UI + nice demo polish)
- `api`: FastAPI (you already move fast in Python)
- Google Cloud:
  - `Cloud Run` (backend)
  - `Cloud Storage` (generated image/audio/video assets)
  - `Firestore` (session/story metadata) or skip DB and use JSON in GCS for MVP
- Gemini:
  - use **GenAI SDK** (faster than ADK for this category unless you want complex orchestration)

**Core MVP Flow (what judges should see)**
1. User enters a brief (`audience`, `tone`, `goal`, optional docs/images).
2. Backend starts a **streaming generation session**.
3. UI renders interleaved events live:
   - narration text chunk
   - scene image
   - voiceover/audio snippet
   - caption/overlay text
   - next scene beat
4. Final output page shows:
   - story transcript
   - storyboard frames
   - audio track(s)
   - optional stitched “animatic” video export

**Important Design Choice**
- Build around a **single event stream** (SSE/WebSocket) so the experience feels “live” and interleaved.
- Event types example:
  - `story_text_delta`
  - `scene_start`
  - `image_ready`
  - `audio_ready`
  - `caption_ready`
  - `timeline_update`
  - `final_bundle_ready`

**What to Build First (in order)**
1. Streaming text + placeholder scene cards
2. Real image generation inline
3. Audio/voiceover generation inline
4. Save/export final bundle
5. Optional MP4 compile
6. Demo polish (loading states, progress, retries)

**Contest-Specific Submission Checklist (don’t miss)**
- `README.md` with spin-up instructions
- Architecture diagram
- Public repo
- Live demo link (if possible)
- Demo video <= 4 min (real software footage)
- Separate GCP proof clip or code proof showing Cloud Run/GCP usage
- Mention third-party tools clearly if used

**Pragmatic note**
The rules also emphasize robustness/grounding under technical execution. Even in a creative project, add a lightweight “source mode” or “fact mode” toggle for explainers (citations/grounding) to score higher on architecture credibility.

The rules page also appears to contain a likely typo in the judging period line (`April 3, 2025`), but the contest dates and submission deadline are otherwise clearly shown for 2026.

Sources:
- [Gemini Live Agent Challenge Rules (Devpost)](https://geminiliveagentchallenge.devpost.com/rules)
