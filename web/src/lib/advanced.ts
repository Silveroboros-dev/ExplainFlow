import {
  type LucideIcon,
  GitBranch,
  ImageIcon,
  LayoutGrid,
  Newspaper,
  PenTool,
  Presentation,
  Rows3,
  ScanLine,
  Shapes,
  Workflow,
} from "lucide-react";

export const ADVANCED_API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const ADVANCED_WORKFLOW_STORAGE_KEY = "explainflow.advanced.workflow_id";

export const SIGNAL_EXPLAINER_TEXT = [
  "Structured extraction converts long input into a stable JSON contract.",
  "",
  "Why this is better than uncontrolled extraction:",
  "- Predictable downstream planning and rendering",
  "- Traceable claim references across scenes",
  "- Cleaner visual prompts with less source noise",
  "",
  "What the extractor learns:",
  "- Thesis and key claims",
  "- Concepts and narrative beats",
  "- Visual candidates and quality-risk scores",
].join("\n");

export const SIGNAL_JSON_PREVIEW = `{
  "version": "v1.0",
  "thesis": { "one_liner": "...", "expanded_summary": "..." },
  "key_claims": [{ "claim_id": "c1", "claim_text": "...", "confidence": 0.86 }],
  "concepts": [{ "concept_id": "k1", "label": "...", "importance": 0.79 }],
  "visual_candidates": [
    { "candidate_id": "v1", "recommended_structure": "comparison", "claim_refs": ["c1"] }
  ],
  "narrative_beats": [{ "beat_id": "b1", "role": "hook", "claim_refs": ["c1"] }],
  "signal_quality": { "coverage_score": 0.9, "ambiguity_score": 0.2, "hallucination_risk": 0.1 }
}`;

export const SCRIPT_EXPLAINER_TEXT = [
  "Building an artifact-aware script pack from the locked signal and render profile.",
  "",
  "Workflow architecture in this stage:",
  "- Use the locked signal as the source-grounded truth layer",
  "- Apply artifact policy, audience level, density, and taste controls",
  "- Build scene roles, module structure, claim coverage, and visual directives",
  "- Carry forward proof-linked source media where evidence can anchor later rendering",
  "",
  "Quality guardrails:",
  "- Scene-level repair can patch weak planning before the pack is locked",
  "- Constrained replan can run if mandatory coverage is still missing",
  "- Later generation can still regenerate individual scenes without reopening the whole workflow",
  "",
  "Result:",
  "- An artifact-aware script pack ready for interleaved generation and proof-aware rendering",
].join("\n");

export const SCRIPT_JSON_PREVIEW = `{
  "plan_id": "script-pack-...",
  "planning_mode": "sequential",
  "script_shape": "storyboard_grid",
  "artifact_type": "storyboard_grid",
  "scene_count": 4,
  "scenes": [
    {
      "scene_id": "scene-1",
      "title": "...",
      "narration_focus": "...",
      "visual_prompt": "...",
      "claim_refs": ["c1"],
      "evidence_refs": ["e1"],
      "render_strategy": "hybrid",
      "source_media": [{ "asset_id": "page-2", "usage": "proof_clip" }],
      "acceptance_checks": ["..."]
    }
  ],
  "planner_qa_summary": {
    "mode": "repaired",
    "summary": "Artifact-aware plan repaired and locked with mandatory claim coverage."
  }
}`;

export const STREAM_EXPLAINER_TEXT = [
  "Generation Stream runs from the locked script pack, not directly from raw source.",
  "",
  "What happens now:",
  "- Queue scenes and preserve claim/evidence links",
  "- Stream narration deltas into each scene card",
  "- Attach visuals, proof media, and audio as they become ready",
  "- Run per-scene QA and retry weak outputs before completion",
  "",
  "Workflow architecture:",
  "- SSE events keep the studio live and incremental",
  "- Traceability and proof metadata remain attached throughout",
  "- Final bundle is assembled after the stream stabilizes",
].join("\n");

