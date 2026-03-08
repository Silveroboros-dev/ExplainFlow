"use client";

import Image from 'next/image';
import React, { useState } from 'react';
import SceneCard from '@/components/SceneCard';
import FinalBundle from '@/components/FinalBundle';
import AgentActivityPanel, { AgentNote, AgentNoteType } from '@/components/AgentActivityPanel';
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  type LucideIcon,
  GitBranch,
  ImageIcon,
  LayoutGrid,
  Loader2,
  Newspaper,
  PenTool,
  Presentation,
  Rows3,
  ScanLine,
  Shapes,
  Upload,
  Workflow,
} from "lucide-react";
import { Toaster, toast } from "sonner";

const SIGNAL_EXPLAINER_TEXT = [
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

const SIGNAL_JSON_PREVIEW = `{
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

const SCRIPT_EXPLAINER_TEXT = [
  "Building script pack from your locked signal and render profile.",
  "",
  "What happens now:",
  "- Map claims to scenes",
  "- Build narration focus + visual directives",
  "- Add continuity hints and acceptance checks",
  "",
  "Result:",
  "- Scene-by-scene script ready for interleaved generation",
].join("\n");

const SCRIPT_JSON_PREVIEW = `{
  "plan_id": "script-pack-...",
  "scene_count": 4,
  "scenes": [
    {
      "scene_id": "scene-1",
      "title": "...",
      "narration_focus": "...",
      "visual_prompt": "...",
      "claim_refs": ["c1"]
    }
  ]
}`;

const SIGNAL_TYPEWRITER_DURATION_MS = 45000;
const SCRIPT_TYPEWRITER_DURATION_MS = 20000;
const PRIMARY_ACTION_CARD_CLASS = "h-auto w-full rounded-[24px] bg-slate-950 px-5 py-4 text-left text-white shadow-[0_18px_36px_rgba(15,23,42,0.18)] transition-transform hover:-translate-y-0.5 hover:bg-slate-900 disabled:opacity-100 disabled:bg-slate-300 disabled:text-slate-500 disabled:hover:translate-y-0";
const SECONDARY_ACTION_CARD_CLASS = "h-auto w-full rounded-[24px] border-slate-200 bg-slate-50 px-5 py-4 text-left text-slate-900 shadow-none transition-transform hover:-translate-y-0.5 hover:bg-slate-100 disabled:opacity-100 disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400 disabled:hover:translate-y-0";

type SelectionTile = {
  value: string;
  title: string;
  description: string;
  icon: LucideIcon;
  baseClassName: string;
  selectedClassName: string;
  iconClassName: string;
  selectedIconClassName: string;
};

const ARTIFACT_SELECTION_TILES: SelectionTile[] = [
  {
    value: 'storyboard_grid',
    title: 'Storyboard Grid',
    description: 'Multi-scene explainer flow with progression and payoff.',
    icon: LayoutGrid,
    baseClassName: 'border-blue-100 bg-blue-50/80 text-blue-950',
    selectedClassName: 'border-blue-300 bg-blue-100/95 shadow-[0_18px_40px_rgba(59,130,246,0.16)]',
    iconClassName: 'bg-white/80 text-blue-700',
    selectedIconClassName: 'bg-blue-700 text-white',
  },
  {
    value: 'technical_infographic',
    title: 'Technical Infographic',
    description: 'Dense factual board for mechanisms, systems, and evidence.',
    icon: Shapes,
    baseClassName: 'border-emerald-100 bg-emerald-50/80 text-emerald-950',
    selectedClassName: 'border-emerald-300 bg-emerald-100/95 shadow-[0_18px_40px_rgba(16,185,129,0.16)]',
    iconClassName: 'bg-white/80 text-emerald-700',
    selectedIconClassName: 'bg-emerald-700 text-white',
  },
  {
    value: 'process_diagram',
    title: 'Process Diagram',
    description: 'Step logic, flows, transitions, and causal routing.',
    icon: Workflow,
    baseClassName: 'border-teal-100 bg-teal-50/80 text-teal-950',
    selectedClassName: 'border-teal-300 bg-teal-100/95 shadow-[0_18px_40px_rgba(20,184,166,0.16)]',
    iconClassName: 'bg-white/80 text-teal-700',
    selectedIconClassName: 'bg-teal-700 text-white',
  },
  {
    value: 'comparison_one_pager',
    title: 'One-Pager',
    description: 'Single dense poster-style board arranged in modules.',
    icon: Newspaper,
    baseClassName: 'border-amber-100 bg-amber-50/80 text-amber-950',
    selectedClassName: 'border-amber-300 bg-amber-100/95 shadow-[0_18px_40px_rgba(245,158,11,0.16)]',
    iconClassName: 'bg-white/80 text-amber-700',
    selectedIconClassName: 'bg-amber-700 text-white',
  },
  {
    value: 'slide_thumbnail',
    title: 'Slide Thumbnail',
    description: 'Single cover frame with one strong hook and clear hierarchy.',
    icon: Presentation,
    baseClassName: 'border-fuchsia-100 bg-fuchsia-50/80 text-fuchsia-950',
    selectedClassName: 'border-fuchsia-300 bg-fuchsia-100/95 shadow-[0_18px_40px_rgba(217,70,239,0.16)]',
    iconClassName: 'bg-white/80 text-fuchsia-700',
    selectedIconClassName: 'bg-fuchsia-700 text-white',
  },
];

const VISUAL_MODE_TILES: SelectionTile[] = [
  {
    value: 'diagram',
    title: 'Diagram',
    description: 'Clean schematic visuals, logic-first composition.',
    icon: ScanLine,
    baseClassName: 'border-cyan-100 bg-cyan-50/80 text-cyan-950',
    selectedClassName: 'border-cyan-300 bg-cyan-100/95 shadow-[0_14px_28px_rgba(8,145,178,0.14)]',
    iconClassName: 'bg-white/80 text-cyan-700',
    selectedIconClassName: 'bg-cyan-700 text-white',
  },
  {
    value: 'illustration',
    title: 'Illustration',
    description: 'More expressive framing, shape language, and cinematic metaphor.',
    icon: PenTool,
    baseClassName: 'border-indigo-100 bg-indigo-50/80 text-indigo-950',
    selectedClassName: 'border-indigo-300 bg-indigo-100/95 shadow-[0_14px_28px_rgba(99,102,241,0.14)]',
    iconClassName: 'bg-white/80 text-indigo-700',
    selectedIconClassName: 'bg-indigo-700 text-white',
  },
  {
    value: 'hybrid',
    title: 'Hybrid',
    description: 'Blend diagram clarity with illustration polish.',
    icon: GitBranch,
    baseClassName: 'border-violet-100 bg-violet-50/80 text-violet-950',
    selectedClassName: 'border-violet-300 bg-violet-100/95 shadow-[0_14px_28px_rgba(139,92,246,0.14)]',
    iconClassName: 'bg-white/80 text-violet-700',
    selectedIconClassName: 'bg-violet-700 text-white',
  },
];

const AUDIENCE_LEVEL_TILES: SelectionTile[] = [
  {
    value: 'beginner',
    title: 'Beginner',
    description: 'Assume little prior context. Use simpler framing and less compression.',
    icon: ScanLine,
    baseClassName: 'border-sky-100 bg-sky-50/80 text-sky-950',
    selectedClassName: 'border-sky-300 bg-sky-100/95 shadow-[0_14px_28px_rgba(14,165,233,0.14)]',
    iconClassName: 'bg-white/80 text-sky-700',
    selectedIconClassName: 'bg-sky-700 text-white',
  },
  {
    value: 'intermediate',
    title: 'Intermediate',
    description: 'Balanced depth for informed viewers who still need structure.',
    icon: LayoutGrid,
    baseClassName: 'border-indigo-100 bg-indigo-50/80 text-indigo-950',
    selectedClassName: 'border-indigo-300 bg-indigo-100/95 shadow-[0_14px_28px_rgba(99,102,241,0.14)]',
    iconClassName: 'bg-white/80 text-indigo-700',
    selectedIconClassName: 'bg-indigo-700 text-white',
  },
  {
    value: 'expert',
    title: 'Expert',
    description: 'Allow denser reasoning, stronger compression, and domain fluency.',
    icon: Shapes,
    baseClassName: 'border-slate-200 bg-slate-50/90 text-slate-950',
    selectedClassName: 'border-slate-400 bg-slate-100/95 shadow-[0_14px_28px_rgba(15,23,42,0.12)]',
    iconClassName: 'bg-white/80 text-slate-700',
    selectedIconClassName: 'bg-slate-800 text-white',
  },
];

const DENSITY_TILES: SelectionTile[] = [
  {
    value: 'simple',
    title: 'Simple',
    description: 'Less on-screen complexity, lighter pacing, bigger visual beats.',
    icon: ImageIcon,
    baseClassName: 'border-emerald-100 bg-emerald-50/80 text-emerald-950',
    selectedClassName: 'border-emerald-300 bg-emerald-100/95 shadow-[0_14px_28px_rgba(16,185,129,0.14)]',
    iconClassName: 'bg-white/80 text-emerald-700',
    selectedIconClassName: 'bg-emerald-700 text-white',
  },
  {
    value: 'standard',
    title: 'Standard',
    description: 'Balanced information load with clear hierarchy and useful detail.',
    icon: Rows3,
    baseClassName: 'border-amber-100 bg-amber-50/80 text-amber-950',
    selectedClassName: 'border-amber-300 bg-amber-100/95 shadow-[0_14px_28px_rgba(245,158,11,0.14)]',
    iconClassName: 'bg-white/80 text-amber-700',
    selectedIconClassName: 'bg-amber-700 text-white',
  },
  {
    value: 'detailed',
    title: 'Detailed',
    description: 'Higher information pressure, more claims, and richer scene modules.',
    icon: GitBranch,
    baseClassName: 'border-rose-100 bg-rose-50/80 text-rose-950',
    selectedClassName: 'border-rose-300 bg-rose-100/95 shadow-[0_14px_28px_rgba(244,63,94,0.14)]',
    iconClassName: 'bg-white/80 text-rose-700',
    selectedIconClassName: 'bg-rose-700 text-white',
  },
];

const TASTE_BAR_TILES: SelectionTile[] = [
  {
    value: 'standard',
    title: 'Standard',
    description: 'Good default polish without pushing art direction aggressively.',
    icon: Presentation,
    baseClassName: 'border-slate-200 bg-slate-50/90 text-slate-950',
    selectedClassName: 'border-slate-400 bg-slate-100/95 shadow-[0_14px_28px_rgba(15,23,42,0.12)]',
    iconClassName: 'bg-white/80 text-slate-700',
    selectedIconClassName: 'bg-slate-800 text-white',
  },
  {
    value: 'high',
    title: 'High',
    description: 'Stronger composition, better restraint, and more intentional visual taste.',
    icon: PenTool,
    baseClassName: 'border-violet-100 bg-violet-50/80 text-violet-950',
    selectedClassName: 'border-violet-300 bg-violet-100/95 shadow-[0_14px_28px_rgba(139,92,246,0.14)]',
    iconClassName: 'bg-white/80 text-violet-700',
    selectedIconClassName: 'bg-violet-700 text-white',
  },
  {
    value: 'very_high',
    title: 'Very High',
    description: 'Pushes for the strongest editorial taste and least-generic output.',
    icon: Newspaper,
    baseClassName: 'border-fuchsia-100 bg-fuchsia-50/80 text-fuchsia-950',
    selectedClassName: 'border-fuchsia-300 bg-fuchsia-100/95 shadow-[0_14px_28px_rgba(217,70,239,0.14)]',
    iconClassName: 'bg-white/80 text-fuchsia-700',
    selectedIconClassName: 'bg-fuchsia-700 text-white',
  },
];

type ExtractedSignal = {
  thesis?: { one_liner?: string };
  [key: string]: unknown;
};

type SceneViewModel = {
  id: string;
  title?: string;
  text: string;
  imageUrl?: string;
  audioUrl?: string;
  claim_refs?: string[];
  evidence_refs?: string[];
  render_strategy?: 'generated' | 'source_media' | 'hybrid';
  source_media?: SourceMediaViewModel[];
  status: string;
  qa_status?: 'PASS' | 'WARN' | 'FAIL';
  qa_reasons?: string[];
  qa_score?: number;
  qa_word_count?: number;
  auto_retry_count?: number;
};

type SourceMediaViewModel = {
  asset_id: string;
  modality: 'audio' | 'video' | 'image' | 'pdf_page';
  usage: 'background' | 'hero' | 'proof_clip' | 'region_crop' | 'callout';
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

type UploadedSourceAsset = {
  asset_id: string;
  modality: 'audio' | 'image' | 'pdf_page';
  uri: string;
  mime_type?: string;
  title?: string;
  page_index?: number;
  metadata?: Record<string, unknown>;
};

type SceneQueueItem = {
  scene_id: string;
  title?: string;
  claim_refs?: string[];
  evidence_refs?: string[];
  render_strategy?: 'generated' | 'source_media' | 'hybrid';
  source_media_count?: number;
  narration_focus?: string;
};

type SceneQaPayload = {
  scene_id: string;
  status: 'PASS' | 'WARN' | 'FAIL';
  score: number;
  reasons: string[];
  attempt: number;
  word_count: number;
};

type PlannerQaSummary = {
  mode: 'direct' | 'repaired' | 'replanned';
  summary: string;
  initial_hard_issue_count: number;
  initial_warning_count: number;
  final_warning_count: number;
  repair_applied: boolean;
  replan_attempted: boolean;
  details: string[];
};

type ScriptPackPayload = {
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
    render_strategy?: 'generated' | 'source_media' | 'hybrid';
    continuity_refs: string[];
    acceptance_checks: string[];
  }>;
};

type EvidenceViewerState = {
  sceneId: string;
  sceneTitle?: string;
  claimRef?: string;
  media: SourceMediaViewModel;
};

type WorkflowSnapshot = {
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

type AdvancedPanel = 'source' | 'profile' | 'signal' | 'stream' | 'script';
type ActionDialogStage = 'extract' | 'profile' | 'script' | 'stream';
type RenderProfileStep = 'output' | 'audience' | 'style' | 'constraints';
type ChatRole = 'agent' | 'user' | 'system';

type ChatMessage = {
  id: string;
  role: ChatRole;
  text: string;
  timestamp: number;
};

type WorkflowAgentApiTurn = {
  role: 'user' | 'agent' | 'system';
  text: string;
};

type WorkflowAgentChatResponse = {
  status?: 'success' | 'error';
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

const CHECKPOINT_LABELS: Record<string, string> = {
  CP1_SIGNAL_READY: "Signal Ready",
  CP2_ARTIFACTS_LOCKED: "Artifacts Locked",
  CP3_RENDER_LOCKED: "Render Locked",
  CP4_SCRIPT_LOCKED: "Script Pack Ready",
  CP5_STREAM_COMPLETE: "Stream Complete",
  CP6_BUNDLE_FINALIZED: "Final Bundle Ready",
};

const RENDER_PROFILE_STEPS: RenderProfileStep[] = ['output', 'audience', 'style', 'constraints'];
const RENDER_PROFILE_STEP_LABELS: Record<RenderProfileStep, string> = {
  output: '1. Output Goal',
  audience: '2. Audience',
  style: '3. Style',
  constraints: '4. Constraints',
};

const snapshotStatusSummary = (snapshot: WorkflowSnapshot | null): string => {
  if (!snapshot) return '';
  const checkpoints = snapshot.checkpoint_state ?? {};

  if (checkpoints.CP6_BUNDLE_FINALIZED === 'passed') {
    return 'Final bundle ready.';
  }
  if (checkpoints.CP5_STREAM_COMPLETE === 'failed' || checkpoints.CP6_BUNDLE_FINALIZED === 'failed') {
    return snapshot.last_error || 'Latest stream run failed.';
  }
  if (checkpoints.CP5_STREAM_COMPLETE === 'passed') {
    return 'Stream complete.';
  }
  if (checkpoints.CP4_SCRIPT_LOCKED === 'passed') {
    return 'Script pack locked and ready for stream.';
  }
  if (checkpoints.CP3_RENDER_LOCKED === 'passed') {
    return 'Render profile locked. Confirm signal to generate script pack.';
  }
  if (snapshot.render_profile_queued) {
    return 'Artifacts locked. Render profile is queued until signal extraction completes.';
  }
  if (checkpoints.CP2_ARTIFACTS_LOCKED === 'passed') {
    return 'Artifact scope locked. Apply render profile when ready.';
  }
  if (checkpoints.CP1_SIGNAL_READY === 'passed') {
    return 'Signal extracted. Apply render profile next.';
  }
  return snapshot.workflow_id ? 'Workflow initialized. Signal extraction is pending.' : '';
};

const asPlannerQaSummary = (value: unknown): PlannerQaSummary | null => {
  if (!value || typeof value !== 'object') return null;
  const candidate = value as Record<string, unknown>;
  if (
    candidate.mode !== 'direct'
    && candidate.mode !== 'repaired'
    && candidate.mode !== 'replanned'
  ) {
    return null;
  }
  if (typeof candidate.summary !== 'string' || !candidate.summary.trim()) {
    return null;
  }
  return {
    mode: candidate.mode as PlannerQaSummary['mode'],
    summary: candidate.summary,
    initial_hard_issue_count: typeof candidate.initial_hard_issue_count === 'number' ? candidate.initial_hard_issue_count : 0,
    initial_warning_count: typeof candidate.initial_warning_count === 'number' ? candidate.initial_warning_count : 0,
    final_warning_count: typeof candidate.final_warning_count === 'number' ? candidate.final_warning_count : 0,
    repair_applied: Boolean(candidate.repair_applied),
    replan_attempted: Boolean(candidate.replan_attempted),
    details: Array.isArray(candidate.details)
      ? candidate.details.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
      : [],
  };
};

const asNumberArray = (value: unknown): number[] => (
  Array.isArray(value) ? value.filter((item): item is number => typeof item === 'number' && Number.isFinite(item)) : []
);

const asSourceMedia = (value: unknown): SourceMediaViewModel | null => {
  if (!value || typeof value !== 'object') return null;
  const candidate = value as Record<string, unknown>;
  const modality = candidate.modality;
  const usage = candidate.usage;
  const url = candidate.url;
  if (
    modality !== 'audio'
    && modality !== 'video'
    && modality !== 'image'
    && modality !== 'pdf_page'
  ) {
    return null;
  }
  if (
    usage !== 'background'
    && usage !== 'hero'
    && usage !== 'proof_clip'
    && usage !== 'region_crop'
    && usage !== 'callout'
  ) {
    return null;
  }
  if (typeof url !== 'string' || !url.trim()) {
    return null;
  }
  return {
    asset_id: typeof candidate.asset_id === 'string' ? candidate.asset_id : '',
    modality,
    usage,
    url,
    original_url: typeof candidate.original_url === 'string' ? candidate.original_url : undefined,
    start_ms: typeof candidate.start_ms === 'number' ? candidate.start_ms : undefined,
    end_ms: typeof candidate.end_ms === 'number' ? candidate.end_ms : undefined,
    page_index: typeof candidate.page_index === 'number' ? candidate.page_index : undefined,
    bbox_norm: asNumberArray(candidate.bbox_norm),
    claim_refs: Array.isArray(candidate.claim_refs)
      ? candidate.claim_refs.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
      : [],
    evidence_refs: Array.isArray(candidate.evidence_refs)
      ? candidate.evidence_refs.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
      : [],
    label: typeof candidate.label === 'string' ? candidate.label : undefined,
    quote_text: typeof candidate.quote_text === 'string' ? candidate.quote_text : undefined,
    visual_context: typeof candidate.visual_context === 'string' ? candidate.visual_context : undefined,
    matched_excerpt: typeof candidate.matched_excerpt === 'string' ? candidate.matched_excerpt : undefined,
    line_start: typeof candidate.line_start === 'number' ? candidate.line_start : undefined,
    line_end: typeof candidate.line_end === 'number' ? candidate.line_end : undefined,
    speaker: typeof candidate.speaker === 'string' ? candidate.speaker : undefined,
    loop: typeof candidate.loop === 'boolean' ? candidate.loop : undefined,
    muted: typeof candidate.muted === 'boolean' ? candidate.muted : undefined,
  };
};

const asSourceMediaList = (value: unknown): SourceMediaViewModel[] => (
  Array.isArray(value)
    ? value.map(asSourceMedia).filter((item): item is SourceMediaViewModel => item !== null)
    : []
);

const asUploadedSourceAsset = (value: unknown): UploadedSourceAsset | null => {
  if (!value || typeof value !== 'object') return null;
  const candidate = value as Record<string, unknown>;
  const modality = candidate.modality;
  const uri = candidate.uri;
  if (modality !== 'audio' && modality !== 'image' && modality !== 'pdf_page') {
    return null;
  }
  if (typeof uri !== 'string' || !uri.trim()) {
    return null;
  }
  return {
    asset_id: typeof candidate.asset_id === 'string' ? candidate.asset_id : '',
    modality,
    uri,
    mime_type: typeof candidate.mime_type === 'string' ? candidate.mime_type : undefined,
    title: typeof candidate.title === 'string' ? candidate.title : undefined,
    page_index: typeof candidate.page_index === 'number' ? candidate.page_index : undefined,
    metadata: candidate.metadata && typeof candidate.metadata === 'object'
      ? candidate.metadata as Record<string, unknown>
      : undefined,
  };
};

const actionInvalidatesGeneratedOutputs = (action?: string): boolean => (
  action === 'extract_signal'
  || action === 'apply_render_profile'
  || action === 'confirm_signal'
  || action === 'generate_script_pack'
);

const formatMilliseconds = (value?: number): string => {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return '';
  const totalSeconds = Math.floor(value / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
};

const withMediaFragment = (url: string, startMs?: number, endMs?: number): string => {
  if (!url || typeof startMs !== 'number') return url;
  const startSeconds = Math.max(0, Math.floor(startMs / 1000));
  const endSeconds = typeof endMs === 'number' ? Math.max(startSeconds + 1, Math.floor(endMs / 1000)) : undefined;
  return endSeconds ? `${url}#t=${startSeconds},${endSeconds}` : `${url}#t=${startSeconds}`;
};

