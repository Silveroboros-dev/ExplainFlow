"use client";

import React from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import StageProgressList from "@/components/StageProgressList";
import type { StageProgressItem } from "@/lib/advanced";

type AdvancedGenerationStreamPanelProps = {
  isGenerating: boolean;
  isGeneratingScriptPack: boolean;
  primaryActionText: string;
  primaryDisabled: boolean;
  secondaryDisabled: boolean;
  generationStatus: string;
  generationProgress: number;
  completedSceneCount: number;
  totalSceneCount: number;
  generationError: string;
  progressItems: StageProgressItem[];
  primaryActionClassName: string;
  primaryActionLabelClassName: string;
  secondaryActionClassName: string;
  onGenerate: () => void;
  onRegenerate: () => void;
};

export default function AdvancedGenerationStreamPanel({
  isGenerating,
  isGeneratingScriptPack,
  primaryActionText,
  primaryDisabled,
  secondaryDisabled,
  generationStatus,
  generationProgress,
  completedSceneCount,
  totalSceneCount,
  generationError,
  progressItems,
  primaryActionClassName,
  primaryActionLabelClassName,
  secondaryActionClassName,
  onGenerate,
  onRegenerate,
}: AdvancedGenerationStreamPanelProps) {
  const streamSummary = isGenerating
    ? `${completedSceneCount}/${Math.max(totalSceneCount, completedSceneCount)} scenes complete in the current run.`
    : isGeneratingScriptPack
      ? "Finish script planning before starting the scene stream."
      : totalSceneCount > 0
        ? "Locked script pack is ready for scene execution and final bundle assembly."
        : "Lock signal, artifacts, and render profile before starting the stream.";

  return (
    <Card className="flex h-full flex-col bg-white/95 text-slate-900 backdrop-blur-xl shadow-[0_20px_40px_rgba(15,23,42,0.08)] border-slate-300/70">
      <CardHeader className="pb-3">
        <CardTitle className="text-slate-900">5. Generation Stream</CardTitle>
        <CardDescription className="text-slate-600">
          Start the run and monitor scene-by-scene output as the bundle forms.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col space-y-4 overflow-hidden">
        <div className="rounded-[28px] border border-slate-200 bg-slate-50/85 p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_14px_28px_rgba(15,23,42,0.06)]">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-1 px-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Ready to generate
              </p>
              <p className="text-sm text-slate-700">{streamSummary}</p>
            </div>
            <div className="flex flex-col gap-2 lg:min-w-[320px]">
              <Button
                className={primaryActionClassName}
                size="lg"
                onClick={onGenerate}
                disabled={primaryDisabled}
              >
                <span className="flex w-full items-center justify-between gap-4">
                  <span className="space-y-1 text-left">
                    <span className={primaryActionLabelClassName}>
                      Generation Stream
                    </span>
                    <span className="block text-base font-semibold">{primaryActionText}</span>
                  </span>
                  {isGenerating ? (
                    <Loader2 className="h-5 w-5 animate-spin text-slate-100" />
                  ) : null}
                </span>
              </Button>
              <Button
                type="button"
                variant="outline"
                className={`${secondaryActionClassName} w-auto self-start rounded-full px-4 py-2.5 text-sm shadow-none lg:self-end`}
                onClick={onRegenerate}
                disabled={secondaryDisabled}
              >
                Regenerate stream
              </Button>
            </div>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto pr-2">
          <div className="space-y-4">
            <StageProgressList
              title="Generation Progress"
              subtitle="Live execution reports from the scene-by-scene stream."
              items={progressItems}
            />
            {generationStatus ? (
              <div className="rounded-[18px] border border-blue-200 bg-blue-50/85 p-4 text-blue-900">
                <h4 className="font-semibold mb-1">Generation Status</h4>
                <p className="text-sm">{generationStatus}</p>
              </div>
            ) : null}
            {isGenerating ? (
              <div className="space-y-2">
                <Progress value={generationProgress} className="h-2 bg-blue-100 [&>*]:bg-blue-500" />
                <p className="text-xs text-slate-600">Scenes complete: {completedSceneCount}/{Math.max(totalSceneCount, completedSceneCount)}</p>
              </div>
            ) : null}
            {generationError ? (
              <p className="text-sm font-medium text-rose-600">{generationError}</p>
            ) : null}
            {isGeneratingScriptPack && !isGenerating ? (
              <div className="rounded-[18px] border border-sky-200 bg-sky-50/85 px-3 py-2 text-sm text-sky-900">
                Stream generation will be available as soon as the current script-pack run finishes.
              </div>
            ) : null}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