export const STREAM_JSON_PREVIEW = `event: scene_queue_ready
data: {
  "scenes": [
    { "scene_id": "scene-1", "title": "Hook", "claim_refs": ["c1"] }
  ]
}

event: story_text_delta
data: { "scene_id": "scene-1", "delta": "..." }

event: diagram_ready
data: { "scene_id": "scene-1", "url": "/static/assets/scene-1.png" }

event: qa_status
data: { "scene_id": "scene-1", "status": "PASS" }

event: final_bundle_ready
data: { "claim_traceability": { "claims_referenced": 6, "claims_total": 6 } }`;

export const SIGNAL_TYPEWRITER_DURATION_MS = 45000;
export const SCRIPT_TYPEWRITER_DURATION_MS = 62000;
export const STREAM_TYPEWRITER_DURATION_MS = 26000;
export const PRIMARY_ACTION_CARD_CLASS = "group h-auto w-full rounded-[24px] bg-slate-950 px-5 py-4 text-left text-white shadow-[0_18px_36px_rgba(15,23,42,0.18)] transition-transform hover:-translate-y-0.5 hover:bg-slate-900 disabled:opacity-100 disabled:bg-slate-300 disabled:text-slate-500 disabled:hover:translate-y-0";
export const SECONDARY_ACTION_CARD_CLASS = "h-auto w-full rounded-[24px] border-slate-200 bg-slate-50 px-5 py-4 text-left text-slate-900 shadow-none transition-transform hover:-translate-y-0.5 hover:bg-slate-100 disabled:opacity-100 disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400 disabled:hover:translate-y-0";
export const PRIMARY_ACTION_LABEL_CLASS = "block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300 transition-colors group-disabled:text-slate-600";

export type SelectionTile = {
  value: string;
  title: string;
  description: string;
  icon: LucideIcon;
  baseClassName: string;
  selectedClassName: string;
  iconClassName: string;
  selectedIconClassName: string;
};

export const RENDER_PROFILE_TILE_CLASS = "rounded-[24px] border p-4 text-left transition-all duration-200";
export const RENDER_PROFILE_TILE_HOVER_CLASS = "hover:-translate-y-0.5 hover:shadow-[0_12px_24px_rgba(15,23,42,0.08)]";

export const ARTIFACT_SELECTION_TILES: SelectionTile[] = [
  {
    value: "storyboard_grid",
    title: "Storyboard Grid",
    description: "Multi-scene explainer flow with progression and payoff.",
    icon: LayoutGrid,
    baseClassName: "border-blue-100 bg-blue-50/80 text-blue-950",
    selectedClassName: "border-blue-300 bg-blue-100/95 shadow-[0_18px_40px_rgba(59,130,246,0.16)]",
    iconClassName: "bg-white/80 text-blue-700",
    selectedIconClassName: "bg-blue-700 text-white",
  },
  {
    value: "technical_infographic",
    title: "Technical Infographic",
    description: "Dense factual board for mechanisms, systems, and evidence.",
    icon: Shapes,
    baseClassName: "border-emerald-100 bg-emerald-50/80 text-emerald-950",
    selectedClassName: "border-emerald-300 bg-emerald-100/95 shadow-[0_18px_40px_rgba(16,185,129,0.16)]",
    iconClassName: "bg-white/80 text-emerald-700",
    selectedIconClassName: "bg-emerald-700 text-white",
  },
  {
    value: "process_diagram",
    title: "Process Diagram",
    description: "Step logic, flows, transitions, and causal routing.",
    icon: Workflow,
    baseClassName: "border-teal-100 bg-teal-50/80 text-teal-950",
    selectedClassName: "border-teal-300 bg-teal-100/95 shadow-[0_18px_40px_rgba(20,184,166,0.16)]",
    iconClassName: "bg-white/80 text-teal-700",
    selectedIconClassName: "bg-teal-700 text-white",
  },
  {
    value: "comparison_one_pager",
    title: "One-Pager",
    description: "Single dense poster-style board arranged in modules.",
    icon: Newspaper,
    baseClassName: "border-amber-100 bg-amber-50/80 text-amber-950",
    selectedClassName: "border-amber-300 bg-amber-100/95 shadow-[0_18px_40px_rgba(245,158,11,0.16)]",
    iconClassName: "bg-white/80 text-amber-700",
    selectedIconClassName: "bg-amber-700 text-white",
  },
  {
    value: "slide_thumbnail",
    title: "Slide Thumbnail",
    description: "Single cover frame with one strong hook and clear hierarchy.",
    icon: Presentation,
    baseClassName: "border-fuchsia-100 bg-fuchsia-50/80 text-fuchsia-950",
    selectedClassName: "border-fuchsia-300 bg-fuchsia-100/95 shadow-[0_18px_40px_rgba(217,70,239,0.16)]",
    iconClassName: "bg-white/80 text-fuchsia-700",
    selectedIconClassName: "bg-fuchsia-700 text-white",
  },
];

