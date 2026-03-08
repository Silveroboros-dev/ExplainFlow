"use client";

import Image from 'next/image';
import React, { useState } from 'react';
import SceneCard from '@/components/SceneCard';
import FinalBundle from '@/components/FinalBundle';
import AgentActivityPanel, { AgentNote, AgentNoteType } from '@/components/AgentActivityPanel';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  type LucideIcon,
  Blend,
  Blocks,
  GalleryVerticalEnd,
  GraduationCap,
  LayoutGrid,
  Loader2,
  Mic,
  Sparkles,
  Square,
  UserRound,
} from "lucide-react";

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

type QuickScene = {
  id: string;
  title?: string;
  text: string;
  imageUrl?: string;
  audioUrl?: string;
  status: string;
};

type SceneQueueItem = {
  scene_id: string;
  title?: string;
  narration_focus?: string;
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

const CHECKPOINT_LABELS: Record<string, string> = {
  CP1_SIGNAL_READY: "Signal Ready",
  CP2_ARTIFACTS_LOCKED: "Artifacts Locked",
  CP3_RENDER_LOCKED: "Render Locked",
  CP4_SCRIPT_LOCKED: "Script Pack Ready",
  CP5_STREAM_COMPLETE: "Stream Complete",
  CP6_BUNDLE_FINALIZED: "Final Bundle Ready",
};

export default function QuickGenerate() {
  const [topic, setTopic] = useState('');
  const [audience, setAudience] = useState('Beginner');
  const [customAudience, setCustomAudience] = useState('');
  const [tone, setTone] = useState('');
  const [visualMode, setVisualMode] = useState('illustration');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationStatus, setGenerationStatus] = useState('');
  const [generationError, setGenerationError] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [speechError, setSpeechError] = useState('');
  const [scenes, setScenes] = useState<Record<string, QuickScene>>({});
  const [agentNotes, setAgentNotes] = useState<AgentNote[]>([]);

  const fullTextBuffer = React.useRef<Record<string, string>>({});
  const recognitionRef = React.useRef<BrowserSpeechRecognition | null>(null);

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

  const updateSceneMetadata = (
    sceneId: string,
    patch: Partial<{ id: string, title?: string, imageUrl?: string, audioUrl?: string, status: string }>
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
    return () => {
      recognitionRef.current?.stop();
      recognitionRef.current = null;
    };
  }, []);

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

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic) return;
    if (isListening && recognitionRef.current) {
      recognitionRef.current.stop();
    }
    
    setIsGenerating(true);
    setGenerationError('');
    setGenerationStatus('Connecting to generation stream...');
    setScenes({}); 
    setAgentNotes([]);
    fullTextBuffer.current = {};
    pushAgentNote("info", "Session", "Quick generation started. Planning scene outline.");
    
    const url = new URL('http://localhost:8000/api/generate-stream');
    url.searchParams.append('topic', topic);
    url.searchParams.append('audience', audience === 'Other' ? customAudience : audience);
    url.searchParams.append('tone', tone);
    url.searchParams.append('visual_mode', visualMode);
    
    const eventSource = new EventSource(url.toString());
    
    eventSource.addEventListener('scene_queue_ready', (event: MessageEvent) => {
      const data = JSON.parse(event.data) as { scenes?: SceneQueueItem[] };
      const initialScenes: Record<string, QuickScene> = {};
      (data.scenes ?? []).forEach((s) => {
        initialScenes[s.scene_id] = {
          id: s.scene_id,
          title: s.title,
          text: '',
          status: 'queued'
        };
        fullTextBuffer.current[s.scene_id] = s.narration_focus || ''; 
      });
      setScenes(initialScenes);
      setGenerationStatus('Scene queue ready. Starting generation...');
      pushAgentNote("info", "Planning", `Scene queue ready with ${Object.keys(initialScenes).length} scenes.`);
    });

    eventSource.addEventListener('scene_start', (event) => {
      const data = JSON.parse(event.data);
      fullTextBuffer.current[data.scene_id] = ''; 
      const patch: Partial<{ id: string, title?: string, imageUrl?: string, audioUrl?: string, status: string }> = {
        status: 'generating',
      };
      if (typeof data.title === 'string' && data.title.trim()) {
        patch.title = data.title;
      }
      updateSceneMetadata(data.scene_id, patch);
      if (data.title) {
        setGenerationStatus(`Generating ${data.title}...`);
        pushAgentNote("info", data.scene_id ?? "Scene", `Generating ${data.title}.`);
      }
    });

    eventSource.addEventListener('story_text_delta', (event) => {
      const data = JSON.parse(event.data);
      fullTextBuffer.current[data.scene_id] = (fullTextBuffer.current[data.scene_id] || '') + data.delta;
    });

    eventSource.addEventListener('diagram_ready', (event) => {
      const data = JSON.parse(event.data);
      updateSceneMetadata(data.scene_id, { imageUrl: data.url });
    });

    eventSource.addEventListener('audio_ready', (event) => {
      const data = JSON.parse(event.data);
      updateSceneMetadata(data.scene_id, { audioUrl: data.url });
    });

    eventSource.addEventListener('scene_done', (event) => {
      const data = JSON.parse(event.data);
      updateSceneMetadata(data.scene_id, { status: 'ready' });
      pushAgentNote("info", data.scene_id ?? "Scene", "Scene generation completed.");
    });

    eventSource.addEventListener('status', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as { message?: string };
        if (data.message) {
          setGenerationStatus(data.message);
          pushAgentNote("info", "Agent", data.message);
        }
      } catch {
        // Ignore malformed status chunks.
      }
    });

    eventSource.addEventListener('checkpoint', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as { checkpoint?: string; status?: string };
        const checkpoint = typeof data.checkpoint === "string" ? data.checkpoint : "";
        const status = typeof data.status === "string" ? data.status.toUpperCase() : "";
        if (!checkpoint || !status) return;
        const label = CHECKPOINT_LABELS[checkpoint] ?? checkpoint;
        const noteType: AgentNoteType = status === "FAILED" ? "error" : "checkpoint";
        pushAgentNote(noteType, "Checkpoint", `${label}: ${status}`);
      } catch {
        // Ignore malformed checkpoint chunks.
      }
    });

    eventSource.addEventListener('qa_status', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as { scene_id?: string; status?: string; reasons?: string[] };
        const sceneId = typeof data.scene_id === "string" ? data.scene_id : "Scene";
        const status = typeof data.status === "string" ? data.status.toUpperCase() : "WARN";
        const reason = Array.isArray(data.reasons) && data.reasons.length > 0 ? data.reasons[0] : "Quality check update received.";
        pushAgentNote("qa", sceneId, `QA ${status}: ${reason}`);
      } catch {
        // Ignore malformed QA chunks.
      }
    });

    eventSource.addEventListener('qa_retry', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as { scene_id?: string };
        const sceneId = typeof data.scene_id === "string" ? data.scene_id : "Scene";
        pushAgentNote("qa", sceneId, "QA requested a retry for this scene.");
      } catch {
        // Ignore malformed retry chunks.
      }
    });

    eventSource.addEventListener('final_bundle_ready', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as {
          claim_traceability?: { claims_total?: number; claims_referenced?: number };
        };
        const traceability = data.claim_traceability;
        if (traceability && typeof traceability.claims_total === "number" && typeof traceability.claims_referenced === "number") {
          pushAgentNote(
            "trace",
            "Traceability",
            `Claims covered: ${traceability.claims_referenced}/${traceability.claims_total}.`
          );
        }
      } catch {
        // Ignore malformed final bundle chunks.
      }
      eventSource.close();
      setGenerationStatus('Generation complete.');
      pushAgentNote("checkpoint", "Session", "Generation complete. Final bundle is ready.");
      setIsGenerating(false);
    });

    eventSource.addEventListener('error', (event: Event) => {
      console.error("SSE Error:", event);
      const messageEvent = event as MessageEvent;
      let serverError = '';
      if (typeof messageEvent.data === 'string' && messageEvent.data.trim()) {
        try {
          const parsed = JSON.parse(messageEvent.data) as { error?: string };
          serverError = parsed.error || '';
        } catch {
          serverError = '';
        }
      }
      setGenerationError(serverError || 'Stream connection interrupted.');
      setGenerationStatus('');
      pushAgentNote("error", "Session", serverError || "Stream connection interrupted.");
      eventSource.close();
      setIsGenerating(false);
    });
  };

  const handleRegenerate = (sceneId: string, newText: string, newImageUrl: string, newAudioUrl: string) => {
    fullTextBuffer.current[sceneId] = newText;
    setScenes(prev => ({
      ...prev,
      [sceneId]: { ...prev[sceneId], text: '', imageUrl: newImageUrl, audioUrl: newAudioUrl, status: 'ready' }
    }));
  };

  const totalSceneCount = Object.keys(scenes).length;
  const completedSceneCount = Object.values(scenes).filter(scene => scene.status === 'ready').length;
  const generationProgress = totalSceneCount > 0
    ? Math.round((completedSceneCount / totalSceneCount) * 100)
    : (isGenerating ? 8 : 0);

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
                <Button type="submit" className="w-full" disabled={isGenerating} size="lg">
                  {isGenerating ? (
                    <>
                      <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                      Generating Stream...
                    </>
                  ) : (
                    'Generate Explainer Stream'
                  )}
                </Button>
              </div>

              {(generationStatus || generationError || isGenerating) && (
                <div className="md:col-span-2 space-y-2">
                  {generationStatus && (
                    <p className="text-sm text-blue-700 font-medium">{generationStatus}</p>
                  )}
                  {isGenerating && (
                    <>
                      <Progress value={generationProgress} className="h-2 bg-blue-100 [&>*]:bg-blue-500" />
                      <p className="text-xs text-slate-600">
                        Scenes complete: {completedSceneCount}/{Math.max(totalSceneCount, completedSceneCount)}
                      </p>
                    </>
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
                status={scene.status}
                audioStatus={isGenerating && !scene.audioUrl ? "Generating..." : "Ready"} 
              />
            ))}
          </div>

          {!isGenerating && Object.values(scenes).length > 0 && (
            <FinalBundle scenes={scenes} topic={topic} />
          )}
        </div>

      </div>
    </main>
  );
}
