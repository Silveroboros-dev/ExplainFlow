"use client";

import Image from 'next/image';
import React, { useState } from 'react';
import SceneCard from '@/components/SceneCard';
import FinalBundle from '@/components/FinalBundle';
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Loader2 } from "lucide-react";

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
  status: string;
  qa_status?: 'PASS' | 'WARN' | 'FAIL';
  qa_reasons?: string[];
  qa_score?: number;
  qa_word_count?: number;
  auto_retry_count?: number;
};

type SceneQueueItem = {
  scene_id: string;
  title?: string;
  claim_refs?: string[];
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

type ScriptPackPayload = {
  plan_id: string;
  plan_summary: string;
  audience_descriptor: string;
  scene_count: number;
  scenes: Array<{
    scene_id: string;
    title: string;
    scene_goal: string;
    narration_focus: string;
    visual_prompt: string;
    claim_refs: string[];
    continuity_refs: string[];
    acceptance_checks: string[];
  }>;
};

type AdvancedPanel = 'source' | 'profile' | 'signal' | 'stream' | 'script';
type ActionDialogStage = 'extract' | 'profile' | 'signal' | 'script' | 'stream';

export default function AdvancedStudio() {
  const [sourceDoc, setSourceDoc] = useState('');
  const [visualMode, setVisualMode] = useState('illustration');
  const [artifactType, setArtifactType] = useState('storyboard_grid');
  const [lowKeyPreview, setLowKeyPreview] = useState(true);
  const [fidelity, setFidelity] = useState('high');
  const [density, setDensity] = useState('standard');
  const [audienceLevel, setAudienceLevel] = useState('intermediate');
  const [audiencePersona, setAudiencePersona] = useState('Product manager');
  const [domainContext, setDomainContext] = useState('');
  const [tasteBar, setTasteBar] = useState('high');
  const [mustIncludeText, setMustIncludeText] = useState('');
  const [mustAvoidText, setMustAvoidText] = useState('');
  const [activePanel, setActivePanel] = useState<AdvancedPanel>('source');
  const [actionDialogStage, setActionDialogStage] = useState<ActionDialogStage | null>(null);
  const [showAmendHelp, setShowAmendHelp] = useState(false);
  
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractedSignal, setExtractedSignal] = useState<ExtractedSignal | null>(null);
  const [extractProgress, setExtractProgress] = useState(0);
  const [signalStage, setSignalStage] = useState<'idle' | 'sending' | 'structuring' | 'ready' | 'error'>('idle');
  const [error, setError] = useState('');
  const [generationError, setGenerationError] = useState('');
  const [generationStatus, setGenerationStatus] = useState('');
  const [typedExplainer, setTypedExplainer] = useState('');
  const [typedPreview, setTypedPreview] = useState('');

  const [isGenerating, setIsGenerating] = useState(false);
  const [isGeneratingScriptPack, setIsGeneratingScriptPack] = useState(false);
  const [scenes, setScenes] = useState<Record<string, SceneViewModel>>({});
  const [scriptPack, setScriptPack] = useState<ScriptPackPayload | null>(null);
  
  // Ref for the typewriter effect to track full text without causing infinite re-renders
  const fullTextBuffer = React.useRef<Record<string, string>>({});

  const asStringArray = (value: unknown): string[] => (
    Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
  );

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

    const targetDurationMs = 33000;
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

  const openActionDialog = (stage: ActionDialogStage) => {
    setActionDialogStage(stage);
    setShowAmendHelp(false);
  };

  const closeActionDialog = () => {
    setActionDialogStage(null);
    setShowAmendHelp(false);
  };

  const runExtraction = async () => {
    if (!sourceDoc.trim()) {
      return false;
    }

    setIsExtracting(true);
    setSignalStage('sending');
    setExtractProgress(8);
    setError('');
    setGenerationError('');
    setExtractedSignal(null);
    setGenerationStatus('');
    setScenes({});
    setScriptPack(null);
    fullTextBuffer.current = {};
    
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/extract-signal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input_text: sourceDoc })
      });
      
      const data: {
        status?: string;
        content_signal?: ExtractedSignal;
        message?: string;
      } = await response.json();
      if (data.status === 'success') {
        setExtractedSignal(data.content_signal ?? null);
        setSignalStage('ready');
        setExtractProgress(100);
        return true;
      } else {
        setError(data.message || 'Extraction failed');
        setSignalStage('error');
        setExtractProgress(0);
        return false;
      }
    } catch (err) {
      console.error(err);
      setError('Network error during extraction');
      setSignalStage('error');
      setExtractProgress(0);
      return false;
    } finally {
      setIsExtracting(false);
    }
  };

  const handleExtract = (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceDoc.trim()) {
      return;
    }
    setActivePanel('profile');
    openActionDialog('extract');
  };

  const handleApplyRenderProfile = () => {
    setActivePanel('signal');
    openActionDialog('profile');
  };

  const handleConfirmSignal = () => {
    if (!extractedSignal) {
      setGenerationStatus('Extract signal first.');
      return;
    }
    setActivePanel('script');
    openActionDialog('signal');
  };

  const buildRenderProfilePayload = () => ({
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
    low_key_preview: lowKeyPreview,
    style: {
      descriptors: [visualMode === "illustration" ? "cinematic" : "clean", "modern"]
    },
    fidelity: fidelity,
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

  const handleGenerateScriptPack = async () => {
    if (!extractedSignal) return;

    setIsGeneratingScriptPack(true);
    setGenerationError('');
    setGenerationStatus('Generating script pack from extracted signal...');
    setScriptPack(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/generate-script-pack-advanced`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content_signal: extractedSignal,
          render_profile: buildRenderProfilePayload()
        })
      });
      const data = await response.json();
      if (data?.status === 'success' && data?.script_pack) {
        setScriptPack(data.script_pack as ScriptPackPayload);
        setGenerationStatus('Script pack is ready. Review and amend before starting stream generation.');
      } else {
        setGenerationError(typeof data?.message === 'string' ? data.message : 'Script pack generation failed.');
        setGenerationStatus('');
      }
    } catch (err) {
      console.error("Script pack error:", err);
      setGenerationError('Unable to generate script pack.');
      setGenerationStatus('');
    } finally {
      setIsGeneratingScriptPack(false);
    }
  };

  const handleGenerateStream = async () => {
    if (!extractedSignal) return;
    
    setIsGenerating(true);
    setGenerationError('');
    setGenerationStatus('Preparing generation pipeline...');
    setScenes({});
    fullTextBuffer.current = {};
    
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/generate-stream-advanced`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content_signal: extractedSignal,
          render_profile: buildRenderProfilePayload(),
          script_pack: scriptPack ?? undefined
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
                    text: '',
                    status: 'queued'
                  };
                  fullTextBuffer.current[sceneItem.scene_id] = sceneItem.narration_focus || '';
                });
                setScenes(initialScenes);
              } else if (currentEvent === 'script_pack_ready') {
                const rawPack = data.script_pack;
                if (rawPack && typeof rawPack === 'object') {
                  setScriptPack(rawPack as ScriptPackPayload);
                }
              } else if (currentEvent === 'scene_start') {
                const sceneId = typeof data.scene_id === 'string' ? data.scene_id : '';
                if (!sceneId) continue;
                fullTextBuffer.current[sceneId] = '';
                if (typeof data.title === 'string' && data.title.trim()) {
                  setGenerationStatus(`Generating ${data.title}...`);
                }
                const patch: Partial<SceneViewModel> = {
                  claim_refs: asStringArray(data.claim_refs),
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
              } else if (currentEvent === 'status') {
                if (typeof data.message === 'string' && data.message.trim()) {
                  setGenerationStatus(data.message);
                }
              } else if (currentEvent === 'final_bundle_ready') {
                setGenerationStatus('');
                setIsGenerating(false);
              } else if (currentEvent === 'error') {
                setGenerationError(typeof data.error === 'string' ? data.error : 'Generation failed.');
                setGenerationStatus('');
                setIsGenerating(false);
              }
            } catch (e) {
              console.error("Error parsing SSE data:", e);
            }
          }
        }
      }
      setIsGenerating(false);
    } catch (err) {
      console.error("Stream error:", err);
      setGenerationError('Unable to connect to generation stream.');
      setGenerationStatus('');
      setIsGenerating(false);
    }
  };

  const handleScriptPackAction = () => {
    if (!extractedSignal || isGeneratingScriptPack || isGenerating) return;
    openActionDialog('script');
  };

  const handleGenerateStreamAction = () => {
    if (!extractedSignal || !scriptPack || isGenerating) return;
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
      setGenerationStatus('Render profile saved for next generation run.');
      closeActionDialog();
      return;
    }
    if (stage === 'signal') {
      setGenerationStatus('Signal confirmed for planning and generation.');
      closeActionDialog();
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
    if (actionDialogStage === 'signal') {
      setActivePanel('source');
      setGenerationStatus('Update source material or profile, then extract signal again.');
    } else if (actionDialogStage === 'script') {
      setActivePanel('profile');
      setGenerationStatus('Adjust render profile and regenerate script pack.');
    }
    closeActionDialog();
  };

  const handleDialogRelaunch = async () => {
    if (actionDialogStage === 'signal') {
      if (!sourceDoc.trim()) {
        setActivePanel('source');
        setGenerationStatus('Add source material first, then rerun signal extraction.');
        closeActionDialog();
        return;
      }
      closeActionDialog();
      setActivePanel('profile');
      await runExtraction();
      return;
    }
    if (actionDialogStage === 'script') {
      closeActionDialog();
      await handleGenerateScriptPack();
    }
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
  const streamStatusLabel = isGenerating
    ? 'Generating'
    : generationError
      ? 'Error'
      : totalSceneCount > 0
        ? 'Complete'
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

  const stageProgress = (() => {
    if (!sourceDoc.trim()) return 0;
    if (scriptPack) return 88;
    if (generationError) return 88;
    if (totalSceneCount > 0 && !isGenerating) return 100;
    if (isGenerating) return Math.max(80, generationProgress);
    if (extractedSignal) return 70;
    if (isExtracting) return 35;
    if (activePanel === 'profile') return 45;
    if (activePanel === 'signal') return 60;
    return 20;
  })();

  const stageBadgeClass = (panel: AdvancedPanel): string => {
    if (panel === 'signal') {
      if (signalStatusLabel === 'Ready') return 'border-emerald-300 bg-emerald-100 text-emerald-800';
      if (signalStatusLabel === 'Extracting') return 'border-amber-300 bg-amber-100 text-amber-900';
      if (signalStatusLabel === 'Error') return 'border-rose-300 bg-rose-100 text-rose-900';
    }
    if (panel === 'stream') {
      if (streamStatusLabel === 'Complete') return 'border-emerald-300 bg-emerald-100 text-emerald-800';
      if (streamStatusLabel === 'Generating') return 'border-blue-300 bg-blue-100 text-blue-900';
      if (streamStatusLabel === 'Error') return 'border-rose-300 bg-rose-100 text-rose-900';
    }
    if (panel === 'script' && scriptPack) {
      return 'border-indigo-300 bg-indigo-100 text-indigo-900';
    }
    if (activePanel === panel) return 'border-blue-300 bg-blue-100 text-blue-900';
    return 'border-slate-300 bg-slate-100 text-slate-700';
  };
  const activeStageNote = activePanel === 'source'
    ? 'Stage 1: Ingest source material and start structured signal extraction.'
    : activePanel === 'profile'
      ? 'Stage 2: Set audience and style controls while extraction continues.'
      : activePanel === 'signal'
        ? 'Stage 3: Review extracted signal and confirm readiness for stream generation.'
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
      : actionDialogStage === 'signal'
        ? {
          title: 'Confirm Signal?',
          description: 'You moved to Script Pack. Continue to confirm this signal, or amend and relaunch extraction.',
          continueLabel: 'Confirm and Continue',
          amendLabel: 'Amend Signal',
          amendHelp: 'If the signal is off, update source material or profile controls, then relaunch extraction to rebuild claims, concepts, and narrative beats.',
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
    || (actionDialogStage === 'extract' && (!sourceDoc.trim() || isExtracting))
    || (actionDialogStage === 'signal' && !extractedSignal)
    || (actionDialogStage === 'script' && (!extractedSignal || isGeneratingScriptPack || isGenerating))
    || (actionDialogStage === 'stream' && (!extractedSignal || !scriptPack || isGenerating));

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
                      Start with source text. Extraction can run while you configure style in the next stage.
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
                          required
                        />
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <Button type="submit" className="w-full" disabled={isExtracting} size="lg">
                          {isExtracting ? (
                            <>
                              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                              Extracting Signal...
                            </>
                          ) : (
                            'Extract Content Signal'
                          )}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          className="w-full border-slate-300"
                          onClick={() => setActivePanel(collapseTarget.source)}
                        >
                          Collapse Window
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
                      Configure output while signal extraction runs in parallel.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="high-contrast-form-labels space-y-5">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="visualMode">Visual Mode</Label>
                        <Select value={visualMode} onValueChange={setVisualMode}>
                          <SelectTrigger id="visualMode" className="bg-white text-slate-900 border-slate-300 data-[placeholder]:text-slate-500">
                            <SelectValue placeholder="Select..." />
                          </SelectTrigger>
                          <SelectContent className="bg-white text-slate-900 border-slate-300">
                            <SelectItem value="diagram">Diagram</SelectItem>
                            <SelectItem value="illustration">Illustration</SelectItem>
                            <SelectItem value="hybrid">Hybrid</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="artifactType">Artifact Type</Label>
                        <Select value={artifactType} onValueChange={setArtifactType}>
                          <SelectTrigger id="artifactType" className="bg-white text-slate-900 border-slate-300 data-[placeholder]:text-slate-500">
                            <SelectValue placeholder="Select artifact type" />
                          </SelectTrigger>
                          <SelectContent className="bg-white text-slate-900 border-slate-300">
                            <SelectItem value="storyboard_grid">Storyboard Grid</SelectItem>
                            <SelectItem value="technical_infographic">Technical Infographic</SelectItem>
                            <SelectItem value="process_diagram">Process Diagram</SelectItem>
                            <SelectItem value="comparison_one_pager">Comparison One-Pager</SelectItem>
                            <SelectItem value="slide_thumbnail">Slide Thumbnail</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="fidelity">Fidelity</Label>
                        <Select value={fidelity} onValueChange={setFidelity}>
                          <SelectTrigger id="fidelity" className="bg-white text-slate-900 border-slate-300 data-[placeholder]:text-slate-500">
                            <SelectValue placeholder="Select..." />
                          </SelectTrigger>
                          <SelectContent className="bg-white text-slate-900 border-slate-300">
                            <SelectItem value="low">Low (Draft)</SelectItem>
                            <SelectItem value="medium">Medium</SelectItem>
                            <SelectItem value="high">High (Final)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="lowKeyPreview">Low-Key Preview</Label>
                        <Select value={lowKeyPreview ? "on" : "off"} onValueChange={(v) => setLowKeyPreview(v === "on")}>
                          <SelectTrigger id="lowKeyPreview" className="bg-white text-slate-900 border-slate-300 data-[placeholder]:text-slate-500">
                            <SelectValue placeholder="Select mode" />
                          </SelectTrigger>
                          <SelectContent className="bg-white text-slate-900 border-slate-300">
                            <SelectItem value="on">On (Faster Draft)</SelectItem>
                            <SelectItem value="off">Off (Higher Quality)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="density">Information Density</Label>
                        <Select value={density} onValueChange={setDensity}>
                          <SelectTrigger id="density" className="bg-white text-slate-900 border-slate-300 data-[placeholder]:text-slate-500">
                            <SelectValue placeholder="Select..." />
                          </SelectTrigger>
                          <SelectContent className="bg-white text-slate-900 border-slate-300">
                            <SelectItem value="simple">Simple</SelectItem>
                            <SelectItem value="standard">Standard</SelectItem>
                            <SelectItem value="detailed">Detailed</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="audienceLevel">Audience Level</Label>
                        <Select value={audienceLevel} onValueChange={setAudienceLevel}>
                          <SelectTrigger id="audienceLevel" className="bg-white text-slate-900 border-slate-300 data-[placeholder]:text-slate-500">
                            <SelectValue placeholder="Select audience level" />
                          </SelectTrigger>
                          <SelectContent className="bg-white text-slate-900 border-slate-300">
                            <SelectItem value="beginner">Beginner</SelectItem>
                            <SelectItem value="intermediate">Intermediate</SelectItem>
                            <SelectItem value="expert">Expert</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="audiencePersona">Audience Persona</Label>
                      <Input
                        id="audiencePersona"
                        value={audiencePersona}
                        onChange={e => setAudiencePersona(e.target.value)}
                        placeholder="e.g. Product manager, data journalist, startup founder"
                        className="bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
                      />
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

                    <div className="space-y-2">
                      <Label htmlFor="tasteBar">Taste Bar</Label>
                      <Select value={tasteBar} onValueChange={setTasteBar}>
                        <SelectTrigger id="tasteBar" className="bg-white text-slate-900 border-slate-300 data-[placeholder]:text-slate-500">
                          <SelectValue placeholder="Select taste bar" />
                        </SelectTrigger>
                        <SelectContent className="bg-white text-slate-900 border-slate-300">
                          <SelectItem value="standard">Standard</SelectItem>
                          <SelectItem value="high">High</SelectItem>
                          <SelectItem value="very_high">Very High</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

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

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                      <Button
                        type="button"
                        className="w-full"
                        onClick={handleApplyRenderProfile}
                      >
                        Apply Render Profile
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        className="w-full border-slate-300"
                        onClick={() => setActivePanel(collapseTarget.profile)}
                      >
                        Collapse Window
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
                          <h4 className="font-semibold mb-1">Signal Locked</h4>
                          <p className="text-sm">
                            Ready to collapse this panel and move to generation stream.
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
                        className="w-full"
                        onClick={handleConfirmSignal}
                        disabled={!extractedSignal}
                      >
                        Confirm Signal
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        className="w-full border-slate-300"
                        onClick={() => setActivePanel(collapseTarget.signal)}
                      >
                        Collapse Window
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
                      <Button className="w-full" size="lg" onClick={() => void handleGenerateStreamAction()} disabled={isGenerating || !extractedSignal || !scriptPack || isGeneratingScriptPack}>
                        {isGenerating ? (
                          <>
                            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                            Generating Stream...
                          </>
                        ) : isGeneratingScriptPack ? (
                          'Script Pack in Progress...'
                        ) : !scriptPack ? (
                          'Generate Script Pack First'
                        ) : !extractedSignal ? (
                          'Extract Signal First'
                        ) : (
                          'Generate Explainer Stream'
                        )}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        className="w-full border-slate-300"
                        onClick={() => setActivePanel(collapseTarget.stream)}
                      >
                        Collapse Window
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
                    ) : (
                      <div className="flex min-h-[220px] flex-col items-center justify-center rounded-md border-2 border-dashed border-slate-300 p-8 text-slate-500">
                        <p className="text-center font-medium">Script pack not available yet.</p>
                        <p className="mt-1 text-center text-sm">Generate script pack first, then review before starting stream.</p>
                      </div>
                    )}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <Button
                        type="button"
                        className="w-full"
                        onClick={() => void handleScriptPackAction()}
                        disabled={isGeneratingScriptPack || isGenerating || !extractedSignal}
                      >
                        {isGeneratingScriptPack ? 'Generating Script Pack...' : scriptPack ? 'Regenerate Script Pack' : 'Generate Script Pack'}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        className="w-full border-slate-300"
                        onClick={() => setActivePanel(collapseTarget.script)}
                      >
                        Collapse Window
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}
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
                audioUrl={scene.audioUrl} 
                visualMode={visualMode}
                onRegenerate={handleRegenerate}
                claimRefs={scene.claim_refs}
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
            <FinalBundle scenes={scenes} topic={extractedSignal?.thesis?.one_liner || 'Advanced Explainer'} />
          )}
        </div>

      </div>
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
                  disabled={actionDialogStage === 'script' ? isGenerating || !extractedSignal : isExtracting}
                >
                  Relaunch Segment
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}
