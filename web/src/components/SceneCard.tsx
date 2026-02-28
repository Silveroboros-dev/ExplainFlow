import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function SceneCard({ sceneId, title, text, imageUrl, audioStatus, audioUrl }: { sceneId: string, title?: string, text: string, imageUrl?: string, audioStatus: string, audioUrl?: string }) {
  return (
    <Card className="w-full mb-4 overflow-hidden border-slate-200">
      <div className="flex flex-col md:flex-row h-full">
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
            <Button variant="outline" size="sm" className="mt-4">
              Regenerate Scene
            </Button>
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
