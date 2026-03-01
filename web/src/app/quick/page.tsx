"use client";

import Image from 'next/image';
import React, { useState } from 'react';
import SceneCard from '@/components/SceneCard';
import FinalBundle from '@/components/FinalBundle';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2 } from "lucide-react";

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

export default function QuickGenerate() {
  const [topic, setTopic] = useState('');
  const [audience, setAudience] = useState('Beginner');
  const [customAudience, setCustomAudience] = useState('');
  const [tone, setTone] = useState('');
  const [visualMode, setVisualMode] = useState('illustration');
  const [isGenerating, setIsGenerating] = useState(false);
  const [scenes, setScenes] = useState<Record<string, QuickScene>>({});

  const fullTextBuffer = React.useRef<Record<string, string>>({});

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

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic) return;
    
    setIsGenerating(true);
    setScenes({}); 
    fullTextBuffer.current = {};
    
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
    });

    eventSource.addEventListener('scene_start', (event) => {
      const data = JSON.parse(event.data);
      fullTextBuffer.current[data.scene_id] = ''; 
      updateSceneMetadata(data.scene_id, { title: data.title, status: 'generating' });
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
    });

    eventSource.addEventListener('final_bundle_ready', () => {
      eventSource.close();
      setIsGenerating(false);
    });

    eventSource.addEventListener('error', (event) => {
      console.error("SSE Error:", event);
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
                <Label htmlFor="topic">Topic</Label>
                <Input 
                  id="topic" 
                  value={topic} 
                  onChange={e => setTopic(e.target.value)} 
                  placeholder="e.g. How does photosynthesis work?" 
                  required 
                  className="text-lg bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="audience">Target Audience</Label>
                <Select value={audience} onValueChange={setAudience}>
                  <SelectTrigger id="audience" className="bg-white text-slate-900 border-slate-300 data-[placeholder]:text-slate-500">
                    <SelectValue placeholder="Select audience" />
                  </SelectTrigger>
                  <SelectContent className="bg-white text-slate-900 border-slate-300">
                    <SelectItem value="Beginner">Beginner (Simple language)</SelectItem>
                    <SelectItem value="Intermediate">Intermediate (General Public)</SelectItem>
                    <SelectItem value="Expert">Expert (Technical)</SelectItem>
                    <SelectItem value="Other">Other (Specify...)</SelectItem>
                  </SelectContent>
                </Select>
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
                    className="bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
                  />
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="visualMode">Visual Style</Label>
                <Select value={visualMode} onValueChange={setVisualMode}>
                  <SelectTrigger id="visualMode" className="bg-white text-slate-900 border-slate-300 data-[placeholder]:text-slate-500">
                    <SelectValue placeholder="Select visual style" />
                  </SelectTrigger>
                  <SelectContent className="bg-white text-slate-900 border-slate-300">
                    <SelectItem value="illustration">Illustration (Cinematic 3D)</SelectItem>
                    <SelectItem value="diagram">Diagram (Clean Vectors)</SelectItem>
                    <SelectItem value="hybrid">Hybrid (3D + UI Elements)</SelectItem>
                  </SelectContent>
                </Select>
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
            </form>
          </CardContent>
        </Card>

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