export const VISUAL_MODE_TILES: SelectionTile[] = [
  {
    value: "diagram",
    title: "Diagram",
    description: "Clean schematic visuals, logic-first composition.",
    icon: ScanLine,
    baseClassName: "border-cyan-100 bg-cyan-50/80 text-cyan-950",
    selectedClassName: "border-cyan-300 bg-cyan-100/95 shadow-[0_14px_28px_rgba(8,145,178,0.14)]",
    iconClassName: "bg-white/80 text-cyan-700",
    selectedIconClassName: "bg-cyan-700 text-white",
  },
  {
    value: "illustration",
    title: "Illustration",
    description: "More expressive framing, shape language, and cinematic metaphor.",
    icon: PenTool,
    baseClassName: "border-indigo-100 bg-indigo-50/80 text-indigo-950",
    selectedClassName: "border-indigo-300 bg-indigo-100/95 shadow-[0_14px_28px_rgba(99,102,241,0.14)]",
    iconClassName: "bg-white/80 text-indigo-700",
    selectedIconClassName: "bg-indigo-700 text-white",
  },
  {
    value: "hybrid",
    title: "Hybrid",
    description: "Blend diagram clarity with illustration polish.",
    icon: GitBranch,
    baseClassName: "border-violet-100 bg-violet-50/80 text-violet-950",
    selectedClassName: "border-violet-300 bg-violet-100/95 shadow-[0_14px_28px_rgba(139,92,246,0.14)]",
    iconClassName: "bg-white/80 text-violet-700",
    selectedIconClassName: "bg-violet-700 text-white",
  },
];

export const AUDIENCE_LEVEL_TILES: SelectionTile[] = [
  {
    value: "beginner",
    title: "Beginner",
    description: "Assume little prior context. Use simpler framing and less compression.",
    icon: ScanLine,
    baseClassName: "border-sky-100 bg-sky-50/80 text-sky-950",
    selectedClassName: "border-sky-300 bg-sky-100/95 shadow-[0_14px_28px_rgba(14,165,233,0.14)]",
    iconClassName: "bg-white/80 text-sky-700",
    selectedIconClassName: "bg-sky-700 text-white",
  },
  {
    value: "intermediate",
    title: "Intermediate",
    description: "Balanced depth for informed viewers who still need structure.",
    icon: LayoutGrid,
    baseClassName: "border-indigo-100 bg-indigo-50/80 text-indigo-950",
    selectedClassName: "border-indigo-300 bg-indigo-100/95 shadow-[0_14px_28px_rgba(99,102,241,0.14)]",
    iconClassName: "bg-white/80 text-indigo-700",
    selectedIconClassName: "bg-indigo-700 text-white",
  },
  {
    value: "expert",
    title: "Expert",
    description: "Allow denser reasoning, stronger compression, and domain fluency.",
    icon: Shapes,
    baseClassName: "border-slate-200 bg-slate-50/90 text-slate-950",
    selectedClassName: "border-slate-400 bg-slate-100/95 shadow-[0_14px_28px_rgba(15,23,42,0.12)]",
    iconClassName: "bg-white/80 text-slate-700",
    selectedIconClassName: "bg-slate-800 text-white",
  },
];

