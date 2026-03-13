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
  return (
    <Card className="flex h-full flex-col bg-white text-slate-900 backdrop-blur-xl shadow-xl border-slate-300/70">
      <CardHeader>
        <CardTitle className="text-slate-900">5. Generation Stream</CardTitle>
        <CardDescription className="text-slate-600">
          Start generation and monitor live scene-by-scene output.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col space-y-4 overflow-hidden">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Button
            className={primaryActionClassName}
            size="lg"
            onClick={onGenerate}
            disabled={primaryDisabled}
          >
            <span className="flex w-full items-center justify-between gap-4">
              <span className="space-y-1 text-left">
                <span className={primaryActionLabelClassName}>
                  Primary Action
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
            className={secondaryActionClassName}
            onClick={onRegenerate}
            disabled={secondaryDisabled}
          >
            <span className="space-y-1 text-left">
              <span className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Secondary Action
              </span>
              <span className="block text-base font-semibold">Regenerate Stream</span>
            </span>
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto pr-2">
          <div className="space-y-4">
            <StageProgressList
              title="Generation Progress"
              subtitle="Live execution reports from the scene-by-scene stream."
              items={progressItems}
            />
            {generationStatus ? (
              <div className="p-4 bg-blue-50 text-blue-900 rounded-md border border-blue-200">
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
              <div className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900">
                Stream generation will be available as soon as the current script-pack run finishes.
              </div>
            ) : null}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
