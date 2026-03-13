"use client";

import React from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import StageProgressList from "@/components/StageProgressList";
import type { StageProgressItem } from "@/lib/advanced";

type AdvancedScriptPackPanelProps = {
  scriptPack: unknown;
  scriptPackProgress: number;
  scriptPackPhaseText: string;
  progressItems: StageProgressItem[];
  isGeneratingScriptPack: boolean;
  primaryActionText: string;
  primaryDisabled: boolean;
  secondaryDisabled: boolean;
  primaryActionClassName: string;
  primaryActionLabelClassName: string;
  secondaryActionClassName: string;
  onGenerate: () => void;
  onRegenerate: () => void;
};

export default function AdvancedScriptPackPanel({
  scriptPack,
  scriptPackProgress,
  scriptPackPhaseText,
  progressItems,
  isGeneratingScriptPack,
  primaryActionText,
  primaryDisabled,
  secondaryDisabled,
  primaryActionClassName,
  primaryActionLabelClassName,
  secondaryActionClassName,
  onGenerate,
  onRegenerate,
}: AdvancedScriptPackPanelProps) {
  return (
    <Card className="bg-white text-slate-900 backdrop-blur-xl shadow-xl border-slate-300/70">
      <CardHeader>
        <CardTitle className="text-slate-900">4. Script Pack</CardTitle>
        <CardDescription className="text-slate-600">
          Planner output generated from the extracted signal and current render profile.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {scriptPack ? (
          <div className="space-y-3">
            <div className="bg-slate-900 text-slate-50 p-4 rounded-md overflow-auto max-h-[460px] text-xs font-mono">
              <pre>{JSON.stringify(scriptPack, null, 2)}</pre>
            </div>
            <p className="text-xs text-slate-600">
              Change render profile settings and run generation again to regenerate this script pack.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <StageProgressList
              title="Planner Progress"
              subtitle="Real workflow steps for artifact-aware script planning."
              items={progressItems}
            />
            {scriptPackProgress > 0 ? (
              <>
                <Progress value={scriptPackProgress} className="h-2 bg-blue-100 [&>*]:bg-blue-500" />
                {scriptPackPhaseText ? <p className="text-sm text-slate-700">{scriptPackPhaseText}</p> : null}
              </>
            ) : null}
            <div className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900">
              Script planning can take around a minute on the current architecture. You can keep asking questions in the assistant chat while it runs.
            </div>
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Button
            type="button"
            className={primaryActionClassName}
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
              {isGeneratingScriptPack ? (
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
              <span className="block text-base font-semibold">Regenerate Script</span>
            </span>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
