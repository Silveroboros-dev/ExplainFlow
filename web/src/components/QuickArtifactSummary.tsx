"use client";

import { PanelTop, Wand2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { type QuickArtifact, type UploadedQuickSourceAsset } from "@/lib/quick";

type QuickArtifactSummaryProps = {
  artifact: QuickArtifact;
  activeSourceAsset: UploadedQuickSourceAsset | null;
  heroSourceMediaUrl: string | null;
  onOpenGlobalOverride: () => void;
};

export default function QuickArtifactSummary({
  artifact,
  activeSourceAsset,
  heroSourceMediaUrl,
  onOpenGlobalOverride,
}: QuickArtifactSummaryProps) {
  return (
    <Card className="overflow-hidden border-white/15 bg-white/95 text-slate-900 shadow-[0_26px_60px_rgba(15,23,42,0.28)]">
      <CardContent className="grid gap-6 p-6 lg:grid-cols-[1.25fr_0.75fr]">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="rounded-full bg-slate-900 text-white hover:bg-slate-900">
                Quick Mode
              </Badge>
              <Badge variant="outline" className="rounded-full border-slate-300 text-slate-600">
                {artifact.visual_style}
              </Badge>
              {activeSourceAsset ? (
                <Badge variant="outline" className="rounded-full border-slate-300 text-slate-600">
                  {activeSourceAsset.provider === "youtube" ? "YouTube Transcript-Backed" : "Uploaded Video"}
                </Badge>
              ) : null}
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-2 rounded-full"
              onClick={onOpenGlobalOverride}
            >
              <Wand2 className="h-4 w-4" />
              Redirect Whole Artifact
            </Button>
          </div>
          <div className="space-y-2">
            <h3 className="text-3xl font-semibold tracking-tight text-slate-950">{artifact.title}</h3>
            <p className="text-lg text-slate-600">{artifact.subtitle}</p>
          </div>
          <p className="max-w-3xl text-base leading-7 text-slate-700">{artifact.summary}</p>
        </div>
        <div className="rounded-[28px] border border-slate-200 bg-slate-50 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.9)]">
          <div className="flex items-center gap-3">
            <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-900 text-white">
              <PanelTop className="h-5 w-5" />
            </span>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                {artifact.hero_image_url ? "Hero Visual" : heroSourceMediaUrl ? "Hero Clip" : "Hero Direction"}
              </p>
              <p className="text-sm font-medium text-slate-900">{artifact.hero_direction}</p>
            </div>
          </div>
          {artifact.hero_image_url ? (
            <div className="mt-4 overflow-hidden rounded-[24px] border border-slate-200 bg-slate-950">
              <img
                src={artifact.hero_image_url}
                alt={artifact.title}
                className="h-[220px] w-full object-cover"
              />
            </div>
          ) : heroSourceMediaUrl ? (
            <div className="mt-4 overflow-hidden rounded-[24px] border border-slate-200 bg-slate-950">
              {activeSourceAsset?.provider === "youtube" ? (
                <iframe
                  title={`${artifact.title} hero clip`}
                  src={heroSourceMediaUrl}
                  className="h-[220px] w-full"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                />
              ) : (
                <video
                  controls
                  preload="metadata"
                  className="h-[220px] w-full object-cover"
                  src={heroSourceMediaUrl}
                />
              )}
            </div>
          ) : null}
          <p className="mt-4 text-sm leading-6 text-slate-600">
            This Quick artifact is rendered as HTML-first modules so each block can be steered independently without rerunning the whole workflow.
            {activeSourceAsset
              ? ` Source-backed blocks can also carry direct proof clips from the ${activeSourceAsset.provider === "youtube" ? "YouTube source" : "uploaded video"}.`
              : ""}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