export const DENSITY_TILES: SelectionTile[] = [
  {
    value: "simple",
    title: "Simple",
    description: "Less on-screen complexity, lighter pacing, bigger visual beats.",
    icon: ImageIcon,
    baseClassName: "border-emerald-100 bg-emerald-50/80 text-emerald-950",
    selectedClassName: "border-emerald-300 bg-emerald-100/95 shadow-[0_14px_28px_rgba(16,185,129,0.14)]",
    iconClassName: "bg-white/80 text-emerald-700",
    selectedIconClassName: "bg-emerald-700 text-white",
  },
  {
    value: "standard",
    title: "Standard",
    description: "Balanced information load with clear hierarchy and useful detail.",
    icon: Rows3,
    baseClassName: "border-amber-100 bg-amber-50/80 text-amber-950",
    selectedClassName: "border-amber-300 bg-amber-100/95 shadow-[0_14px_28px_rgba(245,158,11,0.14)]",
    iconClassName: "bg-white/80 text-amber-700",
    selectedIconClassName: "bg-amber-700 text-white",
  },
  {
    value: "detailed",
    title: "Detailed",
    description: "Higher information pressure, more claims, and richer scene modules.",
    icon: GitBranch,
    baseClassName: "border-rose-100 bg-rose-50/80 text-rose-950",
    selectedClassName: "border-rose-300 bg-rose-100/95 shadow-[0_14px_28px_rgba(244,63,94,0.14)]",
    iconClassName: "bg-white/80 text-rose-700",
    selectedIconClassName: "bg-rose-700 text-white",
  },
];

export const TASTE_BAR_TILES: SelectionTile[] = [
  {
    value: "standard",
    title: "Standard",
    description: "Good default polish without pushing art direction aggressively.",
    icon: Presentation,
    baseClassName: "border-slate-200 bg-slate-50/90 text-slate-950",
    selectedClassName: "border-slate-400 bg-slate-100/95 shadow-[0_14px_28px_rgba(15,23,42,0.12)]",
    iconClassName: "bg-white/80 text-slate-700",
    selectedIconClassName: "bg-slate-800 text-white",
  },
  {
    value: "high",
    title: "High",
    description: "Stronger composition, better restraint, and more intentional visual taste.",
    icon: PenTool,
    baseClassName: "border-violet-100 bg-violet-50/80 text-violet-950",
    selectedClassName: "border-violet-300 bg-violet-100/95 shadow-[0_14px_28px_rgba(139,92,246,0.14)]",
    iconClassName: "bg-white/80 text-violet-700",
    selectedIconClassName: "bg-violet-700 text-white",
  },
  {
    value: "very_high",
    title: "Very High",
    description: "Pushes for the strongest editorial taste and least-generic output.",
    icon: Newspaper,
    baseClassName: "border-fuchsia-100 bg-fuchsia-50/80 text-fuchsia-950",
    selectedClassName: "border-fuchsia-300 bg-fuchsia-100/95 shadow-[0_14px_28px_rgba(217,70,239,0.14)]",
    iconClassName: "bg-white/80 text-fuchsia-700",
    selectedIconClassName: "bg-fuchsia-700 text-white",
  },
];

export type ExtractedSignal = {
  thesis?: { one_liner?: string };
  [key: string]: unknown;
};

