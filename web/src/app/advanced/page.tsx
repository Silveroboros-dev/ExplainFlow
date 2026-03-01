"use client";

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

export default function AdvancedStudio() {
  const [sourceDoc, setSourceDoc] = useState('');
  const [visualMode, setVisualMode] = useState('illustration');
  const [fidelity, setFidelity] = useState('high');
  const [density, setDensity] = useState('standard');
  const [audience, setAudience] = useState('Beginner');
  const [customAudience, setCustomAudience] = useState('');
  
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractedSignal, setExtractedSignal] = useState<any>(null);
  const [error, setError] = useState('');

  const [isGenerating, setIsGenerating] = useState(false);
  const [scenes, setScenes] = useState<Record<string, { id: string, title?: string, text: string, imageUrl?: string, audioUrl?: string, claim_refs?: string[], status: string }>>({});
  
  // Ref for the typewriter effect to track full text without causing infinite re-renders
  const fullTextBuffer = React.useRef<Record<string, string>>({});

  const updateSceneMetadata = (
    sceneId: string,
    patch: Partial<{ id: string, title?: string, imageUrl?: string, audioUrl?: string, claim_refs?: string[], status: string }>
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
      
      const data = await response.json();
      if (data.status === 'success') {
        setExtractedSignal(data.content_signal);
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
    setScenes({});
    fullTextBuffer.current = {};
    
    // Construct a strict Render Profile matching the schema
    const renderProfile = {
      profile_id: "rp_custom_" + Date.now(),
      goal: "teach",
      audience_level: audience === 'Other' ? customAudience : audience.toLowerCase(),
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
              const data = JSON.parse(dataStr);
              
              if (currentEvent === 'scene_queue_ready') {
                const initialScenes: Record<string, any> = {};
                data.scenes.forEach((s: any) => {
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
                fullTextBuffer.current[data.scene_id] = ''; // Clear placeholder
                updateSceneMetadata(data.scene_id, { title: data.title, claim_refs: data.claim_refs, status: 'generating' });
              } else if (currentEvent === 'story_text_delta') {
                fullTextBuffer.current[data.scene_id] = (fullTextBuffer.current[data.scene_id] || '') + data.delta;
              } else if (currentEvent === 'diagram_ready') {
                updateSceneMetadata(data.scene_id, { imageUrl: data.url });
              } else if (currentEvent === 'audio_ready') {
                updateSceneMetadata(data.scene_id, { audioUrl: data.url });
              } else if (currentEvent === 'scene_done') {
                updateSceneMetadata(data.scene_id, { status: 'ready' });
              } else if (currentEvent === 'final_bundle_ready' || currentEvent === 'error') {
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
    <main className="min-h-screen bg-slate-50 py-12 px-4 sm:px-6 lg:px-8 font-sans">
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Header Section */}
        <div className="text-center space-y-2">
          <h1 className="text-4xl font-extrabold tracking-tight text-slate-900">Advanced Studio</h1>
          <p className="text-lg text-slate-500">Long-document input and granular render profile control.</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          
          {/* Left Column: Input Form */}
          <div className="space-y-6">
            <Card className="shadow-sm border-slate-200">
              <CardHeader>
                <CardTitle>1. Source Material</CardTitle>
                <CardDescription>Paste your long-form document, article, or transcript.</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleExtract} className="space-y-6">
                  
                  <div className="space-y-2">
                    <Label htmlFor="sourceDoc">Document Text</Label>
                    <Textarea 
                      id="sourceDoc" 
                      value={sourceDoc} 
                      onChange={e => setSourceDoc(e.target.value)} 
                      placeholder="Paste long document here..." 
                      className="min-h-[250px] text-base"
                      required
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="visualMode">Visual Mode</Label>
                      <Select value={visualMode} onValueChange={setVisualMode}>
                        <SelectTrigger id="visualMode">
                          <SelectValue placeholder="Select..." />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="diagram">Diagram</SelectItem>
                          <SelectItem value="illustration">Illustration</SelectItem>
                          <SelectItem value="hybrid">Hybrid</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="fidelity">Fidelity</Label>
                      <Select value={fidelity} onValueChange={setFidelity}>
                        <SelectTrigger id="fidelity">
                          <SelectValue placeholder="Select..." />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="low">Low (Draft)</SelectItem>
                          <SelectItem value="medium">Medium</SelectItem>
                          <SelectItem value="high">High (Final)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="density">Information Density</Label>
                      <Select value={density} onValueChange={setDensity}>
                        <SelectTrigger id="density">
                          <SelectValue placeholder="Select..." />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="simple">Simple</SelectItem>
                          <SelectItem value="standard">Standard</SelectItem>
                          <SelectItem value="detailed">Detailed</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="audience">Target Audience</Label>
                      <Select value={audience} onValueChange={setAudience}>
                        <SelectTrigger id="audience">
                          <SelectValue placeholder="Select audience" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Beginner">Beginner (Simple language)</SelectItem>
                          <SelectItem value="Intermediate">Intermediate (General Public)</SelectItem>
                          <SelectItem value="Expert">Expert (Technical)</SelectItem>
                          <SelectItem value="Other">Other (Specify...)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  {audience === 'Other' && (
                    <div className="space-y-2">
                      <Label htmlFor="customAudience">Specify Audience</Label>
                      <Input 
                        id="customAudience" 
                        value={customAudience} 
                        onChange={e => setCustomAudience(e.target.value)} 
                        placeholder="e.g. 5-year old children, investors..." 
                        required 
                      />
                    </div>
                  )}

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
            <Card className="shadow-sm border-slate-200 h-full flex flex-col">
              <CardHeader>
                <CardTitle>2. Content Signal</CardTitle>
                <CardDescription>The style-agnostic extraction of your document.</CardDescription>
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
          {Object.values(scenes).length > 0 && (
            <h2 className="text-2xl font-bold tracking-tight text-slate-900 mb-6">Generated Explainer</h2>
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
