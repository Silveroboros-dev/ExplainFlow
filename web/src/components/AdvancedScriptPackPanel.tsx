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
  const scriptSummary = scriptPack
    ? "Script pack is ready for scene execution and downstream proof linking."
    : isGeneratingScriptPack
      ? "Planner is running against the current locked signal and render profile."
      : "Generate the script pack after locking signal and render profile.";

  return (
    <Card className="bg-white/95 text-slate-900 backdrop-blur-xl shadow-[0_20px_40px_rgba(15,23,42,0.08)] border-slate-300/70">
      <CardHeader className="pb-3">
        <CardTitle className="text-slate-900">4. Script Pack</CardTitle>
        <CardDescription className="text-slate-600">
          Planner output built from the locked signal and current render profile.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {scriptPack ? (
          <div className="space-y-3">
            <div className="rounded-[18px] bg-slate-950 p-4 text-xs font-mono text-slate-50 overflow-auto max-h-[460px] shadow-[0_14px_28px_rgba(15,23,42,0.12)]">
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
            <div className="rounded-[18px] border border-sky-200 bg-sky-50/85 px-3 py-2 text-sm text-sky-900">
              Script planning can take around a minute on the current architecture. You can keep asking questions in the assistant chat while it runs.
            </div>
          </div>
        )}
        <div className="rounded-[28px] border border-slate-200 bg-slate-50/85 p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_14px_28px_rgba(15,23,42,0.06)]">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-1 px-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Ready to plan
              </p>
              <p className="text-sm text-slate-700">{scriptSummary}</p>
            </div>
            <div className="flex flex-col gap-2 lg:min-w-[320px]">
              <Button
                type="button"
                className={primaryActionClassName}
                onClick={onGenerate}
                disabled={primaryDisabled}
              >
                <span className="flex w-full items-center justify-between gap-4">
                  <span className="space-y-1 text-left">
                    <span className={primaryActionLabelClassName}>
                      Script Pack
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
                className={`${secondaryActionClassName} w-auto self-start rounded-full px-4 py-2.5 text-sm shadow-none lg:self-end`}
                onClick={onRegenerate}
                disabled={secondaryDisabled}
              >
                Regenerate script
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