export type SceneViewModel = {
  id: string;
  title?: string;
  text: string;
  imageUrl?: string;
  audioUrl?: string;
  claim_refs?: string[];
  evidence_refs?: string[];
  render_strategy?: "generated" | "source_media" | "hybrid";
  source_media?: SourceMediaViewModel[];
  expected_source_media_count?: number;
  source_proof_warning?: string;
  status: string;
  qa_status?: "PASS" | "WARN" | "FAIL";
  qa_reasons?: string[];
  qa_score?: number;
  qa_word_count?: number;
  auto_retry_count?: number;
};

export type SourceMediaViewModel = {
  asset_id: string;
  modality: "audio" | "video" | "image" | "pdf_page";
  usage: "background" | "hero" | "proof_clip" | "region_crop" | "callout";
  url: string;
  original_url?: string;
  start_ms?: number;
  end_ms?: number;
  page_index?: number;
  bbox_norm?: number[];
  claim_refs: string[];
  evidence_refs: string[];
  label?: string;
  quote_text?: string;
  visual_context?: string;
  matched_excerpt?: string;
  line_start?: number;
  line_end?: number;
  speaker?: string;
  loop?: boolean;
  muted?: boolean;
};

export type UploadedSourceAsset = {
  asset_id: string;
  modality: "audio" | "image" | "pdf_page" | "video";
  uri: string;
  mime_type?: string;
  title?: string;
  page_index?: number;
  duration_ms?: number;
  metadata?: Record<string, unknown>;
};

export type AdvancedSourceManifestAsset = {
  asset_id: string;
  modality: UploadedSourceAsset["modality"];
  uri: string;
  mime_type?: string;
  title?: string;
  page_index?: number;
  duration_ms?: number;
  metadata?: Record<string, unknown>;
};

export type AdvancedSourceManifest = {
  assets: AdvancedSourceManifestAsset[];
};

export type SceneQueueItem = {
  scene_id: string;
  title?: string;
  claim_refs?: string[];
  evidence_refs?: string[];
  render_strategy?: "generated" | "source_media" | "hybrid";
  source_media_count?: number;
  narration_focus?: string;
};

export type SceneQaPayload = {
  scene_id: string;
  status: "PASS" | "WARN" | "FAIL";
  score: number;
  reasons: string[];
  attempt: number;
  word_count: number;
};

export type PlannerQaSummary = {
  mode: "direct" | "repaired" | "replanned";
  summary: string;
  initial_hard_issue_count: number;
  initial_warning_count: number;
  final_warning_count: number;
  repair_applied: boolean;
  replan_attempted: boolean;
  details: string[];
};

export type ScriptPackPayload = {
  plan_id: string;
  plan_summary: string;
  audience_descriptor: string;
  scene_count: number;
  artifact_type?: string;
  scenes: Array<{
    scene_id: string;
    title: string;
    scene_goal: string;
    narration_focus: string;
    visual_prompt: string;
    claim_refs: string[];
    evidence_refs?: string[];
    render_strategy?: "generated" | "source_media" | "hybrid";
    continuity_refs: string[];
    acceptance_checks: string[];
  }>;
};

export type EvidenceViewerState = {
  sceneId: string;
  sceneTitle?: string;
  claimRef?: string;
  media: SourceMediaViewModel;
};

export type WorkflowSnapshot = {
  workflow_id: string;
  checkpoint_state: Record<string, string>;
  join_gate_ready: boolean;
  ready_for_script_pack: boolean;
  ready_for_stream: boolean;
  source_text_chars?: number;
  artifact_scope?: string[];
  has_signal?: boolean;
  has_render_profile?: boolean;
  render_profile_queued?: boolean;
  has_script_pack?: boolean;
  planner_qa_summary?: PlannerQaSummary | null;
  latest_run_id?: string | null;
  latest_bundle_url?: string | null;
  last_error?: string | null;
  trace?: unknown;
};

export type AdvancedPanel = "source" | "profile" | "signal" | "stream" | "script";
export type ActionDialogStage = "extract" | "profile" | "script" | "stream";
export type RenderProfileStep = "output" | "audience" | "style" | "constraints";
export type ChatRole = "agent" | "user" | "system";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  text: string;
  timestamp: number;
};

