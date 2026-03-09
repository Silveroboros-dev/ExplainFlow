# Gemini Context & Project Learnings

This document is the short operational memory for ExplainFlow. It describes the current architecture, where Gemini is used, and the constraints that matter for demos and deployments.

## 1. Current Generation Shape

ExplainFlow has two user-facing paths:

1. **Advanced Studio**
   - Extract a structured content signal from source text or source assets.
   - Build a script pack and stream scene generation over SSE.
   - Attach claim refs, evidence refs, and source media to the generated scenes.

2. **Quick**
   - Build a lightweight four-block artifact quickly.
   - Optionally derive a Proof Reel from those blocks.
   - Keep latency low and avoid heavy replanning passes.

## 2. Model Routing Policy

Current defaults are intentionally split by job type:

- `gemini-3.1-pro-preview`
  - structural extraction
  - heavier planning and review
- `gemini-3-flash-preview`
  - fast text-heavy Quick paths
  - source normalization and lighter precompute work
- `gemini-3-pro-image-preview`
  - image generation and interleaved multimodal scene/image output

Do not rename model IDs casually. Quota availability and behavior vary by project. Validate changes against the actual project quotas before switching defaults.

## 3. Streaming Constraint

True mixed text+image generation is supported, but long first-token latency can break browser and proxy timeouts. The practical pattern is:

1. plan first
2. generate scene by scene
3. stream partial progress early

If streaming appears broken, verify infrastructure timeouts before assuming the generation code is wrong.

## 4. Prompt Rules That Matter

- Scene narration must be raw spoken copy, not markdown or assistant framing.
- Structured extraction should stay JSON-first.
- Claim refs and evidence refs are part of the product, not just debug metadata.
- Quick overrides should stay deterministic and local unless explicitly upgrading the UX.

## 5. Traceability Principle

The product value is not only generation quality. It is also proof:

1. extract grounded claims and evidence
2. propagate refs into artifacts and scenes
3. surface those refs in the UI
4. reuse them in Proof Reel selection

Any refactor that makes outputs prettier but weakens traceability is a regression.

## 6. Infrastructure Notes

- Cloud Run and similar environments need timeout headroom for streaming generation.
- Gemini quotas differ sharply across projects and billing setups.
- Large source uploads need guardrails; transcript-backed video is the safest current demo path.

## 7. Repository Hygiene

- Prefer centralized model constants over scattered hardcoded model IDs.
- Prefer shared frontend API base configuration over inline localhost URLs.
- Keep repo-facing docs aligned with the actual shipped architecture.

