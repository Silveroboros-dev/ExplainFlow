"use client";

import { useState } from 'react';
import SceneCard from '@/components/SceneCard';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2 } from "lucide-react";

export default function QuickGenerate() {
  const [topic, setTopic] = useState('');
  const [audience, setAudience] = useState('Beginner');
  const [tone, setTone] = useState('');
  const [visualMode, setVisualMode] = useState('illustration');
  const [isGenerating, setIsGenerating] = useState(false);
  const [scenes, setScenes] = useState<Record<string, { id: string, title?: string, text: string, imageUrl?: string, audioUrl?: string }>>({});

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic) return;
    
    setIsGenerating(true);
    setScenes({}); // clear previous output
    
    // Connect to the backend SSE endpoint
    const url = new URL('http://localhost:8000/api/generate-stream');
    url.searchParams.append('topic', topic);
    url.searchParams.append('audience', audience);
    url.searchParams.append('tone', tone);
    url.searchParams.append('visual_mode', visualMode);
    
    const eventSource = new EventSource(url.toString());
    
    eventSource.addEventListener('scene_start', (event) => {
      const data = JSON.parse(event.data);
      setScenes(prev => ({
        ...prev,
        [data.scene_id]: { id: data.scene_id, title: data.title, text: '' }
      }));
    });

    eventSource.addEventListener('story_text_delta', (event) => {
      const data = JSON.parse(event.data);
      setScenes(prev => {
        const scene = prev[data.scene_id];
        if (!scene) return prev;
        return {
          ...prev,
          [data.scene_id]: { ...scene, text: scene.text + data.delta }
        };
      });
    });

    eventSource.addEventListener('diagram_ready', (event) => {
      const data = JSON.parse(event.data);
      setScenes(prev => {
        const scene = prev[data.scene_id];
        if (!scene) return prev;
        return {
          ...prev,
          [data.scene_id]: { ...scene, imageUrl: data.url }
        };
      });
    });

    eventSource.addEventListener('audio_ready', (event) => {
      const data = JSON.parse(event.data);
      setScenes(prev => {
        const scene = prev[data.scene_id];
        if (!scene) return prev;
        return {
          ...prev,
          [data.scene_id]: { ...scene, audioUrl: data.url }
        };
      });
    });

    eventSource.addEventListener('scene_done', (event) => {
      // Logic for when a scene is completely finished
    });

    eventSource.addEventListener('final_bundle_ready', (event) => {
      eventSource.close();
      setIsGenerating(false);
    });

    eventSource.addEventListener('error', (event) => {
      console.error("SSE Error:", event);
      eventSource.close();
      setIsGenerating(false);
    });
  };

  return (
    <main className="min-h-screen bg-slate-50 py-12 px-4 sm:px-6 lg:px-8 font-sans">
      <div className="max-w-5xl mx-auto space-y-8">
        
        {/* Header Section */}
        <div className="text-center space-y-2">
          <h1 className="text-4xl font-extrabold tracking-tight text-slate-900">ExplainFlow</h1>
          <p className="text-lg text-slate-500">Live Interleaved Generative Storyteller</p>
        </div>

        {/* Configuration Form */}
        <Card className="shadow-sm border-slate-200">
          <CardHeader>
            <CardTitle>Quick Generate</CardTitle>
            <CardDescription>Enter a topic and style to generate a complete visual explainer instantly.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleGenerate} className="grid grid-cols-1 md:grid-cols-2 gap-6">
              
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="topic">Topic</Label>
                <Input 
                  id="topic" 
                  value={topic} 
                  onChange={e => setTopic(e.target.value)} 
                  placeholder="e.g. How does photosynthesis work?" 
                  required 
                  className="text-lg"
                />
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
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="visualMode">Visual Style</Label>
                <Select value={visualMode} onValueChange={setVisualMode}>
                  <SelectTrigger id="visualMode">
                    <SelectValue placeholder="Select visual style" />
                  </SelectTrigger>
                  <SelectContent>
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
                audioStatus={isGenerating && !scene.audioUrl ? "Generating..." : "Ready"} 
              />
            ))}
          </div>
        </div>

      </div>
    </main>
  );
}