export type WorkflowAgentApiTurn = {
  role: "user" | "agent" | "system";
  text: string;
};

export type WorkflowAgentChatResponse = {
  status?: "success" | "error";
  assistant_message?: string;
  selected_action?: string;
  workflow_id?: string | null;
  workflow?: WorkflowSnapshot;
  content_signal?: ExtractedSignal | null;
  script_pack?: ScriptPackPayload | null;
  planner_qa_summary?: PlannerQaSummary | null;
  ui?: {
    active_panel?: AdvancedPanel | null;
    start_stream?: boolean;
  };
  message?: string | null;
};

export const CHECKPOINT_LABELS: Record<string, string> = {
  CP1_SIGNAL_READY: "Signal Ready",
  CP2_ARTIFACTS_LOCKED: "Artifacts Locked",
  CP3_RENDER_LOCKED: "Render Locked",
  CP4_SCRIPT_LOCKED: "Script Pack Ready",
  CP5_STREAM_COMPLETE: "Stream Complete",
  CP6_BUNDLE_FINALIZED: "Final Bundle Ready",
};

export const RENDER_PROFILE_STEPS: RenderProfileStep[] = ["output", "audience", "style", "constraints"];
export const RENDER_PROFILE_STEP_LABELS: Record<RenderProfileStep, string> = {
  output: "1. Output Goal",
  audience: "2. Audience",
  style: "3. Style",
  constraints: "4. Constraints",
};

export const snapshotStatusSummary = (snapshot: WorkflowSnapshot | null): string => {
  if (!snapshot) return "";
  const checkpoints = snapshot.checkpoint_state ?? {};

  if (checkpoints.CP6_BUNDLE_FINALIZED === "passed") {
    return "Final bundle ready.";
  }
  if (checkpoints.CP5_STREAM_COMPLETE === "failed" || checkpoints.CP6_BUNDLE_FINALIZED === "failed") {
    return snapshot.last_error || "Latest stream run failed.";
  }
  if (checkpoints.CP5_STREAM_COMPLETE === "passed") {
    return "Stream complete.";
  }
  if (checkpoints.CP4_SCRIPT_LOCKED === "passed") {
    return "Script pack locked and ready for stream.";
  }
  if (checkpoints.CP3_RENDER_LOCKED === "passed") {
    return "Render profile locked. Confirm signal to generate script pack.";
  }
  if (snapshot.render_profile_queued) {
    return "Artifacts locked. Render profile is queued until signal extraction completes.";
  }
  if (checkpoints.CP2_ARTIFACTS_LOCKED === "passed") {
    return "Artifact scope locked. Apply render profile when ready.";
  }
  if (checkpoints.CP1_SIGNAL_READY === "passed") {
    return "Signal extracted. Apply render profile next.";
  }
  return snapshot.workflow_id ? "Workflow initialized. Signal extraction is pending." : "";
};

export const apiErrorMessage = (payload: unknown, fallback: string): string => {
  if (payload && typeof payload === "object") {
    const candidate = payload as Record<string, unknown>;
    if (typeof candidate.detail === "string" && candidate.detail.trim()) return candidate.detail;
    if (typeof candidate.message === "string" && candidate.message.trim()) return candidate.message;
  }
  return fallback;
};

export type WorkflowRequestError = Error & { statusCode?: number };

export const createApiRequestError = (
  payload: unknown,
  fallback: string,
  statusCode?: number,
): WorkflowRequestError => {
  const error = new Error(apiErrorMessage(payload, fallback)) as WorkflowRequestError;
  error.statusCode = statusCode;
  return error;
};

export const isUnknownWorkflowMessage = (value: unknown): boolean => (
  typeof value === "string" && value.includes("Unknown workflow_id:")
);

