# ExplainFlow Demo — Voiceover Script

**Total: ~484 words | 3:53 | 124 wpm avg**

---

## BEAT 1 — Cold Open (0:00 – 0:25)

Current AI video tools are black boxes — you can't control the narrative or verify the facts. ExplainFlow is a Director's Console that exposes the middle. You approve the facts and lock the outline first. And when the visual story is done, every single claim remains fully traceable back to your original source.

---

## BEAT 2 — Advanced Studio: Extraction (0:25 – 1:20) **LIVE**

This is the Advanced Studio. I paste Mandelbrot's classic paper on fractal coastlines and start extraction. On the left, Agent Session Notes stream in real time. On the right, extraction stages transition live — this is not a spinner, this is a director console.

While it runs, I lock the render profile in parallel — output goal, visual mode, audience persona, information density, and taste. These parameters give the story its ears, and locking them triggers a second Gemini pass that generates narrative beats and visual candidates on top of the structural truth.

And now the signal arrives — thesis, claims, evidence chains, narrative beats. Notice this is pure content — no fonts, no visual direction. That separation is an engineering decision: when an LLM extracts facts and picks styles at the same time, it hallucinates. Extract truth first, lock it, then spend the generation budget.

---

## BEAT 3 — Script Pack + Planner QA (1:20 – 1:45) **LIVE**

Now watch ExplainFlow do something most AI systems never do — criticize its own plan before spending a cent on generation. The Script Pack locks every scene's goal and claim coverage, then Planner QA tears it apart, repairs weak spots, and locks acceptance checks that every generated scene must pass. If the plan fails, it replans automatically.

---

## BEAT 4 — Streaming, Proof + Regeneration (1:45 – 2:55) **LIVE**

Watch this. Text narration types out, then an image lands — generated together in one Gemini call, not stitched after the fact. Scene by scene, the stream builds a complete visual story. Notice the visual continuity — anchor terms carry forward between scenes to prevent narrative drift.

See those badges? Each scene is scored by an Auto QA Gate. Every scene you see already passed. The ones that didn't were retried automatically — you'll never see them.

And every claim badge you see is a live link back to the original source evidence.

Click any claim badge — the original source evidence opens. The proof survived the entire pipeline. And if I don't like a scene, I regenerate just that one with a custom instruction — every other scene stays locked. Every image can be upscaled to print resolution, and the entire production exports as a single ZIP — script, images, and audio. Directing, not restarting.

---

## BEAT 5 — Quick Mic Drop (2:55 – 3:45) **CUT**

That was the full Advanced pipeline — four Gemini models, each assigned to a different stage. FastAPI on Cloud Run, managed with Terraform. Now watch Quick do all of it in one shot.

I paste a YouTube video about brain cells playing DOOM, and out comes a grounded artifact with claim refs on every block. Blocks can be regenerated individually here too.

In the Proof Reel, I choose per segment: original YouTube footage, generated images, or both. Watch — the playlist plays source clips interleaved with generated visuals. Imagine a three-hour Karpathy lecture condensed to five minutes with every key moment pulled from source. Export to MP4 — generated visuals, voiceover, and cinematic transitions bundled into one video. Done.

---

## BEAT 6 — Close (3:45 – 3:53)

We skipped the Assistant chat for time, but it is checkpoint-aware — users can ask questions or recover the workflow through natural language at any stage.

ExplainFlow is not a generator. It is a director. Extract, plan, self-check, stream, prove, and repair. Thank you.
