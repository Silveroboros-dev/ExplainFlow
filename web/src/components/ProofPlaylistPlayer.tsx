"use client";

import React, { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { SkipBack, SkipForward, X } from "lucide-react";

export type ProofPlaylistSegment = {
  segment_id: string;
  title: string;
  caption_text: string;
  claim_refs: string[];
  kind: "youtube" | "video" | "image";
  render_label: string;
  source_label?: string | null;
  range_label?: string | null;
  duration_ms: number;
  image_url?: string | null;
  video_src?: string | null;
  youtube_embed_url?: string | null;
  start_ms?: number | null;
  end_ms?: number | null;
};

type ProofPlaylistPlayerProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  segments: ProofPlaylistSegment[];
  unmuteLocalSourceClips: boolean;
};

const SEGMENT_END_FUDGE_SECONDS = 0.1;

export default function ProofPlaylistPlayer({
  open,
  onOpenChange,
  title,
  segments,
  unmuteLocalSourceClips,
}: ProofPlaylistPlayerProps) {
  const [currentSegmentIndex, setCurrentSegmentIndex] = useState(0);
  const timerRef = useRef<number | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const currentSegment = segments[currentSegmentIndex] ?? null;

  const clearPlaybackTimer = () => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const goToSegment = (nextIndex: number) => {
    clearPlaybackTimer();
    if (nextIndex < 0) {
      setCurrentSegmentIndex(0);
      return;
    }
    if (nextIndex >= segments.length) {
      onOpenChange(false);
      return;
    }
    setCurrentSegmentIndex(nextIndex);
  };

  const goToNextSegment = () => {
    goToSegment(currentSegmentIndex + 1);
  };

  const goToPreviousSegment = () => {
    goToSegment(currentSegmentIndex - 1);
  };

  useEffect(() => {
    if (!open) {
      clearPlaybackTimer();
      return;
    }
    setCurrentSegmentIndex(0);
    return () => {
      clearPlaybackTimer();
    };
  }, [open]);

  useEffect(() => {
    if (!open || segments.length === 0) {
      if (open && segments.length === 0) {
        onOpenChange(false);
      }
      return;
    }
    if (currentSegmentIndex >= segments.length) {
      setCurrentSegmentIndex(0);
    }
  }, [currentSegmentIndex, onOpenChange, open, segments.length]);

  useEffect(() => {
    clearPlaybackTimer();
    if (!open || !currentSegment) {
      return;
    }
    if (currentSegment.kind === "image" || currentSegment.kind === "youtube") {
      timerRef.current = window.setTimeout(() => {
        goToNextSegment();
      }, currentSegment.duration_ms);
    }
    return () => {
      clearPlaybackTimer();
    };
  }, [currentSegment, open]);

  useEffect(() => {
    if (!open || !currentSegment || currentSegment.kind !== "video") {
      return;
    }

    const video = videoRef.current;
    if (!video) {
      return;
    }

    const startSeconds = typeof currentSegment.start_ms === "number"
      ? Math.max(0, currentSegment.start_ms / 1000)
      : 0;

    const startPlayback = () => {
      if (startSeconds > 0) {
        try {
          video.currentTime = startSeconds;
        } catch {
          // Ignore if the browser refuses the seek before media is ready.
        }
      }
      const playbackAttempt = video.play();
      if (playbackAttempt && typeof playbackAttempt.catch === "function") {
        playbackAttempt.catch(() => {});
      }
    };

    if (video.readyState >= 1) {
      startPlayback();
      return;
    }

    video.addEventListener("loadedmetadata", startPlayback, { once: true });
    return () => {
      video.removeEventListener("loadedmetadata", startPlayback);
    };
  }, [currentSegment, open]);

  const handleVideoTimeUpdate = () => {
    if (!currentSegment || currentSegment.kind !== "video" || !videoRef.current) {
      return;
    }
    if (typeof currentSegment.end_ms !== "number") {
      return;
    }
    const endSeconds = currentSegment.end_ms / 1000;
    if (videoRef.current.currentTime >= endSeconds - SEGMENT_END_FUDGE_SECONDS) {
      goToNextSegment();
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="h-[92vh] w-[96vw] max-w-[1200px] overflow-hidden border-slate-800 bg-slate-950 p-0 text-white">
        <DialogTitle className="sr-only">{title}</DialogTitle>
        <DialogDescription className="sr-only">
          Plays selected proof reel segments in order as a presentation playlist.
        </DialogDescription>

        <div className="relative flex h-full flex-col bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.18),_transparent_38%),linear-gradient(180deg,_rgba(15,23,42,0.98),_rgba(2,6,23,1))]">
          <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge className="rounded-full bg-white/10 text-white hover:bg-white/10">
                  Quick Proof Playlist
                </Badge>
                <Badge variant="outline" className="rounded-full border-white/20 bg-white/5 text-slate-200">
                  {segments.length} Segments
                </Badge>
                {currentSegment ? (
                  <Badge variant="outline" className="rounded-full border-white/20 bg-white/5 text-slate-200">
                    {currentSegmentIndex + 1} / {segments.length}
                  </Badge>
                ) : null}
              </div>
              <div>
                <p className="text-sm font-medium text-slate-300">{title}</p>
                <h3 className="text-2xl font-semibold text-white">
                  {currentSegment?.title ?? "No selected proof segments"}
                </h3>
              </div>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-10 w-10 rounded-full text-slate-200 hover:bg-white/10 hover:text-white"
              onClick={() => onOpenChange(false)}
            >
              <X className="h-5 w-5" />
            </Button>
          </div>

          <div className="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden px-6 py-6">
            {currentSegment?.kind === "youtube" && currentSegment.youtube_embed_url ? (
              <iframe
                key={`${currentSegment.segment_id}-${currentSegmentIndex}`}
                title={`${currentSegment.title} playlist clip`}
                src={currentSegment.youtube_embed_url}
                className="h-full w-full rounded-[28px] border border-white/10 bg-black shadow-[0_30px_80px_rgba(0,0,0,0.45)]"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
              />
            ) : null}

            {currentSegment?.kind === "video" && currentSegment.video_src ? (
              <video
                key={`${currentSegment.segment_id}-${currentSegmentIndex}`}
                ref={videoRef}
                muted={!unmuteLocalSourceClips}
                autoPlay
                playsInline
                preload="metadata"
                className="h-full w-full rounded-[28px] border border-white/10 bg-black object-contain shadow-[0_30px_80px_rgba(0,0,0,0.45)]"
                src={currentSegment.video_src}
                onEnded={goToNextSegment}
                onTimeUpdate={handleVideoTimeUpdate}
              />
            ) : null}

            {currentSegment?.kind === "image" && currentSegment.image_url ? (
              <div className="flex h-full w-full items-center justify-center rounded-[28px] border border-white/10 bg-black/50 p-4 shadow-[0_30px_80px_rgba(0,0,0,0.45)]">
                <img
                  key={`${currentSegment.segment_id}-${currentSegmentIndex}`}
                  src={currentSegment.image_url}
                  alt={currentSegment.title}
                  className="max-h-full w-auto max-w-full rounded-[22px] object-contain"
                />
              </div>
            ) : null}

            {!currentSegment ? (
              <div className="flex h-full w-full items-center justify-center rounded-[28px] border border-dashed border-white/10 bg-white/5 p-8 text-center text-sm text-slate-300">
                Select at least one playable proof-reel segment to open the playlist.
              </div>
            ) : null}

            <div className="absolute inset-x-6 bottom-6 rounded-[28px] border border-white/10 bg-slate-950/88 p-5 shadow-[0_30px_80px_rgba(0,0,0,0.45)] backdrop-blur">
              <div className="flex flex-wrap items-center gap-2">
                <Badge className="rounded-full bg-sky-500/20 text-sky-100 hover:bg-sky-500/20">
                  {currentSegment?.render_label ?? "playlist"}
                </Badge>
                {currentSegment?.range_label ? (
                  <Badge variant="outline" className="rounded-full border-white/20 bg-white/5 text-slate-200">
                    {currentSegment.range_label}
                  </Badge>
                ) : null}
                {currentSegment?.source_label ? (
                  <Badge variant="outline" className="rounded-full border-white/20 bg-white/5 text-slate-200">
                    {currentSegment.source_label}
                  </Badge>
                ) : null}
              </div>
              <p className="mt-3 text-lg leading-8 text-white">
                {currentSegment?.caption_text ?? "No caption available for this segment."}
              </p>
              {currentSegment?.claim_refs.length ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  {currentSegment.claim_refs.map((claimRef) => (
                    <Badge key={claimRef} variant="outline" className="rounded-full border-white/20 bg-white/5 text-slate-200">
                      {claimRef}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </div>
          </div>

          <div className="flex items-center justify-between border-t border-white/10 px-6 py-4">
            <p className="text-sm text-slate-400">
              {unmuteLocalSourceClips
                ? "Local source clips play with audio. YouTube proof playback still follows embed defaults."
                : "Source clips autoplay muted in playlist mode so the reel can advance reliably."}
            </p>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                className="gap-2 rounded-full border-white/15 bg-white/5 text-slate-100 hover:bg-white/10 hover:text-white"
                onClick={goToPreviousSegment}
                disabled={!currentSegment || currentSegmentIndex === 0}
              >
                <SkipBack className="h-4 w-4" />
                Previous
              </Button>
              <Button
                type="button"
                variant="outline"
                className="gap-2 rounded-full border-white/15 bg-white/5 text-slate-100 hover:bg-white/10 hover:text-white"
                onClick={goToNextSegment}
                disabled={!currentSegment}
              >
                <SkipForward className="h-4 w-4" />
                {currentSegmentIndex >= segments.length - 1 ? "Finish" : "Next"}
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