const withPdfPageFragment = (url: string, pageIndex?: number): string => {
  if (!url || typeof pageIndex !== 'number' || !Number.isFinite(pageIndex)) return url;
  const pageNumber = Math.max(1, Math.trunc(pageIndex));
  return `${url}#page=${pageNumber}`;
};

export default function AdvancedStudio() {
  const [sourceDoc, setSourceDoc] = useState('');
  const [uploadedSourceAssets, setUploadedSourceAssets] = useState<UploadedSourceAsset[]>([]);
  const [visualMode, setVisualMode] = useState('illustration');
  const [artifactType, setArtifactType] = useState('storyboard_grid');
  const [fidelityPreference, setFidelityPreference] = useState<'preview' | 'high'>('preview');
  const [density, setDensity] = useState('standard');
  const [audienceLevel, setAudienceLevel] = useState('intermediate');
  const [audiencePersona, setAudiencePersona] = useState('Product manager');
  const [domainContext, setDomainContext] = useState('');
  const [tasteBar, setTasteBar] = useState('high');
  const [mustIncludeText, setMustIncludeText] = useState('');
  const [mustAvoidText, setMustAvoidText] = useState('');
  const [activePanel, setActivePanel] = useState<AdvancedPanel>('source');
  const [profileStep, setProfileStep] = useState<RenderProfileStep>('output');
  const [actionDialogStage, setActionDialogStage] = useState<ActionDialogStage | null>(null);
  const [showAmendHelp, setShowAmendHelp] = useState(false);
  
  const [isExtracting, setIsExtracting] = useState(false);
  const [isUploadingAssets, setIsUploadingAssets] = useState(false);
  const [extractedSignal, setExtractedSignal] = useState<ExtractedSignal | null>(null);
  const [extractProgress, setExtractProgress] = useState(0);
  const [signalStage, setSignalStage] = useState<'idle' | 'sending' | 'structuring' | 'ready' | 'error'>('idle');
  const [error, setError] = useState('');
  const [generationError, setGenerationError] = useState('');
  const [generationStatus, setGenerationStatus] = useState('');
  const [typedExplainer, setTypedExplainer] = useState('');
  const [typedPreview, setTypedPreview] = useState('');
  const [typedScriptExplainer, setTypedScriptExplainer] = useState('');
  const [typedScriptPreview, setTypedScriptPreview] = useState('');
  const [scriptPresentationMode, setScriptPresentationMode] = useState<'review' | 'auto'>('auto');

  const [isGenerating, setIsGenerating] = useState(false);
  const [isGeneratingScriptPack, setIsGeneratingScriptPack] = useState(false);
  const [isApplyingProfile, setIsApplyingProfile] = useState(false);
  const [scenes, setScenes] = useState<Record<string, SceneViewModel>>({});
  const [scriptPack, setScriptPack] = useState<ScriptPackPayload | null>(null);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [workflowSnapshot, setWorkflowSnapshot] = useState<WorkflowSnapshot | null>(null);
  const [evidenceViewer, setEvidenceViewer] = useState<EvidenceViewerState | null>(null);
  const [agentNotes, setAgentNotes] = useState<AgentNote[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: 'chat-welcome',
      role: 'agent',
      text: 'Hi, I will help you onboard ExplainFlow and get maximum value from your request. ExplainFlow turns source material into a structured signal, script pack, and interleaved text-image-audio output. Shall we start?',
      timestamp: Date.now(),
    },
  ]);
  const chatScrollAnchorRef = React.useRef<HTMLDivElement | null>(null);
  
  // Ref for the typewriter effect to track full text without causing infinite re-renders
  const fullTextBuffer = React.useRef<Record<string, string>>({});
  const sourceAssetsInputRef = React.useRef<HTMLInputElement | null>(null);

  const asStringArray = (value: unknown): string[] => (
    Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
  );

  const pushChatMessage = (role: ChatRole, text: string) => {
    const message: ChatMessage = {
      id: `chat-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      role,
      text,
      timestamp: Date.now(),
    };
    setChatMessages((prev) => {
      const withoutSameRole = prev.filter((item) => item.role !== role);
      const next = [...withoutSameRole, message].sort((a, b) => a.timestamp - b.timestamp);
      return next.slice(-2);
    });
  };

  const pushAgentNote = (type: AgentNoteType, stage: string, message: string) => {
    const note: AgentNote = {
      id: `note-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      type,
      stage,
      message,
      timestamp: Date.now(),
    };
    setAgentNotes((prev) => [note, ...prev].slice(0, 80));
    if (type === 'checkpoint') {
      toast.success(`${stage}`, { description: message, duration: 2600 });
    } else if (type === 'error') {
      toast.error(`${stage}`, { description: message, duration: 3400 });
    }
  };

  const pushPlannerQaNote = (summary: PlannerQaSummary | null | undefined) => {
    if (!summary?.summary) return;
    const extras: string[] = [];
    if (summary.initial_hard_issue_count > 0) {
      extras.push(`${summary.initial_hard_issue_count} mandatory issue${summary.initial_hard_issue_count === 1 ? '' : 's'} found initially`);
    }
    if (summary.final_warning_count > 0) {
      extras.push(`${summary.final_warning_count} warning${summary.final_warning_count === 1 ? '' : 's'} remain`);
    }
    const detail = extras.length > 0 ? `${summary.summary} ${extras.join('. ')}.` : summary.summary;
    pushAgentNote('qa', 'Planner QA', detail);
  };

  React.useEffect(() => {
    chatScrollAnchorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [chatMessages.length, isExtracting, isApplyingProfile, isGeneratingScriptPack, isGenerating]);

  const mapArtifactScope = (selectedArtifactType: string): string[] => {
    if (selectedArtifactType === 'slide_thumbnail') {
      return ['thumbnail', 'social_caption'];
    }
    if (selectedArtifactType === 'storyboard_grid') {
      return ['storyboard', 'voiceover', 'social_caption'];
    }
    if (selectedArtifactType === 'comparison_one_pager') {
      return ['story_cards', 'social_caption'];
    }
    return ['story_cards', 'voiceover'];
  };

  const updateWorkflowSnapshot = (snapshot: unknown) => {
    if (!snapshot || typeof snapshot !== 'object') return;
    const candidate = snapshot as WorkflowSnapshot;
    if (!candidate.workflow_id || typeof candidate.workflow_id !== 'string') return;
    setWorkflowSnapshot(candidate);
    setWorkflowId(candidate.workflow_id);
  };

  const buildSourceManifestPayload = () => (
    uploadedSourceAssets.length > 0
      ? {
        assets: uploadedSourceAssets.map((asset) => ({
          asset_id: asset.asset_id,
          modality: asset.modality,
          uri: asset.uri,
          mime_type: asset.mime_type,
          title: asset.title,
          page_index: asset.page_index,
          metadata: asset.metadata,
        })),
      }
      : undefined
  );

  const hasSourceInput = sourceDoc.trim().length > 0 || uploadedSourceAssets.length > 0;
  const clearGeneratedOutputs = () => {
    setScriptPack(null);
    setScenes({});
    setEvidenceViewer(null);
    fullTextBuffer.current = {};
  };

  const removeUploadedSourceAsset = (assetId: string) => {
    setUploadedSourceAssets((prev) => prev.filter((asset) => asset.asset_id !== assetId));
  };

  const handleSourceAssetUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files ? Array.from(event.target.files) : [];
    event.target.value = '';
    if (files.length === 0) {
      return;
    }

    setIsUploadingAssets(true);
    setError('');

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const formData = new FormData();
      files.forEach((file) => formData.append('files', file));

      const response = await fetch(`${apiUrl}/api/source-assets/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (!response.ok || data?.status !== 'success' || !Array.isArray(data?.assets)) {
        const detail = typeof data?.detail === 'string'
          ? data.detail
          : (typeof data?.message === 'string' ? data.message : 'Source upload failed.');
        setError(detail);
        toast.error(detail);
        return;
      }

      const newAssets = data.assets
        .map(asUploadedSourceAsset)
        .filter((asset: UploadedSourceAsset | null): asset is UploadedSourceAsset => asset !== null);

      setUploadedSourceAssets((prev) => {
        const next = [...prev];
        newAssets.forEach((asset: UploadedSourceAsset) => {
          if (!next.some((existing) => existing.asset_id === asset.asset_id)) {
            next.push(asset);
          }
        });
        return next;
      });
      toast.success(`Uploaded ${newAssets.length} source asset${newAssets.length === 1 ? '' : 's'}.`);
    } catch (err) {
      console.error('Source asset upload error:', err);
      const detail = 'Unable to upload source assets.';
      setError(detail);
      toast.error(detail);
    } finally {
      setIsUploadingAssets(false);
    }
  };

  const updateSceneMetadata = (
    sceneId: string,
    patch: Partial<SceneViewModel>
  ) => {
    setScenes(prev => {
      const existing = prev[sceneId] ?? { id: sceneId, text: '', status: 'queued' };
      return {
        ...prev,
        [sceneId]: {
          ...existing,
          ...patch,
        }
      };
    });
  };

  const appendSourceMedia = (sceneId: string, media: SourceMediaViewModel) => {
    setScenes(prev => {
      const existing = prev[sceneId] ?? { id: sceneId, text: '', status: 'queued' };
      const currentMedia = Array.isArray(existing.source_media) ? existing.source_media : [];
      const existingIndex = currentMedia.findIndex(item => (
        item.asset_id === media.asset_id
        && item.url === media.url
        && item.start_ms === media.start_ms
        && item.end_ms === media.end_ms
        && item.page_index === media.page_index
      ));
      const nextMedia = [...currentMedia];
      if (existingIndex >= 0) {
        const prior = nextMedia[existingIndex];
        nextMedia[existingIndex] = {
          ...prior,
          ...media,
          claim_refs: Array.from(new Set([...(prior.claim_refs ?? []), ...(media.claim_refs ?? [])])),
          evidence_refs: Array.from(new Set([...(prior.evidence_refs ?? []), ...(media.evidence_refs ?? [])])),
        };
      } else {
        nextMedia.push(media);
      }
      return {
        ...prev,
        [sceneId]: {
          ...existing,
          source_media: nextMedia,
          evidence_refs: Array.from(new Set([...(existing.evidence_refs ?? []), ...media.evidence_refs])),
        },
      };
    });
  };

  const selectEvidenceMedia = (scene: SceneViewModel | undefined, claimRef?: string): SourceMediaViewModel | null => {
    if (!scene?.source_media?.length) return null;
    const scoreMedia = (media: SourceMediaViewModel): number => {
      let score = 0;
      if (media.modality === 'pdf_page') score += 40;
      if (media.modality === 'image') score += 30;
      if (media.usage === 'region_crop') score += 20;
      if (typeof media.page_index === 'number') score += 15;
      if (typeof media.start_ms === 'number') score += 5;
      if (media.modality === 'audio') score -= 5;
      return score;
    };

    const candidates = claimRef
      ? scene.source_media.filter((item) => item.claim_refs.includes(claimRef))
      : scene.source_media;

    if (candidates.length === 0) {
      return scene.source_media[0] ?? null;
    }

    return [...candidates].sort((left, right) => scoreMedia(right) - scoreMedia(left))[0] ?? null;
  };

  const openEvidenceViewer = (sceneId: string, claimRef?: string) => {
    const scene = scenes[sceneId];
    const media = selectEvidenceMedia(scene, claimRef);
    if (!media) {
      toast.error('No linked source proof is available for this claim yet.');
      return;
    }
    setEvidenceViewer({
      sceneId,
      sceneTitle: scene?.title,
      claimRef,
      media,
    });
  };

  const fetchWorkflowSnapshot = async (workflowIdValue: string): Promise<void> => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const response = await fetch(`${apiUrl}/api/workflow/${workflowIdValue}`);
    const snapshot = await response.json() as WorkflowSnapshot;
    updateWorkflowSnapshot(snapshot);
    const streamFailed = snapshot.checkpoint_state?.CP5_STREAM_COMPLETE === 'failed'
      || snapshot.checkpoint_state?.CP6_BUNDLE_FINALIZED === 'failed';
    if (streamFailed && typeof snapshot.last_error === 'string' && snapshot.last_error.trim()) {
      setGenerationError(snapshot.last_error);
    } else if (
      snapshot.checkpoint_state?.CP5_STREAM_COMPLETE === 'passed'
      || snapshot.checkpoint_state?.CP6_BUNDLE_FINALIZED === 'passed'
    ) {
      setGenerationError('');
    }
  };

  // Typewriter effect loop
  React.useEffect(() => {
    let animationFrameId: number;
    
    const updateTypewriter = () => {
      setScenes(currentScenes => {
        let hasChanges = false;
        const nextScenes = { ...currentScenes };
        
        Object.keys(fullTextBuffer.current).forEach(sceneId => {
          const currentScene = nextScenes[sceneId];
          if (!currentScene) return;
          
          const targetText = fullTextBuffer.current[sceneId];
          const currentTextLength = currentScene.text.length;
          
          if (currentTextLength < targetText.length) {
            // Add characters based on how much is left to type
            const charsToAdd = Math.max(1, Math.ceil((targetText.length - currentTextLength) / 15));
            nextScenes[sceneId] = {
              ...currentScene,
              text: targetText.substring(0, currentTextLength + charsToAdd)
            };
            hasChanges = true;
          }
        });
        
        return hasChanges ? nextScenes : currentScenes;
      });
      animationFrameId = requestAnimationFrame(updateTypewriter);
    };
    
    animationFrameId = requestAnimationFrame(updateTypewriter);
    return () => cancelAnimationFrame(animationFrameId);
  }, []);

  React.useEffect(() => {
    if (!isExtracting) {
      return;
    }

    const stageTimer = window.setTimeout(() => {
      setSignalStage(prev => (prev === 'sending' ? 'structuring' : prev));
    }, 1200);

    const progressSteps = [14, 22, 34, 47, 58, 67, 76, 84, 90, 94];
    let stepIndex = 0;
    const progressTimer = window.setInterval(() => {
      setExtractProgress(prev => {
        if (prev >= 94) return prev;
        const nextValue = progressSteps[Math.min(stepIndex, progressSteps.length - 1)];
        stepIndex += 1;
        return Math.max(prev, nextValue);
      });
    }, 900);

    return () => {
      window.clearTimeout(stageTimer);
      window.clearInterval(progressTimer);
    };
  }, [isExtracting]);

  React.useEffect(() => {
    if (!isExtracting) {
      setTypedExplainer('');
      setTypedPreview('');
      return;
    }

    setTypedExplainer('');
    setTypedPreview('');

    const targetDurationMs = SIGNAL_TYPEWRITER_DURATION_MS;
    const tickMs = 60;
    const totalChars = SIGNAL_EXPLAINER_TEXT.length + SIGNAL_JSON_PREVIEW.length;
    const totalTicks = Math.max(1, Math.ceil(targetDurationMs / tickMs));
    const charsPerTick = totalChars / totalTicks;
    let cursor = 0;

    const intervalId = window.setInterval(() => {
      cursor = Math.min(totalChars, cursor + charsPerTick);
      const shownChars = Math.floor(cursor);
      const explainerChars = Math.min(shownChars, SIGNAL_EXPLAINER_TEXT.length);
      const previewChars = Math.max(0, shownChars - SIGNAL_EXPLAINER_TEXT.length);

      setTypedExplainer(SIGNAL_EXPLAINER_TEXT.slice(0, explainerChars));
      setTypedPreview(SIGNAL_JSON_PREVIEW.slice(0, previewChars));

      if (cursor >= totalChars) {
        window.clearInterval(intervalId);
      }
    }, tickMs);

    return () => window.clearInterval(intervalId);
  }, [isExtracting]);

  React.useEffect(() => {
    const scriptTypingEnabled = isGeneratingScriptPack;
    if (!scriptTypingEnabled) {
      setTypedScriptExplainer('');
      setTypedScriptPreview('');
      return;
    }

    setTypedScriptExplainer('');
    setTypedScriptPreview('');

    const targetDurationMs = SCRIPT_TYPEWRITER_DURATION_MS;
    const tickMs = 60;
    const totalChars = SCRIPT_EXPLAINER_TEXT.length + SCRIPT_JSON_PREVIEW.length;
    const totalTicks = Math.max(1, Math.ceil(targetDurationMs / tickMs));
    const charsPerTick = totalChars / totalTicks;
    let cursor = 0;

    const intervalId = window.setInterval(() => {
      cursor = Math.min(totalChars, cursor + charsPerTick);
      const shownChars = Math.floor(cursor);
      const explainerChars = Math.min(shownChars, SCRIPT_EXPLAINER_TEXT.length);
      const previewChars = Math.max(0, shownChars - SCRIPT_EXPLAINER_TEXT.length);
      setTypedScriptExplainer(SCRIPT_EXPLAINER_TEXT.slice(0, explainerChars));
      setTypedScriptPreview(SCRIPT_JSON_PREVIEW.slice(0, previewChars));

      if (cursor >= totalChars) {
        window.clearInterval(intervalId);
      }
    }, tickMs);

    return () => window.clearInterval(intervalId);
  }, [isGeneratingScriptPack, scriptPresentationMode]);

  const openActionDialog = (stage: ActionDialogStage) => {
    setActionDialogStage(stage);
    setShowAmendHelp(false);
  };

  const closeActionDialog = () => {
    setActionDialogStage(null);
    setShowAmendHelp(false);
  };

  const runExtraction = async () => {
    if (!hasSourceInput) {
      return false;
    }

    setAgentNotes([]);
    pushAgentNote('info', 'Extraction', 'Signal extraction started from source material.');
    setIsExtracting(true);
    setSignalStage('sending');
    setExtractProgress(8);
    setError('');
    setGenerationError('');
    setExtractedSignal(null);
    setGenerationStatus('');
    clearGeneratedOutputs();
    setFidelityPreference('preview');
    setWorkflowId(null);
    setWorkflowSnapshot(null);
    
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const sourceManifest = buildSourceManifestPayload();
      const startResponse = await fetch(`${apiUrl}/api/workflow/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_text: sourceDoc,
          ...(sourceManifest ? { source_manifest: sourceManifest } : {}),
        })
      });
      const startData: {
        workflow_id?: string;
        workflow?: WorkflowSnapshot;
        status?: string;
      } = await startResponse.json();
      if (!startResponse.ok || startData.status !== 'success' || !startData.workflow_id) {
        setError('Unable to initialize workflow.');
        pushAgentNote('error', 'Extraction', 'Workflow initialization failed.');
        setSignalStage('error');
        setExtractProgress(0);
        return false;
      }
      setWorkflowId(startData.workflow_id);
      if (startData.workflow) {
        updateWorkflowSnapshot(startData.workflow);
      }

      const extractResponse = await fetch(`${apiUrl}/api/workflow/${startData.workflow_id}/extract-signal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_text: sourceDoc,
          ...(sourceManifest ? { source_manifest: sourceManifest } : {}),
        })
      });

      const data: {
        workflow_id?: string;
        workflow?: WorkflowSnapshot;
        status?: string;
        content_signal?: ExtractedSignal;
        message?: string;
      } = await extractResponse.json();
      if (data.workflow) {
        updateWorkflowSnapshot(data.workflow);
      }
      if (data.status === 'success') {
        setExtractedSignal(data.content_signal ?? null);
        setSignalStage('ready');
        setExtractProgress(100);
        setGenerationStatus(
          data.workflow
            ? snapshotStatusSummary(data.workflow)
            : 'Signal extracted. Next: lock artifact scope and render profile.'
        );
        pushAgentNote('checkpoint', 'Extraction', 'Signal extracted and schema validation passed.');
        return true;
      } else {
        setError(data.message || 'Extraction failed');
        pushAgentNote('error', 'Extraction', data.message || 'Signal extraction failed.');
        setSignalStage('error');
        setExtractProgress(0);
        return false;
      }
    } catch (err) {
      console.error(err);
      setError('Network error during extraction');
      pushAgentNote('error', 'Extraction', 'Network error during signal extraction.');
      setSignalStage('error');
      setExtractProgress(0);
      return false;
    } finally {
      setIsExtracting(false);
    }
  };

  const handleExtract = (e: React.FormEvent) => {
    e.preventDefault();
    if (!hasSourceInput) {
      return;
    }
    setActivePanel('profile');
    if (!extractedSignal) {
      void runExtraction();
      return;
    }
    pushAgentNote('info', 'Extraction', 'Re-extraction requested. Waiting for confirmation.');
    openActionDialog('extract');
  };

  const handleApplyRenderProfile = () => {
    setActivePanel('signal');
    pushAgentNote('info', 'Render Profile', 'Render profile ready. Waiting for lock confirmation.');
    openActionDialog('profile');
  };

  const handleProfileStepBack = () => {
    if (!canMoveProfileBack) return;
    const previousStep = RENDER_PROFILE_STEPS[profileStepIndex - 1];
    if (previousStep) {
      setProfileStep(previousStep);
    }
  };

  const handleProfileStepNext = () => {
    if (!canMoveProfileNext) return;
    const nextStep = RENDER_PROFILE_STEPS[profileStepIndex + 1];
    if (nextStep) {
      setProfileStep(nextStep);
    }
  };

  const handleConfirmSignal = async () => {
    if (!extractedSignal) {
      setGenerationStatus('Extract signal first.');
      pushAgentNote('error', 'Signal', 'Signal confirmation blocked: extract signal first.');
      return;
    }
    if (!workflowSnapshot?.ready_for_script_pack) {
      setGenerationStatus('Workflow gate not ready. Lock artifact scope and render profile first.');
      pushAgentNote('error', 'Signal', 'Signal confirmation blocked by join gate (artifacts/render not locked).');
      return;
    }
    setActivePanel('script');
    setGenerationStatus('Signal confirmed. Generating script pack...');
    pushAgentNote('info', 'Signal', 'Signal confirmed. Script pack generation started.');
    await handleGenerateScriptPack(scriptPresentationMode);
  };

  const buildRenderProfilePayload = (mode: 'preview' | 'high' = fidelityPreference) => ({
    profile_id: `rp_custom_${Date.now()}`,
    goal: "teach",
    audience: {
      level: audienceLevel,
      persona: audiencePersona,
      domain_context: domainContext || undefined,
      taste_bar: tasteBar,
      must_include: mustIncludeText
        ? mustIncludeText.split(',').map(item => item.trim()).filter(Boolean).slice(0, 8)
        : undefined,
      must_avoid: mustAvoidText
        ? mustAvoidText.split(',').map(item => item.trim()).filter(Boolean).slice(0, 8)
        : undefined
    },
    visual_mode: visualMode,
    artifact_type: artifactType,
    low_key_preview: true,
    style: {
      descriptors: [visualMode === "illustration" ? "cinematic" : "clean", "modern"]
    },
    fidelity: mode === 'high' ? 'high' : 'medium',
    density: density,
    palette: {
      mode: "auto"
    },
    output_controls: {
      scene_count: 4,
      target_duration_sec: 60,
      aspect_ratio: "16:9"
    },
    voiceover: {
      enabled: true,
      voice_style: "neutral",
      pace_wpm: 150
    }
  });

  const applyProfileToWorkflow = async (
    mode: 'preview' | 'high' = fidelityPreference,
  ): Promise<WorkflowSnapshot | null> => {
    if (!workflowId) {
      setGenerationStatus('Start with extraction first so a workflow can be created.');
      pushAgentNote('error', 'Render Profile', 'Cannot lock render profile before workflow start.');
      return null;
    }

    setIsApplyingProfile(true);
    setGenerationError('');
    setGenerationStatus('Locking artifact scope and render profile...');
    pushAgentNote('info', 'Render Profile', 'Locking artifact scope and render profile for this run.');

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const artifactScope = mapArtifactScope(artifactType);

      const artifactRes = await fetch(`${apiUrl}/api/workflow/${workflowId}/lock-artifacts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ artifact_scope: artifactScope })
      });
      const artifactData = await artifactRes.json();
      if (!artifactRes.ok || artifactData?.status !== 'success') {
        const detail = typeof artifactData?.detail === 'string'
          ? artifactData.detail
          : (typeof artifactData?.message === 'string' ? artifactData.message : 'Artifact scope lock failed.');
        setGenerationError(detail);
        pushAgentNote('error', 'Render Profile', detail);
        setGenerationStatus('');
        return null;
      }
      if (artifactData.workflow) {
        updateWorkflowSnapshot(artifactData.workflow);
      }

      const renderProfile = buildRenderProfilePayload(mode);
      const renderRes = await fetch(`${apiUrl}/api/workflow/${workflowId}/lock-render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ render_profile: renderProfile })
      });
      const renderData = await renderRes.json();
      if (!renderRes.ok || renderData?.status !== 'success') {
        const detail = typeof renderData?.detail === 'string'
          ? renderData.detail
          : (typeof renderData?.message === 'string' ? renderData.message : 'Render profile lock failed.');
        setGenerationError(detail);
        pushAgentNote('error', 'Render Profile', detail);
        setGenerationStatus('');
        return null;
      }

      const updatedWorkflow = renderData.workflow as WorkflowSnapshot | undefined;
      if (updatedWorkflow) {
        updateWorkflowSnapshot(updatedWorkflow);
      }
      const cp3Status = typeof renderData?.workflow?.checkpoint_state?.CP3_RENDER_LOCKED === 'string'
        ? renderData.workflow.checkpoint_state.CP3_RENDER_LOCKED
        : '';
      if (cp3Status === 'passed') {
        setGenerationStatus(
          mode === 'high'
            ? 'High-fidelity profile locked. Current bundle images can now be upscaled without changing the script.'
            : 'Render profile locked. Continue to signal confirmation and script planning.'
        );
        pushAgentNote('checkpoint', 'Render Profile', 'Render profile locked and ready.');
      } else {
        setGenerationStatus('Artifacts locked. Render profile queued and will auto-lock when signal extraction completes.');
        pushAgentNote('info', 'Render Profile', 'Artifacts locked. Render lock is queued until signal is ready.');
      }
      return updatedWorkflow ?? null;
    } catch (err) {
      console.error('Apply profile error:', err);
      setGenerationError('Unable to lock render profile in workflow.');
      pushAgentNote('error', 'Render Profile', 'Unable to lock render profile in workflow.');
      setGenerationStatus('');
      return null;
    } finally {
      setIsApplyingProfile(false);
    }
  };

  const handleGenerateScriptPack = async (mode: 'review' | 'auto' = 'review') => {
    if (!workflowId) {
      setGenerationStatus('Run extraction first to initialize workflow.');
      pushAgentNote('error', 'Script Pack', 'Cannot generate script pack before extraction workflow starts.');
      return;
    }
    if (!workflowSnapshot?.ready_for_script_pack) {
      setGenerationStatus('Workflow gate not ready. Lock artifacts and render profile first.');
      pushAgentNote('error', 'Script Pack', 'Script pack generation blocked by workflow gate.');
      return;
    }

    setIsGeneratingScriptPack(true);
    setScriptPresentationMode(mode);
    setGenerationError('');
    setGenerationStatus(
      mode === 'review'
        ? 'Preparing script pack for your confirmation...'
        : 'Preparing script pack for immediate use...'
    );
    pushAgentNote(
      'info',
      'Script Pack',
      mode === 'review'
        ? 'Generating script pack for review.'
        : 'Generating script pack for immediate streaming.'
    );
    setScriptPack(null);
    if (mode === 'review') {
      setActivePanel('script');
    }

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/workflow/${workflowId}/generate-script-pack`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await response.json();
      if (data?.workflow) {
        updateWorkflowSnapshot(data.workflow);
      }
      if (data?.status === 'success' && data?.script_pack) {
        const approvedScriptPack = data.script_pack as ScriptPackPayload;
        setScriptPack(approvedScriptPack);
        pushPlannerQaNote(asPlannerQaSummary(data.planner_qa_summary));
        if (mode === 'review') {
          setGenerationStatus('Script pack is ready. Review and amend before starting stream generation.');
          setActivePanel('script');
          pushAgentNote('checkpoint', 'Script Pack', 'Script pack ready for review.');
        } else {
          setGenerationStatus('Script pack approved. Starting generation stream automatically...');
          setActivePanel('stream');
          pushAgentNote('checkpoint', 'Script Pack', 'Script pack approved. Starting stream automatically.');
          setIsGeneratingScriptPack(false);
          await handleGenerateStream(approvedScriptPack, {
            gateReadyOverride: true,
            preparationMessage: 'Script pack approved. Preparing generation pipeline...',
            startNote: 'Script pack approved. Generation stream started automatically.',
          });
          return;
        }
      } else {
        const detail = typeof data?.detail === 'string'
          ? data.detail
          : (typeof data?.message === 'string' ? data.message : 'Script pack generation failed.');
        setGenerationError(detail);
        pushAgentNote('error', 'Script Pack', detail);
        setGenerationStatus('');
      }
    } catch (err) {
      console.error("Script pack error:", err);
      setGenerationError('Unable to generate script pack.');
      pushAgentNote('error', 'Script Pack', 'Unable to generate script pack.');
      setGenerationStatus('');
    } finally {
      setIsGeneratingScriptPack(false);
    }
  };

  const handleEnableHighFidelity = async () => {
    if (!workflowId || isGenerating || isGeneratingScriptPack || isApplyingProfile) {
      return;
    }

    const currentScenes = Object.values(scenes);
    const sceneImages = currentScenes.filter((scene) => typeof scene.imageUrl === 'string' && scene.imageUrl.trim().length > 0);
    if (!scriptPack || currentScenes.length === 0 || sceneImages.length === 0) {
      setGenerationStatus('Generate a preview bundle first so the current scene images can be upscaled.');
      pushAgentNote('error', 'Final Bundle', 'High-fidelity upgrade needs an existing preview bundle with scene images.');
      return;
    }

    setFidelityPreference('high');
    setGenerationError('');
    setGenerationStatus('Switching to high-fidelity mode...');
    pushAgentNote('info', 'Final Bundle', 'Switching to high-fidelity mode.');
    const updatedSnapshot = await applyProfileToWorkflow('high');
    if (!updatedSnapshot) {
      return;
    }
    if (updatedSnapshot.checkpoint_state?.CP3_RENDER_LOCKED !== 'passed') {
      setGenerationStatus('High-fidelity settings are queued. Finish signal extraction, then regenerate the bundle.');
      return;
    }
    if (!updatedSnapshot.ready_for_stream || !scriptPack) {
      setGenerationStatus('High-fidelity mode is active. Generate or restore the locked script pack before rerunning the bundle.');
      return;
    }

    setIsGenerating(true);
    setGenerationStatus('Upscaling the current bundle images to 2x high-fidelity assets...');
    pushAgentNote('info', 'Final Bundle', 'High-fidelity upscale started using the current scene images.');

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/final-bundle/upscale`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scale_factor: 2,
          scenes: currentScenes.map((scene) => ({
            scene_id: scene.id,
            image_url: scene.imageUrl,
          })),
        }),
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok || data?.status !== 'success') {
        const detail = typeof data?.detail === 'string'
          ? data.detail
          : (typeof data?.message === 'string' ? data.message : 'High-fidelity upscale failed.');
        setGenerationError(detail);
        setGenerationStatus('');
        pushAgentNote('error', 'Final Bundle', detail);
        return;
      }

      const replacements = new Map<string, string>();
      if (Array.isArray(data?.scenes)) {
        data.scenes.forEach((scene: unknown) => {
          if (!scene || typeof scene !== 'object') return;
          const candidate = scene as Record<string, unknown>;
          if (typeof candidate.scene_id === 'string' && typeof candidate.image_url === 'string' && candidate.image_url.trim()) {
            replacements.set(candidate.scene_id, candidate.image_url);
          }
        });
      }

      if (replacements.size > 0) {
        setScenes((prev) => {
          const next = { ...prev };
          replacements.forEach((imageUrl, sceneId) => {
            const existing = next[sceneId];
            if (!existing) return;
            next[sceneId] = {
              ...existing,
              imageUrl,
              status: existing.status || 'done',
            };
          });
          return next;
        });
      }

      setGenerationStatus('High-fidelity bundle ready. Existing text and audio were preserved while scene images were upscaled 2x.');
      pushAgentNote('checkpoint', 'Final Bundle', 'High-fidelity bundle ready with 2x upscaled scene images.');
    } catch (err) {
      console.error('High-fidelity upscale error:', err);
      setGenerationError('Unable to upscale the current bundle.');
      setGenerationStatus('');
      pushAgentNote('error', 'Final Bundle', 'Unable to upscale the current bundle.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleGenerateStream = async (
    scriptPackOverride?: ScriptPackPayload | null,
    options: {
      preserveExistingScenes?: boolean;
      preparationMessage?: string;
      startNote?: string;
      gateReadyOverride?: boolean;
    } = {},
  ) => {
    if (!workflowId) {
      setGenerationStatus('Run extraction first to initialize workflow.');
      pushAgentNote('error', 'Generation', 'Cannot start generation before extraction workflow starts.');
      return;
    }
    const {
      preserveExistingScenes = false,
      preparationMessage = 'Preparing generation pipeline...',
      startNote = 'Interleaved generation stream started.',
      gateReadyOverride = false,
    } = options;
    if (!gateReadyOverride && !workflowSnapshot?.ready_for_stream) {
      setGenerationStatus('Workflow gate not ready for stream. Confirm script pack first.');
      pushAgentNote('error', 'Generation', 'Generation blocked by workflow gate (script pack not locked).');
      return;
    }

    setIsGenerating(true);
    setGenerationError('');
    setGenerationStatus(preparationMessage);
    if (!preserveExistingScenes) {
      setScenes({});
    }
    fullTextBuffer.current = {};
    pushAgentNote('info', 'Generation', startNote);
    
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/workflow/${workflowId}/generate-stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script_pack: scriptPackOverride ?? scriptPack ?? undefined
        })
      });

      if (!response.body) throw new Error("ReadableStream not supported in this browser.");

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || "";

        let currentEvent = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.substring(7).trim();
          } else if (line.startsWith("data: ")) {
            const dataStr = line.substring(6).trim();
            if (!dataStr) continue;
            
            try {
              const parsedData: unknown = JSON.parse(dataStr);
              if (!parsedData || typeof parsedData !== 'object') continue;
              const data = parsedData as Record<string, unknown>;
              
              if (currentEvent === 'scene_queue_ready') {
                const initialScenes: Record<string, SceneViewModel> = {};
                const queueScenes = Array.isArray(data.scenes) ? data.scenes : [];
                queueScenes.forEach(scene => {
                  if (!scene || typeof scene !== 'object') return;
                  const sceneItem = scene as SceneQueueItem;
                  if (!sceneItem.scene_id) return;
                  initialScenes[sceneItem.scene_id] = {
                    id: sceneItem.scene_id,
                    title: sceneItem.title,
                    claim_refs: sceneItem.claim_refs,
                    evidence_refs: sceneItem.evidence_refs,
                    render_strategy: sceneItem.render_strategy,
                    text: '',
                    status: 'queued'
                  };
                  fullTextBuffer.current[sceneItem.scene_id] = sceneItem.narration_focus || '';
                });
                setScenes(initialScenes);
                pushAgentNote(
                  'info',
                  'Planning',
                  `Scene queue ready with ${Object.keys(initialScenes).length} scenes.`
                );
              } else if (currentEvent === 'script_pack_ready') {
                const rawPack = data.script_pack;
                if (rawPack && typeof rawPack === 'object') {
                  setScriptPack(rawPack as ScriptPackPayload);
                  pushAgentNote('checkpoint', 'Script Pack', 'Script pack received in stream context.');
                }
                pushPlannerQaNote(asPlannerQaSummary(data.planner_qa_summary));
              } else if (currentEvent === 'scene_start') {
                const sceneId = typeof data.scene_id === 'string' ? data.scene_id : '';
                if (!sceneId) continue;
                fullTextBuffer.current[sceneId] = '';
                if (typeof data.title === 'string' && data.title.trim()) {
                  setGenerationStatus(`Generating ${data.title}...`);
                  pushAgentNote('info', sceneId, `Generating ${data.title}.`);
                }
                const patch: Partial<SceneViewModel> = {
                  claim_refs: asStringArray(data.claim_refs),
                  evidence_refs: asStringArray(data.evidence_refs),
                  render_strategy: data.render_strategy === 'generated' || data.render_strategy === 'source_media' || data.render_strategy === 'hybrid'
                    ? data.render_strategy
                    : undefined,
                  source_media: asSourceMediaList(data.source_media),
                  status: 'generating',
                };
                if (typeof data.title === 'string' && data.title.trim()) {
                  patch.title = data.title;
                }
                updateSceneMetadata(sceneId, patch);
              } else if (currentEvent === 'story_text_delta') {
                const sceneId = typeof data.scene_id === 'string' ? data.scene_id : '';
                if (!sceneId) continue;
                const delta = typeof data.delta === 'string' ? data.delta : '';
                fullTextBuffer.current[sceneId] = (fullTextBuffer.current[sceneId] || '') + delta;
              } else if (currentEvent === 'diagram_ready') {
                const sceneId = typeof data.scene_id === 'string' ? data.scene_id : '';
                if (!sceneId) continue;
                updateSceneMetadata(sceneId, { imageUrl: typeof data.url === 'string' ? data.url : undefined });
              } else if (currentEvent === 'audio_ready') {
                const sceneId = typeof data.scene_id === 'string' ? data.scene_id : '';
                if (!sceneId) continue;
                updateSceneMetadata(sceneId, { audioUrl: typeof data.url === 'string' ? data.url : undefined });
              } else if (currentEvent === 'source_media_ready') {
                const sceneId = typeof data.scene_id === 'string' ? data.scene_id : '';
                if (!sceneId) continue;
                const sourceMedia = asSourceMedia(data);
                if (!sourceMedia) continue;
                appendSourceMedia(sceneId, sourceMedia);
              } else if (currentEvent === 'qa_status') {
                const qa = data as unknown as SceneQaPayload;
                if (!qa.scene_id) continue;
                updateSceneMetadata(qa.scene_id, {
                  qa_status: qa.status,
                  qa_reasons: Array.isArray(qa.reasons) ? qa.reasons : [],
                  qa_score: typeof qa.score === 'number' ? qa.score : undefined,
                  qa_word_count: typeof qa.word_count === 'number' ? qa.word_count : undefined,
                  status: qa.status === 'FAIL' ? 'qa-failed' : 'generating',
                });
                const qaReason = Array.isArray(qa.reasons) && qa.reasons.length > 0 ? qa.reasons[0] : 'Quality check updated.';
                pushAgentNote('qa', qa.scene_id, `QA ${qa.status}: ${qaReason}`);
              } else if (currentEvent === 'qa_retry') {
                const sceneId = typeof data.scene_id === 'string' ? data.scene_id : '';
                if (!sceneId) continue;
                setScenes(prev => {
                  const existing = prev[sceneId] ?? { id: sceneId, text: '', status: 'queued' };
                  return {
                    ...prev,
                    [sceneId]: {
                      ...existing,
                      status: 'retrying',
                      auto_retry_count: (existing.auto_retry_count ?? 0) + 1,
                    },
                  };
                });
                pushAgentNote('qa', sceneId, 'QA requested a retry for this scene.');
              } else if (currentEvent === 'scene_retry_reset') {
                const sceneId = typeof data.scene_id === 'string' ? data.scene_id : '';
                if (!sceneId) continue;
                fullTextBuffer.current[sceneId] = '';
                updateSceneMetadata(sceneId, {
                  text: '',
                  imageUrl: undefined,
                  audioUrl: undefined,
                  status: 'generating',
                });
              } else if (currentEvent === 'scene_done') {
                const sceneId = typeof data.scene_id === 'string' ? data.scene_id : '';
                if (!sceneId) continue;
                const qaStatus = typeof data.qa_status === 'string' ? data.qa_status : '';
                const autoRetries = typeof data.auto_retries === 'number' ? data.auto_retries : undefined;
                updateSceneMetadata(sceneId, {
                  status: qaStatus === 'FAIL' ? 'qa-failed' : 'ready',
                  auto_retry_count: autoRetries,
                });
                if (qaStatus) {
                  pushAgentNote('info', sceneId, `Scene done with QA ${qaStatus}.`);
                }
              } else if (currentEvent === 'status') {
                if (typeof data.message === 'string' && data.message.trim()) {
                  setGenerationStatus(data.message);
                  pushAgentNote('info', 'Agent', data.message);
                }
              } else if (currentEvent === 'checkpoint') {
                const checkpoint = typeof data.checkpoint === 'string' ? data.checkpoint : '';
                const status = typeof data.status === 'string' ? data.status : '';
                if (checkpoint && status) {
                  setGenerationStatus(`${checkpoint}: ${status}`);
                  const checkpointLabel = CHECKPOINT_LABELS[checkpoint] ?? checkpoint;
                  const normalizedStatus = status.toUpperCase();
                  pushAgentNote(
                    normalizedStatus === 'FAILED' ? 'error' : 'checkpoint',
                    'Checkpoint',
                    `${checkpointLabel}: ${normalizedStatus}`
                  );
                }
              } else if (currentEvent === 'final_bundle_ready') {
                setGenerationStatus('');
                setIsGenerating(false);
                const traceabilityRaw = data.claim_traceability;
                if (traceabilityRaw && typeof traceabilityRaw === 'object') {
                  const traceability = traceabilityRaw as {
                    claims_total?: number;
                    claims_referenced?: number;
                    evidence_total?: number;
                    evidence_referenced?: number;
                  };
                  if (typeof traceability.claims_total === 'number' && typeof traceability.claims_referenced === 'number') {
                    pushAgentNote(
                      'trace',
                      'Traceability',
                      typeof traceability.evidence_total === 'number' && typeof traceability.evidence_referenced === 'number'
                        ? `Claims covered: ${traceability.claims_referenced}/${traceability.claims_total}. Evidence linked: ${traceability.evidence_referenced}/${traceability.evidence_total}.`
                        : `Claims covered: ${traceability.claims_referenced}/${traceability.claims_total}.`
                    );
                  }
                }
                pushAgentNote('checkpoint', 'Generation', 'Final bundle ready.');
                if (workflowId) {
                  try {
                    await fetchWorkflowSnapshot(workflowId);
                  } catch {
                    // Snapshot refresh is best-effort.
                  }
                }
              } else if (currentEvent === 'error') {
                setGenerationError(typeof data.error === 'string' ? data.error : 'Generation failed.');
                pushAgentNote('error', 'Generation', typeof data.error === 'string' ? data.error : 'Generation failed.');
                setGenerationStatus('');
                setIsGenerating(false);
                if (workflowId) {
                  try {
                    await fetchWorkflowSnapshot(workflowId);
                  } catch {
                    // Snapshot refresh is best-effort.
                  }
                }
              }
            } catch (e) {
              console.error("Error parsing SSE data:", e);
            }
          }
        }
      }
    } catch (err) {
      console.error("Stream error:", err);
      setGenerationError('Unable to connect to generation stream.');
      pushAgentNote('error', 'Generation', 'Unable to connect to generation stream.');
      setGenerationStatus('');
    } finally {
      if (workflowId) {
        try {
          await fetchWorkflowSnapshot(workflowId);
        } catch {
          // Snapshot refresh is best-effort.
        }
      }
      setIsGenerating(false);
    }
  };

  const handleScriptPackAction = () => {
    if (!workflowSnapshot?.ready_for_script_pack || isGeneratingScriptPack || isGenerating) return;
    void handleGenerateScriptPack('review');
  };

  const handleGenerateStreamAction = () => {
    if (!workflowSnapshot?.ready_for_stream || !scriptPack || isGenerating) return;
    if (scriptPresentationMode === 'auto') {
      void handleGenerateStream();
      return;
    }
    openActionDialog('stream');
  };

  const handleDialogContinue = async () => {
    const stage = actionDialogStage;
    if (!stage) return;

    if (stage === 'extract') {
      closeActionDialog();
      await runExtraction();
      return;
    }
    if (stage === 'profile') {
      closeActionDialog();
      await applyProfileToWorkflow();
      return;
    }
    if (stage === 'script' || stage === 'stream') {
      closeActionDialog();
      if (stage === 'script') {
        await handleGenerateScriptPack();
      } else {
        await handleGenerateStream();
      }
    }
  };

  const handleDialogGoBack = () => {
    if (actionDialogStage === 'script') {
      setActivePanel('profile');
      setGenerationStatus('Adjust render profile and regenerate script pack.');
    }
    closeActionDialog();
  };

  const handleDialogRelaunch = async () => {
    if (actionDialogStage === 'script') {
      closeActionDialog();
      await handleGenerateScriptPack();
    }
  };

  const handleChatCommand = async (rawInput: string) => {
    const message = rawInput.trim();
    if (!message) return;

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const conversation: WorkflowAgentApiTurn[] = chatMessages.slice(-10).map((turn) => ({
      role: turn.role === 'agent' ? 'agent' : turn.role === 'system' ? 'system' : 'user',
      text: turn.text,
    }));

    try {
      setGenerationError('');
      const response = await fetch(`${apiUrl}/api/workflow/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          context: {
            workflow_id: workflowId,
            active_panel: activePanel,
            source_text: sourceDoc,
            source_manifest: buildSourceManifestPayload(),
            render_profile: buildRenderProfilePayload(),
            artifact_scope: mapArtifactScope(artifactType),
            script_presentation_mode: scriptPresentationMode,
          },
          conversation,
        }),
      });
      const data = await response.json() as WorkflowAgentChatResponse;
      const returnedWorkflow = data.workflow && typeof data.workflow === 'object'
        ? data.workflow as WorkflowSnapshot
        : null;
      const returnedWorkflowId = typeof data.workflow_id === 'string'
        ? data.workflow_id
        : returnedWorkflow?.workflow_id ?? null;
      const workflowChanged = Boolean(returnedWorkflowId && returnedWorkflowId !== workflowId);

      if (typeof data.workflow_id === 'string') {
        setWorkflowId(data.workflow_id);
      }
      if (workflowChanged) {
        setExtractedSignal(null);
        setSignalStage('idle');
        clearGeneratedOutputs();
      }
      if (returnedWorkflow) {
        updateWorkflowSnapshot(returnedWorkflow);
        if (returnedWorkflow.has_signal === false && !data.content_signal) {
          setExtractedSignal(null);
          setSignalStage(
            returnedWorkflow.checkpoint_state?.CP1_SIGNAL_READY === 'failed' ? 'error' : 'idle'
          );
        }
        if (returnedWorkflow.has_script_pack === false && !data.script_pack) {
          setScriptPack(null);
        }
        if (
          workflowChanged
          || (
            actionInvalidatesGeneratedOutputs(data.selected_action)
            && returnedWorkflow.checkpoint_state?.CP5_STREAM_COMPLETE !== 'passed'
          )
        ) {
          setScenes({});
          fullTextBuffer.current = {};
        }
      }
      if (data.content_signal && typeof data.content_signal === 'object') {
        setExtractedSignal(data.content_signal);
        setSignalStage('ready');
        setExtractProgress(100);
      }
      let scriptPackOverride: ScriptPackPayload | null = null;
      if (data.script_pack && typeof data.script_pack === 'object') {
        scriptPackOverride = data.script_pack as ScriptPackPayload;
        setScriptPack(scriptPackOverride);
      }
      pushPlannerQaNote(asPlannerQaSummary(data.planner_qa_summary));
      if (data.ui?.active_panel) {
        setActivePanel(data.ui.active_panel);
      }
      if (typeof data.assistant_message === 'string' && data.assistant_message.trim()) {
        pushChatMessage('agent', data.assistant_message.trim());
      }

      const detail = typeof data.message === 'string'
        ? data.message
        : (!response.ok ? 'Agent request failed.' : '');
      if (detail) {
        setGenerationError(detail);
        pushAgentNote('error', 'Agent', detail);
      } else if (
        data.selected_action
        && !['respond', 'open_panel', 'generate_stream'].includes(data.selected_action)
      ) {
        const nextStatus = snapshotStatusSummary(returnedWorkflow ?? workflowSnapshot);
        if (nextStatus) {
          setGenerationStatus(nextStatus);
        }
      }

      if (data.ui?.start_stream) {
        await handleGenerateStream(scriptPackOverride ?? scriptPack ?? null);
      }
    } catch (err) {
      console.error("Agent chat error:", err);
      setGenerationError('Unable to contact agent.');
      pushAgentNote('error', 'Agent', 'Unable to contact agent.');
    }
  };

  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = chatInput.trim();
    if (!text) return;
    pushChatMessage('user', text);
    setChatInput('');
    await handleChatCommand(text);
  };

  const handleRegenerate = (sceneId: string, newText: string, newImageUrl: string, newAudioUrl: string) => {
    fullTextBuffer.current[sceneId] = newText;
    setScenes(prev => ({
      ...prev,
      [sceneId]: { ...prev[sceneId], text: '', imageUrl: newImageUrl, audioUrl: newAudioUrl, status: 'ready' }
    }));
  };

  const totalSceneCount = Object.keys(scenes).length;
  const completedSceneCount = Object.values(scenes).filter(
    scene => scene.status === 'ready' || scene.status === 'qa-failed'
  ).length;
  const generationProgress = totalSceneCount > 0
    ? Math.round((completedSceneCount / totalSceneCount) * 100)
    : 0;
  const signalStatusLabel = extractedSignal
    ? 'Ready'
    : isExtracting
      ? 'Extracting'
      : signalStage === 'error'
        ? 'Error'
        : 'Idle';
  const profileStatusLabel = workflowSnapshot?.checkpoint_state?.CP3_RENDER_LOCKED === 'passed'
    ? 'Locked'
    : workflowSnapshot?.checkpoint_state?.CP3_RENDER_LOCKED === 'failed'
      ? 'Error'
      : isApplyingProfile
        ? 'Locking'
        : 'Idle';
  const scriptStatusLabel = workflowSnapshot?.checkpoint_state?.CP4_SCRIPT_LOCKED === 'passed'
    ? 'Ready'
    : workflowSnapshot?.checkpoint_state?.CP4_SCRIPT_LOCKED === 'failed'
      ? 'Error'
      : isGeneratingScriptPack
        ? 'Planning'
        : 'Idle';
  const streamCheckpointStatus = workflowSnapshot?.checkpoint_state?.CP5_STREAM_COMPLETE;
  const bundleCheckpointStatus = workflowSnapshot?.checkpoint_state?.CP6_BUNDLE_FINALIZED;
  const streamStatusLabel = isGenerating
    ? 'Generating'
    : generationError || streamCheckpointStatus === 'failed' || bundleCheckpointStatus === 'failed'
      ? 'Error'
      : bundleCheckpointStatus === 'passed'
        ? 'Complete'
        : workflowSnapshot?.ready_for_stream
          ? 'Ready'
        : 'Idle';
  const extractionPhaseText = signalStage === 'sending'
    ? 'Uploading source and validating extraction schema...'
    : signalStage === 'structuring'
      ? 'Structuring thesis, claims, concepts, and narrative beats...'
      : signalStage === 'ready'
        ? 'Signal extraction complete.'
        : '';
  const panelOrder: AdvancedPanel[] = ['source', 'profile', 'signal', 'script', 'stream'];
  const panelLabel: Record<AdvancedPanel, string> = {
    source: 'Extract Signal',
    profile: 'Render Profile',
    signal: 'Content Signal',
    script: 'Script Pack',
    stream: 'Generate Stream',
  };
  const collapseTarget: Record<AdvancedPanel, AdvancedPanel> = {
    source: 'profile',
    profile: 'signal',
    signal: 'script',
    script: 'stream',
    stream: 'script',
  };
  const profileStepIndex = RENDER_PROFILE_STEPS.indexOf(profileStep);
  const canMoveProfileBack = profileStepIndex > 0;
  const canMoveProfileNext = profileStepIndex < RENDER_PROFILE_STEPS.length - 1;
  const agentIsWorking = isExtracting || isApplyingProfile || isGeneratingScriptPack || isGenerating;
  const chatRoleMeta = (role: ChatRole): {
    rowClassName: string;
    bubbleClassName: string;
    label: string;
  } => {
    if (role === 'user') {
      return {
        rowClassName: 'justify-end',
        bubbleClassName: 'border-blue-300 bg-blue-50 text-blue-950',
        label: 'You',
      };
    }
    if (role === 'system') {
      return {
        rowClassName: 'justify-center',
        bubbleClassName: 'border-slate-300 bg-slate-100 text-slate-700',
        label: 'System',
      };
    }
    return {
      rowClassName: 'justify-start',
      bubbleClassName: 'border-slate-200 bg-white text-slate-900',
      label: 'ExplainFlow',
    };
  };
  const stageProgress = (() => {
    if (!hasSourceInput) return 0;
    if (workflowSnapshot?.checkpoint_state?.CP6_BUNDLE_FINALIZED === 'passed') return 100;
    if (scriptPack) return 88;
    if (generationError) return 88;
    if (totalSceneCount > 0 && !isGenerating) return 100;
    if (isGenerating) return Math.max(80, generationProgress);
    if (workflowSnapshot?.checkpoint_state?.CP3_RENDER_LOCKED === 'passed') return 62;
    if (extractedSignal) return 52;
    if (isExtracting) return 35;
    if (activePanel === 'profile') return 45;
    if (activePanel === 'signal') return 60;
    return 20;
  })();

  const stageBadgeClass = (panel: AdvancedPanel): string => {
    if (panel === 'profile') {
      if (profileStatusLabel === 'Locked') return 'border-emerald-300 bg-emerald-100 text-emerald-800';
      if (profileStatusLabel === 'Locking') return 'border-blue-300 bg-blue-100 text-blue-900';
      if (profileStatusLabel === 'Error') return 'border-rose-300 bg-rose-100 text-rose-900';
    }
    if (panel === 'signal') {
      if (signalStatusLabel === 'Ready') return 'border-emerald-300 bg-emerald-100 text-emerald-800';
      if (signalStatusLabel === 'Extracting') return 'border-amber-300 bg-amber-100 text-amber-900';
      if (signalStatusLabel === 'Error') return 'border-rose-300 bg-rose-100 text-rose-900';
    }
    if (panel === 'script') {
      if (scriptStatusLabel === 'Ready') return 'border-indigo-300 bg-indigo-100 text-indigo-900';
      if (scriptStatusLabel === 'Planning') return 'border-blue-300 bg-blue-100 text-blue-900';
      if (scriptStatusLabel === 'Error') return 'border-rose-300 bg-rose-100 text-rose-900';
    }
    if (panel === 'stream') {
      if (streamStatusLabel === 'Complete') return 'border-emerald-300 bg-emerald-100 text-emerald-800';
      if (streamStatusLabel === 'Generating') return 'border-blue-300 bg-blue-100 text-blue-900';
      if (streamStatusLabel === 'Error') return 'border-rose-300 bg-rose-100 text-rose-900';
    }
    if (activePanel === panel) return 'border-blue-300 bg-blue-100 text-blue-900';
    return 'border-slate-300 bg-slate-100 text-slate-700';
  };
  const activeStageNote = activePanel === 'source'
    ? 'Stage 1: Ingest source material and start structured signal extraction.'
    : activePanel === 'profile'
      ? 'Stage 2: Set audience and style controls while extraction continues.'
      : activePanel === 'signal'
        ? 'Stage 3: Review extracted signal and confirm to auto-generate script pack.'
        : activePanel === 'script'
          ? 'Stage 4: Inspect planner output generated from signal + render profile.'
          : 'Stage 5: Generate interleaved scenes and monitor stream progress.';
  const dialogMeta = actionDialogStage === 'extract'
    ? {
      title: 'Ready to Start Extraction',
      description: 'You moved to Render Profile. Continue to start extraction, or close this and adjust your source first.',
      continueLabel: 'Start Extraction',
      amendLabel: null as string | null,
      amendHelp: '',
    }
    : actionDialogStage === 'profile'
      ? {
        title: 'Apply Render Profile?',
        description: 'You moved to Content Signal. Continue to lock profile settings for this run.',
        continueLabel: 'Apply and Continue',
        amendLabel: null as string | null,
        amendHelp: '',
      }
    : actionDialogStage === 'script'
          ? {
            title: 'Generate Script Pack?',
            description: 'Continue to generate the script pack first. You can review and amend it before stream generation.',
            continueLabel: 'Generate Script Pack',
            amendLabel: 'Amend Script',
            amendHelp: 'If the script misses tone or structure, adjust render profile (audience, taste bar, must-include, must-avoid) and relaunch script generation.',
          }
          : actionDialogStage === 'stream'
            ? {
              title: 'Start Generation Stream?',
              description: 'Continue to generate scenes now. You can return to earlier stages anytime and rerun.',
              continueLabel: 'Start Stream',
              amendLabel: null as string | null,
              amendHelp: '',
            }
            : null;
  const dialogContinueDisabled = !dialogMeta
    || (actionDialogStage === 'extract' && (!hasSourceInput || isExtracting || isUploadingAssets))
    || (actionDialogStage === 'profile' && (!workflowId || isApplyingProfile))
    || (actionDialogStage === 'script' && (!workflowSnapshot?.ready_for_script_pack || isGeneratingScriptPack || isGenerating))
    || (actionDialogStage === 'stream' && (!workflowSnapshot?.ready_for_stream || !scriptPack || isGenerating));

  return (
    <main className="relative isolate min-h-screen overflow-x-clip bg-[#05070f] py-12 px-4 sm:px-6 lg:px-8 font-sans text-slate-100">
      <div className="landing-bg page-bg-muted pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden>
        <div className="landing-aurora" />
        <div className="landing-grid" />
        <div className="landing-noise" />
        <div className="landing-collage">
          <div className="collage-tile tile-1">
            <Image src="/humanity/vitruvian.jpg" alt="" fill sizes="180px" className="object-contain p-4" />
            <div className="collage-tile-frame" />
            <div className="collage-tile-glow" />
          </div>
          <div className="collage-tile tile-2">
            <Image src="/humanity/mandelbrot.jpg" alt="" fill sizes="180px" className="object-cover" />
            <div className="collage-tile-frame" />
            <div className="collage-tile-glow" />
          </div>
        </div>
        <div className="landing-rings">
          <div className="landing-ring landing-ring-a" />
          <div className="landing-ring landing-ring-b" />
          <div className="landing-ring landing-ring-c" />
        </div>
      </div>

      <div className="relative z-10 max-w-6xl mx-auto space-y-8">
        
        {/* Header Section */}
        <div className="text-center space-y-2">
          <h1 className="text-4xl font-extrabold tracking-tight text-slate-100 drop-shadow-[0_2px_16px_rgba(2,6,23,0.75)]">Advanced Studio</h1>
          <p className="text-lg text-slate-200/95 drop-shadow-[0_1px_8px_rgba(2,6,23,0.6)]">Long-document input and granular render profile control.</p>
        </div>

        <div className="grid items-start gap-6 lg:grid-cols-[1.2fr_1fr]">
          <div className="space-y-6 lg:sticky lg:top-4">
            <Card className="bg-white text-slate-900 backdrop-blur-xl shadow-xl border-slate-300/70">
              <CardHeader>
                <CardTitle className="text-slate-900">ExplainFlow Assistant</CardTitle>
                <CardDescription className="text-slate-600">
                  Workflow orchestration console. Shows only the latest request/response while detailed logs stay in Agent Session Notes.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                  <div className="mb-3 flex items-center justify-between gap-3 px-1">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Latest Exchange</p>
                    <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">
                      Live
                    </span>
                  </div>
                <ScrollArea className="h-[300px] rounded-xl border border-slate-200 bg-white p-3 md:h-[340px]">
                  <div className="space-y-3 pr-2">
                    {chatMessages.map((message) => {
                      const meta = chatRoleMeta(message.role);
                      return (
                        <div key={message.id} className={`flex w-full items-start gap-2 ${meta.rowClassName}`}>
                          <div className={`max-w-[85%] rounded-2xl border px-3 py-2 text-sm leading-6 shadow-sm ${meta.bubbleClassName}`}>
                            <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide opacity-70">{meta.label}</p>
                            <p className="whitespace-pre-wrap">{message.text}</p>
                          </div>
                        </div>
                      );
                    })}
                    {agentIsWorking && (
                      <div className="flex w-full items-start gap-2 justify-start">
                        <div className="max-w-[85%] rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-sm">
                          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-600">ExplainFlow</p>
                          <Skeleton className="h-3 w-28 bg-slate-200" />
                          <Skeleton className="mt-2 h-3 w-44 bg-slate-200" />
                          <Skeleton className="mt-2 h-3 w-36 bg-slate-200" />
                        </div>
                      </div>
                    )}
                    <div ref={chatScrollAnchorRef} />
                  </div>
                </ScrollArea>
                </div>
                <form onSubmit={(e) => void handleChatSubmit(e)} className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <Textarea
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder='Ask naturally, e.g. "What should I do next?" or "Open render profile."'
                    className="min-h-[84px] resize-none bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
                  />
                  <Button
                    type="submit"
                    className="h-auto w-full rounded-[24px] bg-slate-950 px-5 py-4 text-left text-white shadow-[0_18px_36px_rgba(15,23,42,0.18)] transition-transform hover:-translate-y-0.5 hover:bg-slate-900 disabled:opacity-100 disabled:bg-slate-300 disabled:text-slate-500 disabled:hover:translate-y-0"
                  >
                    <span className="space-y-1 text-left">
                      <span className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300">
                        Assistant Action
                      </span>
                      <span className="block text-base font-semibold">Send Request</span>
                    </span>
                  </Button>
                </form>
              </CardContent>
            </Card>

            <AgentActivityPanel
              title="Agent Session Notes"
              subtitle="Checkpoint, QA, and traceability notes from the active workflow."
              notes={agentNotes}
              currentStatus={generationStatus}
            />
          </div>

          <div className="space-y-6">
        <Card className="bg-white text-slate-900 backdrop-blur-xl shadow-xl border-slate-300/70">
          <CardContent className="pt-6 space-y-4">
            <div className="overflow-x-auto">
              <div className="min-w-[720px] gap-2 pb-1" style={{ display: 'flex' }}>
                {panelOrder.map((panel) => (
                  <button
                    key={panel}
                    type="button"
                    onClick={() => setActivePanel(panel)}
                    style={{ flex: '1 1 0%' }}
                    className={`w-full rounded-md border px-3 py-2 text-center text-xs font-semibold transition hover:brightness-95 ${stageBadgeClass(panel)}`}
                  >
                    {panelLabel[panel]}
                  </button>
                ))}
              </div>
            </div>
            <Progress value={stageProgress} className="h-2 bg-blue-100 [&>*]:bg-blue-500" />
            <p className="text-xs text-slate-600">{activeStageNote}</p>
          </CardContent>
        </Card>

        <div className="relative min-h-[420px]">
          <div className="mx-auto max-w-4xl">
            <div key={activePanel} className="animate-in fade-in-0 zoom-in-95 duration-300">
              {activePanel === 'source' && (
                <Card className="bg-white text-slate-900 backdrop-blur-xl shadow-xl border-slate-300/70">
                  <CardHeader>
                    <CardTitle className="text-slate-900">1. Source Material</CardTitle>
                    <CardDescription className="text-slate-600">
                      Start with source text, uploaded source assets, or both. Images and audio can flow into claim-level proof links; PDFs are accepted for extraction and page-linked proof viewing with matched excerpts when available.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <form onSubmit={handleExtract} className="high-contrast-form-labels space-y-6">
                      <div className="space-y-2">
                        <Label htmlFor="sourceDoc">Document Text</Label>
                        <Textarea
                          id="sourceDoc"
                          value={sourceDoc}
                          onChange={e => setSourceDoc(e.target.value)}
                          placeholder="Paste long document here..."
                          className="min-h-[280px] text-base bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
                        />
                        <p className="text-xs text-slate-500">
                          Optional when uploaded assets already contain the source material. Use page-image uploads if you want crop-level proof on slides; PDFs now add page-linked excerpts when local text matching succeeds.
                        </p>
                      </div>
                      <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                          <div className="space-y-2">
                            <div className="flex items-center gap-3">
                              <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
                                <Upload className="h-5 w-5" />
                              </span>
                              <div>
                                <Label className="text-base text-slate-900">Source Assets</Label>
                                <p className="text-xs uppercase tracking-[0.14em] text-slate-500">
                                  PDFs, images, audio
                                </p>
                              </div>
                            </div>
                            <p className="text-sm leading-6 text-slate-600">
                              Upload proof-backed source files. PDFs drive extraction and page-linked proof, while per-page images still give the tightest crop-level evidence.
                            </p>
                            <div className="flex flex-wrap gap-2">
                              {['image', 'audio', 'pdf'].map((kind) => (
                                <span
                                  key={kind}
                                  className="inline-flex rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600"
                                >
                                  {kind}
                                </span>
                              ))}
                            </div>
                          </div>
                          <div className="space-y-2 sm:min-w-[220px]">
                            <Input
                              id="sourceAssets"
                              ref={sourceAssetsInputRef}
                              type="file"
                              accept="image/*,audio/*,application/pdf"
                              multiple
                              onChange={handleSourceAssetUpload}
                              disabled={isUploadingAssets || isExtracting}
                              className="sr-only"
                            />
                            <Button
                              type="button"
                              className="w-full"
                              variant="outline"
                              disabled={isUploadingAssets || isExtracting}
                              onClick={() => sourceAssetsInputRef.current?.click()}
                            >
                              {isUploadingAssets ? (
                                <>
                                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                  Uploading...
                                </>
                              ) : (
                                'Choose Source Files'
                              )}
                            </Button>
                            <p className="text-xs text-slate-500">
                              {uploadedSourceAssets.length > 0
                                ? `${uploadedSourceAssets.length} asset${uploadedSourceAssets.length === 1 ? '' : 's'} attached`
                                : 'No assets attached yet'}
                            </p>
                          </div>
                        </div>
                        {isUploadingAssets ? (
                          <div className="flex items-center gap-2 text-sm text-slate-600">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Uploading source assets...
                          </div>
                        ) : null}
                        {uploadedSourceAssets.length > 0 ? (
                          <div className="space-y-2">
                            {uploadedSourceAssets.map((asset) => (
                              <div
                                key={asset.asset_id}
                                className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                              >
                                <div className="min-w-0 space-y-1">
                                  <span className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">
                                    {asset.modality}
                                  </span>
                                  <p className="truncate text-sm font-medium text-slate-900">
                                    {asset.title || asset.asset_id}
                                  </p>
                                  <p className="text-xs text-slate-500">
                                    {asset.mime_type ? `${asset.mime_type}` : 'Source asset'}
                                    {typeof asset.page_index === 'number' ? ` • page ${asset.page_index}` : ''}
                                  </p>
                                </div>
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  className="border-slate-300"
                                  onClick={() => removeUploadedSourceAsset(asset.asset_id)}
                                >
                                  Remove
                                </Button>
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <Button
                          type="submit"
                          className={PRIMARY_ACTION_CARD_CLASS}
                          disabled={!hasSourceInput || isExtracting || isUploadingAssets}
                          size="lg"
                        >
                          <span className="flex w-full items-center justify-between gap-4">
                            <span className="space-y-1 text-left">
                              <span className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300">
                                Primary Action
                              </span>
                              <span className="block text-base font-semibold">
                                {isExtracting
                                  ? 'Extracting Signal...'
                                  : isUploadingAssets
                                    ? 'Uploading Assets...'
                                    : 'Extract Content Signal'}
                              </span>
                            </span>
                            {(isExtracting || isUploadingAssets) ? (
                              <Loader2 className="h-5 w-5 animate-spin text-slate-100" />
                            ) : null}
                          </span>
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          className={SECONDARY_ACTION_CARD_CLASS}
                          onClick={() => setActivePanel(collapseTarget.source)}
                        >
                          <span className="space-y-1 text-left">
                            <span className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                              Secondary Action
                            </span>
                            <span className="block text-base font-semibold">Collapse Window</span>
                          </span>
                        </Button>
                      </div>
                      {(isExtracting || extractProgress > 0) && (
                        <div className="space-y-2">
                          <Progress value={extractProgress} className="h-2 bg-amber-100 [&>*]:bg-amber-500" />
                          <p className="text-xs text-slate-600">
                            {isExtracting ? extractionPhaseText : signalStage === 'ready' ? 'Signal is ready for generation.' : ''}
                          </p>
                        </div>
                      )}
                      {error && <p className="text-red-500 text-sm font-medium">{error}</p>}
                    </form>
                  </CardContent>
                </Card>
              )}

              {activePanel === 'profile' && (
                <Card className="bg-white text-slate-900 backdrop-blur-xl shadow-xl border-slate-300/70">
                  <CardHeader>
                    <CardTitle className="text-slate-900">2. Render Profile</CardTitle>
                    <CardDescription className="text-slate-600">
                      Configure output while signal extraction runs in parallel. Questions are split so each choice is deliberate.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="high-contrast-form-labels space-y-5">
                    <Tabs value={profileStep} onValueChange={(value) => setProfileStep(value as RenderProfileStep)} className="space-y-4">
                      <TabsList className="grid w-full grid-cols-2 md:grid-cols-4">
                        {RENDER_PROFILE_STEPS.map((step) => (
                          <TabsTrigger key={step} value={step}>
                            {RENDER_PROFILE_STEP_LABELS[step]}
                          </TabsTrigger>
                        ))}
                      </TabsList>

                      <TabsContent value="output" className="space-y-4">
                        <p className="text-sm text-slate-600">Question 1: What output format and visual mode should the agent optimize for?</p>
                        <div className="space-y-3">
                          <Label>Artifact Type</Label>
                          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                            {ARTIFACT_SELECTION_TILES.map((tile) => {
                              const isSelected = artifactType === tile.value;
                              const Icon = tile.icon;
                              return (
                                <button
                                  key={tile.value}
                                  type="button"
                                  onClick={() => setArtifactType(tile.value)}
                                  className={`rounded-[28px] border p-4 text-left transition-all duration-200 ${
                                    tile.baseClassName
                                  } ${isSelected ? tile.selectedClassName : 'hover:-translate-y-0.5 hover:shadow-[0_12px_24px_rgba(15,23,42,0.08)]'}`}
                                >
                                  <div className="mb-6 flex items-start justify-between gap-3">
                                    <span
                                      className={`inline-flex h-12 w-12 items-center justify-center rounded-2xl ${
                                        isSelected ? tile.selectedIconClassName : tile.iconClassName
                                      }`}
                                    >
                                      <Icon className="h-5 w-5" />
                                    </span>
                                    {isSelected ? (
                                      <span className="rounded-full border border-slate-900/10 bg-white/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-700">
                                        Selected
                                      </span>
                                    ) : null}
                                  </div>
                                  <div className="space-y-1.5">
                                    <p className="text-lg font-semibold">{tile.title}</p>
                                    <p className="text-sm leading-6 text-slate-700/90">{tile.description}</p>
                                  </div>
                                </button>
                              );
                            })}
                          </div>
                        </div>
                        <div className="space-y-3">
                          <Label>Visual Mode</Label>
                          <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
                            {VISUAL_MODE_TILES.map((tile) => {
                              const isSelected = visualMode === tile.value;
                              const Icon = tile.icon;
                              return (
                                <button
                                  key={tile.value}
                                  type="button"
                                  onClick={() => setVisualMode(tile.value)}
                                  className={`rounded-[26px] border p-4 text-left transition-all duration-200 ${
                                    tile.baseClassName
                                  } ${isSelected ? tile.selectedClassName : 'hover:-translate-y-0.5 hover:shadow-[0_12px_24px_rgba(15,23,42,0.08)]'}`}
                                >
                                  <div className="mb-4 flex items-center gap-3">
                                    <span
                                      className={`inline-flex h-11 w-11 items-center justify-center rounded-2xl ${
                                        isSelected ? tile.selectedIconClassName : tile.iconClassName
                                      }`}
                                    >
                                      <Icon className="h-5 w-5" />
                                    </span>
                                    <div>
                                      <p className="font-semibold">{tile.title}</p>
                                      <p className="text-xs uppercase tracking-[0.14em] text-slate-600">
                                        {isSelected ? 'Active mode' : 'Tap to select'}
                                      </p>
                                    </div>
                                  </div>
                                  <p className="text-sm leading-6 text-slate-700/90">{tile.description}</p>
                                </button>
                              );
                            })}
                          </div>
                        </div>
                        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Current Selection</p>
                          <p className="mt-2 text-sm text-slate-700">
                            {ARTIFACT_SELECTION_TILES.find((item) => item.value === artifactType)?.title ?? artifactType}
                            {' · '}
                            {VISUAL_MODE_TILES.find((item) => item.value === visualMode)?.title ?? visualMode}
                          </p>
                        </div>
                      </TabsContent>

                      <TabsContent value="audience" className="space-y-4">
                        <p className="text-sm text-slate-600">Question 2: Who is this explainer for?</p>
                        <div className="space-y-3">
                          <Label>Audience Level</Label>
                          <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
                            {AUDIENCE_LEVEL_TILES.map((tile) => {
                              const isSelected = audienceLevel === tile.value;
                              const Icon = tile.icon;
                              return (
                                <button
                                  key={tile.value}
                                  type="button"
                                  onClick={() => setAudienceLevel(tile.value)}
                                  className={`rounded-[26px] border p-4 text-left transition-all duration-200 ${
                                    tile.baseClassName
                                  } ${isSelected ? tile.selectedClassName : 'hover:-translate-y-0.5 hover:shadow-[0_12px_24px_rgba(15,23,42,0.08)]'}`}
                                >
                                  <div className="mb-4 flex items-center gap-3">
                                    <span
                                      className={`inline-flex h-11 w-11 items-center justify-center rounded-2xl ${
                                        isSelected ? tile.selectedIconClassName : tile.iconClassName
                                      }`}
                                    >
                                      <Icon className="h-5 w-5" />
                                    </span>
                                    <div>
                                      <p className="font-semibold">{tile.title}</p>
                                      <p className="text-xs uppercase tracking-[0.14em] text-slate-600">
                                        {isSelected ? 'Active level' : 'Tap to select'}
                                      </p>
                                    </div>
                                  </div>
                                  <p className="text-sm leading-6 text-slate-700/90">{tile.description}</p>
                                </button>
                              );
                            })}
                          </div>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          <div className="space-y-2 sm:col-span-2">
                            <Label htmlFor="audiencePersona">Audience Persona</Label>
                            <Input
                              id="audiencePersona"
                              value={audiencePersona}
                              onChange={e => setAudiencePersona(e.target.value)}
                              placeholder="e.g. Product manager, data journalist, startup founder"
                              className="bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
                            />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="domainContext">Domain Context (Optional)</Label>
                          <Input
                            id="domainContext"
                            value={domainContext}
                            onChange={e => setDomainContext(e.target.value)}
                            placeholder="e.g. B2B SaaS roadmap decisions"
                            className="bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
                          />
                        </div>
                      </TabsContent>

                      <TabsContent value="style" className="space-y-4">
                        <p className="text-sm text-slate-600">Question 3: What quality and density should visuals and narration target?</p>
                        <div className="space-y-3">
                          <Label>Information Density</Label>
                          <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
                            {DENSITY_TILES.map((tile) => {
                              const isSelected = density === tile.value;
                              const Icon = tile.icon;
                              return (
                                <button
                                  key={tile.value}
                                  type="button"
                                  onClick={() => setDensity(tile.value)}
                                  className={`rounded-[26px] border p-4 text-left transition-all duration-200 ${
                                    tile.baseClassName
                                  } ${isSelected ? tile.selectedClassName : 'hover:-translate-y-0.5 hover:shadow-[0_12px_24px_rgba(15,23,42,0.08)]'}`}
                                >
                                  <div className="mb-4 flex items-center gap-3">
                                    <span
                                      className={`inline-flex h-11 w-11 items-center justify-center rounded-2xl ${
                                        isSelected ? tile.selectedIconClassName : tile.iconClassName
                                      }`}
                                    >
                                      <Icon className="h-5 w-5" />
                                    </span>
                                    <div>
                                      <p className="font-semibold">{tile.title}</p>
                                      <p className="text-xs uppercase tracking-[0.14em] text-slate-600">
                                        {isSelected ? 'Active density' : 'Tap to select'}
                                      </p>
                                    </div>
                                  </div>
                                  <p className="text-sm leading-6 text-slate-700/90">{tile.description}</p>
                                </button>
                              );
                            })}
                          </div>
                        </div>
                        <div className="space-y-3">
                          <Label>Taste Bar</Label>
                          <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
                            {TASTE_BAR_TILES.map((tile) => {
                              const isSelected = tasteBar === tile.value;
                              const Icon = tile.icon;
                              return (
                                <button
                                  key={tile.value}
                                  type="button"
                                  onClick={() => setTasteBar(tile.value)}
                                  className={`rounded-[26px] border p-4 text-left transition-all duration-200 ${
                                    tile.baseClassName
                                  } ${isSelected ? tile.selectedClassName : 'hover:-translate-y-0.5 hover:shadow-[0_12px_24px_rgba(15,23,42,0.08)]'}`}
                                >
                                  <div className="mb-4 flex items-center gap-3">
                                    <span
                                      className={`inline-flex h-11 w-11 items-center justify-center rounded-2xl ${
                                        isSelected ? tile.selectedIconClassName : tile.iconClassName
                                      }`}
                                    >
                                      <Icon className="h-5 w-5" />
                                    </span>
                                    <div>
                                      <p className="font-semibold">{tile.title}</p>
                                      <p className="text-xs uppercase tracking-[0.14em] text-slate-600">
                                        {isSelected ? 'Active taste bar' : 'Tap to select'}
                                      </p>
                                    </div>
                                  </div>
                                  <p className="text-sm leading-6 text-slate-700/90">{tile.description}</p>
                                </button>
                              );
                            })}
                          </div>
                        </div>
                        <div className="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
                          Low-key preview is always enabled for speed. You can request a high-fidelity rerun at Final Bundle stage.
                        </div>
                      </TabsContent>

                      <TabsContent value="constraints" className="space-y-4">
                        <p className="text-sm text-slate-600">Question 4: What should always be included, and what must be avoided?</p>
                        <div className="space-y-2">
                          <Label htmlFor="mustInclude">Must Include (Optional)</Label>
                          <Input
                            id="mustInclude"
                            value={mustIncludeText}
                            onChange={e => setMustIncludeText(e.target.value)}
                            placeholder="Comma-separated, e.g. business tradeoffs, clean hierarchy"
                            className="bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="mustAvoid">Must Avoid (Optional)</Label>
                          <Input
                            id="mustAvoid"
                            value={mustAvoidText}
                            onChange={e => setMustAvoidText(e.target.value)}
                            placeholder="Comma-separated, e.g. typical AI-generated gibberish, very abstract speculation"
                            className="bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
                          />
                        </div>
                      </TabsContent>
                    </Tabs>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <Button
                        type="button"
                        variant="outline"
                        className="w-full border-slate-300"
                        onClick={handleProfileStepBack}
                        disabled={!canMoveProfileBack}
                      >
                        Previous Question
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        className="w-full border-slate-300"
                        onClick={handleProfileStepNext}
                        disabled={!canMoveProfileNext}
                      >
                        {canMoveProfileNext ? 'Next Question' : 'All Questions Answered'}
                      </Button>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                      <Button
                        type="button"
                        className={PRIMARY_ACTION_CARD_CLASS}
                        onClick={handleApplyRenderProfile}
                        disabled={isApplyingProfile || !workflowId}
                      >
                        <span className="flex w-full items-center justify-between gap-4">
                          <span className="space-y-1 text-left">
                            <span className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300">
                              Primary Action
                            </span>
                            <span className="block text-base font-semibold">
                              {isApplyingProfile ? 'Locking Profile...' : 'Apply Render Profile'}
                            </span>
                          </span>
                          {isApplyingProfile ? (
                            <Loader2 className="h-5 w-5 animate-spin text-slate-100" />
                          ) : null}
                        </span>
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        className={SECONDARY_ACTION_CARD_CLASS}
                        onClick={() => setActivePanel(collapseTarget.profile)}
                      >
                        <span className="space-y-1 text-left">
                          <span className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                            Secondary Action
                          </span>
                          <span className="block text-base font-semibold">Collapse Window</span>
                        </span>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {activePanel === 'signal' && (
                <Card className="bg-white text-slate-900 backdrop-blur-xl shadow-xl border-slate-300/70">
                  <CardHeader>
                    <CardTitle className="text-slate-900">3. Content Signal</CardTitle>
                    <CardDescription className="text-slate-600">Style-agnostic structured extraction from the source document.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {extractedSignal ? (
                      <div className="space-y-4">
                        <div className="bg-slate-900 text-slate-50 p-4 rounded-md overflow-auto max-h-[460px] text-xs font-mono">
                          <pre>{JSON.stringify(extractedSignal, null, 2)}</pre>
                        </div>
                        <div className="p-4 bg-blue-50 text-blue-900 rounded-md border border-blue-200">
                          <h4 className="font-semibold mb-1">Signal Extracted</h4>
                          <p className="text-sm">
                            Review the extracted structure, then confirm signal to generate script pack.
                          </p>
                        </div>
                      </div>
                    ) : isExtracting ? (
                      <div className="space-y-4">
                        <Progress value={extractProgress} className="h-2 bg-amber-100 [&>*]:bg-amber-500" />
                        <p className="text-sm text-slate-700">{extractionPhaseText}</p>
                        <div className="p-4 bg-amber-50 text-amber-950 rounded-md border border-amber-200">
                          <h4 className="font-semibold mb-2">Extracting Structured Signal...</h4>
                          <p className="text-sm whitespace-pre-wrap font-mono leading-6">
                            {typedExplainer}
                            <span className="animate-pulse">|</span>
                          </p>
                        </div>
                        <div className="bg-slate-900 text-slate-50 p-4 rounded-md overflow-auto max-h-[360px] text-xs font-mono">
                          <pre>
                            {typedPreview}
                            <span className="animate-pulse">|</span>
                          </pre>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center text-slate-400 border-2 border-dashed border-slate-300 rounded-md p-8 min-h-[240px]">
                        <p className="text-center font-medium">Signal not started yet.</p>
                        <p className="text-center text-sm mt-1">Open Source Material stage and run extraction first.</p>
                      </div>
                    )}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                      <Button
                        type="button"
                        className={PRIMARY_ACTION_CARD_CLASS}
                        onClick={() => void handleConfirmSignal()}
                        disabled={!extractedSignal}
                      >
                        <span className="space-y-1 text-left">
                          <span className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300">
                            Primary Action
                          </span>
                          <span className="block text-base font-semibold">Confirm Signal</span>
                        </span>
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        className={SECONDARY_ACTION_CARD_CLASS}
                        onClick={() => setActivePanel(collapseTarget.signal)}
                      >
                        <span className="space-y-1 text-left">
                          <span className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                            Secondary Action
                          </span>
                          <span className="block text-base font-semibold">Collapse Window</span>
                        </span>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {activePanel === 'stream' && (
                <Card className="bg-white text-slate-900 backdrop-blur-xl shadow-xl border-slate-300/70">
                  <CardHeader>
                    <CardTitle className="text-slate-900">5. Generation Stream</CardTitle>
                    <CardDescription className="text-slate-600">
                      Start generation and monitor live scene-by-scene output.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <Button className={PRIMARY_ACTION_CARD_CLASS} size="lg" onClick={() => void handleGenerateStreamAction()} disabled={isGenerating || !workflowSnapshot?.ready_for_stream || !scriptPack || isGeneratingScriptPack}>
                        <span className="flex w-full items-center justify-between gap-4">
                          <span className="space-y-1 text-left">
                            <span className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300">
                              Primary Action
                            </span>
                            <span className="block text-base font-semibold">
                              {isGenerating ? (
                                'Generating Stream...'
                              ) : isGeneratingScriptPack ? (
                                'Script Pack in Progress...'
                              ) : !workflowSnapshot?.ready_for_script_pack ? (
                                'Lock Signal + Artifacts + Profile First'
                              ) : !scriptPack ? (
                                'Generate Script Pack First'
                              ) : !workflowSnapshot?.ready_for_stream ? (
                                'Script Pack Must Be Locked'
                              ) : (
                                'Generate Explainer Stream'
                              )}
                            </span>
                          </span>
                          {isGenerating ? (
                            <Loader2 className="h-5 w-5 animate-spin text-slate-100" />
                          ) : null}
                        </span>
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        className={SECONDARY_ACTION_CARD_CLASS}
                        onClick={() => setActivePanel(collapseTarget.stream)}
                      >
                        <span className="space-y-1 text-left">
                          <span className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                            Secondary Action
                          </span>
                          <span className="block text-base font-semibold">Collapse Window</span>
                        </span>
                      </Button>
                    </div>
                    {generationStatus && (
                      <div className="p-4 bg-blue-50 text-blue-900 rounded-md border border-blue-200">
                        <h4 className="font-semibold mb-1">Generation Status</h4>
                        <p className="text-sm">{generationStatus}</p>
                      </div>
                    )}
                    {isGenerating && (
                      <div className="space-y-2">
                        <Progress value={generationProgress} className="h-2 bg-blue-100 [&>*]:bg-blue-500" />
                        <p className="text-xs text-slate-600">Scenes complete: {completedSceneCount}/{Math.max(totalSceneCount, completedSceneCount)}</p>
                      </div>
                    )}
                    {generationError && (
                      <p className="text-sm font-medium text-rose-600">{generationError}</p>
                    )}
                  </CardContent>
                </Card>
              )}

              {activePanel === 'script' && (
                <Card className="bg-white text-slate-900 backdrop-blur-xl shadow-xl border-slate-300/70">
                  <CardHeader>
                    <CardTitle className="text-slate-900">4. Script Pack</CardTitle>
                    <CardDescription className="text-slate-600">
                      Planner output generated from the extracted signal and current render profile.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {scriptPack ? (
                      <div className="space-y-3">
                        <div className="bg-slate-900 text-slate-50 p-4 rounded-md overflow-auto max-h-[460px] text-xs font-mono">
                          <pre>{JSON.stringify(scriptPack, null, 2)}</pre>
                        </div>
                        <p className="text-xs text-slate-600">
                          Change render profile settings and run generation again to regenerate this script pack.
                        </p>
                      </div>
                    ) : isGeneratingScriptPack ? (
                      <div className="space-y-4">
                        <div className="p-4 bg-blue-50 text-blue-900 rounded-md border border-blue-200">
                          <h4 className="font-semibold mb-2">Drafting Script Pack...</h4>
                          <p className="text-sm whitespace-pre-wrap font-mono leading-6">
                            {typedScriptExplainer}
                            <span className="animate-pulse">|</span>
                          </p>
                        </div>
                        <div className="bg-slate-900 text-slate-50 p-4 rounded-md overflow-auto max-h-[360px] text-xs font-mono">
                          <pre>
                            {typedScriptPreview}
                            <span className="animate-pulse">|</span>
                          </pre>
                        </div>
                      </div>
                    ) : (
                      <div className="flex min-h-[220px] flex-col items-center justify-center rounded-md border-2 border-dashed border-slate-300 p-8 text-slate-500">
                        <p className="text-center font-medium">Script pack not available yet.</p>
                        <p className="mt-1 text-center text-sm">Generate script pack first, then review before starting stream.</p>
                      </div>
                    )}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <Button
                        type="button"
                        className={PRIMARY_ACTION_CARD_CLASS}
                        onClick={() => void handleScriptPackAction()}
                        disabled={isGeneratingScriptPack || isGenerating || !workflowSnapshot?.ready_for_script_pack}
                      >
                        <span className="flex w-full items-center justify-between gap-4">
                          <span className="space-y-1 text-left">
                            <span className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300">
                              Primary Action
                            </span>
                            <span className="block text-base font-semibold">
                              {isGeneratingScriptPack ? 'Generating Script Pack...' : scriptPack ? 'Regenerate Script Pack' : 'Generate Script Pack'}
                            </span>
                          </span>
                          {isGeneratingScriptPack ? (
                            <Loader2 className="h-5 w-5 animate-spin text-slate-100" />
                          ) : null}
                        </span>
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        className={SECONDARY_ACTION_CARD_CLASS}
                        onClick={() => setActivePanel(collapseTarget.script)}
                      >
                        <span className="space-y-1 text-left">
                          <span className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                            Secondary Action
                          </span>
                          <span className="block text-base font-semibold">Collapse Window</span>
                        </span>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </div>
          </div>
        </div>

        {/* Timeline Stream Area */}
        <div className="space-y-6 mt-12">
          {generationError && (
            <div className="p-4 bg-red-50 text-red-900 rounded-md border border-red-200">
              <h4 className="font-semibold mb-1">Generation Error</h4>
              <p className="text-sm">{generationError}</p>
            </div>
          )}

          {Object.values(scenes).length > 0 && (
            <h2 className="text-2xl font-bold tracking-tight text-slate-100 mb-6">Generated Explainer</h2>
          )}
          
          <div className="flex flex-col gap-6">
            {Object.values(scenes).map(scene => (
              <SceneCard 
                key={scene.id} 
                sceneId={scene.id} 
                title={scene.title}
                text={scene.text} 
                imageUrl={scene.imageUrl} 
                artifactType={scriptPack?.artifact_type ?? artifactType}
                audioUrl={scene.audioUrl} 
                visualMode={visualMode}
                onRegenerate={handleRegenerate}
                onOpenEvidence={openEvidenceViewer}
                claimRefs={scene.claim_refs}
                sourceMedia={scene.source_media}
                status={scene.status}
                qaStatus={scene.qa_status}
                qaReasons={scene.qa_reasons}
                qaScore={scene.qa_score}
                qaWordCount={scene.qa_word_count}
                autoRetryCount={scene.auto_retry_count}
                audioStatus={isGenerating && !scene.audioUrl ? "Generating..." : "Ready"} 
              />
            ))}
          </div>

          {!isGenerating && Object.values(scenes).length > 0 && (
            <>
              {fidelityPreference !== 'high' ? (
                <Card className="bg-white text-slate-900 border-slate-300 shadow-md">
                  <CardContent className="pt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="font-semibold">Need a higher-quality final bundle?</p>
                      <p className="text-sm text-slate-600">
                        Current run used low-key preview mode for speed. Upgrade the current scene images to 2x high fidelity without changing text.
                      </p>
                    </div>
                    <Button
                      type="button"
                      onClick={() => void handleEnableHighFidelity()}
                      disabled={isApplyingProfile || isGenerating || isGeneratingScriptPack}
                    >
                      Upscale Bundle Images (2x)
                    </Button>
                  </CardContent>
                </Card>
              ) : (
                <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
                  High-fidelity mode is active for this bundle. Text/audio are preserved and scene images use the upscaled assets.
                </div>
              )}
              <FinalBundle scenes={scenes} topic={extractedSignal?.thesis?.one_liner || 'Advanced Explainer'} />
            </>
          )}
        </div>

      </div>
      <Dialog open={Boolean(evidenceViewer)} onOpenChange={(open) => { if (!open) setEvidenceViewer(null); }}>
        <DialogContent className="bg-white text-slate-900 border-slate-300 max-w-3xl">
          <DialogHeader>
            <DialogTitle>{evidenceViewer?.sceneTitle ? `${evidenceViewer.sceneTitle} Proof` : 'Source Proof'}</DialogTitle>
            <DialogDescription className="text-slate-700">
              {evidenceViewer?.claimRef
                ? `Showing linked source evidence for ${evidenceViewer.claimRef}.`
                : 'Showing the strongest linked source proof for this scene.'}
            </DialogDescription>
          </DialogHeader>
              {evidenceViewer?.media ? (
            <div className="space-y-4">
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                {evidenceViewer.media.modality === 'audio' ? (
                  <audio
                    key={`${evidenceViewer.media.url}-${evidenceViewer.media.start_ms ?? 0}-${evidenceViewer.media.end_ms ?? 0}`}
                    controls
                    src={withMediaFragment(
                      evidenceViewer.media.url,
                      evidenceViewer.media.start_ms,
                      evidenceViewer.media.end_ms,
                    )}
                    className="w-full"
                  />
                ) : evidenceViewer.media.modality === 'pdf_page'
                  && (
                    evidenceViewer.media.url.toLowerCase().includes('.pdf')
                    || evidenceViewer.media.original_url?.toLowerCase().includes('.pdf')
                  ) ? (
                  <iframe
                    src={withPdfPageFragment(
                      evidenceViewer.media.url,
                      evidenceViewer.media.page_index,
                    )}
                    title={evidenceViewer.media.label || 'Source document proof'}
                    className="h-[520px] w-full rounded-md border border-slate-200 bg-white"
                  />
                ) : (
                  <div className="overflow-hidden rounded-md border border-slate-200 bg-white">
                    <img
                      src={evidenceViewer.media.url}
                      alt={evidenceViewer.media.label || 'Source proof'}
                      className="w-full h-auto object-contain"
                    />
                  </div>
                )}
              </div>
              <div className="grid gap-2 text-sm text-slate-700">
                {evidenceViewer.media.label ? (
                  <p><span className="font-semibold text-slate-900">Label:</span> {evidenceViewer.media.label}</p>
                ) : null}
                <p><span className="font-semibold text-slate-900">Type:</span> {evidenceViewer.media.modality}</p>
                {typeof evidenceViewer.media.page_index === 'number' ? (
                  <p><span className="font-semibold text-slate-900">Page:</span> {evidenceViewer.media.page_index}</p>
                ) : null}
                {typeof evidenceViewer.media.line_start === 'number' ? (
                  <p>
                    <span className="font-semibold text-slate-900">Lines:</span> {evidenceViewer.media.line_start}
                    {typeof evidenceViewer.media.line_end === 'number' && evidenceViewer.media.line_end !== evidenceViewer.media.line_start
                      ? `-${evidenceViewer.media.line_end}`
                      : ''}
                  </p>
                ) : null}
                {typeof evidenceViewer.media.start_ms === 'number' ? (
                  <p>
                    <span className="font-semibold text-slate-900">Time:</span> {formatMilliseconds(evidenceViewer.media.start_ms)}
                    {typeof evidenceViewer.media.end_ms === 'number' ? ` - ${formatMilliseconds(evidenceViewer.media.end_ms)}` : ''}
                  </p>
                ) : null}
                {evidenceViewer.media.matched_excerpt ? (
                  <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Matched Excerpt</p>
                    <p className="mt-2 text-sm leading-6 text-slate-800">{evidenceViewer.media.matched_excerpt}</p>
                  </div>
                ) : null}
                {evidenceViewer.media.quote_text ? (
                  <p><span className="font-semibold text-slate-900">Quote:</span> {evidenceViewer.media.quote_text}</p>
                ) : null}
                {evidenceViewer.media.visual_context ? (
                  <p><span className="font-semibold text-slate-900">Visual Context:</span> {evidenceViewer.media.visual_context}</p>
                ) : null}
                {evidenceViewer.media.evidence_refs.length > 0 ? (
                  <p><span className="font-semibold text-slate-900">Evidence Refs:</span> {evidenceViewer.media.evidence_refs.join(', ')}</p>
                ) : null}
              </div>
              <DialogFooter className="gap-2">
                {evidenceViewer.media.original_url ? (
                  <Button type="button" variant="outline" className="border-slate-300" asChild>
                    <a
                      href={evidenceViewer.media.modality === 'pdf_page'
                        ? withPdfPageFragment(evidenceViewer.media.original_url, evidenceViewer.media.page_index)
                        : evidenceViewer.media.original_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open Original Asset
                    </a>
                  </Button>
                ) : null}
                <Button type="button" onClick={() => setEvidenceViewer(null)}>Close</Button>
              </DialogFooter>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
      <Dialog open={Boolean(actionDialogStage)} onOpenChange={(open) => { if (!open) closeActionDialog(); }}>
        <DialogContent className="bg-white text-slate-900 border-slate-300">
          <DialogHeader>
            <DialogTitle>{dialogMeta?.title}</DialogTitle>
            <DialogDescription className="text-slate-700">
              {dialogMeta?.description}
            </DialogDescription>
          </DialogHeader>

          {showAmendHelp && dialogMeta?.amendHelp && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
              {dialogMeta.amendHelp}
            </div>
          )}

          <DialogFooter className="gap-2">
            {!showAmendHelp && (
              <>
                {dialogMeta?.amendLabel && (
                  <Button
                    type="button"
                    variant="outline"
                    className="border-slate-300"
                    onClick={() => setShowAmendHelp(true)}
                  >
                    {dialogMeta.amendLabel}
                  </Button>
                )}
                <Button type="button" onClick={() => void handleDialogContinue()} disabled={dialogContinueDisabled}>
                  {dialogMeta?.continueLabel ?? 'Continue'}
                </Button>
              </>
            )}

            {showAmendHelp && (
              <>
                <Button type="button" variant="outline" className="border-slate-300" onClick={handleDialogGoBack}>
                  Go Back to Amend
                </Button>
                <Button
                  type="button"
                  onClick={() => void handleDialogRelaunch()}
                  disabled={actionDialogStage === 'script' ? isGenerating || !workflowSnapshot?.ready_for_script_pack : isExtracting}
                >
                  Relaunch Segment
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Toaster position="top-right" richColors closeButton />
    </main>
  );
}