export const isUnknownWorkflowError = (error: unknown): boolean => (
  error instanceof Error
  && (
    isUnknownWorkflowMessage(error.message)
    || ((error as WorkflowRequestError).statusCode === 404 && isUnknownWorkflowMessage(error.message))
  )
);

export const EXPIRED_WORKFLOW_MESSAGE = "Saved workflow session expired on the server. Start extraction again.";

export const deriveSceneCount = (scriptPack: ScriptPackPayload | null | undefined): number => {
  if (!scriptPack) return 0;
  if (typeof scriptPack.scene_count === "number" && Number.isFinite(scriptPack.scene_count) && scriptPack.scene_count > 0) {
    return scriptPack.scene_count;
  }
  return Array.isArray(scriptPack.scenes) ? scriptPack.scenes.length : 0;
};

export const asPlannerQaSummary = (value: unknown): PlannerQaSummary | null => {
  if (!value || typeof value !== "object") return null;
  const candidate = value as Record<string, unknown>;
  if (
    candidate.mode !== "direct"
    && candidate.mode !== "repaired"
    && candidate.mode !== "replanned"
  ) {
    return null;
  }
  if (typeof candidate.summary !== "string" || !candidate.summary.trim()) {
    return null;
  }
  return {
    mode: candidate.mode as PlannerQaSummary["mode"],
    summary: candidate.summary,
    initial_hard_issue_count: typeof candidate.initial_hard_issue_count === "number" ? candidate.initial_hard_issue_count : 0,
    initial_warning_count: typeof candidate.initial_warning_count === "number" ? candidate.initial_warning_count : 0,
    final_warning_count: typeof candidate.final_warning_count === "number" ? candidate.final_warning_count : 0,
    repair_applied: Boolean(candidate.repair_applied),
    replan_attempted: Boolean(candidate.replan_attempted),
    details: Array.isArray(candidate.details)
      ? candidate.details.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
      : [],
  };
};

export const asStringArray = (value: unknown): string[] => (
  Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : []
);

const asNumberArray = (value: unknown): number[] => (
  Array.isArray(value) ? value.filter((item): item is number => typeof item === "number" && Number.isFinite(item)) : []
);

export const asSourceMedia = (value: unknown): SourceMediaViewModel | null => {
  if (!value || typeof value !== "object") return null;
  const candidate = value as Record<string, unknown>;
  const modality = candidate.modality;
  const usage = candidate.usage;
  const url = candidate.url;
  if (
    modality !== "audio"
    && modality !== "video"
    && modality !== "image"
    && modality !== "pdf_page"
  ) {
    return null;
  }
  if (
    usage !== "background"
    && usage !== "hero"
    && usage !== "proof_clip"
    && usage !== "region_crop"
    && usage !== "callout"
  ) {
    return null;
  }
  if (typeof url !== "string" || !url.trim()) {
    return null;
  }
  return {
    asset_id: typeof candidate.asset_id === "string" ? candidate.asset_id : "",
    modality,
    usage,
    url,
    original_url: typeof candidate.original_url === "string" ? candidate.original_url : undefined,
    start_ms: typeof candidate.start_ms === "number" ? candidate.start_ms : undefined,
    end_ms: typeof candidate.end_ms === "number" ? candidate.end_ms : undefined,
    page_index: typeof candidate.page_index === "number" ? candidate.page_index : undefined,
    bbox_norm: asNumberArray(candidate.bbox_norm),
    claim_refs: Array.isArray(candidate.claim_refs)
      ? candidate.claim_refs.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
      : [],
    evidence_refs: Array.isArray(candidate.evidence_refs)
      ? candidate.evidence_refs.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
      : [],
    label: typeof candidate.label === "string" ? candidate.label : undefined,
    quote_text: typeof candidate.quote_text === "string" ? candidate.quote_text : undefined,
    visual_context: typeof candidate.visual_context === "string" ? candidate.visual_context : undefined,
    matched_excerpt: typeof candidate.matched_excerpt === "string" ? candidate.matched_excerpt : undefined,
    line_start: typeof candidate.line_start === "number" ? candidate.line_start : undefined,
    line_end: typeof candidate.line_end === "number" ? candidate.line_end : undefined,
    speaker: typeof candidate.speaker === "string" ? candidate.speaker : undefined,
    loop: typeof candidate.loop === "boolean" ? candidate.loop : undefined,
    muted: typeof candidate.muted === "boolean" ? candidate.muted : undefined,
  };
};

