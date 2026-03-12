import { type SyntheticEvent, useRef, useState } from 'react';
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Loader2, Wand2, Link as LinkIcon } from "lucide-react";

interface SceneCardProps {
  sceneId: string;
  title?: string;
  text: string;
  imageUrl?: string;
  artifactType?: string;
  sourceMedia?: Array<{
    asset_id: string;
    modality: 'audio' | 'video' | 'image' | 'pdf_page';
    claim_refs: string[];
    evidence_refs: string[];
  }>;
  audioStatus: string;
  audioUrl?: string;
  claimRefs?: string[];
  status?: string;
  qaStatus?: 'PASS' | 'WARN' | 'FAIL';
  qaReasons?: string[];
  qaScore?: number;
  qaWordCount?: number;
  autoRetryCount?: number;
  sourceProofWarning?: string;
  regenerationDisabled?: boolean;
  isRegenerating?: boolean;
  onRegenerate?: (sceneId: string, instruction: string) => Promise<void>;
  onOpenEvidence?: (sceneId: string, claimRef?: string) => void;
}

export default function SceneCard({
  sceneId,
  title,
  text,
  imageUrl,
  artifactType,
  sourceMedia,
  audioStatus,
  audioUrl,
  claimRefs,
  status = 'ready',
  qaStatus,
  qaReasons = [],
  qaScore,
  qaWordCount,
  autoRetryCount,
  sourceProofWarning,
  regenerationDisabled = false,
  isRegenerating = false,
  onRegenerate,
  onOpenEvidence,
}: SceneCardProps) {
  const [instruction, setInstruction] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [regenerationError, setRegenerationError] = useState('');
  const [imageFitClass, setImageFitClass] = useState<'w-full h-auto' | 'w-auto h-full'>('w-full h-auto');
  const imageViewportRef = useRef<HTMLDivElement | null>(null);
  const showAudio = artifactType !== 'slide_thumbnail';
  const hasSourceProofs = Array.isArray(sourceMedia) && sourceMedia.length > 0;
  const claimHasSourceProof = (claimRef: string): boolean => (
    Array.isArray(sourceMedia)
      ? sourceMedia.some((item) => Array.isArray(item.claim_refs) && item.claim_refs.includes(claimRef))
      : false
  );

  // Determine badge color based on status
  const badgeColor = status === 'queued' ? 'bg-slate-200 text-slate-600' : 
                     status === 'generating' || status === 'retrying' ? 'bg-blue-100 text-blue-700 border-blue-200 animate-pulse' :
                     status === 'qa-failed' ? 'bg-rose-100 text-rose-700 border-rose-200' :
                     'bg-green-100 text-green-700 border-green-200';
  const qaBadgeColor = qaStatus === 'PASS'
    ? 'bg-emerald-100 text-emerald-700 border-emerald-200'
    : qaStatus === 'WARN'
      ? 'bg-amber-100 text-amber-700 border-amber-200'
      : 'bg-rose-100 text-rose-700 border-rose-200';

  const handleRegenSubmit = async () => {
    const nextInstruction = instruction.trim();
    if (!nextInstruction || regenerationDisabled || !onRegenerate) return;

    setRegenerationError('');
    try {
      await onRegenerate(sceneId, nextInstruction);
      setIsOpen(false);
      setInstruction('');
    } catch (err) {
      console.error("Regen failed:", err);
      setRegenerationError(err instanceof Error ? err.message : 'Unable to regenerate scene.');
    }
  };

  const handleSceneImageLoad = (event: SyntheticEvent<HTMLImageElement>) => {
    const img = event.currentTarget;
    const viewport = imageViewportRef.current;
    if (!viewport) return;

    const naturalWidth = img.naturalWidth || 1;
    const naturalHeight = img.naturalHeight || 1;
    const viewportWidth = viewport.clientWidth || 1;
    const viewportHeight = viewport.clientHeight || 1;

    const imageRatio = naturalWidth / naturalHeight;
    const viewportRatio = viewportWidth / viewportHeight;
    setImageFitClass(imageRatio >= viewportRatio ? 'w-full h-auto' : 'w-auto h-full');
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
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <h3 className="text-xl font-semibold">{title || `Scene: ${sceneId}`}</h3>
                <Badge className={`${badgeColor} uppercase text-[10px] tracking-wider border pointer-events-none`}>
                  {status}
                </Badge>
              </div>
              {claimRefs && claimRefs.length > 0 && (
                <div className="flex gap-1 flex-wrap justify-end">
                  {claimRefs.map(ref => (
                    claimHasSourceProof(ref) && onOpenEvidence ? (
                      <button
                        key={ref}
                        type="button"
                        onClick={() => onOpenEvidence(sceneId, ref)}
                        className="rounded-full"
                      >
                        <Badge variant="secondary" className="text-[10px] flex items-center gap-1 opacity-90 hover:opacity-100 cursor-pointer">
                          <LinkIcon className="h-3 w-3" />
                          {ref}
                        </Badge>
                      </button>
                    ) : (
                      <Badge key={ref} variant="secondary" className="text-[10px] flex items-center gap-1 opacity-70">
                        <LinkIcon className="h-3 w-3" />
                        {ref}
                      </Badge>
                    )
                  ))}
                </div>
              )}
            </div>
            <p className={`leading-relaxed transition-opacity duration-300 ${status === 'queued' ? 'text-slate-400 italic' : 'text-slate-700'}`}>
              {text || (status === 'queued' ? "Waiting for AI generation..." : "")}
            </p>
            {qaStatus && (
              <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge className={`${qaBadgeColor} border text-[10px] tracking-wider`}>QA {qaStatus}</Badge>
                  {typeof qaScore === 'number' && (
                    <span className="text-xs text-slate-600">Score: {qaScore.toFixed(2)}</span>
                  )}
                  {typeof qaWordCount === 'number' && (
                    <span className="text-xs text-slate-600">Words: {qaWordCount}</span>
                  )}
                  {(autoRetryCount ?? 0) > 0 && (
                    <span className="text-xs text-slate-600">Auto-retries: {autoRetryCount}</span>
                  )}
                </div>
                {qaReasons.length > 0 && (
                  <p className="mt-2 text-xs text-slate-600">
                    {qaReasons.slice(0, 2).join(' ')}
                  </p>
                )}
              </div>
            )}
            {!hasSourceProofs && sourceProofWarning ? (
              <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-amber-900">Source Proof Warning</p>
                <p className="mt-1 text-sm text-amber-950">{sourceProofWarning}</p>
              </div>
            ) : null}
            {hasSourceProofs && onOpenEvidence && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="mt-2 px-0 text-xs text-slate-600 hover:text-slate-900"
                onClick={() => onOpenEvidence(sceneId)}
              >
                View Source Proof ({sourceMedia?.length ?? 0})
              </Button>
            )}
          </div>
          
          <div className="mt-auto pt-4">
            {showAudio ? (
              audioUrl ? (
                <audio controls src={audioUrl} className="w-full h-10 rounded-md">
                  Your browser does not support the audio element.
                </audio>
              ) : (
                <div className="h-10 flex items-center px-4 bg-slate-100 rounded-md border border-slate-200">
                  <p className="text-sm text-slate-500 font-medium">Audio: {audioStatus}</p>
                </div>
              )
            ) : null}

            <Dialog
              open={isOpen}
              onOpenChange={(nextOpen) => {
                if (!nextOpen && isRegenerating) return;
                setIsOpen(nextOpen);
                if (!nextOpen) {
                  setRegenerationError('');
                }
              }}
            >
              <DialogTrigger asChild>
                <Button variant="outline" size="sm" className="mt-4 gap-2" disabled={regenerationDisabled || isRegenerating}>
                  <Wand2 className="h-4 w-4" />
                  Regenerate Scene
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Regenerate Scene</DialogTitle>
                  <DialogDescription>
                    Tell the AI what to change about this scene (for example: make it more dramatic, or focus more on the chemistry).
                  </DialogDescription>
                </DialogHeader>
                <div className="py-4">
                  <Textarea 
                    placeholder="Instruction for regeneration..." 
                    value={instruction}
                    onChange={(e) => {
                      setInstruction(e.target.value);
                      if (regenerationError) {
                        setRegenerationError('');
                      }
                    }}
                    className="min-h-[100px]"
                  />
                  {regenerationError ? (
                    <p className="mt-3 text-sm text-rose-600">{regenerationError}</p>
                  ) : null}
                </div>
                <DialogFooter>
                  <Button variant="ghost" onClick={() => setIsOpen(false)} disabled={isRegenerating}>Cancel</Button>
                  <Button onClick={handleRegenSubmit} disabled={isRegenerating || regenerationDisabled || !instruction.trim()}>
                    {isRegenerating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Wand2 className="mr-2 h-4 w-4" />}
                    Apply Edit
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Right Side: Visual */}
        <div className="flex-1 bg-slate-100 min-h-[300px] md:min-h-[340px] border-l border-slate-200 relative p-4">
          <div
            ref={imageViewportRef}
            className="w-full h-full min-h-[260px] md:min-h-[320px] rounded-md border border-slate-200 bg-slate-50 flex items-center justify-center overflow-hidden"
          >
            {imageUrl ? (
              <img
                src={imageUrl}
                alt="Scene Visual"
                loading="lazy"
                onLoad={handleSceneImageLoad}
                className={`${imageFitClass} max-w-full max-h-full object-contain rounded-md drop-shadow-sm`}
              />
            ) : (
              <div className="flex flex-col items-center justify-center text-slate-400">
                <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mb-2 opacity-50"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>
                <span className="font-medium text-sm">Waiting for visual...</span>
              </div>
            )}
          </div>
          {imageUrl && (
            <div className="pointer-events-none absolute inset-x-4 bottom-4 h-10 bg-gradient-to-t from-slate-50/75 to-transparent rounded-b-md" />
          )}
        </div>
      </div>
    </Card>
  );
}
