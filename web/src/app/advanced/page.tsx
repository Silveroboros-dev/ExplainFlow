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
};

type SceneQueueItem = {
  scene_id: string;
  title?: string;
  claim_refs?: string[];
  narration_focus?: string;
};

export default function AdvancedStudio() {
  const [sourceDoc, setSourceDoc] = useState('');
  const [visualMode, setVisualMode] = useState('illustration');
  const [fidelity, setFidelity] = useState('high');
  const [density, setDensity] = useState('standard');
  const [audienceLevel, setAudienceLevel] = useState('intermediate');
  const [audiencePersona, setAudiencePersona] = useState('Product manager');
  const [domainContext, setDomainContext] = useState('');
  const [tasteBar, setTasteBar] = useState('high');
  const [mustIncludeText, setMustIncludeText] = useState('');
  const [mustAvoidText, setMustAvoidText] = useState('');
  
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractedSignal, setExtractedSignal] = useState<ExtractedSignal | null>(null);
  const [error, setError] = useState('');
  const [generationError, setGenerationError] = useState('');
  const [typedExplainer, setTypedExplainer] = useState('');
  const [typedPreview, setTypedPreview] = useState('');

  const [isGenerating, setIsGenerating] = useState(false);
  const [scenes, setScenes] = useState<Record<string, SceneViewModel>>({});
  
  // Ref for the typewriter effect to track full text without causing infinite re-renders
  const fullTextBuffer = React.useRef<Record<string, string>>({});

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

  const handleExtract = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceDoc) return;
    
    setIsExtracting(true);
    setError('');
    setExtractedSignal(null);
    setScenes({});
    fullTextBuffer.current = {};
    
    try {
      const response = await fetch('http://localhost:8000/api/extract-signal', {
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
      } else {
        setError(data.message || 'Extraction failed');
      }
    } catch {
      setError('Network error during extraction');
    } finally {
      setIsExtracting(false);
    }
  };

  const handleGenerateStream = async () => {
    if (!extractedSignal) return;
    
    setIsGenerating(true);
    setGenerationError('');
    setScenes({});
    fullTextBuffer.current = {};
    
    // Construct a strict Render Profile matching the schema
    const renderProfile = {
      profile_id: "rp_custom_" + Date.now(),
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
    };

    try {
      const response = await fetch('http://localhost:8000/api/generate-stream-advanced', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content_signal: extractedSignal,
          render_profile: renderProfile
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
              const data: unknown = JSON.parse(dataStr);
              
              if (currentEvent === 'scene_queue_ready') {
                const queue = data as { scenes?: SceneQueueItem[] };
                const initialScenes: Record<string, SceneViewModel> = {};
                (queue.scenes ?? []).forEach((s) => {
                  initialScenes[s.scene_id] = {
                    id: s.scene_id,
                    title: s.title,
                    claim_refs: s.claim_refs,
                    text: '',
                    status: 'queued'
                  };
                  fullTextBuffer.current[s.scene_id] = s.narration_focus || ''; 
                });
                setScenes(initialScenes);
              } else if (currentEvent === 'scene_start') {
                const payload = data as { scene_id: string; title?: string; claim_refs?: string[] };
                fullTextBuffer.current[payload.scene_id] = ''; // Clear placeholder
                updateSceneMetadata(payload.scene_id, { title: payload.title, claim_refs: payload.claim_refs, status: 'generating' });
              } else if (currentEvent === 'story_text_delta') {
                const payload = data as { scene_id: string; delta?: string };
                fullTextBuffer.current[payload.scene_id] = (fullTextBuffer.current[payload.scene_id] || '') + (payload.delta || '');
              } else if (currentEvent === 'diagram_ready') {
                const payload = data as { scene_id: string; url?: string };
                updateSceneMetadata(payload.scene_id, { imageUrl: payload.url });
              } else if (currentEvent === 'audio_ready') {
                const payload = data as { scene_id: string; url?: string };
                updateSceneMetadata(payload.scene_id, { audioUrl: payload.url });
              } else if (currentEvent === 'scene_done') {
                const payload = data as { scene_id: string };
                updateSceneMetadata(payload.scene_id, { status: 'ready' });
              } else if (currentEvent === 'final_bundle_ready') {
                setIsGenerating(false);
              } else if (currentEvent === 'error') {
                const payload = data as { error?: string };
                setGenerationError(payload.error || 'Generation failed.');
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
      setIsGenerating(false);
    }
  };

  const handleRegenerate = (sceneId: string, newText: string, newImageUrl: string, newAudioUrl: string) => {
    fullTextBuffer.current[sceneId] = newText;
    setScenes(prev => ({
      ...prev,
      [sceneId]: { ...prev[sceneId], text: '', imageUrl: newImageUrl, audioUrl: newAudioUrl, status: 'ready' }
    }));
  };

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

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          
          {/* Left Column: Input Form */}
          <div className="space-y-6">
            <Card className="bg-white text-slate-900 backdrop-blur-xl shadow-xl border-slate-300/70">
              <CardHeader>
                <CardTitle className="text-slate-900">1. Source Material</CardTitle>
                <CardDescription className="text-slate-600">Paste your long-form document, article, or transcript.</CardDescription>
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
                      className="min-h-[250px] text-base bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
                      required
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
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
                      required
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
                  
                  {error && <p className="text-red-500 text-sm font-medium">{error}</p>}
                </form>
              </CardContent>
            </Card>
          </div>

          {/* Right Column: Signal Data & Next Steps */}
          <div className="space-y-6">
            <Card className="bg-white text-slate-900 backdrop-blur-xl shadow-xl border-slate-300/70 h-full flex flex-col">
              <CardHeader>
                <CardTitle className="text-slate-900">2. Content Signal</CardTitle>
                <CardDescription className="text-slate-600">The style-agnostic extraction of your document.</CardDescription>
              </CardHeader>
              <CardContent className="flex-1 flex flex-col">
                {extractedSignal ? (
                  <div className="space-y-4 flex-1 flex flex-col">
                    <div className="bg-slate-900 text-slate-50 p-4 rounded-md overflow-auto max-h-[400px] text-xs font-mono">
                      <pre>{JSON.stringify(extractedSignal, null, 2)}</pre>
                    </div>
                    
                    <div className="mt-auto pt-4 space-y-4">
                      <div className="p-4 bg-blue-50 text-blue-900 rounded-md border border-blue-200">
                        <h4 className="font-semibold mb-1">Ready for Generation</h4>
                        <p className="text-sm">The content signal is locked. You can now generate the explainer stream, or tweak the Render Profile settings and re-run the stream without re-extracting the document.</p>
                      </div>
                      <Button className="w-full" size="lg" variant="default" onClick={handleGenerateStream} disabled={isGenerating}>
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
                  </div>
                ) : isExtracting ? (
                  <div className="space-y-4 flex-1 flex flex-col">
                    <div className="p-4 bg-amber-50 text-amber-950 rounded-md border border-amber-200">
                      <h4 className="font-semibold mb-2">Extracting Structured Signal...</h4>
                      <p className="text-sm whitespace-pre-wrap font-mono leading-6">
                        {typedExplainer}
                        <span className="animate-pulse">|</span>
                      </p>
                    </div>
                    <div className="bg-slate-900 text-slate-50 p-4 rounded-md overflow-auto max-h-[400px] text-xs font-mono">
                      <pre>
                        {typedPreview}
                        <span className="animate-pulse">|</span>
                      </pre>
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center text-slate-400 border-2 border-dashed border-slate-200 rounded-md p-8">
                    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mb-4 opacity-50"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/><line x1="10" x2="8" y1="9" y2="9"/></svg>
                    <p className="text-center font-medium">Awaiting source material...</p>
                    <p className="text-center text-sm mt-1">Paste a document and click Extract to see the signal JSON.</p>
                  </div>
                )}
              </CardContent>
            </Card>
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
                audioStatus={isGenerating && !scene.audioUrl ? "Generating..." : "Ready"} 
              />
            ))}
          </div>

          {!isGenerating && Object.values(scenes).length > 0 && (
            <FinalBundle scenes={scenes} topic={extractedSignal?.thesis?.one_liner || 'Advanced Explainer'} />
          )}
        </div>

      </div>
    </main>
  );
}
