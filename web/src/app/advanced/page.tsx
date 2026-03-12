"use client";

import Image from 'next/image';
import React, { useState } from 'react';
import AdvancedActionDialog from '@/components/AdvancedActionDialog';
import AdvancedAssistantPanel from '@/components/AdvancedAssistantPanel';
import AdvancedContentSignalPanel from '@/components/AdvancedContentSignalPanel';
import AdvancedGeneratedExplainerSection from '@/components/AdvancedGeneratedExplainerSection';
import AdvancedGenerationStreamPanel from '@/components/AdvancedGenerationStreamPanel';
import AdvancedProofDialog from '@/components/AdvancedProofDialog';
import AdvancedRenderProfilePanel from '@/components/AdvancedRenderProfilePanel';
import AdvancedScriptPackPanel from '@/components/AdvancedScriptPackPanel';
import AdvancedSourcePanel from '@/components/AdvancedSourcePanel';
import AgentActivityPanel, { AgentNote, AgentNoteType } from '@/components/AgentActivityPanel';
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import useAdvancedWorkflowActions from "@/hooks/useAdvancedWorkflowActions";
import useAdvancedWorkflowSession from "@/hooks/useAdvancedWorkflowSession";
import {
  openAdvancedWorkflowStream,
  submitAdvancedWorkflowChat,
  uploadAdvancedSourceAssets,
  upscaleAdvancedFinalBundle,
} from "@/lib/advanced-api";
import { Toaster, toast } from "sonner";
import {
  ADVANCED_API_BASE as API_BASE,
  ARTIFACT_SELECTION_TILES,
  AUDIENCE_LEVEL_TILES,
  CHECKPOINT_LABELS,
  DENSITY_TILES,
  PRIMARY_ACTION_CARD_CLASS,
  PRIMARY_ACTION_LABEL_CLASS,
  RENDER_PROFILE_STEPS,
  RENDER_PROFILE_STEP_LABELS,
  RENDER_PROFILE_TILE_CLASS,
  RENDER_PROFILE_TILE_HOVER_CLASS,
  SCRIPT_EXPLAINER_TEXT,
  SCRIPT_JSON_PREVIEW,
  SCRIPT_TYPEWRITER_DURATION_MS,
  SECONDARY_ACTION_CARD_CLASS,
  SIGNAL_EXPLAINER_TEXT,
  SIGNAL_JSON_PREVIEW,
  SIGNAL_TYPEWRITER_DURATION_MS,
  STREAM_EXPLAINER_TEXT,
  STREAM_JSON_PREVIEW,
  STREAM_TYPEWRITER_DURATION_MS,
  TASTE_BAR_TILES,
  VISUAL_MODE_TILES,
  actionInvalidatesGeneratedOutputs,
  apiErrorMessage,
  asPlannerQaSummary,
  asSourceMedia,
  asSourceMediaList,
  asStringArray,
  buildAdvancedSourceManifest,
  deriveSceneCount,
  formatMilliseconds,
  isUnknownWorkflowMessage,
  mapArtifactScope,
  readVideoDurationMs,
  snapshotStatusSummary,
  type ActionDialogStage,
  type AdvancedPanel,
  type ChatMessage,
  type ChatRole,
  type EvidenceViewerState,
  type ExtractedSignal,
  type PlannerQaSummary,
  type RenderProfileStep,
  type SceneQaPayload,
  type SceneQueueItem,
  type SceneViewModel,
  type ScriptPackPayload,
  type SourceMediaViewModel,
  type UploadedSourceAsset,
  type WorkflowAgentApiTurn,
  type WorkflowAgentChatResponse,
  type WorkflowSnapshot,
} from "@/lib/advanced";

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
  const [scriptPackProgress, setScriptPackProgress] = useState(0);
  const [scriptPackStage, setScriptPackStage] = useState<'idle' | 'outlining' | 'structuring' | 'validating' | 'ready' | 'error'>('idle');
  const [error, setError] = useState('');
  const [generationError, setGenerationError] = useState('');
  const [generationStatus, setGenerationStatus] = useState('');
  const [typedExplainer, setTypedExplainer] = useState('');
  const [typedPreview, setTypedPreview] = useState('');
  const [typedScriptExplainer, setTypedScriptExplainer] = useState('');
  const [typedScriptPreview, setTypedScriptPreview] = useState('');
  const [typedStreamExplainer, setTypedStreamExplainer] = useState('');
  const [typedStreamPreview, setTypedStreamPreview] = useState('');
  const [signalTypewriterArmed, setSignalTypewriterArmed] = useState(false);
  const [scriptTypewriterArmed, setScriptTypewriterArmed] = useState(false);
  const [streamTypewriterArmed, setStreamTypewriterArmed] = useState(false);
  const [signalTypingRunId, setSignalTypingRunId] = useState(0);
  const [scriptTypingRunId, setScriptTypingRunId] = useState(0);
  const [streamTypingRunId, setStreamTypingRunId] = useState(0);
  const [scriptPresentationMode, setScriptPresentationMode] = useState<'review' | 'auto'>('auto');

  const [isGenerating, setIsGenerating] = useState(false);
  const [isGeneratingScriptPack, setIsGeneratingScriptPack] = useState(false);
  const [isApplyingProfile, setIsApplyingProfile] = useState(false);
  const [scenes, setScenes] = useState<Record<string, SceneViewModel>>({});
  const [expectedSceneCount, setExpectedSceneCount] = useState(0);
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

  const resetSignalPreviewRun = () => {
    setTypedExplainer('');
    setTypedPreview('');
    setSignalTypewriterArmed(false);
  };

  const startSignalPreviewRun = () => {
    setTypedExplainer('');
    setTypedPreview('');
    setSignalTypewriterArmed(true);
    setSignalTypingRunId((prev) => prev + 1);
  };

  const resetScriptPreviewRun = () => {
    setTypedScriptExplainer('');
    setTypedScriptPreview('');
    setScriptTypewriterArmed(false);
  };

  const startScriptPreviewRun = () => {
    setTypedScriptExplainer('');
    setTypedScriptPreview('');
    setScriptTypewriterArmed(true);
    setScriptTypingRunId((prev) => prev + 1);
  };

  const resetStreamPreviewRun = () => {
    setTypedStreamExplainer('');
    setTypedStreamPreview('');
    setStreamTypewriterArmed(false);
  };

  const startStreamPreviewRun = () => {
    setTypedStreamExplainer('');
    setTypedStreamPreview('');
    setStreamTypewriterArmed(true);
    setStreamTypingRunId((prev) => prev + 1);
  };

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

  const {
    fetchWorkflowSignal,
    fetchWorkflowSnapshot,
    handleUnknownWorkflowError,
    recoverWorkflowState,
    resetWorkflowSession,
    syncWorkflowUiFromSnapshot,
    updateWorkflowSnapshot,
  } = useAdvancedWorkflowSession({
    apiBase: API_BASE,
    workflowId,
    setWorkflowId,
    setWorkflowSnapshot,
    setExtractedSignal,
    setSignalStage,
    setExtractProgress,
    setError,
    setGenerationError,
    setGenerationStatus,
    setIsExtracting,
    setIsApplyingProfile,
    setIsGeneratingScriptPack,
    setIsGenerating,
    setActionDialogStage,
    setShowAmendHelp,
    setActivePanel,
    setScriptPack,
    setScriptPackStage,
    setScriptPackProgress,
    setScenes,
    setExpectedSceneCount,
    setEvidenceViewer,
    fullTextBufferRef: fullTextBuffer,
    resetSignalPreviewRun,
    resetScriptPreviewRun,
    resetStreamPreviewRun,
    pushAgentNote,
  });

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
  }, [chatMessages.length]);

  const hasSourceInput = sourceDoc.trim().length > 0 || uploadedSourceAssets.length > 0;
  const clearGeneratedOutputs = () => {
    setScriptPack(null);
    setScriptPackProgress(0);
    setScriptPackStage('idle');
    setScenes({});
    setExpectedSceneCount(0);
    setEvidenceViewer(null);
    fullTextBuffer.current = {};
  };

  const {
    applyProfileToWorkflow,
    buildRenderProfilePayload,
    confirmSignal,
    generateScriptPack,
    runExtraction,
  } = useAdvancedWorkflowActions({
    apiBase: API_BASE,
    sourceDoc,
    uploadedSourceAssets,
    hasSourceInput,
    workflowId,
    workflowSnapshot,
    extractedSignal,
    scriptPack,
    fidelityPreference,
    scriptPresentationMode,
    renderProfileInput: {
      artifactType,
      visualMode,
      density,
      audienceLevel,
      audiencePersona,
      domainContext,
      tasteBar,
      mustIncludeText,
      mustAvoidText,
    },
    setWorkflowId,
    setWorkflowSnapshot,
    setAgentNotes,
    setIsExtracting,
    setSignalStage,
    setExtractProgress,
    setError,
    setGenerationError,
    setExtractedSignal,
    setGenerationStatus,
    setFidelityPreference,
    setIsApplyingProfile,
    setIsGeneratingScriptPack,
    setScriptPresentationMode,
    setActivePanel,
    setScriptPack,
    setExpectedSceneCount,
    setScriptPackStage,
    setScriptPackProgress,
    clearGeneratedOutputs,
    startSignalPreviewRun,
    resetSignalPreviewRun,
    startScriptPreviewRun,
    resetScriptPreviewRun,
    resetStreamPreviewRun,
    updateWorkflowSnapshot,
    syncWorkflowUiFromSnapshot,
    recoverWorkflowState,
    fetchWorkflowSnapshot,
    fetchWorkflowSignal,
    handleUnknownWorkflowError,
    pushAgentNote,
    pushPlannerQaNote,
  });

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
      const formData = new FormData();
      const assetDescriptors = await Promise.all(
        files.map(async (file) => ({
          filename: file.name,
          duration_ms: await readVideoDurationMs(file),
        }))
      );
      files.forEach((file) => formData.append('files', file));
      formData.append('asset_descriptors', JSON.stringify(assetDescriptors));

      const uploadResult = await uploadAdvancedSourceAssets(API_BASE, formData);
      if (!uploadResult.ok || uploadResult.status !== 'success') {
        const detail = uploadResult.detail || uploadResult.message || 'Source upload failed.';
        setError(detail);
        toast.error(detail);
        return;
      }

      const newAssets = uploadResult.assets;

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
        && item.start_ms === media.start_ms
        && item.end_ms === media.end_ms
        && item.usage === media.usage
        && (
          item.url === media.url
          || (
            item.original_url === media.original_url
            && item.page_index === media.page_index
          )
          || (
            item.evidence_refs.length > 0
            && media.evidence_refs.length > 0
            && item.evidence_refs.some(ref => media.evidence_refs.includes(ref))
          )
        )
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
      if (typeof media.page_index === 'number' && media.page_index >= 1) score += 20;
      if (typeof media.line_start === 'number') score += 12;
      if (typeof media.line_end === 'number') score += 4;
      if (typeof media.matched_excerpt === 'string' && media.matched_excerpt.trim()) score += 10;
      if (typeof media.start_ms === 'number') score += 5;
      if (media.modality === 'audio') score -= 5;
      if (typeof media.page_index === 'number' && media.page_index < 1) score -= 25;
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
    if (!isGeneratingScriptPack) {
      return;
    }

    setScriptPackStage('outlining');
    setScriptPackProgress((prev) => Math.max(prev, 10));

    const structuringTimer = window.setTimeout(() => {
      setScriptPackStage((prev) => (prev === 'outlining' ? 'structuring' : prev));
    }, 1300);

    const validatingTimer = window.setTimeout(() => {
      setScriptPackStage((prev) => (
        prev === 'outlining' || prev === 'structuring'
          ? 'validating'
          : prev
      ));
    }, 3200);

    const progressSteps = [16, 24, 35, 47, 58, 68, 77, 85, 91, 95];
    let stepIndex = 0;
    const progressTimer = window.setInterval(() => {
      setScriptPackProgress((prev) => {
        if (prev >= 95) return prev;
        const nextValue = progressSteps[Math.min(stepIndex, progressSteps.length - 1)];
        stepIndex += 1;
        return Math.max(prev, nextValue);
      });
    }, 950);

    return () => {
      window.clearTimeout(structuringTimer);
      window.clearTimeout(validatingTimer);
      window.clearInterval(progressTimer);
    };
  }, [isGeneratingScriptPack]);

  React.useEffect(() => {
    if (signalTypingRunId === 0 || extractedSignal) {
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
  }, [signalTypingRunId, extractedSignal]);

  React.useEffect(() => {
    if (scriptTypingRunId === 0 || scriptPack) {
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
  }, [scriptTypingRunId, scriptPack]);

  React.useEffect(() => {
    const streamOutputReady = Object.values(scenes).some((scene) => (
      scene.text.trim().length > 0
      || Boolean(scene.imageUrl)
      || Boolean(scene.audioUrl)
      || (scene.source_media?.length ?? 0) > 0
      || scene.status === 'ready'
      || scene.status === 'qa-failed'
    ));
    if (streamTypingRunId === 0 || streamOutputReady) {
      return;
    }

    setTypedStreamExplainer('');
    setTypedStreamPreview('');

    const targetDurationMs = STREAM_TYPEWRITER_DURATION_MS;
    const tickMs = 60;
    const totalChars = STREAM_EXPLAINER_TEXT.length + STREAM_JSON_PREVIEW.length;
    const totalTicks = Math.max(1, Math.ceil(targetDurationMs / tickMs));
    const charsPerTick = totalChars / totalTicks;
    let cursor = 0;

    const intervalId = window.setInterval(() => {
      cursor = Math.min(totalChars, cursor + charsPerTick);
      const shownChars = Math.floor(cursor);
      const explainerChars = Math.min(shownChars, STREAM_EXPLAINER_TEXT.length);
      const previewChars = Math.max(0, shownChars - STREAM_EXPLAINER_TEXT.length);
      setTypedStreamExplainer(STREAM_EXPLAINER_TEXT.slice(0, explainerChars));
      setTypedStreamPreview(STREAM_JSON_PREVIEW.slice(0, previewChars));

      if (cursor >= totalChars) {
        window.clearInterval(intervalId);
      }
    }, tickMs);

    return () => window.clearInterval(intervalId);
  }, [streamTypingRunId, scenes]);

  React.useEffect(() => {
    if (!extractedSignal) return;
    setTypedExplainer('');
    setTypedPreview('');
    setSignalTypewriterArmed(false);
  }, [extractedSignal]);

  React.useEffect(() => {
    if (!scriptPack) return;
    setTypedScriptExplainer('');
    setTypedScriptPreview('');
    setScriptTypewriterArmed(false);
  }, [scriptPack]);

  React.useEffect(() => {
    const streamOutputReady = Object.values(scenes).some((scene) => (
      scene.text.trim().length > 0
      || Boolean(scene.imageUrl)
      || Boolean(scene.audioUrl)
      || (scene.source_media?.length ?? 0) > 0
      || scene.status === 'ready'
      || scene.status === 'qa-failed'
    ));
    if (!streamOutputReady) return;
    setTypedStreamExplainer('');
    setTypedStreamPreview('');
    setStreamTypewriterArmed(false);
  }, [scenes]);

  const openActionDialog = (stage: ActionDialogStage) => {
    setActionDialogStage(stage);
    setShowAmendHelp(false);
  };

  const closeActionDialog = () => {
    setActionDialogStage(null);
    setShowAmendHelp(false);
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
    startSignalPreviewRun();
    pushAgentNote('info', 'Render Profile', 'Render profile ready. Waiting for lock confirmation.');
    openActionDialog('profile');
  };

  const handleRegenerateSignal = () => {
    if (!hasSourceInput || isExtracting || isUploadingAssets) return;
    setActivePanel('signal');
    void runExtraction({ armSignalPreview: true });
  };

  const handleRegenerateScript = () => {
    if (!scriptPack || isGeneratingScriptPack || isGenerating) return;
    void handleGenerateScriptPack('review');
  };

  const handleRegenerateStream = () => {
    if (isGenerating || !scriptPack || Object.keys(scenes).length === 0) return;
    void handleGenerateStreamAction();
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
      const upscaleResult = await upscaleAdvancedFinalBundle(API_BASE, {
        scale_factor: 2,
        scenes: currentScenes.map((scene) => ({
          scene_id: scene.id,
          image_url: scene.imageUrl,
        })),
      });
      const data = upscaleResult.data;
      if (!upscaleResult.ok || data?.status !== 'success') {
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
    startStreamPreviewRun();
    setExpectedSceneCount(deriveSceneCount(scriptPackOverride ?? scriptPack ?? null));
    if (!preserveExistingScenes) {
      setScenes({});
    }
    fullTextBuffer.current = {};
    pushAgentNote('info', 'Generation', startNote);
    
    try {
      const response = await openAdvancedWorkflowStream(
        API_BASE,
        workflowId,
        scriptPackOverride ?? scriptPack ?? undefined,
      );

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
                    expected_source_media_count: sceneItem.source_media_count,
                    text: '',
                    status: 'queued'
                  };
                  fullTextBuffer.current[sceneItem.scene_id] = sceneItem.narration_focus || '';
                });
                setExpectedSceneCount(queueScenes.length);
                setScenes(initialScenes);
                pushAgentNote(
                  'info',
                  'Planning',
                  `Scene queue ready with ${Object.keys(initialScenes).length} scenes.`
                );
              } else if (currentEvent === 'script_pack_ready') {
                const rawPack = data.script_pack;
                if (rawPack && typeof rawPack === 'object') {
                  const streamScriptPack = rawPack as ScriptPackPayload;
                  setScriptPack(streamScriptPack);
                  setExpectedSceneCount(deriveSceneCount(streamScriptPack));
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
                  source_proof_warning: undefined,
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
                updateSceneMetadata(sceneId, { source_proof_warning: undefined });
              } else if (currentEvent === 'source_media_warning') {
                const sceneId = typeof data.scene_id === 'string' ? data.scene_id : '';
                const message = typeof data.message === 'string' ? data.message.trim() : '';
                if (!sceneId || !message) continue;
                updateSceneMetadata(sceneId, { source_proof_warning: message });
                pushAgentNote('qa', sceneId, message);
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
                setScenes((prev) => {
                  const existing = prev[sceneId] ?? { id: sceneId, text: '', status: 'queued' };
                  const sourceMediaCount = Array.isArray(existing.source_media) ? existing.source_media.length : 0;
                  const expectedSourceMediaCount = existing.expected_source_media_count ?? 0;
                  const nextWarning = (
                    (expectedSourceMediaCount > 0 || (existing.evidence_refs?.length ?? 0) > 0)
                    && sourceMediaCount === 0
                    && !existing.source_proof_warning
                  )
                    ? 'Source proof was planned for this scene, but no resolved proof links were attached.'
                    : existing.source_proof_warning;
                  return {
                    ...prev,
                    [sceneId]: {
                      ...existing,
                      status: qaStatus === 'FAIL' ? 'qa-failed' : 'ready',
                      auto_retry_count: autoRetries,
                      source_proof_warning: nextWarning,
                    },
                  };
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
                  } catch (snapshotError) {
                    handleUnknownWorkflowError(snapshotError, { silent: true, noteStage: 'Generation' });
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
                  } catch (snapshotError) {
                    handleUnknownWorkflowError(snapshotError, { silent: true, noteStage: 'Generation' });
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
        } catch (snapshotError) {
          handleUnknownWorkflowError(snapshotError, { silent: true, noteStage: 'Generation' });
          // Snapshot refresh is best-effort.
        }
      }
      setIsGenerating(false);
    }
  };

  const handleGenerateScriptPack = async (mode: 'review' | 'auto' = 'review') => {
    await generateScriptPack(mode, { onAutoStartStream: handleGenerateStream });
  };

  const handleConfirmSignal = async () => {
    await confirmSignal({ onAutoStartStream: handleGenerateStream });
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

    const conversation: WorkflowAgentApiTurn[] = chatMessages.slice(-10).map((turn) => ({
      role: turn.role === 'agent' ? 'agent' : turn.role === 'system' ? 'system' : 'user',
      text: turn.text,
    }));

    try {
      setGenerationError('');
      const agentResult = await submitAdvancedWorkflowChat(API_BASE, {
        message,
        context: {
          workflow_id: workflowId,
          active_panel: activePanel,
          source_text: sourceDoc,
          source_manifest: buildAdvancedSourceManifest(uploadedSourceAssets),
          render_profile: buildRenderProfilePayload(),
          artifact_scope: mapArtifactScope(artifactType),
          script_presentation_mode: scriptPresentationMode,
        },
        conversation,
      });
      const data = agentResult.data as WorkflowAgentChatResponse;
      if (!agentResult.ok) {
        const detail = apiErrorMessage(data, 'Agent request failed.');
        if (isUnknownWorkflowMessage(detail)) {
          resetWorkflowSession({ noteStage: 'Agent' });
          return;
        }
        setGenerationError(detail);
        pushAgentNote('error', 'Agent', detail);
        return;
      }
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
          setExpectedSceneCount(0);
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
        setExpectedSceneCount(deriveSceneCount(scriptPackOverride));
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
        : '';
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

  const totalSceneCount = Math.max(expectedSceneCount, Object.keys(scenes).length);
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
  const scriptPackPhaseText = scriptPackStage === 'outlining'
    ? 'Mapping scene roles, claim coverage, and artifact structure...'
    : scriptPackStage === 'structuring'
      ? 'Drafting narration focus, visual directives, and continuity...'
      : scriptPackStage === 'validating'
        ? 'Running planner QA, repairs, and script-pack locking...'
        : scriptPackStage === 'ready'
          ? 'Script pack ready for review.'
          : '';
  const streamOutputReady = Object.values(scenes).some((scene) => (
    scene.text.trim().length > 0
    || Boolean(scene.imageUrl)
    || Boolean(scene.audioUrl)
    || (scene.source_media?.length ?? 0) > 0
    || scene.status === 'ready'
    || scene.status === 'qa-failed'
  ));
  const showSignalTypingPreview = signalTypewriterArmed
    && signalStage !== 'error'
    && !extractedSignal;
  const scriptPreviewFailed = scriptTypewriterArmed && !isGeneratingScriptPack && !scriptPack && generationError.trim().length > 0;
  const showScriptTypingPreview = scriptTypewriterArmed
    && !scriptPreviewFailed
    && !scriptPack;
  const streamPreviewFailed = streamTypewriterArmed && !isGenerating && !streamOutputReady && generationError.trim().length > 0;
  const showStreamTypingPreview = streamTypewriterArmed
    && !streamPreviewFailed
    && !streamOutputReady;
  const signalAlreadyConfirmed = Boolean(
    isGeneratingScriptPack
    || scriptPack
    || workflowSnapshot?.has_script_pack
    || workflowSnapshot?.ready_for_stream
    || workflowSnapshot?.checkpoint_state?.CP4_SCRIPT_LOCKED === 'passed'
  );
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
            <AdvancedAssistantPanel
              chatMessages={chatMessages}
              chatInput={chatInput}
              isWorking={agentIsWorking}
              primaryActionClassName={PRIMARY_ACTION_CARD_CLASS}
              primaryActionLabelClassName={PRIMARY_ACTION_LABEL_CLASS}
              chatScrollAnchorRef={chatScrollAnchorRef}
              onSubmit={(event) => void handleChatSubmit(event)}
              onChatInputChange={setChatInput}
            />

            <AgentActivityPanel
              title="Agent Session Notes"
              subtitle="Checkpoint, QA, and traceability notes from the active workflow."
              notes={agentNotes}
              currentStatus={generationStatus}
            />
          </div>

          <div className="space-y-6">
        <div className="mx-auto max-w-4xl">
        <Card className="bg-white text-slate-900 backdrop-blur-xl shadow-xl border-slate-300/70">
          <CardContent className="pt-6">
            <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between gap-3 px-1">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Workflow Stages</p>
                <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">
                  Active Flow
                </span>
              </div>
              <div className="overflow-x-auto">
                <div className="min-w-[720px] gap-2 pb-1" style={{ display: 'flex' }}>
                  {panelOrder.map((panel) => (
                    <button
                      key={panel}
                      type="button"
                      onClick={() => setActivePanel(panel)}
                      style={{ flex: '1 1 0%' }}
                      className={`w-full rounded-[18px] border px-3 py-2 text-center text-xs font-semibold transition hover:brightness-95 ${stageBadgeClass(panel)}`}
                    >
                      {panelLabel[panel]}
                    </button>
                  ))}
                </div>
              </div>
              <Progress value={stageProgress} className="h-2 bg-blue-100 [&>*]:bg-blue-500" />
              <p className="px-1 text-xs text-slate-600">{activeStageNote}</p>
            </div>
          </CardContent>
        </Card>
        </div>

        <div className="relative min-h-[420px]">
          <div className="mx-auto max-w-4xl">
            <div key={activePanel} className="animate-in fade-in-0 zoom-in-95 duration-300">
              {activePanel === 'source' && (
                <AdvancedSourcePanel
                  sourceDoc={sourceDoc}
                  uploadedSourceAssets={uploadedSourceAssets}
                  isUploadingAssets={isUploadingAssets}
                  isExtracting={isExtracting}
                  hasSourceInput={hasSourceInput}
                  extractProgress={extractProgress}
                  extractProgressMessage={isExtracting ? extractionPhaseText : signalStage === 'ready' ? 'Signal is ready for generation.' : ''}
                  errorMessage={error}
                  sourceAssetsInputRef={sourceAssetsInputRef}
                  primaryActionClassName={PRIMARY_ACTION_CARD_CLASS}
                  primaryActionLabelClassName={PRIMARY_ACTION_LABEL_CLASS}
                  secondaryActionClassName={SECONDARY_ACTION_CARD_CLASS}
                  onSubmit={handleExtract}
                  onSourceDocChange={setSourceDoc}
                  onSourceAssetUpload={handleSourceAssetUpload}
                  onRemoveUploadedSourceAsset={removeUploadedSourceAsset}
                  onCollapse={() => setActivePanel(collapseTarget.source)}
                  formatDuration={formatMilliseconds}
                />
              )}

              {activePanel === 'profile' && (
                <AdvancedRenderProfilePanel
                  profileStep={profileStep}
                  renderProfileSteps={RENDER_PROFILE_STEPS}
                  renderProfileStepLabels={RENDER_PROFILE_STEP_LABELS}
                  artifactTiles={ARTIFACT_SELECTION_TILES}
                  visualModeTiles={VISUAL_MODE_TILES}
                  audienceLevelTiles={AUDIENCE_LEVEL_TILES}
                  densityTiles={DENSITY_TILES}
                  tasteBarTiles={TASTE_BAR_TILES}
                  artifactType={artifactType}
                  visualMode={visualMode}
                  audienceLevel={audienceLevel}
                  audiencePersona={audiencePersona}
                  domainContext={domainContext}
                  density={density}
                  tasteBar={tasteBar}
                  mustIncludeText={mustIncludeText}
                  mustAvoidText={mustAvoidText}
                  currentSelectionLabel={`${ARTIFACT_SELECTION_TILES.find((item) => item.value === artifactType)?.title ?? artifactType} · ${VISUAL_MODE_TILES.find((item) => item.value === visualMode)?.title ?? visualMode}`}
                  canMoveProfileBack={canMoveProfileBack}
                  canMoveProfileNext={canMoveProfileNext}
                  isApplyingProfile={isApplyingProfile}
                  applyDisabled={!workflowId}
                  primaryActionClassName={PRIMARY_ACTION_CARD_CLASS}
                  primaryActionLabelClassName={PRIMARY_ACTION_LABEL_CLASS}
                  secondaryActionClassName={SECONDARY_ACTION_CARD_CLASS}
                  tileClassName={RENDER_PROFILE_TILE_CLASS}
                  tileHoverClassName={RENDER_PROFILE_TILE_HOVER_CLASS}
                  onProfileStepChange={(value) => setProfileStep(value as RenderProfileStep)}
                  onArtifactTypeChange={setArtifactType}
                  onVisualModeChange={setVisualMode}
                  onAudienceLevelChange={setAudienceLevel}
                  onAudiencePersonaChange={setAudiencePersona}
                  onDomainContextChange={setDomainContext}
                  onDensityChange={setDensity}
                  onTasteBarChange={setTasteBar}
                  onMustIncludeTextChange={setMustIncludeText}
                  onMustAvoidTextChange={setMustAvoidText}
                  onProfileStepBack={handleProfileStepBack}
                  onProfileStepNext={handleProfileStepNext}
                  onApply={handleApplyRenderProfile}
                  onCollapse={() => setActivePanel(collapseTarget.profile)}
                />
              )}

              {activePanel === 'signal' && (
                <AdvancedContentSignalPanel
                  extractedSignal={extractedSignal}
                  showTypingPreview={showSignalTypingPreview}
                  extractProgress={extractProgress}
                  extractionPhaseText={extractionPhaseText}
                  typedExplainer={typedExplainer}
                  typedPreview={typedPreview}
                  signalAlreadyConfirmed={signalAlreadyConfirmed}
                  hasSourceInput={hasSourceInput}
                  isExtracting={isExtracting}
                  isUploadingAssets={isUploadingAssets}
                  primaryActionClassName={PRIMARY_ACTION_CARD_CLASS}
                  primaryActionLabelClassName={PRIMARY_ACTION_LABEL_CLASS}
                  secondaryActionClassName={SECONDARY_ACTION_CARD_CLASS}
                  onConfirm={() => void handleConfirmSignal()}
                  onRegenerate={handleRegenerateSignal}
                />
              )}

              {activePanel === 'stream' && (
                <AdvancedGenerationStreamPanel
                  showTypingPreview={showStreamTypingPreview}
                  typedStreamExplainer={typedStreamExplainer}
                  typedStreamPreview={typedStreamPreview}
                  isGenerating={isGenerating}
                  isGeneratingScriptPack={isGeneratingScriptPack}
                  primaryActionText={isGenerating
                    ? 'Generating Stream...'
                    : isGeneratingScriptPack
                      ? 'Script Pack in Progress...'
                      : !workflowSnapshot?.ready_for_script_pack
                        ? 'Lock Signal + Artifacts + Profile First'
                        : !scriptPack
                          ? 'Generate Script Pack First'
                          : !workflowSnapshot?.ready_for_stream
                            ? 'Script Pack Must Be Locked'
                            : 'Generate Explainer Stream'}
                  primaryDisabled={isGenerating || !workflowSnapshot?.ready_for_stream || !scriptPack || isGeneratingScriptPack}
                  secondaryDisabled={isGenerating || !scriptPack || Object.keys(scenes).length === 0}
                  generationStatus={generationStatus}
                  generationProgress={generationProgress}
                  completedSceneCount={completedSceneCount}
                  totalSceneCount={totalSceneCount}
                  generationError={generationError}
                  primaryActionClassName={PRIMARY_ACTION_CARD_CLASS}
                  primaryActionLabelClassName={PRIMARY_ACTION_LABEL_CLASS}
                  secondaryActionClassName={SECONDARY_ACTION_CARD_CLASS}
                  onGenerate={() => void handleGenerateStreamAction()}
                  onRegenerate={handleRegenerateStream}
                />
              )}

              {activePanel === 'script' && (
                <AdvancedScriptPackPanel
                  scriptPack={scriptPack}
                  showTypingPreview={showScriptTypingPreview}
                  scriptPackProgress={scriptPackProgress}
                  scriptPackPhaseText={scriptPackPhaseText}
                  typedScriptExplainer={typedScriptExplainer}
                  typedScriptPreview={typedScriptPreview}
                  isGeneratingScriptPack={isGeneratingScriptPack}
                  primaryActionText={isGeneratingScriptPack ? 'Generating Script Pack...' : scriptPack ? 'Regenerate Script Pack' : 'Generate Script Pack'}
                  primaryDisabled={isGeneratingScriptPack || isGenerating || !workflowSnapshot?.ready_for_script_pack}
                  secondaryDisabled={isGeneratingScriptPack || isGenerating || !scriptPack}
                  primaryActionClassName={PRIMARY_ACTION_CARD_CLASS}
                  primaryActionLabelClassName={PRIMARY_ACTION_LABEL_CLASS}
                  secondaryActionClassName={SECONDARY_ACTION_CARD_CLASS}
                  onGenerate={() => void handleScriptPackAction()}
                  onRegenerate={handleRegenerateScript}
                />
              )}
            </div>
          </div>
        </div>
          </div>
        </div>

        <AdvancedGeneratedExplainerSection
          scenes={scenes}
          artifactType={scriptPack?.artifact_type ?? artifactType}
          visualMode={visualMode}
          generationError={generationError}
          fidelityPreference={fidelityPreference}
          isApplyingProfile={isApplyingProfile}
          isGenerating={isGenerating}
          isGeneratingScriptPack={isGeneratingScriptPack}
          topic={extractedSignal?.thesis?.one_liner || 'Advanced Explainer'}
          onEnableHighFidelity={() => void handleEnableHighFidelity()}
          onRegenerate={handleRegenerate}
          onOpenEvidence={openEvidenceViewer}
        />

      </div>
      <AdvancedProofDialog
        evidenceViewer={evidenceViewer}
        onClose={() => setEvidenceViewer(null)}
      />
      <AdvancedActionDialog
        open={Boolean(actionDialogStage)}
        dialogMeta={dialogMeta}
        showAmendHelp={showAmendHelp}
        continueDisabled={dialogContinueDisabled}
        relaunchDisabled={actionDialogStage === 'script' ? isGenerating || !workflowSnapshot?.ready_for_script_pack : isExtracting}
        onOpenChange={(open) => { if (!open) closeActionDialog(); }}
        onShowAmendHelp={() => setShowAmendHelp(true)}
        onContinue={() => void handleDialogContinue()}
        onGoBack={handleDialogGoBack}
        onRelaunch={() => void handleDialogRelaunch()}
      />
      <Toaster position="top-right" richColors closeButton />
    </main>
  );
}
