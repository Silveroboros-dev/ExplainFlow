"use client";

import { useState } from "react";
import { Download, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type FinalBundleScene = {
  id: string;
  title?: string;
  text: string;
  imageUrl?: string;
  audioUrl?: string;
};

interface FinalBundleProps {
  scenes: Record<string, FinalBundleScene>;
  topic: string;
}

const slugify = (value: string, fallback: string): string => {
  const slug = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || fallback;
};

export default function FinalBundle({ scenes, topic }: FinalBundleProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState("");

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

  const handleDownloadBundle = async () => {
    setIsExporting(true);
    setExportError("");

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${apiUrl}/api/final-bundle/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic,
          scenes: sceneList.map((scene) => ({
            scene_id: scene.id,
            title: scene.title,
            text: scene.text,
            image_url: scene.imageUrl,
            audio_url: scene.audioUrl,
          })),
        }),
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

  return (
    <Card className="bg-white text-slate-900 border-slate-300 shadow-md">
      <CardContent className="pt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <p className="font-semibold">Download Final Bundle</p>
          <p className="text-sm text-slate-600">
            Exports one zip with `script.txt`, scene images, and available audio files.
          </p>
          {exportError ? (
            <p className="text-sm font-medium text-rose-600">{exportError}</p>
          ) : null}
        </div>
        <Button
          type="button"
          onClick={() => void handleDownloadBundle()}
          disabled={isExporting}
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
      </CardContent>
    </Card>
  );
}
