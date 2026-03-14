"use client";

import Image from 'next/image';
import React, { useEffect, useRef, useState } from 'react';
import AgentActivityPanel, { AgentNote, AgentNoteType } from '@/components/AgentActivityPanel';
import QuickArtifactView from '@/components/QuickArtifactView';
import QuickArtifactSummary from '@/components/QuickArtifactSummary';
import QuickSourceForm from '@/components/QuickSourceForm';
import ProofPlaylistPlayer, { type ProofPlaylistSegment } from '@/components/ProofPlaylistPlayer';
import QuickReelView from '@/components/QuickReelView';
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import {
  Bot,
  Loader2,
  Wand2,
} from "lucide-react";
import {
  type PlaylistPresentationMode,
  type QuickArtifact,
  type QuickArtifactBlock,
  type QuickReelSegment,
  type QuickSourceMedia,
  type UploadedQuickSourceAsset,
  formatMilliseconds,
  formatTimeRangeLabel,
} from "@/lib/quick";
import { Toaster, toast } from "sonner";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const apiHeaders = (extra?: Record<string, string>): Record<string, string> => {
  const key = process.env.NEXT_PUBLIC_RATE_LIMIT_BYPASS_KEY;
  return {
    ...(key ? { "X-RateLimit-Bypass": key } : {}),
    ...extra,
  };
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

const quickIndexingCopy = (
  asset: UploadedQuickSourceAsset,
  hasTranscript: boolean,
) => {
  if (asset.provider === 'youtube') {
    return {
      startStatus: 'Indexing YouTube transcript...',
      startNote: 'Transcript-backed YouTube indexing started.',
      completeNote: 'YouTube indexing complete. Building artifact from transcript-backed signal.',
      reuseStatus: 'Reusing indexed YouTube signal...',
      reuseNote: 'Reusing previously indexed YouTube signal for a faster quick artifact pass.',
    };
  }

  if (hasTranscript) {
    return {
      startStatus: 'Indexing source video with transcript...',
      startNote: 'Transcript-backed video indexing started.',
      completeNote: 'Video indexing complete. Building artifact from transcript-backed signal.',
      reuseStatus: 'Reusing indexed transcript-backed video signal...',
      reuseNote: 'Reusing previously indexed transcript-backed video signal for a faster quick artifact pass.',
    };
  }

  return {
    startStatus: 'Indexing source video...',
    startNote: 'Source-backed video indexing started.',
    completeNote: 'Video indexing complete. Building artifact from source-backed signal.',
    reuseStatus: 'Reusing indexed source-backed video signal...',
    reuseNote: 'Reusing previously indexed source-backed video signal for a faster quick artifact pass.',
  };
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

const quickVideoFilename = (videoUrl: string, artifactTitle?: string | null) => {
  try {
    const parsed = new URL(videoUrl);
    const assetName = parsed.pathname.split('/').filter(Boolean).pop();
    if (assetName) {
      return assetName;
    }
  } catch {
    // Fall back to a title-based filename below.
  }

  const normalizedTitle = (artifactTitle || 'quick-proof-reel')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48);
  return `${normalizedTitle || 'quick-proof-reel'}.mp4`;
};

const estimatePlaylistSlideDurationMs = (text: string) => {
  const wordCount = text.trim().split(/\s+/).filter(Boolean).length;
  const estimatedMs = Math.round((wordCount / 200) * 60000) + 2000;
  return Math.max(4000, Math.min(12000, estimatedMs || 4000));
};

const estimateClipDurationMs = (startMs?: number | null, endMs?: number | null) => {
  if (
    typeof startMs === 'number'
    && typeof endMs === 'number'
    && Number.isFinite(startMs)
    && Number.isFinite(endMs)
    && endMs > startMs
  ) {
    return endMs - startMs;
  }
  return 6000;
};

const buildYouTubePlaylistEmbedUrl = (videoId: string, startMs?: number | null, endMs?: number | null) => {
  const embedUrl = new URL(buildYouTubeEmbedUrl(videoId, startMs, endMs));
  embedUrl.searchParams.set('autoplay', '1');
  embedUrl.searchParams.set('mute', '1');
  embedUrl.searchParams.set('playsinline', '1');
  return embedUrl.toString();
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
  const [isHydratingArtifactVisuals, setIsHydratingArtifactVisuals] = useState(false);
  const [generationStatus, setGenerationStatus] = useState('');
  const [generationError, setGenerationError] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [speechError, setSpeechError] = useState('');
  const [artifact, setArtifact] = useState<QuickArtifact | null>(null);
  const [activeQuickView, setActiveQuickView] = useState<'artifact' | 'reel'>('artifact');
  const [isBuildingReel, setIsBuildingReel] = useState(false);
  const [reelError, setReelError] = useState('');
  const [isRenderingVideo, setIsRenderingVideo] = useState(false);
  const [isDownloadingVideo, setIsDownloadingVideo] = useState(false);
  const [videoError, setVideoError] = useState('');
  const [selectedPlaylistSegmentIds, setSelectedPlaylistSegmentIds] = useState<string[]>([]);
  const [playlistPresentationOverrides, setPlaylistPresentationOverrides] = useState<Record<string, PlaylistPresentationMode>>({});
  const [unmuteLocalSourceClips, setUnmuteLocalSourceClips] = useState(false);
  const [isPlaylistOpen, setIsPlaylistOpen] = useState(false);
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
  const artifactRef = useRef<QuickArtifact | null>(null);
  const activeQuickViewRef = useRef<'artifact' | 'reel'>('artifact');
  const artifactVisualPassRef = useRef(0);
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
      artifactVisualPassRef.current += 1;
      recognitionRef.current?.stop();
      recognitionRef.current = null;
    };
  }, []);

  useEffect(() => {
    artifactRef.current = artifact;
  }, [artifact]);

  useEffect(() => {
    activeQuickViewRef.current = activeQuickView;
  }, [activeQuickView]);

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

  const artifactNeedsVisualHydration = (artifactDraft: QuickArtifact) => (
    !artifactDraft.hero_image_url?.trim()
    || artifactDraft.blocks.some((block) => !block.image_url?.trim())
  );

  const artifactVisualsRequireReelRefresh = (
    previousArtifact: QuickArtifact,
    nextArtifact: QuickArtifact,
  ) => {
    if (!previousArtifact.reel?.segments?.length) {
      return false;
    }

    const reelImageByBlockId = new Map(
      previousArtifact.reel.segments.map((segment) => [
        segment.block_id,
        segment.fallback_image_url?.trim() || '',
      ]),
    );

    return nextArtifact.blocks.some((block) => {
      const nextImageUrl = block.image_url?.trim() || '';
      if (!nextImageUrl) {
        return false;
      }
      const reelImageUrl = reelImageByBlockId.get(block.block_id) || '';
      return reelImageUrl !== nextImageUrl;
    });
  };

  const invalidateQuickArtifactHydration = () => {
    artifactVisualPassRef.current += 1;
    setIsHydratingArtifactVisuals(false);
  };

  const hydrateQuickArtifactVisuals = async ({
    artifactDraft,
    contentSignalDraft,
    sourceManifestDraft,
    pendingStatus,
    completeStatus,
  }: {
    artifactDraft: QuickArtifact;
    contentSignalDraft: Record<string, unknown> | null;
    sourceManifestDraft?: ReturnType<typeof buildQuickSourceManifest>;
    pendingStatus: string;
    completeStatus: string;
  }) => {
    if (!artifactNeedsVisualHydration(artifactDraft)) {
      return artifactDraft;
    }

    const passId = artifactVisualPassRef.current + 1;
    artifactVisualPassRef.current = passId;
    setIsHydratingArtifactVisuals(true);
    setGenerationStatus((prev) => (
      !prev || prev === completeStatus || prev.startsWith('Quick artifact ready')
        ? pendingStatus
        : prev
    ));
    pushAgentNote("info", "Visuals", "Rendering Quick artifact visuals in the background.");

    try {
      const response = await fetch(`${API_BASE}/api/hydrate-quick-artifact-visuals`, {
        method: 'POST',
        headers: apiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          topic,
          audience: audience === 'Other' ? customAudience : audience,
          tone,
          visual_mode: visualMode,
          artifact: artifactDraft,
          source_manifest: sourceManifestDraft,
          content_signal: contentSignalDraft ?? {},
        }),
      });
      const data = await response.json();
      if (!response.ok || data.status !== 'success' || !data.artifact) {
        throw new Error(data.detail || data.message || 'Quick artifact visual hydration failed.');
      }

      if (artifactVisualPassRef.current !== passId) {
        return artifactRef.current;
      }

      const hydratedArtifact = data.artifact as QuickArtifact;
      const currentArtifact = artifactRef.current;
      if (!currentArtifact || currentArtifact.artifact_id !== hydratedArtifact.artifact_id) {
        return currentArtifact;
      }

      const mergedArtifact: QuickArtifact = {
        ...hydratedArtifact,
        reel: currentArtifact.reel ?? hydratedArtifact.reel,
        video: currentArtifact.video ?? hydratedArtifact.video,
      };
      const shouldRefreshReel = artifactVisualsRequireReelRefresh(currentArtifact, mergedArtifact);
      if (shouldRefreshReel) {
        mergedArtifact.video = null;
      }
      artifactRef.current = mergedArtifact;
      setArtifact(mergedArtifact);
      setGenerationStatus((prev) => (prev === pendingStatus ? completeStatus : prev));
      pushAgentNote("checkpoint", "Visuals", "Quick artifact visuals finished rendering.");
      if (shouldRefreshReel) {
        void ensureQuickReel(
          {
            ...mergedArtifact,
            reel: null,
            video: null,
          },
          { forceRefresh: true, silent: true },
        );
      } else if (activeQuickViewRef.current === 'reel') {
        void ensureQuickReel(mergedArtifact);
      }
      return mergedArtifact;
    } catch (error) {
      if (artifactVisualPassRef.current === passId) {
        const message = error instanceof Error ? error.message : 'Quick artifact visual hydration failed.';
        setGenerationStatus((prev) => (prev === pendingStatus ? completeStatus : prev));
        pushAgentNote("error", "Visuals", message);
      }
      return artifactRef.current;
    } finally {
      if (artifactVisualPassRef.current === passId) {
        setIsHydratingArtifactVisuals(false);
      }
    }
  };

  const ensureQuickReel = async (
    artifactDraft?: QuickArtifact | null,
    options: { forceRefresh?: boolean; silent?: boolean } = {},
  ) => {
    const { forceRefresh = false, silent = false } = options;
    const baseArtifact = artifactDraft ?? artifact;
    if (!baseArtifact) {
      return null;
    }
    if (baseArtifact.reel && !forceRefresh) {
      return baseArtifact;
    }

    setIsBuildingReel(true);
    setReelError('');
    if (!silent) {
      setGenerationStatus('Building proof reel...');
      pushAgentNote("info", "Reel", "Deriving Proof Reel segments from the current Quick artifact.");
    }

    try {
      const response = await fetch(`${API_BASE}/api/generate-quick-reel`, {
        method: 'POST',
        headers: apiHeaders({ 'Content-Type': 'application/json' }),
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
      if (!silent) {
        setGenerationStatus('Proof reel ready.');
        pushAgentNote("checkpoint", "Reel", "Proof Reel ready. Each Quick block now maps to an ordered segment.");
      }
      return nextArtifact;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Proof reel generation failed.';
      setReelError(message);
      if (!silent) {
        setGenerationStatus('');
        pushAgentNote("error", "Reel", message);
      }
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
      pushAgentNote("checkpoint", "Source", "Video source uploaded. Ready for Quick indexing.");
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

    invalidateQuickArtifactHydration();
    setIsGenerating(true);
    setGenerationError('');
    setGenerationStatus('Building quick artifact...');
    setArtifact(null);
    setActiveQuickView('artifact');
    setReelError('');
    setVideoError('');
    setAgentNotes([]);
    pushAgentNote("info", "Session", "Quick generation started. Building HTML-first artifact.");

    try {
      const sourceManifest = buildQuickSourceManifest();
      let nextContentSignal = indexedSignal;
      let nextNormalizedSourceText = indexedNormalizedSourceText;
      let nextSourceTextOrigin = indexedSourceTextOrigin;
      const indexingCopy = activeSourceAsset
        ? quickIndexingCopy(activeSourceAsset, Boolean(sourceTranscript.trim()))
        : null;

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
        setGenerationStatus(indexingCopy?.startStatus ?? 'Indexing source...');
        pushAgentNote("info", "Source", indexingCopy?.startNote ?? 'Source indexing started.');
        const startIndexResponse = await fetch(`${API_BASE}/api/quick-source-index/start`, {
          method: 'POST',
          headers: apiHeaders({ 'Content-Type': 'application/json' }),
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
        pushAgentNote("checkpoint", "Source", indexingCopy?.completeNote ?? 'Source indexing complete. Building artifact from grounded signal.');
      } else if (activeSourceAsset && nextContentSignal) {
        setGenerationStatus(indexingCopy?.reuseStatus ?? 'Reusing indexed source signal...');
        pushAgentNote("info", "Source", indexingCopy?.reuseNote ?? 'Reusing previously indexed source signal for a faster quick artifact pass.');
      }

      const response = await fetch(`${API_BASE}/api/generate-quick-artifact`, {
        method: 'POST',
        headers: apiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          topic,
          audience: audience === 'Other' ? customAudience : audience,
          tone,
          visual_mode: visualMode,
          source_text: sourceTranscript,
          source_manifest: sourceManifest,
          normalized_source_text: nextNormalizedSourceText,
          source_text_origin: nextSourceTextOrigin,
          content_signal: nextContentSignal ?? {},
          defer_visuals: true,
        }),
      });
      const data = await response.json();
      if (!response.ok || data.status !== 'success' || !data.artifact) {
        throw new Error(data.message || 'Quick artifact generation failed.');
      }
      const nextArtifact = data.artifact as QuickArtifact;
      setArtifact(nextArtifact);
      setReelError('');
      setVideoError('');
      setGenerationStatus('Quick artifact ready. Rendering visuals...');
      pushAgentNote("checkpoint", "Session", "Quick artifact ready. Blocks can now be directed individually.");
      void hydrateQuickArtifactVisuals({
        artifactDraft: nextArtifact,
        contentSignalDraft: nextContentSignal,
        sourceManifestDraft: sourceManifest,
        pendingStatus: 'Quick artifact ready. Rendering visuals...',
        completeStatus: 'Quick artifact ready.',
      });
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
    invalidateQuickArtifactHydration();
    setIsApplyingOverride(true);
    setGenerationError('');
    setOverrideError('');
    setGenerationStatus('Applying director override...');
    pushAgentNote("info", activeOverrideBlockId, "Applying local override to one artifact block.");
    try {
      const response = await fetch(`${API_BASE}/api/regenerate-quick-block`, {
        method: 'POST',
        headers: apiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          topic,
          audience: audience === 'Other' ? customAudience : audience,
          tone,
          visual_mode: visualMode,
          artifact,
          source_manifest: buildQuickSourceManifest(),
          normalized_source_text: indexedNormalizedSourceText,
          source_text_origin: indexedSourceTextOrigin,
          content_signal: indexedSignal ?? {},
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
        video: null,
        blocks: artifact.blocks.map((block) => (
          block.block_id === activeOverrideBlockId ? updatedBlock : block
        )),
      };
      setArtifact(nextArtifact);
      setReelError('');
      setVideoError('');
      if (activeQuickView === 'reel') {
        void ensureQuickReel(nextArtifact);
      }
      setGenerationStatus('Block updated.');
      pushAgentNote("checkpoint", activeOverrideBlockId, "Block override applied.");
      void hydrateQuickArtifactVisuals({
        artifactDraft: nextArtifact,
        contentSignalDraft: indexedSignal,
        sourceManifestDraft: buildQuickSourceManifest(),
        pendingStatus: 'Block updated. Rendering visuals...',
        completeStatus: 'Block updated.',
      });
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
    invalidateQuickArtifactHydration();
    setIsApplyingGlobalOverride(true);
    setGenerationError('');
    setGlobalOverrideError('');
    setGenerationStatus('Redirecting whole artifact...');
    pushAgentNote("info", "Artifact", "Applying global override to the quick artifact.");
    try {
      const response = await fetch(`${API_BASE}/api/regenerate-quick-artifact`, {
        method: 'POST',
        headers: apiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          topic,
          audience: audience === 'Other' ? customAudience : audience,
          tone,
          visual_mode: visualMode,
          artifact,
          source_manifest: buildQuickSourceManifest(),
          normalized_source_text: indexedNormalizedSourceText,
          source_text_origin: indexedSourceTextOrigin,
          content_signal: indexedSignal ?? {},
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
        video: null,
      };
      setArtifact(nextArtifact);
      setReelError('');
      setVideoError('');
      if (activeQuickView === 'reel') {
        void ensureQuickReel(nextArtifact);
      }
      setGenerationStatus('Artifact updated.');
      pushAgentNote("checkpoint", "Artifact", "Global override applied.");
      void hydrateQuickArtifactVisuals({
        artifactDraft: nextArtifact,
        contentSignalDraft: indexedSignal,
        sourceManifestDraft: buildQuickSourceManifest(),
        pendingStatus: 'Artifact updated. Rendering visuals...',
        completeStatus: 'Artifact updated.',
      });
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
  const activeVideo = artifact?.video ?? null;

  useEffect(() => {
    if (!activeReel) {
      setSelectedPlaylistSegmentIds([]);
      setPlaylistPresentationOverrides({});
      setUnmuteLocalSourceClips(false);
      setIsPlaylistOpen(false);
      return;
    }
    setSelectedPlaylistSegmentIds(activeReel.segments.map((segment) => segment.segment_id));
    setPlaylistPresentationOverrides({});
    setUnmuteLocalSourceClips(false);
    setIsPlaylistOpen(false);
  }, [activeReel?.reel_id]);

  useEffect(() => {
    if (activeSourceAsset?.provider !== 'upload') {
      setUnmuteLocalSourceClips(false);
    }
  }, [activeSourceAsset?.provider]);

  const hasPlayableSourceForSegment = (segment: QuickReelSegment) => {
    if (segment.primary_media?.modality !== 'video' || !activeSourceAsset) {
      return false;
    }
    if (activeSourceAsset.provider === 'youtube') {
      return Boolean(extractYouTubeVideoId(activeSourceAsset.uri));
    }
    return true;
  };

  const hasGeneratedFrameForSegment = (segment: QuickReelSegment) => Boolean(segment.fallback_image_url?.trim());

  const buildPlaylistSegments = (segment: QuickReelSegment): ProofPlaylistSegment[] => {
    const preferredMode = playlistPresentationOverrides[segment.segment_id] ?? 'auto';
    const rangeLabel = formatTimeRangeLabel(segment.start_ms, segment.end_ms);
    const sourceLabel = segment.primary_media?.label ?? segment.primary_media?.visual_context ?? segment.primary_media?.quote_text ?? null;
    const imageUrl = segment.fallback_image_url?.trim() || null;
    const hasPlayableSource = hasPlayableSourceForSegment(segment);
    const hasGeneratedFrame = Boolean(imageUrl);

    const buildImageSegment = (): ProofPlaylistSegment[] => (
      imageUrl
        ? [{
            segment_id: segment.segment_id,
            title: segment.title,
            caption_text: segment.caption_text,
            claim_refs: segment.claim_refs,
            kind: 'image',
            render_label: segment.render_mode === 'generated_image' ? 'slide' : 'generated frame',
            range_label: rangeLabel,
            duration_ms: estimatePlaylistSlideDurationMs(segment.caption_text),
            image_url: imageUrl,
          }]
        : []
    );

    if (preferredMode === 'image' && hasGeneratedFrame) {
      return buildImageSegment();
    }

    if (segment.primary_media?.modality === 'video' && activeSourceAsset && hasPlayableSource) {
      if (activeSourceAsset.provider === 'youtube') {
        const videoId = extractYouTubeVideoId(activeSourceAsset.uri);
        if (!videoId) {
          return buildImageSegment();
        }
        const youtubeSegment: ProofPlaylistSegment = {
          segment_id: segment.segment_id,
          title: segment.title,
          caption_text: segment.caption_text,
          claim_refs: segment.claim_refs,
          kind: 'youtube',
          render_label: 'source proof',
          source_label: sourceLabel,
          range_label: rangeLabel,
          duration_ms: estimateClipDurationMs(segment.start_ms, segment.end_ms),
          youtube_embed_url: buildYouTubePlaylistEmbedUrl(videoId, segment.start_ms, segment.end_ms),
          start_ms: segment.start_ms,
          end_ms: segment.end_ms,
        };
        if (preferredMode === 'source') {
          return [youtubeSegment];
        }
        if (segment.render_mode === 'hybrid' && imageUrl) {
          return [
            youtubeSegment,
            ...buildImageSegment(),
          ];
        }
        return [youtubeSegment];
      }

      const videoSegment: ProofPlaylistSegment = {
        segment_id: segment.segment_id,
        title: segment.title,
        caption_text: segment.caption_text,
        claim_refs: segment.claim_refs,
        kind: 'video',
        render_label: 'source proof',
        source_label: sourceLabel,
        range_label: rangeLabel,
        duration_ms: estimateClipDurationMs(segment.start_ms, segment.end_ms),
        video_src: activeSourceAsset.uri,
        start_ms: segment.start_ms,
        end_ms: segment.end_ms,
      };
      if (preferredMode === 'source') {
        return [videoSegment];
      }
      if (segment.render_mode === 'hybrid' && imageUrl) {
        return [
          videoSegment,
          ...buildImageSegment(),
        ];
      }
      return [videoSegment];
    }

    if (preferredMode === 'source' && !hasPlayableSource) {
      return buildImageSegment();
    }

    return buildImageSegment();
  };

  const selectedPlaylistSegments = activeReel
    ? activeReel.segments.filter((segment) => selectedPlaylistSegmentIds.includes(segment.segment_id))
    : [];
  const playablePlaylistSegments = selectedPlaylistSegments
    .flatMap((segment) => buildPlaylistSegments(segment));

  const togglePlaylistSegment = (segmentId: string) => {
    setSelectedPlaylistSegmentIds((prev) => (
      prev.includes(segmentId)
        ? prev.filter((candidate) => candidate !== segmentId)
        : [...prev, segmentId]
    ));
  };

  const setPlaylistPresentationMode = (segmentId: string, mode: PlaylistPresentationMode) => {
    setPlaylistPresentationOverrides((prev) => {
      if (mode === 'auto') {
        if (!(segmentId in prev)) {
          return prev;
        }
        const next = { ...prev };
        delete next[segmentId];
        return next;
      }
      return {
        ...prev,
        [segmentId]: mode,
      };
    });
  };

  const handleOpenPlaylist = () => {
    if (!playablePlaylistSegments.length) {
      toast.error('Select at least one playable proof-reel segment.', {
        description: 'Source clips and generated frames can be queued into the Quick playlist.',
      });
      return;
    }
    setIsPlaylistOpen(true);
  };

  const handleGenerateQuickVideo = async () => {
    const reelArtifact = await ensureQuickReel();
    if (!reelArtifact) {
      return;
    }

    setIsRenderingVideo(true);
    setVideoError('');
    setGenerationError('');
    setGenerationStatus('Rendering MP4...');
    pushAgentNote("info", "Video", "Rendering Quick MP4 from the current Proof Reel.");

    try {
      const response = await fetch(`${API_BASE}/api/generate-quick-video`, {
        method: 'POST',
        headers: apiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          artifact: reelArtifact,
          content_signal: indexedSignal ?? {},
          source_manifest: buildQuickSourceManifest(),
        }),
      });
      const data = await response.json();
      if (!response.ok || data.status !== 'success' || !data.artifact) {
        throw new Error(data.detail || data.message || 'Quick MP4 generation failed.');
      }

      const nextArtifact = data.artifact as QuickArtifact;
      setArtifact(nextArtifact);
      setGenerationStatus('Quick MP4 ready.');
      pushAgentNote("checkpoint", "Video", "Quick MP4 ready. Preview or download the rendered explainer.");
      toast.success('Quick MP4 ready.', {
        description: 'Proof Reel rendered into a downloadable MP4.',
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Quick MP4 generation failed.';
      setVideoError(message);
      setGenerationStatus('');
      pushAgentNote("error", "Video", message);
      toast.error('Quick MP4 generation failed.', {
        description: message,
      });
    } finally {
      setIsRenderingVideo(false);
    }
  };

  const handleDownloadQuickVideo = async () => {
    if (!activeVideo?.video_url) {
      return;
    }

    setIsDownloadingVideo(true);
    setVideoError('');

    try {
      const downloadUrl = new URL(`${API_BASE}/api/quick-video/download`);
      downloadUrl.searchParams.set('video_url', activeVideo.video_url);
      downloadUrl.searchParams.set('filename', quickVideoFilename(activeVideo.video_url, artifact?.title));
      const anchor = document.createElement('a');
      anchor.href = downloadUrl.toString();
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to download the rendered MP4.';
      setVideoError(message);
      toast.error('MP4 download failed.', {
        description: message,
      });
    } finally {
      setIsDownloadingVideo(false);
    }
  };

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

        <QuickSourceForm
          topic={topic}
          audience={audience}
          customAudience={customAudience}
          visualMode={visualMode}
          tone={tone}
          sourceVideoUrl={sourceVideoUrl}
          sourceTranscript={sourceTranscript}
          speechError={speechError}
          isListening={isListening}
          isUploadingSource={isUploadingSource}
          isGenerating={isGenerating}
          generationStatus={generationStatus}
          generationError={generationError}
          uploadedVideoAsset={uploadedVideoAsset}
          youtubeSourceAsset={youtubeSourceAsset}
          activeSourceAsset={activeSourceAsset}
          sourceFileInputRef={sourceFileInputRef}
          onSubmit={handleGenerate}
          onToggleVoiceInput={toggleVoiceInput}
          onTopicChange={setTopic}
          onAudienceChange={setAudience}
          onCustomAudienceChange={setCustomAudience}
          onVisualModeChange={setVisualMode}
          onToneChange={setTone}
          onSourceVideoUrlChange={(value) => {
            setSourceVideoUrl(value);
            clearIndexedSource();
          }}
          onSourceTranscriptChange={(value) => {
            setSourceTranscript(value);
            clearIndexedSource();
          }}
          onVideoAssetUpload={handleVideoAssetUpload}
          onRemoveYoutubeSource={removeYoutubeSource}
          onRemoveUploadedVideoAsset={removeUploadedVideoAsset}
        />

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
                <div className="flex flex-wrap items-center gap-3">
                  <h2 className="text-2xl font-bold tracking-tight text-slate-100">
                    {activeQuickView === 'artifact' ? 'Quick Artifact' : 'Proof Reel'}
                  </h2>
                  {isHydratingArtifactVisuals ? (
                    <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-slate-200">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Rendering Visuals
                    </span>
                  ) : null}
                </div>
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

              <QuickArtifactSummary
                artifact={artifact}
                activeSourceAsset={activeSourceAsset}
                heroSourceMediaUrl={heroSourceMediaUrl}
                onOpenGlobalOverride={() => {
                  setIsGlobalOverrideOpen(true);
                  setGlobalOverrideInstruction('');
                }}
              />

              {activeQuickView === 'artifact' ? (
                <QuickArtifactView
                  artifact={artifact}
                  activeSourceAsset={activeSourceAsset}
                  heroSourceMediaUrl={heroSourceMediaUrl}
                  resolveSourceMediaUrl={resolveSourceMediaUrl}
                  onOpenGlobalOverride={() => {
                    setIsGlobalOverrideOpen(true);
                    setGlobalOverrideInstruction('');
                  }}
                  onOpenBlockOverride={(blockId) => {
                    setActiveOverrideBlockId(blockId);
                    setOverrideInstruction('');
                    setOverrideError('');
                  }}
                />
              ) : (
                <QuickReelView
                  activeReel={activeReel}
                  activeVideo={activeVideo}
                  activeSourceAsset={activeSourceAsset}
                  isBuildingReel={isBuildingReel}
                  reelError={reelError}
                  videoError={videoError}
                  selectedPlaylistSegmentIds={selectedPlaylistSegmentIds}
                  playablePlaylistSegmentsCount={playablePlaylistSegments.length}
                  unmuteLocalSourceClips={unmuteLocalSourceClips}
                  isRenderingVideo={isRenderingVideo}
                  isDownloadingVideo={isDownloadingVideo}
                  playlistPresentationOverrides={playlistPresentationOverrides}
                  onTogglePlaylistSegment={togglePlaylistSegment}
                  onSetPlaylistPresentationMode={setPlaylistPresentationMode}
                  onSetUnmuteLocalSourceClips={setUnmuteLocalSourceClips}
                  onOpenPlaylist={handleOpenPlaylist}
                  onGenerateVideo={() => void handleGenerateQuickVideo()}
                  onDownloadVideo={() => void handleDownloadQuickVideo()}
                  resolveSourceMediaUrl={resolveSourceMediaUrl}
                  hasPlayableSourceForSegment={hasPlayableSourceForSegment}
                  hasGeneratedFrameForSegment={hasGeneratedFrameForSegment}
                />
              )}
            </>
          )}
        </div>

        <ProofPlaylistPlayer
          open={isPlaylistOpen}
          onOpenChange={setIsPlaylistOpen}
          title={activeReel?.title || artifact?.title || 'Quick Proof Playlist'}
          segments={playablePlaylistSegments}
          unmuteLocalSourceClips={unmuteLocalSourceClips}
        />

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
