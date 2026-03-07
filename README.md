# ExplainFlow: AI Production Studio

ExplainFlow is an agent-coordinated AI Production Studio that transforms complex documents and prompts into high-fidelity, interleaved visual explainer streams.

## Product Vision: The Explainer Director

ExplainFlow represents a pivot from simple "generation" to **"Directed Production."** The system acts as an autonomous studio where a central coordinator manages the entire lifecycle of a visual narrative—from core signal extraction to final validated asset packaging.

### Key Capabilities (Architecture v3)
- **Agentic Coordination**: A persistent `AgentCoordinator` manages production "Gates" (Signal, Profile, Script) using a state-aware `workflow_id`.
- **Conversational Co-Direction**: Interact with the studio via the `WorkflowChatAgent` to adjust styles, personas, or narrative focus through natural language.
- **Self-Healing Production**: An **Auto QA Gate** scores every scene. If quality or alignment fails, the director automatically triggers a **Correction Retry** to fix the scene in real-time.
- **Visual Chaining**: Advanced multimodal continuity that passes visual anchor terms between scenes to prevent narrative drift.
- **Production-Grade Export**: Package your validated explainer into a professional ZIP bundle containing the script, high-res images, and synchronized audio.

## Pipeline Evolution

- **Legacy (v1/v2):** Linear extraction -> planning -> interleaved generation with basic QA.
- **Current (v3):** State-aware **Agentic Studio** with conversational control, checkpoint gates, and coordinated multi-agent logic.

---

## How to Run Locally

### Prerequisites
- Python 3.10+
- Node.js 20+ and `npm`
- A Google GenAI API Key (with access to `gemini-3.1-pro-preview` and `gemini-3-pro-image-preview`)

### 1. Set up the Backend (FastAPI)
```bash
cd api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "GEMINI_API_KEY=your_api_key_here" > .env
uvicorn app.main:app --reload --port 8000
```

### 2. Set up the Frontend (Next.js)
```bash
cd web
npm install
npm run dev
```
*Frontend runs at `http://localhost:3000`. Backend runs at `http://localhost:8000`.*

---

## Technical Core

### 1. Signal Extraction Layer
Extracts a style-agnostic `content_signal` (Thesis, Key Claims, Narrative Beats) using `gemini-3.1-pro-preview`.

### 2. Guided Render Profiling
A multi-stage intake process to define:
- **Audience Persona**: (e.g., Venture Capitalist, Student, Engineer)
- **Art Direction**: (Diagram, Illustration, Hybrid)
- **Constraints**: `must_include` and `must_avoid` rules for strict content alignment.

### 3. Script Pack Compilation
The planner compiles a production manifest before generation, ensuring every scene has clear goals and "Acceptance Checks."

### 4. Live Multimodal Streaming
The "Nano Banana" orchestration loop delivers narration text interleaved with high-fidelity visuals from `gemini-3-pro-image-preview`.

---

## Architecture (Agentic Studio v3)

- **Frontend**: Next.js Studio UI with `AgentActivityPanel` for 100% transparency of agent decisions.
- **Backend**: FastAPI with `AgentCoordinator` service layer and SSE streaming.
- **Orchestration**:
    - **Planner**: Gemini 3.1 Pro (Logic & Extraction)
    - **Director**: Gemini 3 Pro Image (Multimodal Generation)
    - **Co-Director**: Gemini 3.1 Pro (Conversational Control)
- **Infrastructure**: Cloud Run (300s timeouts) + Cloud Storage.

For detailed sequence diagrams, see: `/docs/architecture.md`

---

## TODO / Roadmap

- [ ] **Optional HD Upscale Pass**: Use `imagen-4.0-upscale-preview` for final-bundle quality.
- [ ] **Multimodal Ingestion**: Support PDF logic extraction from charts and diagrams.
- [ ] **Full Video Compositor**: Automated `.mp4` stitching of visuals and audio.
- [ ] **Credit Protection**: Gated access PIN for public demos.

Built for the **Gemini API Developer Competition**.
