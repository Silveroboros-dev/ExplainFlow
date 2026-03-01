# Gemini Context & Project Learnings

This file acts as the AI context memory for the ExplainFlow project. It contains critical architectural learnings, prompt engineering constraints, and model behaviors discovered during development.

## 1. Multimodal Streaming (The "Nano Banana" Architecture)

**The Goal:** The hackathon's Creative Storyteller track requires **"interleaved/mixed output"**. 

**The Challenge:** 
Initially, we tried calling a text model (Gemini 3.1 Pro) and then an image model (Imagen 4.0). While this works, it is not a true interleaved multimodal response.
When we switched to `gemini-3-pro-image-preview` (Nano Banana Pro) to generate the entire 4-scene script AND the 4 images in a single prompt, the model took ~60 seconds of "thinking" time before emitting the first byte, causing the browser's Server-Sent Events (SSE) connection to time out.

**The Solution:**
We retained `gemini-3-pro-image-preview` for true interleaved output (where image bytes arrive directly in the `inline_data` of the stream candidates), but we moved the orchestration into a Python loop.
1. We generate an Outline first.
2. We loop over the scenes. For *each* scene, we send a scoped prompt to Nano Banana Pro: "Given this overall plan, generate ONLY Scene X right now."
3. This forces the model to stream the text instantly, followed by the image, preventing timeouts while maintaining stylistic continuity.

## 2. Prompt Engineering for Audio/UI Rendering

**The Challenge:**
When asking the model to write a scene, it naturally defaults to a conversational chatbot style (e.g., "Here is the explainer for Scene 1...", "### Scene 1: Introduction", "**Narration:** Hello..."). 
Because we pass the raw text stream to Google Text-to-Speech (`gTTS`) to generate voiceovers, these markdown headers and conversational preambles result in robotic, immersion-breaking audio.

**The Solution:**
We apply "Strict Formatting Rules" via negative constraints in the prompt:
- NO conversational filler.
- NO markdown headers or labels.
- Immediately output the exact spoken narration text.

## 3. Strict JSON Schema Extraction

**The Goal:** The "Advanced Studio" requires parsing unstructured text into a locked, style-agnostic "Content Signal."

**The Solution:**
We use `gemini-3.1-pro-preview` with `response_mime_type="application/json"` and pass the raw contents of `content_signal.schema.json` directly into the system prompt. By using a low temperature (`0.2`), the model reliably extracts the thesis, narrative beats, and `claim_refs` perfectly every time. 
*Note: We opted to pass the schema in the prompt rather than using the strict `response_schema` SDK parameter for the extraction endpoint because the schema contains complex nested arrays that the raw string prompt handled more gracefully for this specific task.*

## 4. Visual Consistency (Continuity Rule)

**The Challenge:** 
AI image generators struggle to keep characters or styles consistent across multiple prompts. 

**The Solution:**
Because we process the generation in a loop, we inject a hard continuity rule into the Nano Banana Pro prompt:
> `"CRITICAL CONTINUITY RULE: All generated images MUST share an identical, cohesive visual style. Maintain the exact same art direction as previous scenes."`

## 5. Traceability Pipeline

To prove AI traceability to the judges:
1. The Extraction phase assigns `claim_refs` (e.g., `["c1", "c2"]`) to specific narrative beats.
2. The Generation phase maps those beats directly to Scenes.
3. The UI extracts the `claim_refs` from the SSE event (`scene_start`) and renders them as badges on the final `SceneCard`.

## 6. Agent Interaction Rules

To ensure safety and user control during automated development:
- **Diff Transparency:** Always show a clear diff or summary of the intended changes before applying them.
- **Explicit Permission:** Never overwrite an existing file's entire contents without asking the user for direct, explicit permission to proceed. Surgical edits via `replace` are preferred over full-file `write_file` operations.
- **Discovery Autonomy:** Read-only commands (like `cat`, `grep`, `ls`, `read_file`) and architectural investigation tools should be used autonomously to maintain momentum and never require explicit user permission.
- **Detailed Git Commits:** When committing and pushing to GitHub, always provide a multi-line commit message. Use the first line for a high-level summary and subsequent `-m` flags or lines for a technical breakdown of specific features, fixes, or refactors included in the push.

