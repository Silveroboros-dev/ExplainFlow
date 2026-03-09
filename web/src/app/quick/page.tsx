"use client";

import Image from 'next/image';
import React, { useRef, useState } from 'react';
import AgentActivityPanel, { AgentNote, AgentNoteType } from '@/components/AgentActivityPanel';
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  type LucideIcon,
  Blend,
  Blocks,
  Bot,
  Clapperboard,
  ChevronRight,
  GalleryVerticalEnd,
  GraduationCap,
  LayoutGrid,
  Loader2,
  Mic,
  PanelTop,
  PlayCircle,
  Sparkles,
  Square,
  UserRound,
  Upload,
  Wand2,
} from "lucide-react";
import { Toaster, toast } from "sonner";

type QuickTile = {
  value: string;
  title: string;
  description: string;
  icon: LucideIcon;
  baseClassName: string;
  selectedClassName: string;
  iconClassName: string;
  selectedIconClassName: string;
};

const QUICK_AUDIENCE_TILES: QuickTile[] = [
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

const QUICK_VISUAL_TILES: QuickTile[] = [
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

const QUICK_TONE_PRESETS = [
  'Practical',
  'Clear',
  'Executive',
  'Cinematic',
  'Playful',
];

const QUICK_PRIMARY_ACTION_CARD_CLASS = "group h-auto w-full rounded-[24px] bg-slate-950 px-5 py-4 text-left text-white shadow-[0_18px_36px_rgba(15,23,42,0.18)] transition-transform hover:-translate-y-0.5 hover:bg-slate-900 disabled:opacity-100 disabled:bg-slate-300 disabled:text-slate-500 disabled:hover:translate-y-0";
const QUICK_PRIMARY_ACTION_LABEL_CLASS = "block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300 transition-colors group-disabled:text-slate-600";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type QuickArtifactBlock = {
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

type QuickArtifact = {
  artifact_id: string;
  title: string;
  subtitle: string;
  summary: string;
  visual_style: string;
  hero_direction: string;
  hero_image_url?: string | null;
  reel?: QuickReel | null;
  blocks: QuickArtifactBlock[];
};

type QuickReelSegment = {
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

type QuickReel = {
  reel_id: string;
  title: string;
  summary: string;
  segments: QuickReelSegment[];
};

type QuickSourceMedia = {
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

type UploadedQuickSourceAsset = {
  asset_id: string;
  modality: 'video';
  uri: string;
  title?: string | null;
  duration_ms?: number | null;
  provider: 'upload' | 'youtube';
  embed_url?: string | null;
};

type BrowserSpeechResult = {
  transcript: string;
};

type BrowserSpeechRecognitionEvent = {
  results: ArrayLike<ArrayLike<BrowserSpeechResult>>;
};

type BrowserSpeechRecognitionErrorEvent = {
  error: string;
};

type BrowserSpeechRecognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onresult: ((event: BrowserSpeechRecognitionEvent) => void) | null;
  onerror: ((event: BrowserSpeechRecognitionErrorEvent) => void) | null;
  start: () => void;
  stop: () => void;
};

type BrowserSpeechRecognitionCtor = new () => BrowserSpeechRecognition;

const formatMilliseconds = (value?: number | null) => {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) {
    return null;
  }
  const totalSeconds = Math.max(0, Math.floor(value / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
};

const formatTimeRangeLabel = (startMs?: number | null, endMs?: number | null) => {
  const start = formatMilliseconds(startMs);
  const end = formatMilliseconds(endMs);
  if (start && end) return `${start} - ${end}`;
  return start || end || null;
};

const diffQuickBlockFields = (previousBlock: QuickArtifactBlock, nextBlock: QuickArtifactBlock) => {
  const changedFields: string[] = [];
  if (previousBlock.title !== nextBlock.title) changedFields.push('title');
  if (previousBlock.body !== nextBlock.body) changedFields.push('body');
  if (JSON.stringify(previousBlock.bullets) !== JSON.stringify(nextBlock.bullets)) changedFields.push('bullets');
  if (previousBlock.visual_direction !== nextBlock.visual_direction) changedFields.push('visual direction');
  if (previousBlock.emphasis !== nextBlock.emphasis) changedFields.push('emphasis');
  if (JSON.stringify(previousBlock.claim_refs) !== JSON.stringify(nextBlock.claim_refs)) changedFields.push('claims');
  if ((previousBlock.image_url || '') !== (nextBlock.image_url || '')) changedFields.push('visual');
  return changedFields;
};

const formatChangeSummary = (changedFields: string[]) => {
  if (changedFields.length === 0) return 'content';
  if (changedFields.length === 1) return changedFields[0];
  if (changedFields.length === 2) return `${changedFields[0]} and ${changedFields[1]}`;
  return `${changedFields.slice(0, -1).join(', ')}, and ${changedFields[changedFields.length - 1]}`;
};

const buildMediaFragmentUrl = (url: string, startMs?: number | null, endMs?: number | null) => {
  const startSeconds = typeof startMs === 'number' && startMs >= 0 ? Math.floor(startMs / 1000) : null;
  const endSeconds = typeof endMs === 'number' && endMs > 0 ? Math.floor(endMs / 1000) : null;
  if (startSeconds === null && endSeconds === null) {
    return url;
  }
  if (startSeconds !== null && endSeconds !== null && endSeconds > startSeconds) {
    return `${url}#t=${startSeconds},${endSeconds}`;
  }
  if (startSeconds !== null) {
    return `${url}#t=${startSeconds}`;
  }
  return url;
};

const extractYouTubeVideoId = (rawUrl: string) => {
  const trimmed = rawUrl.trim();
  if (!trimmed) return null;
  try {
    const parsed = new URL(trimmed);
    const host = parsed.hostname.toLowerCase();
    if (host.includes('youtu.be')) {
      const candidate = parsed.pathname.replace(/^\/+/, '').split('/')[0];
      return candidate || null;
    }
    if (host.includes('youtube.com') || host.includes('youtube-nocookie.com')) {
      const watchId = parsed.searchParams.get('v');
      if (watchId) return watchId;
      const segments = parsed.pathname.split('/').filter(Boolean);
      const markerIndex = segments.findIndex((segment) => ['embed', 'shorts', 'live'].includes(segment));
      if (markerIndex >= 0 && segments[markerIndex + 1]) {
        return segments[markerIndex + 1];
      }
    }
  } catch {
    return null;
  }
  return null;
};

const buildYouTubeWatchUrl = (videoId: string) => `https://www.youtube.com/watch?v=${videoId}`;

const buildYouTubeEmbedUrl = (videoId: string, startMs?: number | null, endMs?: number | null) => {
  const params = new URLSearchParams({ rel: '0', modestbranding: '1' });
  const startSeconds = typeof startMs === 'number' && startMs >= 0 ? Math.floor(startMs / 1000) : null;
  const endSeconds = typeof endMs === 'number' && endMs > 0 ? Math.floor(endMs / 1000) : null;
  if (startSeconds !== null) {
    params.set('start', String(startSeconds));
  }
  if (endSeconds !== null && (startSeconds === null || endSeconds > startSeconds)) {
    params.set('end', String(endSeconds));
  }
  return `https://www.youtube-nocookie.com/embed/${videoId}?${params.toString()}`;
};

const asYouTubeQuickSourceAsset = (rawUrl: string): UploadedQuickSourceAsset | null => {
  const videoId = extractYouTubeVideoId(rawUrl);
  if (!videoId) {
    return null;
  }
  return {
    asset_id: `youtube-${videoId}`,
    modality: 'video',
    uri: buildYouTubeWatchUrl(videoId),
    title: `YouTube video ${videoId}`,
    duration_ms: null,
    provider: 'youtube',
    embed_url: buildYouTubeEmbedUrl(videoId),
  };
};

const readVideoDurationMs = (file: File): Promise<number | undefined> => new Promise((resolve) => {
  if (typeof document === 'undefined') {
    resolve(undefined);
    return;
  }
  const video = document.createElement('video');
  const objectUrl = URL.createObjectURL(file);
  const cleanup = () => {
    URL.revokeObjectURL(objectUrl);
    video.remove();
  };
  video.preload = 'metadata';
  video.onloadedmetadata = () => {
    const duration = Number.isFinite(video.duration) && video.duration > 0
      ? Math.round(video.duration * 1000)
      : undefined;
    cleanup();
    resolve(duration);
  };
  video.onerror = () => {
    cleanup();
    resolve(undefined);
  };
  video.src = objectUrl;
});

const asUploadedQuickSourceAsset = (value: unknown): UploadedQuickSourceAsset | null => {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const raw = value as Record<string, unknown>;
  const assetId = typeof raw.asset_id === 'string' ? raw.asset_id : '';
  const modality = raw.modality === 'video' ? 'video' : null;
  const uri = typeof raw.uri === 'string' ? raw.uri : '';
  if (!assetId || !modality || !uri) {
    return null;
  }
  return {
    asset_id: assetId,
    modality,
    uri,
    title: typeof raw.title === 'string' ? raw.title : null,
    duration_ms: typeof raw.duration_ms === 'number' ? raw.duration_ms : null,
    provider: 'upload',
    embed_url: null,
  };
};

export default function QuickGenerate() {
  const [topic, setTopic] = useState('');
  const [audience, setAudience] = useState('Beginner');
  const [customAudience, setCustomAudience] = useState('');
  const [tone, setTone] = useState('');
  const [visualMode, setVisualMode] = useState('illustration');
  const [sourceTranscript, setSourceTranscript] = useState('');
  const [sourceVideoUrl, setSourceVideoUrl] = useState('');
  const [uploadedVideoAsset, setUploadedVideoAsset] = useState<UploadedQuickSourceAsset | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isUploadingSource, setIsUploadingSource] = useState(false);
  const [generationStatus, setGenerationStatus] = useState('');
  const [generationError, setGenerationError] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [speechError, setSpeechError] = useState('');
  const [artifact, setArtifact] = useState<QuickArtifact | null>(null);
  const [activeQuickView, setActiveQuickView] = useState<'artifact' | 'reel'>('artifact');
  const [isBuildingReel, setIsBuildingReel] = useState(false);
  const [reelError, setReelError] = useState('');
  const [indexedSignal, setIndexedSignal] = useState<Record<string, unknown> | null>(null);
  const [indexedNormalizedSourceText, setIndexedNormalizedSourceText] = useState('');
  const [indexedSourceTextOrigin, setIndexedSourceTextOrigin] = useState<string | null>(null);
  const [agentNotes, setAgentNotes] = useState<AgentNote[]>([]);
  const [activeOverrideBlockId, setActiveOverrideBlockId] = useState<string | null>(null);
  const [overrideInstruction, setOverrideInstruction] = useState('');
  const [isApplyingOverride, setIsApplyingOverride] = useState(false);
  const [overrideError, setOverrideError] = useState('');
  const [isGlobalOverrideOpen, setIsGlobalOverrideOpen] = useState(false);
  const [globalOverrideInstruction, setGlobalOverrideInstruction] = useState('');
  const [isApplyingGlobalOverride, setIsApplyingGlobalOverride] = useState(false);
  const [globalOverrideError, setGlobalOverrideError] = useState('');

  const recognitionRef = React.useRef<BrowserSpeechRecognition | null>(null);
  const sourceFileInputRef = useRef<HTMLInputElement | null>(null);
  const youtubeSourceAsset = asYouTubeQuickSourceAsset(sourceVideoUrl);
  const activeSourceAsset = youtubeSourceAsset ?? uploadedVideoAsset;

  const pushAgentNote = (type: AgentNoteType, stage: string, message: string) => {
    const note: AgentNote = {
      id: `note-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      type,
      stage,
      message,
      timestamp: Date.now(),
    };
    setAgentNotes((prev) => [note, ...prev].slice(0, 60));
  };

  React.useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
      recognitionRef.current = null;
    };
  }, []);

  const buildQuickSourceManifest = () => (
    activeSourceAsset
      ? {
          assets: [
            {
              asset_id: activeSourceAsset.asset_id,
              modality: activeSourceAsset.modality,
              uri: activeSourceAsset.uri,
              title: activeSourceAsset.title ?? undefined,
              duration_ms: activeSourceAsset.duration_ms ?? undefined,
              transcript_text: sourceTranscript.trim() || undefined,
              metadata: activeSourceAsset.provider === 'youtube'
                ? {
                    provider: 'youtube',
                    embed_url: activeSourceAsset.embed_url ?? undefined,
                  }
                : undefined,
            },
          ],
        }
      : undefined
  );

  const ensureQuickReel = async (artifactDraft?: QuickArtifact | null) => {
    const baseArtifact = artifactDraft ?? artifact;
    if (!baseArtifact) {
      return null;
    }
    if (baseArtifact.reel) {
      return baseArtifact;
    }

    setIsBuildingReel(true);
    setReelError('');
    setGenerationStatus('Building proof reel...');
    pushAgentNote("info", "Reel", "Deriving Proof Reel segments from the current Quick artifact.");

    try {
      const response = await fetch(`${API_BASE}/api/generate-quick-reel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          artifact: baseArtifact,
          content_signal: indexedSignal ?? {},
          source_manifest: buildQuickSourceManifest(),
        }),
      });
      const data = await response.json();
      if (!response.ok || data.status !== 'success' || !data.artifact) {
        throw new Error(data.detail || data.message || 'Proof reel generation failed.');
      }

      const nextArtifact = data.artifact as QuickArtifact;
      setArtifact(nextArtifact);
      setGenerationStatus('Proof reel ready.');
      pushAgentNote("checkpoint", "Reel", "Proof Reel ready. Each Quick block now maps to an ordered segment.");
      return nextArtifact;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Proof reel generation failed.';
      setReelError(message);
      setGenerationStatus('');
      pushAgentNote("error", "Reel", message);
      return null;
    } finally {
      setIsBuildingReel(false);
    }
  };

  const toggleVoiceInput = () => {
    if (typeof window === 'undefined') return;

    if (isListening && recognitionRef.current) {
      recognitionRef.current.stop();
      return;
    }

    setSpeechError('');
    const speechWindow = window as unknown as {
      SpeechRecognition?: BrowserSpeechRecognitionCtor;
      webkitSpeechRecognition?: BrowserSpeechRecognitionCtor;
    };
    const SpeechRecognitionCtor = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) {
      setSpeechError('Voice input is not supported in this browser.');
      return;
    }

    const recognition = new SpeechRecognitionCtor();
    recognition.lang = 'en-US';
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setIsListening(true);
      setGenerationStatus('Listening for prompt...');
    };

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map(result => result[0]?.transcript ?? '')
        .join(' ')
        .trim();
      if (transcript) {
        setTopic(transcript);
      }
      setGenerationStatus('');
    };

    recognition.onerror = (event) => {
      setSpeechError(`Voice input failed: ${event.error}`);
      setGenerationStatus('');
    };

    recognition.onend = () => {
      setIsListening(false);
      recognitionRef.current = null;
      setGenerationStatus(prev => (prev === 'Listening for prompt...' ? '' : prev));
    };

    recognitionRef.current = recognition;
    recognition.start();
  };

  const clearIndexedSource = () => {
    setIndexedSignal(null);
    setIndexedNormalizedSourceText('');
    setIndexedSourceTextOrigin(null);
  };

  const removeUploadedVideoAsset = () => {
    setUploadedVideoAsset(null);
    clearIndexedSource();
  };

  const removeYoutubeSource = () => {
    setSourceVideoUrl('');
    clearIndexedSource();
  };

  const handleVideoAssetUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    event.target.value = '';
    if (!selectedFile) return;

    setGenerationError('');
    setIsUploadingSource(true);
    setGenerationStatus('Uploading source video...');
    pushAgentNote("info", "Source", `Uploading video source: ${selectedFile.name}`);

    try {
      const durationMs = await readVideoDurationMs(selectedFile);
      const formData = new FormData();
      formData.append('files', selectedFile);
      formData.append('asset_descriptors', JSON.stringify([
        {
          filename: selectedFile.name,
          duration_ms: durationMs ?? null,
        },
      ]));

      const response = await fetch(`${API_BASE}/api/source-assets/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (!response.ok || data.status !== 'success' || !Array.isArray(data.assets) || data.assets.length === 0) {
        throw new Error(data.detail || data.message || 'Video upload failed.');
      }

      const uploadedAsset = asUploadedQuickSourceAsset(data.assets[0]);
      if (!uploadedAsset) {
        throw new Error('Uploaded video response was missing required metadata.');
      }

      setUploadedVideoAsset(uploadedAsset);
      clearIndexedSource();
      setGenerationStatus('Source video ready.');
      pushAgentNote("checkpoint", "Source", "Video source uploaded. Ready for transcript-first indexing.");
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Video upload failed.';
      setGenerationError(message);
      setGenerationStatus('');
      pushAgentNote("error", "Source", message);
    } finally {
      setIsUploadingSource(false);
    }
  };

  const pollQuickSourceIndex = async (jobId: string) => {
    const startedAt = Date.now();
    while (Date.now() - startedAt < 180000) {
      const response = await fetch(`${API_BASE}/api/quick-source-index/${jobId}`, {
        cache: 'no-store',
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Unable to read quick source index status.');
      }
      if (data.status === 'completed') {
        return data;
      }
      if (data.status === 'failed') {
        throw new Error(data.error || data.message || 'Quick source indexing failed.');
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1200));
    }
    throw new Error('Quick source indexing timed out.');
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic) return;
    if (isListening && recognitionRef.current) {
      recognitionRef.current.stop();
    }

    setIsGenerating(true);
    setGenerationError('');
    setGenerationStatus('Building quick artifact...');
    setArtifact(null);
    setActiveQuickView('artifact');
    setReelError('');
    setAgentNotes([]);
    pushAgentNote("info", "Session", "Quick generation started. Building HTML-first artifact.");

    try {
      const sourceManifest = buildQuickSourceManifest();
      let nextContentSignal = indexedSignal;
      let nextNormalizedSourceText = indexedNormalizedSourceText;
      let nextSourceTextOrigin = indexedSourceTextOrigin;

      if (sourceVideoUrl.trim() && !youtubeSourceAsset) {
        throw new Error('Enter a valid YouTube URL before generating a Quick artifact.');
      }

      if (activeSourceAsset && !nextContentSignal) {
        if (activeSourceAsset.provider === 'upload' && (activeSourceAsset.duration_ms ?? 0) > 10 * 60 * 1000) {
          throw new Error('Quick video input is currently limited to 10 minutes.');
        }
        if (
          (activeSourceAsset.provider === 'youtube' && !sourceTranscript.trim())
          || ((activeSourceAsset.duration_ms ?? 0) > 2 * 60 * 1000 && !sourceTranscript.trim())
        ) {
          if (activeSourceAsset.provider === 'youtube') {
            throw new Error('YouTube URLs currently require transcript or subtitles in Quick.');
          }
          throw new Error('Videos longer than 2 minutes require transcript or captions in Quick.');
        }
        setGenerationStatus(activeSourceAsset.provider === 'youtube' ? 'Indexing YouTube transcript...' : 'Indexing source video...');
        pushAgentNote("info", "Source", activeSourceAsset.provider === 'youtube'
          ? 'Transcript-first YouTube indexing started.'
          : 'Transcript-first video indexing started.');
        const startIndexResponse = await fetch(`${API_BASE}/api/quick-source-index/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source_text: sourceTranscript,
            source_manifest: sourceManifest,
          }),
        });
        const startIndexData = await startIndexResponse.json();
        if (!startIndexResponse.ok || startIndexData.status !== 'accepted' || !startIndexData.job_id) {
          throw new Error(startIndexData.detail || startIndexData.message || 'Unable to start quick source indexing.');
        }

        const indexedResult = await pollQuickSourceIndex(startIndexData.job_id);
        nextContentSignal = indexedResult.result?.content_signal ?? null;
        nextNormalizedSourceText = indexedResult.result?.normalized_source_text ?? '';
        nextSourceTextOrigin = indexedResult.result?.source_text_origin ?? null;
        setIndexedSignal(nextContentSignal);
        setIndexedNormalizedSourceText(nextNormalizedSourceText);
        setIndexedSourceTextOrigin(nextSourceTextOrigin);
        setGenerationStatus('Building grounded quick artifact...');
        pushAgentNote("checkpoint", "Source", `${activeSourceAsset.provider === 'youtube' ? 'YouTube' : 'Video'} indexing complete. Building artifact from transcript-backed signal.`);
      } else if (activeSourceAsset && nextContentSignal) {
        setGenerationStatus(activeSourceAsset.provider === 'youtube' ? 'Reusing indexed YouTube signal...' : 'Reusing indexed video signal...');
        pushAgentNote("info", "Source", `Reusing previously indexed ${activeSourceAsset.provider === 'youtube' ? 'YouTube' : 'video'} signal for a faster quick artifact pass.`);
      }

      const response = await fetch(`${API_BASE}/api/generate-quick-artifact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic,
          audience: audience === 'Other' ? customAudience : audience,
          tone,
          visual_mode: visualMode,
          source_text: sourceTranscript,
          source_manifest: sourceManifest,
          normalized_source_text: nextNormalizedSourceText,
          source_text_origin: nextSourceTextOrigin,
          content_signal: nextContentSignal,
        }),
      });
      const data = await response.json();
      if (!response.ok || data.status !== 'success' || !data.artifact) {
        throw new Error(data.message || 'Quick artifact generation failed.');
      }
      setArtifact(data.artifact as QuickArtifact);
      setReelError('');
      setGenerationStatus('Quick artifact ready.');
      pushAgentNote("checkpoint", "Session", "Quick artifact ready. Blocks can now be directed individually.");
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Quick artifact generation failed.';
      setGenerationError(message);
      setGenerationStatus('');
      pushAgentNote("error", "Session", message);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleOverrideBlock = async () => {
    if (!artifact || !activeOverrideBlockId || !overrideInstruction.trim()) return;
    setIsApplyingOverride(true);
    setGenerationError('');
    setOverrideError('');
    setGenerationStatus('Applying director override...');
    pushAgentNote("info", activeOverrideBlockId, "Applying local override to one artifact block.");
    try {
      const response = await fetch(`${API_BASE}/api/regenerate-quick-block`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic,
          audience: audience === 'Other' ? customAudience : audience,
          tone,
          visual_mode: visualMode,
          artifact,
          source_manifest: buildQuickSourceManifest(),
          normalized_source_text: indexedNormalizedSourceText,
          source_text_origin: indexedSourceTextOrigin,
          content_signal: indexedSignal,
          block_id: activeOverrideBlockId,
          instruction: overrideInstruction,
        }),
      });
      const data = await response.json();
      if (!response.ok || data.status !== 'success' || !data.block) {
        throw new Error(data.message || 'Block override failed.');
      }
      const currentBlock = artifact.blocks.find((block) => block.block_id === activeOverrideBlockId) ?? null;
      const updatedBlock = data.block as QuickArtifactBlock;
      const changedFields = currentBlock ? diffQuickBlockFields(currentBlock, updatedBlock) : ['content'];
      if (changedFields.length === 0) {
        setOverrideError('Override completed but produced no visible block changes. Try a more explicit instruction.');
        setGenerationStatus('');
        pushAgentNote("error", activeOverrideBlockId, 'Override returned no visible block changes.');
        toast.warning('Block override returned no visible changes.', {
          description: 'Try a more explicit instruction or ask for a specific visual treatment.',
        });
        return;
      }
      const nextArtifact: QuickArtifact = {
        ...artifact,
        reel: null,
        blocks: artifact.blocks.map((block) => (
          block.block_id === activeOverrideBlockId ? updatedBlock : block
        )),
      };
      setArtifact(nextArtifact);
      setReelError('');
      if (activeQuickView === 'reel') {
        void ensureQuickReel(nextArtifact);
      }
      setGenerationStatus('Block updated.');
      pushAgentNote("checkpoint", activeOverrideBlockId, "Block override applied.");
      toast.success('Block updated.', {
        description: `Changed ${formatChangeSummary(changedFields)}.`,
      });
      setActiveOverrideBlockId(null);
      setOverrideInstruction('');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Block override failed.';
      setGenerationError(message);
      setOverrideError(message);
      setGenerationStatus('');
      pushAgentNote("error", activeOverrideBlockId, message);
      toast.error('Block override failed.', {
        description: message,
      });
    } finally {
      setIsApplyingOverride(false);
    }
  };

  const handleGlobalOverride = async () => {
    if (!artifact || !globalOverrideInstruction.trim()) return;
    setIsApplyingGlobalOverride(true);
    setGenerationError('');
    setGlobalOverrideError('');
    setGenerationStatus('Redirecting whole artifact...');
    pushAgentNote("info", "Artifact", "Applying global override to the quick artifact.");
    try {
      const response = await fetch(`${API_BASE}/api/regenerate-quick-artifact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic,
          audience: audience === 'Other' ? customAudience : audience,
          tone,
          visual_mode: visualMode,
          artifact,
          source_manifest: buildQuickSourceManifest(),
          normalized_source_text: indexedNormalizedSourceText,
          source_text_origin: indexedSourceTextOrigin,
          content_signal: indexedSignal,
          instruction: globalOverrideInstruction,
        }),
      });
      const data = await response.json();
      if (!response.ok || data.status !== 'success' || !data.artifact) {
        throw new Error(data.message || 'Global override failed.');
      }
      const nextArtifact = {
        ...(data.artifact as QuickArtifact),
        reel: null,
      };
      setArtifact(nextArtifact);
      setReelError('');
      if (activeQuickView === 'reel') {
        void ensureQuickReel(nextArtifact);
      }
      setGenerationStatus('Artifact updated.');
      pushAgentNote("checkpoint", "Artifact", "Global override applied.");
      toast.success('Artifact updated.', {
        description: 'Quick artifact and proof reel state were refreshed.',
      });
      setIsGlobalOverrideOpen(false);
      setGlobalOverrideInstruction('');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Global override failed.';
      setGenerationError(message);
      setGlobalOverrideError(message);
      setGenerationStatus('');
      pushAgentNote("error", "Artifact", message);
      toast.error('Global override failed.', {
        description: message,
      });
    } finally {
      setIsApplyingGlobalOverride(false);
    }
  };

  const resolveSourceMediaUrl = (media: QuickSourceMedia) => {
    if (!activeSourceAsset || activeSourceAsset.asset_id !== media.asset_id) {
      return null;
    }
    if (activeSourceAsset.provider === 'youtube') {
      const videoId = extractYouTubeVideoId(activeSourceAsset.uri);
      if (!videoId) {
        return null;
      }
      return buildYouTubeEmbedUrl(videoId, media.start_ms ?? undefined, media.end_ms ?? undefined);
    }
    return buildMediaFragmentUrl(
      activeSourceAsset.uri,
      media.start_ms ?? undefined,
      media.end_ms ?? undefined,
    );
  };

  const heroSourceMedia = artifact?.blocks.flatMap((block) => block.source_media ?? []).find((media) => {
    if (media.modality === 'video') {
      return Boolean(resolveSourceMediaUrl(media));
    }
    return false;
  }) ?? null;
  const heroSourceMediaUrl = heroSourceMedia ? resolveSourceMediaUrl(heroSourceMedia) : null;
  const activeReel = artifact?.reel ?? null;

  return (
    <>
      <Toaster position="top-right" richColors closeButton />
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

      <div className="relative z-10 max-w-5xl mx-auto space-y-8">
        
        <div className="text-center space-y-2">
          <h1 className="text-4xl font-extrabold tracking-tight text-slate-100 drop-shadow-[0_2px_16px_rgba(2,6,23,0.75)]">ExplainFlow</h1>
          <p className="text-lg text-slate-200/95 drop-shadow-[0_1px_8px_rgba(2,6,23,0.6)]">Live Interleaved Generative Storyteller</p>
        </div>

        <Card className="bg-white text-slate-900 backdrop-blur-xl shadow-xl border-slate-300/70">
          <CardHeader>
            <CardTitle className="text-slate-900">Quick Generate</CardTitle>
            <CardDescription className="text-slate-600">Enter a topic and style to generate a complete visual explainer instantly.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleGenerate} className="high-contrast-form-labels grid grid-cols-1 md:grid-cols-2 gap-6">
              
              <div className="space-y-2 md:col-span-2">
                <div className="flex items-center justify-between gap-3">
                  <Label htmlFor="topic">Prompt</Label>
                  <Button
                    type="button"
                    variant={isListening ? "default" : "outline"}
                    size="sm"
                    onClick={toggleVoiceInput}
                    className="shrink-0"
                  >
                    {isListening ? (
                      <>
                        <Square className="mr-2 h-4 w-4" />
                        Stop Listening
                      </>
                    ) : (
                      <>
                        <Mic className="mr-2 h-4 w-4" />
                        Voice Prompt
                      </>
                    )}
                  </Button>
                </div>
                <Input
                  id="topic"
                  value={topic}
                  onChange={e => setTopic(e.target.value)}
                  placeholder="Create visuals that explain [topic/problem] for [audience], tone [tone]."
                  required
                  className="text-lg bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
                />
                <p className="text-xs text-slate-600">
                  Example: &quot;Create visuals explaining model context protocols for PMs, tone practical and clear.&quot;
                </p>
                {speechError && (
                  <p className="text-xs text-rose-600 font-medium">{speechError}</p>
                )}
              </div>

              <div className="space-y-4 md:col-span-2 rounded-[28px] border border-slate-200 bg-slate-50/90 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-slate-700 shadow-[0_10px_24px_rgba(15,23,42,0.08)]">
                      <Clapperboard className="h-5 w-5" />
                    </span>
                    <div className="space-y-1">
                      <Label className="text-sm font-semibold text-slate-900">Source Video or YouTube URL (Optional)</Label>
                      <p className="max-w-2xl text-sm leading-6 text-slate-600">
                        Quick can index an uploaded clip or a YouTube URL, use transcript/captions as the truth layer, and reuse clip-backed proof inside the HTML artifact.
                      </p>
                    </div>
                  </div>
                  <input
                    ref={sourceFileInputRef}
                    type="file"
                    accept="video/*"
                    className="hidden"
                    onChange={handleVideoAssetUpload}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    className="rounded-full"
                    onClick={() => sourceFileInputRef.current?.click()}
                    disabled={isUploadingSource}
                  >
                    {isUploadingSource ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Upload className="mr-2 h-4 w-4" />
                    )}
                    {uploadedVideoAsset ? 'Replace Video' : 'Upload Video'}
                  </Button>
                </div>

                <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
                  <div className="space-y-2">
                    <Label htmlFor="sourceVideoUrl">YouTube URL</Label>
                    <div className="flex gap-3">
                      <Input
                        id="sourceVideoUrl"
                        value={sourceVideoUrl}
                        onChange={(event) => {
                          setSourceVideoUrl(event.target.value);
                          clearIndexedSource();
                        }}
                        placeholder="https://www.youtube.com/watch?v=..."
                        className="bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
                      />
                      {sourceVideoUrl.trim() ? (
                        <Button
                          type="button"
                          variant="outline"
                          className="shrink-0 rounded-full"
                          onClick={removeYoutubeSource}
                        >
                          Clear
                        </Button>
                      ) : null}
                    </div>
                    <p className="text-xs leading-5 text-slate-600">
                      First version: YouTube URLs work only with pasted transcript or subtitles. ExplainFlow does not download the video.
                    </p>
                    <Label htmlFor="sourceTranscript">Transcript or Captions</Label>
                    <Textarea
                      id="sourceTranscript"
                      value={sourceTranscript}
                      onChange={(event) => {
                        setSourceTranscript(event.target.value);
                        clearIndexedSource();
                      }}
                      placeholder="Paste transcript or captions here. Required for YouTube URLs and for videos longer than 2 minutes."
                      className="min-h-[148px] bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
                    />
                    <p className="text-xs leading-5 text-slate-600">
                      ExplainFlow uses transcript text as the main truth layer, then consults video frames only for “this chart,” “as you can see,” clip-worthy moments, and proof playback.
                    </p>
                  </div>

                  <div className="space-y-3 rounded-[24px] border border-slate-200 bg-white p-4">
                    <div className="flex items-center gap-3">
                      <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-100 text-slate-700">
                        <PlayCircle className="h-5 w-5" />
                      </span>
                      <div>
                        <p className="text-sm font-semibold text-slate-900">Video Constraints</p>
                        <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Quick v1</p>
                      </div>
                    </div>
                    <div className="space-y-2 text-sm leading-6 text-slate-600">
                      <p>Uploaded videos up to 2 minutes work without transcript.</p>
                      <p>Uploaded videos up to 10 minutes require transcript or captions.</p>
                      <p>YouTube URLs require transcript or subtitles and stay transcript-first.</p>
                    </div>
                    {youtubeSourceAsset ? (
                      <div className="space-y-3 rounded-[20px] border border-slate-200 bg-slate-50 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                                YouTube
                              </span>
                            </div>
                            <p className="text-sm font-medium text-slate-900">{youtubeSourceAsset.title || 'YouTube source'}</p>
                          </div>
                        </div>
                        {youtubeSourceAsset.embed_url ? (
                          <iframe
                            title="YouTube source preview"
                            src={youtubeSourceAsset.embed_url}
                            className="h-[220px] w-full rounded-2xl border border-slate-200 bg-slate-950"
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                            allowFullScreen
                          />
                        ) : null}
                      </div>
                    ) : uploadedVideoAsset ? (
                      <div className="space-y-3 rounded-[20px] border border-slate-200 bg-slate-50 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                                Video
                              </span>
                              {uploadedVideoAsset.duration_ms ? (
                                <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                                  {formatMilliseconds(uploadedVideoAsset.duration_ms)}
                                </span>
                              ) : null}
                            </div>
                            <p className="text-sm font-medium text-slate-900">{uploadedVideoAsset.title || 'Uploaded video'}</p>
                          </div>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="rounded-full text-slate-500"
                            onClick={removeUploadedVideoAsset}
                          >
                            Remove
                          </Button>
                        </div>
                        <video
                          controls
                          preload="metadata"
                          className="w-full rounded-2xl border border-slate-200 bg-slate-950"
                          src={uploadedVideoAsset.uri}
                        />
                      </div>
                    ) : (
                      <div className="rounded-[20px] border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">
                        No source video attached yet. Quick will still work from the prompt alone, or from a YouTube URL plus transcript.
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="space-y-3 md:col-span-2">
                <Label>Target Audience</Label>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                  {QUICK_AUDIENCE_TILES.map((tile) => {
                    const isSelected = audience === tile.value;
                    const Icon = tile.icon;
                    return (
                      <button
                        key={tile.value}
                        type="button"
                        onClick={() => setAudience(tile.value)}
                        className={`rounded-[24px] border p-4 text-left transition-all duration-200 ${
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
                            <p className="text-[11px] uppercase tracking-[0.14em] text-slate-600">
                              {isSelected ? 'Selected' : 'Tap to select'}
                            </p>
                          </div>
                        </div>
                        <p className="text-sm leading-6 text-slate-700/90">{tile.description}</p>
                      </button>
                    );
                  })}
                </div>
              </div>

              {audience === 'Other' && (
                <div className="space-y-2 md:col-span-2">
                  <Label htmlFor="customAudience">Specify Audience</Label>
                  <Input 
                    id="customAudience" 
                    value={customAudience} 
                    onChange={e => setCustomAudience(e.target.value)} 
                    placeholder="e.g. 5-year old children, investors..." 
                    required 
                    className="bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
                  />
                </div>
              )}

              <div className="space-y-3 md:col-span-2">
                <Label>Visual Style</Label>
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
                  {QUICK_VISUAL_TILES.map((tile) => {
                    const isSelected = visualMode === tile.value;
                    const Icon = tile.icon;
                    return (
                      <button
                        key={tile.value}
                        type="button"
                        onClick={() => setVisualMode(tile.value)}
                        className={`rounded-[24px] border p-4 text-left transition-all duration-200 ${
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
                            <p className="text-[11px] uppercase tracking-[0.14em] text-slate-600">
                              {isSelected ? 'Selected' : 'Tap to select'}
                            </p>
                          </div>
                        </div>
                        <p className="text-sm leading-6 text-slate-700/90">{tile.description}</p>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="tone">Tone of Voice (Optional)</Label>
                <Input 
                  id="tone" 
                  value={tone} 
                  onChange={e => setTone(e.target.value)} 
                  placeholder="e.g. Engaging, Professional, Humorous" 
                  className="bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
                />
                <div className="flex flex-wrap gap-2 pt-1">
                  {QUICK_TONE_PRESETS.map((preset) => {
                    const isSelected = tone.trim().toLowerCase() === preset.toLowerCase();
                    return (
                      <button
                        key={preset}
                        type="button"
                        onClick={() => setTone(preset)}
                        className={`rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.12em] transition-colors ${
                          isSelected
                            ? 'border-slate-900 bg-slate-900 text-white'
                            : 'border-slate-300 bg-slate-50 text-slate-700 hover:border-slate-400 hover:bg-slate-100'
                        }`}
                      >
                        {preset}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="md:col-span-2 pt-4">
                <Button
                  type="submit"
                  className={QUICK_PRIMARY_ACTION_CARD_CLASS}
                  disabled={isGenerating || isUploadingSource}
                  size="lg"
                >
                  <span className="flex w-full items-center justify-between gap-4">
                    <span className="space-y-1 text-left">
                      <span className={QUICK_PRIMARY_ACTION_LABEL_CLASS}>
                        Primary Action
                      </span>
                      <span className="block text-base font-semibold">
                        {isGenerating ? 'Generating Quick Artifact...' : 'Generate Quick Artifact'}
                      </span>
                    </span>
                    {isGenerating ? (
                      <Loader2 className="h-5 w-5 animate-spin text-slate-100" />
                    ) : null}
                  </span>
                </Button>
              </div>

              {(generationStatus || generationError || isGenerating) && (
                <div className="md:col-span-2 space-y-2">
                  {generationStatus && (
                    <p className="text-sm text-blue-700 font-medium">{generationStatus}</p>
                  )}
                  {isGenerating && (
                    <div className="flex items-center gap-2 text-xs text-slate-600">
                      <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                      <span>
                        {activeSourceAsset
                          ? `Indexing transcript-backed ${activeSourceAsset.provider === 'youtube' ? 'YouTube' : 'video'} context, then building lightweight artifact blocks.`
                          : 'Generating lightweight artifact blocks for immediate rendering.'}
                      </span>
                    </div>
                  )}
                  {generationError && (
                    <p className="text-sm text-rose-600 font-medium">{generationError}</p>
                  )}
                </div>
              )}
            </form>
          </CardContent>
        </Card>

        <AgentActivityPanel
          title="Agent Session Notes"
          subtitle="Checkpoint, QA, and traceability events while the stream runs."
          notes={agentNotes}
          currentStatus={generationStatus}
        />

        <div className="space-y-6 mt-12">
          {artifact && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-4">
                <h2 className="text-2xl font-bold tracking-tight text-slate-100">
                  {activeQuickView === 'artifact' ? 'Quick Artifact' : 'Proof Reel'}
                </h2>
                <div className="inline-flex rounded-full border border-white/15 bg-white/10 p-1">
                  <button
                    type="button"
                    onClick={() => setActiveQuickView('artifact')}
                    className={`rounded-full px-4 py-2 text-sm font-semibold transition-colors ${
                      activeQuickView === 'artifact'
                        ? 'bg-white text-slate-950'
                        : 'text-slate-200 hover:text-white'
                    }`}
                  >
                    Artifact
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveQuickView('reel');
                      void ensureQuickReel();
                    }}
                    className={`rounded-full px-4 py-2 text-sm font-semibold transition-colors ${
                      activeQuickView === 'reel'
                        ? 'bg-white text-slate-950'
                        : 'text-slate-200 hover:text-white'
                    }`}
                  >
                    Proof Reel
                  </button>
                </div>
              </div>

              <Card className="overflow-hidden border-white/15 bg-white/95 text-slate-900 shadow-[0_26px_60px_rgba(15,23,42,0.28)]">
                <CardContent className="grid gap-6 p-6 lg:grid-cols-[1.25fr_0.75fr]">
                  <div className="space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge className="rounded-full bg-slate-900 text-white hover:bg-slate-900">
                          Quick Mode
                        </Badge>
                        <Badge variant="outline" className="rounded-full border-slate-300 text-slate-600">
                          {artifact.visual_style}
                        </Badge>
                        {activeSourceAsset ? (
                          <Badge variant="outline" className="rounded-full border-slate-300 text-slate-600">
                            {activeSourceAsset.provider === 'youtube' ? 'YouTube Transcript-Backed' : 'Uploaded Video'}
                          </Badge>
                        ) : null}
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="gap-2 rounded-full"
                        onClick={() => {
                          setIsGlobalOverrideOpen(true);
                          setGlobalOverrideInstruction('');
                        }}
                      >
                        <Wand2 className="h-4 w-4" />
                        Redirect Whole Artifact
                      </Button>
                    </div>
                    <div className="space-y-2">
                      <h3 className="text-3xl font-semibold tracking-tight text-slate-950">{artifact.title}</h3>
                      <p className="text-lg text-slate-600">{artifact.subtitle}</p>
                    </div>
                    <p className="max-w-3xl text-base leading-7 text-slate-700">{artifact.summary}</p>
                  </div>
                  <div className="rounded-[28px] border border-slate-200 bg-slate-50 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.9)]">
                    <div className="flex items-center gap-3">
                      <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-900 text-white">
                        <PanelTop className="h-5 w-5" />
                      </span>
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                          {artifact.hero_image_url ? 'Hero Visual' : heroSourceMediaUrl ? 'Hero Clip' : 'Hero Direction'}
                        </p>
                        <p className="text-sm font-medium text-slate-900">{artifact.hero_direction}</p>
                      </div>
                    </div>
                    {artifact.hero_image_url ? (
                      <div className="mt-4 overflow-hidden rounded-[24px] border border-slate-200 bg-slate-950">
                        <img
                          src={artifact.hero_image_url}
                          alt={artifact.title}
                          className="h-[220px] w-full object-cover"
                        />
                      </div>
                    ) : heroSourceMediaUrl ? (
                      <div className="mt-4 overflow-hidden rounded-[24px] border border-slate-200 bg-slate-950">
                        {activeSourceAsset?.provider === 'youtube' ? (
                          <iframe
                            title={`${artifact.title} hero clip`}
                            src={heroSourceMediaUrl}
                            className="h-[220px] w-full"
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                            allowFullScreen
                          />
                        ) : (
                          <video
                            controls
                            preload="metadata"
                            className="h-[220px] w-full object-cover"
                            src={heroSourceMediaUrl}
                          />
                        )}
                      </div>
                    ) : null}
                    <p className="mt-4 text-sm leading-6 text-slate-600">
                      This Quick artifact is rendered as HTML-first modules so each block can be steered independently without rerunning the whole workflow.
                      {activeSourceAsset ? ` Source-backed blocks can also carry direct proof clips from the ${activeSourceAsset.provider === 'youtube' ? 'YouTube source' : 'uploaded video'}.` : ''}
                    </p>
                  </div>
                </CardContent>
              </Card>

              {activeQuickView === 'artifact' ? (
                <div className="grid gap-5 lg:grid-cols-2">
                  {artifact.blocks.map((block, index) => {
                    const primaryBlockMedia = block.source_media[0] ?? null;
                    const primaryBlockMediaUrl = primaryBlockMedia ? resolveSourceMediaUrl(primaryBlockMedia) : null;
                    return (
                      <Card key={block.block_id} className="overflow-hidden border-white/15 bg-white/95 text-slate-900 shadow-[0_20px_44px_rgba(15,23,42,0.18)]">
                        <CardContent className="space-y-5 p-6">
                          <div className="flex items-start justify-between gap-4">
                            <div className="space-y-2">
                              <div className="flex flex-wrap items-center gap-2">
                                <Badge variant="outline" className="rounded-full border-slate-300 text-[11px] uppercase tracking-[0.16em] text-slate-500">
                                  {block.label}
                                </Badge>
                                <Badge className="rounded-full bg-slate-100 text-slate-700 hover:bg-slate-100">
                                  {block.emphasis}
                                </Badge>
                              </div>
                              <h3 className="text-xl font-semibold text-slate-950">
                                {index + 1}. {block.title}
                              </h3>
                            </div>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="gap-2 rounded-full"
                          onClick={() => {
                            setActiveOverrideBlockId(block.block_id);
                            setOverrideInstruction('');
                            setOverrideError('');
                          }}
                        >
                          <Wand2 className="h-4 w-4" />
                          Direct Block
                            </Button>
                          </div>

                          {(block.image_url || primaryBlockMediaUrl) ? (
                            <div className="rounded-[22px] border border-slate-200 bg-slate-50 p-4">
                              <div className="flex items-center gap-2">
                                <PanelTop className="h-4 w-4 text-slate-700" />
                                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                                  {block.image_url ? 'Block Visual' : primaryBlockMedia?.modality === 'video' ? 'Source Clip' : 'Source Visual'}
                                </p>
                              </div>
                              {block.image_url ? (
                                <div className="mt-3 overflow-hidden rounded-[18px] border border-slate-200 bg-slate-950">
                                  <img
                                    src={block.image_url}
                                    alt={block.title}
                                    className="h-[220px] w-full object-cover"
                                  />
                                </div>
                              ) : primaryBlockMediaUrl && primaryBlockMedia?.modality === 'video' ? (
                                <div className="mt-3 overflow-hidden rounded-[18px] border border-slate-200 bg-slate-950">
                                  {activeSourceAsset?.provider === 'youtube' ? (
                                    <iframe
                                      title={`${block.title} source visual`}
                                      src={primaryBlockMediaUrl}
                                      className="h-[220px] w-full"
                                      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                      allowFullScreen
                                    />
                                  ) : (
                                    <video
                                      controls
                                      preload="metadata"
                                      className="h-[220px] w-full object-cover"
                                      src={primaryBlockMediaUrl}
                                    />
                                  )}
                                </div>
                              ) : null}
                            </div>
                          ) : null}

                          <p className="text-sm leading-7 text-slate-700">{block.body}</p>

                          {block.bullets.length > 0 && (
                            <div className="space-y-2">
                              {block.bullets.map((bullet) => (
                                <div key={bullet} className="flex items-start gap-2 text-sm leading-6 text-slate-600">
                                  <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                                  <span>{bullet}</span>
                                </div>
                              ))}
                            </div>
                          )}

                          {(!block.image_url || block.claim_refs.length > 0) ? (
                            <div className="rounded-[22px] border border-slate-200 bg-slate-50 p-4">
                              {!block.image_url ? (
                                <>
                                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Visual Direction</p>
                                  <p className="mt-2 text-sm leading-6 text-slate-700">{block.visual_direction}</p>
                                </>
                              ) : null}
                              {block.claim_refs.length > 0 ? (
                                <div className={block.image_url ? '' : 'mt-3'}>
                                  <div className="flex flex-wrap gap-2">
                                    {block.claim_refs.map((claimRef) => (
                                      <Badge key={claimRef} variant="outline" className="rounded-full border-slate-300 text-slate-600">
                                        {claimRef}
                                      </Badge>
                                    ))}
                                  </div>
                                </div>
                              ) : null}
                            </div>
                          ) : null}

                          {block.source_media.length > 0 && (
                            <div className="rounded-[22px] border border-emerald-200 bg-emerald-50/70 p-4">
                              <div className="flex items-center gap-2">
                                <PlayCircle className="h-4 w-4 text-emerald-700" />
                                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-700">
                                  Source Proof
                                </p>
                              </div>
                              <div className="mt-3 space-y-4">
                                {block.source_media.map((media) => {
                                  const mediaUrl = resolveSourceMediaUrl(media);
                                  const rangeLabel = formatTimeRangeLabel(media.start_ms, media.end_ms);
                                  return (
                                    <div key={`${block.block_id}-${media.asset_id}-${media.start_ms ?? 'start'}`} className="space-y-3 rounded-[18px] border border-emerald-200 bg-white p-3">
                                      <div className="flex flex-wrap items-center gap-2">
                                        <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-emerald-700">
                                          {media.modality === 'video' ? 'Clip' : media.modality}
                                        </span>
                                        {rangeLabel ? (
                                          <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                                            {rangeLabel}
                                          </span>
                                        ) : null}
                                      </div>
                                      {media.label ? (
                                        <p className="text-sm font-medium text-slate-900">{media.label}</p>
                                      ) : null}
                                      {media.visual_context ? (
                                        <p className="text-sm leading-6 text-slate-600">{media.visual_context}</p>
                                      ) : media.quote_text ? (
                                        <p className="text-sm leading-6 text-slate-600">{media.quote_text}</p>
                                      ) : null}
                                      {media.modality === 'video' && mediaUrl ? (
                                        activeSourceAsset?.provider === 'youtube' ? (
                                          <iframe
                                            title={`${block.title} source clip`}
                                            src={mediaUrl}
                                            className="h-[220px] w-full rounded-2xl border border-emerald-200 bg-slate-950"
                                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                            allowFullScreen
                                          />
                                        ) : (
                                          <video
                                            controls
                                            preload="metadata"
                                            className="w-full rounded-2xl border border-emerald-200 bg-slate-950"
                                            src={mediaUrl}
                                          />
                                        )
                                      ) : null}
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              ) : (
                <div className="space-y-5">
                  {isBuildingReel ? (
                    <Card className="border-white/15 bg-white/95 text-slate-900 shadow-[0_20px_44px_rgba(15,23,42,0.18)]">
                      <CardContent className="flex items-center gap-3 p-6 text-sm text-slate-600">
                        <Loader2 className="h-5 w-5 animate-spin text-slate-700" />
                        Building Proof Reel from the current quick blocks.
                      </CardContent>
                    </Card>
                  ) : null}

                  {reelError ? (
                    <Card className="border-rose-200 bg-rose-50 text-rose-900 shadow-[0_20px_44px_rgba(15,23,42,0.12)]">
                      <CardContent className="p-6 text-sm font-medium">
                        {reelError}
                      </CardContent>
                    </Card>
                  ) : null}

                  {activeReel ? (
                    <>
                      <Card className="overflow-hidden border-white/15 bg-white/95 text-slate-900 shadow-[0_20px_44px_rgba(15,23,42,0.18)]">
                        <CardContent className="space-y-3 p-6">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge className="rounded-full bg-slate-900 text-white hover:bg-slate-900">
                              Proof Reel v1
                            </Badge>
                            <Badge variant="outline" className="rounded-full border-slate-300 text-slate-600">
                              {activeReel.segments.length} Segments
                            </Badge>
                          </div>
                          <div>
                            <h3 className="text-2xl font-semibold text-slate-950">{activeReel.title}</h3>
                            <p className="mt-2 text-sm leading-6 text-slate-600">{activeReel.summary}</p>
                          </div>
                        </CardContent>
                      </Card>

                      <div className="space-y-5">
                        {activeReel.segments.map((segment, index) => {
                          const segmentMediaUrl = segment.primary_media ? resolveSourceMediaUrl(segment.primary_media) : null;
                          const segmentRangeLabel = formatTimeRangeLabel(segment.start_ms, segment.end_ms);
                          return (
                            <Card key={segment.segment_id} className="overflow-hidden border-white/15 bg-white/95 text-slate-900 shadow-[0_20px_44px_rgba(15,23,42,0.18)]">
                              <CardContent className="space-y-5 p-6">
                                <div className="flex flex-wrap items-start justify-between gap-4">
                                  <div className="space-y-2">
                                    <div className="flex flex-wrap items-center gap-2">
                                      <Badge variant="outline" className="rounded-full border-slate-300 text-[11px] uppercase tracking-[0.16em] text-slate-500">
                                        Segment {index + 1}
                                      </Badge>
                                      <Badge className="rounded-full bg-slate-100 text-slate-700 hover:bg-slate-100">
                                        {segment.render_mode.replace('_', ' ')}
                                      </Badge>
                                      {segmentRangeLabel ? (
                                        <Badge variant="outline" className="rounded-full border-slate-300 text-slate-600">
                                          {segmentRangeLabel}
                                        </Badge>
                                      ) : null}
                                      {segment.timing_inferred ? (
                                        <Badge variant="outline" className="rounded-full border-amber-300 text-amber-700">
                                          Timing Inferred
                                        </Badge>
                                      ) : null}
                                    </div>
                                    <h3 className="text-xl font-semibold text-slate-950">{segment.title}</h3>
                                  </div>
                                </div>

                                {(segment.render_mode === 'source_clip' || segment.render_mode === 'hybrid') && segment.primary_media ? (
                                  <div className="rounded-[22px] border border-slate-200 bg-slate-50 p-4">
                                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                                      Source Clip
                                    </p>
                                    {segmentMediaUrl && segment.primary_media.modality === 'video' ? (
                                      <div className="mt-3 overflow-hidden rounded-[18px] border border-slate-200 bg-slate-950">
                                        {activeSourceAsset?.provider === 'youtube' ? (
                                          <iframe
                                            title={`${segment.title} proof reel clip`}
                                            src={segmentMediaUrl}
                                            className="h-[240px] w-full"
                                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                            allowFullScreen
                                          />
                                        ) : (
                                          <video
                                            controls
                                            preload="metadata"
                                            className="h-[240px] w-full object-cover"
                                            src={segmentMediaUrl}
                                          />
                                        )}
                                      </div>
                                    ) : null}
                                    {segment.primary_media.label ? (
                                      <p className="mt-3 text-sm leading-6 text-slate-600">{segment.primary_media.label}</p>
                                    ) : null}
                                  </div>
                                ) : null}

                                {(segment.render_mode === 'generated_image' || segment.render_mode === 'hybrid') && segment.fallback_image_url ? (
                                  <div className="rounded-[22px] border border-slate-200 bg-slate-50 p-4">
                                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                                      Generated Frame
                                    </p>
                                    <div className="mt-3 overflow-hidden rounded-[18px] border border-slate-200 bg-slate-950">
                                      <img
                                        src={segment.fallback_image_url}
                                        alt={segment.title}
                                        className="h-[240px] w-full object-cover"
                                      />
                                    </div>
                                  </div>
                                ) : null}

                                <div className="rounded-[22px] border border-slate-200 bg-slate-50 p-4">
                                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                                    Caption
                                  </p>
                                  <p className="mt-2 text-sm leading-7 text-slate-700">{segment.caption_text}</p>
                                  {segment.claim_refs.length > 0 ? (
                                    <div className="mt-3 flex flex-wrap gap-2">
                                      {segment.claim_refs.map((claimRef) => (
                                        <Badge key={claimRef} variant="outline" className="rounded-full border-slate-300 text-slate-600">
                                          {claimRef}
                                        </Badge>
                                      ))}
                                    </div>
                                  ) : null}
                                </div>
                              </CardContent>
                            </Card>
                          );
                        })}
                      </div>
                    </>
                  ) : null}
                </div>
              )}
            </>
          )}
        </div>

        <Dialog open={Boolean(activeOverrideBlockId)} onOpenChange={(open) => {
          if (!open) {
            setActiveOverrideBlockId(null);
            setOverrideInstruction('');
            setOverrideError('');
          }
        }}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Direct This Block</DialogTitle>
              <DialogDescription>
                Apply a local override to one quick-artifact block without regenerating the whole artifact.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3 py-2">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                <div className="flex items-center gap-2 font-medium text-slate-900">
                  <Bot className="h-4 w-4" />
                  Local override only
                </div>
                <p className="mt-2 leading-6">
                  Good directions: simplify this block, make it more executive, shift the visual to a flowchart, or tighten the takeaway.
                </p>
              </div>
              <Textarea
                value={overrideInstruction}
                onChange={(event) => setOverrideInstruction(event.target.value)}
                placeholder="e.g. Make this block more executive and switch the visual to a cleaner diagram."
                className="min-h-[120px]"
              />
              {overrideError ? (
                <p className="text-sm font-medium text-rose-600">{overrideError}</p>
              ) : null}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => {
                setActiveOverrideBlockId(null);
                setOverrideInstruction('');
                setOverrideError('');
              }}>
                Cancel
              </Button>
              <Button onClick={handleOverrideBlock} disabled={isApplyingOverride || !overrideInstruction.trim()}>
                {isApplyingOverride ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Wand2 className="mr-2 h-4 w-4" />}
                Apply Override
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog open={isGlobalOverrideOpen} onOpenChange={(open) => {
          setIsGlobalOverrideOpen(open);
          if (!open) {
            setGlobalOverrideInstruction('');
            setGlobalOverrideError('');
          }
        }}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Redirect Whole Artifact</DialogTitle>
              <DialogDescription>
                Apply a global direction change across the quick artifact. This is the future Live handoff seam for “from here on out” control.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3 py-2">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                <div className="flex items-center gap-2 font-medium text-slate-900">
                  <Bot className="h-4 w-4" />
                  Global override
                </div>
                <p className="mt-2 leading-6">
                  Good directions: make the artifact more academic, compress the whole draft, or shift the visual language toward cleaner executive panels.
                </p>
              </div>
              <Textarea
                value={globalOverrideInstruction}
                onChange={(event) => setGlobalOverrideInstruction(event.target.value)}
                placeholder="e.g. Make the whole artifact more executive, cut the copy by 20%, and prefer cleaner diagrammatic framing."
                className="min-h-[120px]"
              />
              {globalOverrideError ? (
                <p className="text-sm font-medium text-rose-600">{globalOverrideError}</p>
              ) : null}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => {
                setIsGlobalOverrideOpen(false);
                setGlobalOverrideInstruction('');
                setGlobalOverrideError('');
              }}>
                Cancel
              </Button>
              <Button onClick={handleGlobalOverride} disabled={isApplyingGlobalOverride || !globalOverrideInstruction.trim()}>
                {isApplyingGlobalOverride ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Wand2 className="mr-2 h-4 w-4" />}
                Apply Global Override
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

      </div>
      </main>
    </>
  );
}