export const asSourceMediaList = (value: unknown): SourceMediaViewModel[] => (
  Array.isArray(value)
    ? value.map(asSourceMedia).filter((item): item is SourceMediaViewModel => item !== null)
    : []
);

export const asUploadedSourceAsset = (value: unknown): UploadedSourceAsset | null => {
  if (!value || typeof value !== "object") return null;
  const candidate = value as Record<string, unknown>;
  const modality = candidate.modality;
  const uri = candidate.uri;
  if (modality !== "audio" && modality !== "image" && modality !== "pdf_page" && modality !== "video") {
    return null;
  }
  if (typeof uri !== "string" || !uri.trim()) {
    return null;
  }
  return {
    asset_id: typeof candidate.asset_id === "string" ? candidate.asset_id : "",
    modality,
    uri,
    mime_type: typeof candidate.mime_type === "string" ? candidate.mime_type : undefined,
    title: typeof candidate.title === "string" ? candidate.title : undefined,
    page_index: typeof candidate.page_index === "number" ? candidate.page_index : undefined,
    duration_ms: typeof candidate.duration_ms === "number" ? candidate.duration_ms : undefined,
    metadata: candidate.metadata && typeof candidate.metadata === "object"
      ? candidate.metadata as Record<string, unknown>
      : undefined,
  };
};

export const readVideoDurationMs = async (file: File): Promise<number | undefined> => {
  if (typeof window === "undefined" || !file.type.startsWith("video/")) {
    return undefined;
  }

  return new Promise((resolve) => {
    const video = document.createElement("video");
    const objectUrl = URL.createObjectURL(file);
    const finalize = (value?: number) => {
      URL.revokeObjectURL(objectUrl);
      resolve(value);
    };

    video.preload = "metadata";
    video.onloadedmetadata = () => {
      const duration = Number.isFinite(video.duration) && video.duration >= 0
        ? Math.round(video.duration * 1000)
        : undefined;
      finalize(duration);
    };
    video.onerror = () => finalize(undefined);
    video.src = objectUrl;
  });
};

export const actionInvalidatesGeneratedOutputs = (action?: string): boolean => (
  action === "extract_signal"
  || action === "apply_render_profile"
  || action === "confirm_signal"
  || action === "generate_script_pack"
);

export const formatMilliseconds = (value?: number): string => {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return "";
  const totalSeconds = Math.floor(value / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
};

export const mapArtifactScope = (selectedArtifactType: string): string[] => {
  if (selectedArtifactType === "slide_thumbnail") {
    return ["thumbnail", "social_caption"];
  }
  if (selectedArtifactType === "storyboard_grid") {
    return ["storyboard", "voiceover", "social_caption"];
  }
  if (selectedArtifactType === "comparison_one_pager") {
    return ["story_cards", "social_caption"];
  }
  return ["story_cards", "voiceover"];
};

export const buildAdvancedSourceManifest = (
  uploadedSourceAssets: UploadedSourceAsset[],
): AdvancedSourceManifest | undefined => (
  uploadedSourceAssets.length > 0
    ? {
      assets: uploadedSourceAssets.map((asset) => ({
        asset_id: asset.asset_id,
        modality: asset.modality,
        uri: asset.uri,
        mime_type: asset.mime_type,
        title: asset.title,
        page_index: asset.page_index,
        duration_ms: asset.duration_ms,
        metadata: asset.metadata,
      })),
    }
    : undefined
);
