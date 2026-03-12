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
