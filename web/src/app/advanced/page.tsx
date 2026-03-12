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
import useAdvancedAgentChat from "@/hooks/useAdvancedAgentChat";
import useAdvancedGenerationStream from "@/hooks/useAdvancedGenerationStream";
import useAdvancedWorkflowActions from "@/hooks/useAdvancedWorkflowActions";
import useAdvancedWorkflowSession from "@/hooks/useAdvancedWorkflowSession";
import {
  uploadAdvancedSourceAssets,
  upscaleAdvancedFinalBundle,
} from "@/lib/advanced-api";
import { Toaster, toast } from "sonner";
import {
  ADVANCED_API_BASE as API_BASE,
  ARTIFACT_SELECTION_TILES,
  AUDIENCE_LEVEL_TILES,
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
  formatMilliseconds,
  readVideoDurationMs,
  selectAdvancedEvidenceMedia,
  type ActionDialogStage,
  type AdvancedPanel,
  type ChatMessage,
  type EvidenceViewerState,
  type ExtractedSignal,
  type PlannerQaSummary,
  type RenderProfileStep,
  type SceneViewModel,
  type ScriptPackPayload,
  type UploadedSourceAsset,
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

  const {
    handleGenerateStream,
    handleRegenerateScene,
  } = useAdvancedGenerationStream({
    apiBase: API_BASE,
    workflowId,
    workflowSnapshot,
    scriptPack,
    setIsGenerating,
    setGenerationError,
    setGenerationStatus,
    setExpectedSceneCount,
    setScenes,
    setScriptPack,
    fullTextBufferRef: fullTextBuffer,
    startStreamPreviewRun,
    fetchWorkflowSnapshot,
    handleUnknownWorkflowError,
    pushAgentNote,
    pushPlannerQaNote,
  });

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

  const {
    handleChatSubmit,
  } = useAdvancedAgentChat({
    apiBase: API_BASE,
    workflowId,
    workflowSnapshot,
    activePanel,
    sourceDoc,
    uploadedSourceAssets,
    artifactType,
    scriptPresentationMode,
    scriptPack,
    chatInput,
    chatMessages,
    setChatInput,
    setChatMessages,
    setGenerationError,
    setWorkflowId,
    setExtractedSignal,
    setSignalStage,
    setExtractProgress,
    setScriptPack,
    setExpectedSceneCount,
    setActivePanel,
    setGenerationStatus,
    setScenes,
    clearGeneratedOutputs,
    fullTextBufferRef: fullTextBuffer,
    buildRenderProfilePayload: () => buildRenderProfilePayload(),
    updateWorkflowSnapshot,
    resetWorkflowSession,
    pushAgentNote,
    pushPlannerQaNote,
    handleGenerateStream,
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

  const openEvidenceViewer = (sceneId: string, claimRef?: string) => {
    const scene = scenes[sceneId];
    const media = selectAdvancedEvidenceMedia(scene, claimRef);
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

  const handleRegenerate = handleRegenerateScene;

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
