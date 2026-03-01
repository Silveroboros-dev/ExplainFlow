(as of **February 28, 2026**):

1. **Use gemini-3.1-pro-preview for thinking/planning**
    - Best for: long-doc signal extraction, claim structuring, scene planning, captions/scripts, tool-orchestrated steps.
    - Why: multimodal input + strong reasoning/tool use.
    - Constraint: output is **text only** (no native image generation).
2. **Use Imagen 4 for pure image rendering**
    - Best for: final polished static images when you want dedicated text-to-image output.
    - Models: imagen-4.0-generate-001, imagen-4.0-fast-generate-001, imagen-4.0-ultra-generate-001.
    - Constraint: Imagen is image-focused (not conversational text+image interleaving).
3. **For interleaved text+image UX, use Nano Banana models**
    - gemini-3.1-flash-image-preview (Nano Banana 2): faster, high-volume.
    - gemini-3-pro-image-preview (Nano Banana Pro): higher-end complex image tasks.
    - These return **image + text** and support iterative editing workflows.
4. **Can you call Nano Banana through GenAI SDK?**

- **Yes.** It’s directly supported via Google GenAI SDK using client.models.generate_content(...) with model IDs like gemini-3.1-flash-image-preview.

Quick routing I recommend:

- Extraction/plan: gemini-3.1-pro-preview
- Draft scene visuals: gemini-3.1-flash-image-preview
- Optional hero-frame polish: imagen-4.0-ultra-generate-001

Sources: [Gemini 3.1 Pro model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-pro-preview), [Gemini image generation / Nano Banana](https://ai.google.dev/gemini-api/docs/image-generation), [Gemini 3.1 Flash Image Preview](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-image-preview), [Imagen 4 model page](https://ai.google.dev/gemini-api/docs/models/imagen), [Imagen API model IDs on Vertex AI](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/imagen-api), [Gemini API release notes](https://ai.google.dev/gemini-api/docs/changelog).