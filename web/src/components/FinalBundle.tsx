"use client";

import { useState } from "react";
import { Download, Film, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type FinalBundleScene = {
  id: string;
  title?: string;
  text: string;
  narrationText: string;
  overlayText?: string;
  imageUrl?: string;
  audioUrl?: string;
};

interface FinalBundleProps {
  scenes: Record<string, FinalBundleScene>;
  topic: string;
  disabled?: boolean;
}

type RenderedVideo = {
  videoUrl: string;
  durationMs?: number;
};

const slugify = (value: string, fallback: string): string => {
  const slug = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || fallback;
};

const deriveOverlayText = (title?: string, narrationText?: string, suppliedOverlayText?: string): string => {
  const supplied = (suppliedOverlayText || "").trim();
  if (supplied) {
    const suppliedWords = supplied.split(/\s+/).filter(Boolean);
    if (suppliedWords.length >= 8 && suppliedWords.length <= 15) {
      return supplied;
    }
    if (suppliedWords.length > 15) {
      return `${suppliedWords.slice(0, 15).join(" ").replace(/[.,;:!?]+$/, "")}.`;
    }
  }

  const cleanTitle = (title || "").trim();
  if (cleanTitle) {
    const titleWords = cleanTitle.split(/\s+/).filter(Boolean);
    if (titleWords.length >= 8 && titleWords.length <= 15) {
      return cleanTitle;
    }
  }

  const cleanedNarration = (narrationText || "").replace(/\s+/g, " ").trim();
  if (!cleanedNarration) {
    return cleanTitle || "ExplainFlow Studio scene.";
  }

  let firstSentence = cleanedNarration.split(/(?<=[.!?])\s+/, 1)[0] || cleanedNarration;
  let words = firstSentence.split(/\s+/).filter(Boolean);
  if (words.length < 8 && cleanTitle) {
    firstSentence = `${cleanTitle}. ${firstSentence}`.trim();
    words = firstSentence.split(/\s+/).filter(Boolean);
  }
  if (words.length > 15) {
    return `${words.slice(0, 15).join(" ").replace(/[.,;:!?]+$/, "")}.`;
  }
  return firstSentence;
};

export default function FinalBundle({ scenes, topic, disabled = false }: FinalBundleProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const [isRenderingVideo, setIsRenderingVideo] = useState(false);
  const [videoError, setVideoError] = useState("");
  const [renderedVideo, setRenderedVideo] = useState<RenderedVideo | null>(null);

  const sceneOrder = (id: string): number => {
    const match = id.match(/scene-(\d+)/i);
    return match ? Number.parseInt(match[1], 10) : Number.MAX_SAFE_INTEGER;
  };

  const sceneList = Object.values(scenes).sort((a, b) => {
    const bySceneNumber = sceneOrder(a.id) - sceneOrder(b.id);
    if (bySceneNumber !== 0) return bySceneNumber;
    return a.id.localeCompare(b.id);
  });

  if (sceneList.length === 0) return null;

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const payload = {
    topic,
    scenes: sceneList.map((scene) => {
      const narrationText = scene.narrationText || scene.text;
      return {
        scene_id: scene.id,
        title: scene.title,
        text: narrationText,
        overlay_text: deriveOverlayText(scene.title, narrationText, scene.overlayText),
        image_url: scene.imageUrl,
        audio_url: scene.audioUrl,
      };
    }),
  };

  const handleDownloadBundle = async () => {
    setIsExporting(true);
    setExportError("");

    try {
      const response = await fetch(`${apiUrl}/api/final-bundle/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        let detail = "Failed to export final bundle.";
        try {
          const errorPayload = await response.json();
          if (typeof errorPayload?.detail === "string") {
            detail = errorPayload.detail;
          }
        } catch {
          // Ignore JSON parse errors and keep fallback text.
        }
        throw new Error(detail);
      }

      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = `${slugify(topic, "explainflow")}-final-bundle.zip`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(objectUrl);
    } catch (error) {
      setExportError(error instanceof Error ? error.message : "Failed to export final bundle.");
    } finally {
      setIsExporting(false);
    }
  };

  const handleRenderVideo = async () => {
    setIsRenderingVideo(true);
    setVideoError("");

    try {
      const response = await fetch(`${apiUrl}/api/final-bundle/video`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        let detail = "Failed to export Advanced MP4.";
        try {
          const errorPayload = await response.json();
          if (typeof errorPayload?.detail === "string") {
            detail = errorPayload.detail;
          }
        } catch {
          // Ignore JSON parse errors and keep fallback text.
        }
        throw new Error(detail);
      }

      const result = await response.json();
      if (typeof result?.video_url !== "string" || !result.video_url.trim()) {
        throw new Error("Advanced MP4 export returned no video URL.");
      }

      setRenderedVideo({
        videoUrl: result.video_url,
        durationMs: typeof result.duration_ms === "number" ? result.duration_ms : undefined,
      });
    } catch (error) {
      setVideoError(error instanceof Error ? error.message : "Failed to export Advanced MP4.");
    } finally {
      setIsRenderingVideo(false);
    }
  };

  const handleDownloadVideo = () => {
    if (!renderedVideo?.videoUrl) return;
    const downloadUrl = new URL(`${apiUrl}/api/final-bundle/video/download`);
    downloadUrl.searchParams.set("video_url", renderedVideo.videoUrl);
    downloadUrl.searchParams.set("filename", `${slugify(topic, "explainflow")}-studio-export`);
    const anchor = document.createElement("a");
    anchor.href = downloadUrl.toString();
    anchor.download = `${slugify(topic, "explainflow")}-studio-export.mp4`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
  };

  return (
    <Card className="bg-white text-slate-900 border-slate-300 shadow-md">
      <CardContent className="pt-6 space-y-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-4">
            <div className="space-y-1">
              <p className="font-semibold">Final Bundle Exports</p>
              <p className="text-sm text-slate-600">
                Download the bundle zip or render a narrated MP4 from the current Advanced scenes without rerunning generation.
              </p>
            </div>
            {exportError ? (
              <p className="text-sm font-medium text-rose-600">{exportError}</p>
            ) : null}
            {videoError ? (
              <p className="text-sm font-medium text-rose-600">{videoError}</p>
            ) : null}
            {disabled ? (
              <p className="text-sm font-medium text-slate-500">
                Export controls unlock when the current stream finishes.
              </p>
            ) : null}
          </div>
          <div className="flex w-full flex-col gap-3 sm:w-auto sm:min-w-[260px]">
            <Button
              type="button"
              onClick={() => void handleRenderVideo()}
              disabled={disabled || isRenderingVideo || isExporting}
              className="min-w-[220px]"
            >
              {isRenderingVideo ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Rendering Studio Export...
                </>
              ) : (
                <>
                  <Film className="mr-2 h-4 w-4" />
                  Export MP4 (Beta)
                </>
              )}
            </Button>
            <Button
              type="button"
              onClick={() => void handleDownloadBundle()}
              disabled={disabled || isExporting || isRenderingVideo}
              variant="outline"
              className="min-w-[220px]"
            >
              {isExporting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Building Zip...
                </>
              ) : (
                <>
                  <Download className="mr-2 h-4 w-4" />
                  Download Bundle Zip
                </>
              )}
            </Button>
          </div>
        </div>

        {renderedVideo ? (
          <div className="space-y-3 border-t border-slate-200 pt-5">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-semibold">Studio MP4 Export</p>
                <p className="text-sm text-slate-600">
                  Narrated export built from the current Advanced scenes.
                  {typeof renderedVideo.durationMs === "number"
                    ? ` Duration: ${Math.max(1, Math.round(renderedVideo.durationMs / 1000))}s.`
                    : ""}
                </p>
              </div>
              <Button
                type="button"
                onClick={handleDownloadVideo}
                disabled={disabled}
                variant="outline"
                className="sm:min-w-[220px]"
              >
                <Download className="mr-2 h-4 w-4" />
                Download MP4
              </Button>
            </div>
            <video
              key={renderedVideo.videoUrl}
              controls
              preload="metadata"
              className="w-full rounded-xl border border-slate-200 bg-slate-950"
              src={renderedVideo.videoUrl}
            />
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
