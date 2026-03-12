import { Blend, Blocks, GalleryVerticalEnd, GraduationCap, LayoutGrid, Sparkles, UserRound, type LucideIcon } from "lucide-react";

export type QuickTile = {
  value: string;
  title: string;
  description: string;
  icon: LucideIcon;
  baseClassName: string;
  selectedClassName: string;
  iconClassName: string;
  selectedIconClassName: string;
};

export const QUICK_AUDIENCE_TILES: QuickTile[] = [
  {
    value: 'Beginner',
    title: 'Beginner',
    description: 'Simple language and bigger conceptual steps.',
    icon: GraduationCap,
    baseClassName: 'border-sky-100 bg-sky-50/85 text-sky-950',
    selectedClassName: 'border-sky-300 bg-sky-100 shadow-[0_14px_28px_rgba(14,165,233,0.14)]',
    iconClassName: 'bg-white/80 text-sky-700',
    selectedIconClassName: 'bg-sky-700 text-white',
  },
  {
    value: 'Intermediate',
    title: 'Intermediate',
    description: 'Balanced clarity for informed general audiences.',
    icon: LayoutGrid,
    baseClassName: 'border-indigo-100 bg-indigo-50/85 text-indigo-950',
    selectedClassName: 'border-indigo-300 bg-indigo-100 shadow-[0_14px_28px_rgba(99,102,241,0.14)]',
    iconClassName: 'bg-white/80 text-indigo-700',
    selectedIconClassName: 'bg-indigo-700 text-white',
  },
  {
    value: 'Expert',
    title: 'Expert',
    description: 'Denser framing with more technical compression.',
    icon: Blocks,
    baseClassName: 'border-slate-200 bg-slate-50/95 text-slate-950',
    selectedClassName: 'border-slate-400 bg-slate-100 shadow-[0_14px_28px_rgba(15,23,42,0.12)]',
    iconClassName: 'bg-white/80 text-slate-700',
    selectedIconClassName: 'bg-slate-800 text-white',
  },
  {
    value: 'Other',
    title: 'Custom',
    description: 'Specify your own audience profile.',
    icon: UserRound,
    baseClassName: 'border-amber-100 bg-amber-50/85 text-amber-950',
    selectedClassName: 'border-amber-300 bg-amber-100 shadow-[0_14px_28px_rgba(245,158,11,0.14)]',
    iconClassName: 'bg-white/80 text-amber-700',
    selectedIconClassName: 'bg-amber-700 text-white',
  },
];

export const QUICK_VISUAL_TILES: QuickTile[] = [
  {
    value: 'illustration',
    title: 'Illustration',
    description: 'More cinematic framing and expressive imagery.',
    icon: Sparkles,
    baseClassName: 'border-fuchsia-100 bg-fuchsia-50/85 text-fuchsia-950',
    selectedClassName: 'border-fuchsia-300 bg-fuchsia-100 shadow-[0_14px_28px_rgba(217,70,239,0.14)]',
    iconClassName: 'bg-white/80 text-fuchsia-700',
    selectedIconClassName: 'bg-fuchsia-700 text-white',
  },
  {
    value: 'diagram',
    title: 'Diagram',
    description: 'Cleaner vectors and schematic explanation.',
    icon: GalleryVerticalEnd,
    baseClassName: 'border-emerald-100 bg-emerald-50/85 text-emerald-950',
    selectedClassName: 'border-emerald-300 bg-emerald-100 shadow-[0_14px_28px_rgba(16,185,129,0.14)]',
    iconClassName: 'bg-white/80 text-emerald-700',
    selectedIconClassName: 'bg-emerald-700 text-white',
  },
  {
    value: 'hybrid',
    title: 'Hybrid',
    description: 'Blend structured UI cues with illustration polish.',
    icon: Blend,
    baseClassName: 'border-violet-100 bg-violet-50/85 text-violet-950',
    selectedClassName: 'border-violet-300 bg-violet-100 shadow-[0_14px_28px_rgba(139,92,246,0.14)]',
    iconClassName: 'bg-white/80 text-violet-700',
    selectedIconClassName: 'bg-violet-700 text-white',
  },
];

