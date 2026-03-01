import { useState } from 'react';
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Wand2 } from "lucide-react";

interface SceneCardProps {
  sceneId: string;
  title?: string;
  text: string;
  imageUrl?: string;
  audioStatus: string;
  audioUrl?: string;
  visualMode?: string;
  onRegenerate?: (sceneId: string, newText: string, newImageUrl: string, newAudioUrl: string) => void;
}

export default function SceneCard({ sceneId, title, text, imageUrl, audioStatus, audioUrl, visualMode, onRegenerate }: SceneCardProps) {
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [instruction, setInstruction] = useState('');
  const [isOpen, setIsOpen] = useState(false);

  const handleRegenSubmit = async () => {
    if (!instruction) return;
    setIsRegenerating(true);
    
    try {
      const response = await fetch('http://localhost:8000/api/regenerate-scene', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scene_id: sceneId,
          current_text: text,
          instruction: instruction,
          visual_mode: visualMode || 'illustration'
        })
      });
      
      const data = await response.json();
      if (data.status === 'success' && onRegenerate) {
        onRegenerate(sceneId, data.text, data.imageUrl, data.audioUrl);
        setIsOpen(false);
        setInstruction('');
      }
    } catch (err) {
      console.error("Regen failed:", err);
    } finally {
      setIsRegenerating(false);
    }
  };

  return (
    <Card className={`w-full mb-4 overflow-hidden border-slate-200 transition-all ${isRegenerating ? 'opacity-50 grayscale' : ''}`}>
      <div className="flex flex-col md:flex-row h-full relative">
        
        {isRegenerating && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/50 backdrop-blur-sm">
            <div className="flex flex-col items-center gap-2">
              <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
              <p className="text-sm font-medium text-blue-900">Regenerating Scene...</p>
            </div>
          </div>
        )}

        {/* Left Side: Narration & Audio */}
        <div className="flex-1 p-6 flex flex-col gap-4">
          <div>
            <h3 className="text-xl font-semibold mb-2">{title || `Scene: ${sceneId}`}</h3>
            <p className="text-muted-foreground leading-relaxed">{text}</p>
          </div>
          
          <div className="mt-auto pt-4">
            {audioUrl ? (
              <audio controls src={audioUrl} className="w-full h-10 rounded-md">
                Your browser does not support the audio element.
              </audio>
            ) : (
              <div className="h-10 flex items-center px-4 bg-slate-100 rounded-md border border-slate-200">
                <p className="text-sm text-slate-500 font-medium">Audio: {audioStatus}</p>
              </div>
            )}
            
            <Dialog open={isOpen} onOpenChange={setIsOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" size="sm" className="mt-4 gap-2">
                  <Wand2 className="h-4 w-4" />
                  Regenerate Scene
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Regenerate Scene</DialogTitle>
                  <DialogDescription>
                    Tell the AI what to change about this scene (e.g., "Make it more dramatic" or "Focus more on the chemistry").
                  </DialogDescription>
                </DialogHeader>
                <div className="py-4">
                  <Textarea 
                    placeholder="Instruction for regeneration..." 
                    value={instruction}
                    onChange={(e) => setInstruction(e.target.value)}
                    className="min-h-[100px]"
                  />
                </div>
                <DialogFooter>
                  <Button variant="ghost" onClick={() => setIsOpen(false)}>Cancel</Button>
                  <Button onClick={handleRegenSubmit} disabled={isRegenerating || !instruction}>
                    {isRegenerating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Wand2 className="mr-2 h-4 w-4" />}
                    Apply Edit
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Right Side: Visual */}
        <div className="flex-1 bg-slate-100 min-h-[300px] flex items-center justify-center border-l border-slate-200 relative overflow-hidden">
          {imageUrl ? (
            <img src={imageUrl} alt="Scene Visual" className="absolute inset-0 w-full h-full object-cover" />
          ) : (
            <div className="flex flex-col items-center justify-center text-slate-400">
              <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mb-2 opacity-50"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>
              <span className="font-medium text-sm">Waiting for visual...</span>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