export const QUICK_TONE_PRESETS = [
  'Practical',
  'Clear',
  'Executive',
  'Cinematic',
  'Playful',
];

export const QUICK_PRIMARY_ACTION_CARD_CLASS = "group h-auto w-full rounded-[24px] bg-slate-950 px-5 py-4 text-left text-white shadow-[0_18px_36px_rgba(15,23,42,0.18)] transition-transform hover:-translate-y-0.5 hover:bg-slate-900 disabled:opacity-100 disabled:bg-slate-300 disabled:text-slate-500 disabled:hover:translate-y-0";
export const QUICK_PRIMARY_ACTION_LABEL_CLASS = "block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300 transition-colors group-disabled:text-slate-600";

export type QuickArtifactBlock = {
  block_id: string;
  label: string;
  title: string;
  body: string;
  bullets: string[];
  visual_direction: string;
  image_url?: string | null;
  emphasis: 'hook' | 'core' | 'proof' | 'implication' | 'action';
  claim_refs: string[];
  evidence_refs: string[];
  source_media: QuickSourceMedia[];
};

export type QuickArtifact = {
  artifact_id: string;
  title: string;
  subtitle: string;
  summary: string;
  visual_style: string;
  hero_direction: string;
  hero_image_url?: string | null;
  reel?: QuickReel | null;
  video?: QuickVideo | null;
  blocks: QuickArtifactBlock[];
};

export type QuickReelSegment = {
  segment_id: string;
  block_id: string;
  title: string;
  render_mode: 'source_clip' | 'generated_image' | 'hybrid';
  caption_text: string;
  claim_refs: string[];
  evidence_refs: string[];
  primary_media?: QuickSourceMedia | null;
  fallback_image_url?: string | null;
  start_ms: number | null;
  end_ms: number | null;
  timing_inferred: boolean;
};

export type QuickReel = {
  reel_id: string;
  title: string;
  summary: string;
  segments: QuickReelSegment[];
};

export type PlaylistPresentationMode = 'auto' | 'source' | 'image';

export type QuickVideoSegment = {
  segment_id: string;
  block_id: string;
  title: string;
  caption_text: string;
  voiceover_url?: string | null;
  visual_url?: string | null;
  source_video_url?: string | null;
  source_start_ms: number | null;
  source_end_ms: number | null;
  duration_ms: number | null;
  render_mode: 'image_only' | 'image_plus_clip' | 'clip_only';
};

export type QuickVideo = {
  video_id: string;
  status: 'ready';
  video_url: string;
  duration_ms: number | null;
  segments: QuickVideoSegment[];
};

export type QuickSourceMedia = {
  asset_id: string;
  modality: 'audio' | 'video' | 'image' | 'pdf_page';
  usage: 'background' | 'hero' | 'proof_clip' | 'region_crop' | 'callout';
  claim_refs: string[];
  evidence_refs: string[];
  start_ms: number | null;
  end_ms: number | null;
  page_index: number | null;
  bbox_norm: number[] | null;
  label?: string | null;
  quote_text?: string | null;
  visual_context?: string | null;
  loop?: boolean;
  muted?: boolean;
};

export type UploadedQuickSourceAsset = {
  asset_id: string;
  modality: 'video';
  uri: string;
  title?: string | null;
  duration_ms?: number | null;
  provider: 'upload' | 'youtube';
  embed_url?: string | null;
};

export const formatMilliseconds = (value?: number | null) => {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) {
    return null;
  }
  const totalSeconds = Math.max(0, Math.floor(value / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
};

export const formatTimeRangeLabel = (startMs?: number | null, endMs?: number | null) => {
  const start = formatMilliseconds(startMs);
  const end = formatMilliseconds(endMs);
  if (start && end) return `${start} - ${end}`;
  return start || end || null;
};
