"use client";

import React from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import StageProgressList from "@/components/StageProgressList";
import type { StageProgressItem } from "@/lib/advanced";

type AdvancedContentSignalPanelProps = {
  extractedSignal: unknown;
  extractProgress: number;
  extractionPhaseText: string;
  progressItems: StageProgressItem[];
  signalAlreadyConfirmed: boolean;
  confirmDisabled: boolean;
  regenerateDisabled: boolean;
  primaryActionClassName: string;
  primaryActionLabelClassName: string;
  secondaryActionClassName: string;
  onConfirm: () => void;
  onRegenerate: () => void;
};

export default function AdvancedContentSignalPanel({
  extractedSignal,
  extractProgress,
  extractionPhaseText,
  progressItems,
  signalAlreadyConfirmed,
  confirmDisabled,
  regenerateDisabled,
  primaryActionClassName,
  primaryActionLabelClassName,
  secondaryActionClassName,
  onConfirm,
  onRegenerate,
}: AdvancedContentSignalPanelProps) {
  const signalSummary = extractedSignal
    ? signalAlreadyConfirmed
      ? "Signal is locked and ready for planner generation."
      : "Signal is ready to confirm and pass into script planning."
    : extractProgress > 0
      ? "Extraction is in progress. Review the progress above."
      : "Run extraction first, then confirm the structured signal.";

  return (
    <Card className="bg-white/95 text-slate-900 backdrop-blur-xl shadow-[0_20px_40px_rgba(15,23,42,0.08)] border-slate-300/70">
      <CardHeader className="pb-3">
        <CardTitle className="text-slate-900">3. Content Signal</CardTitle>
        <CardDescription className="text-slate-600">Structured extraction from the source, before styling and scene planning.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {extractedSignal ? (
          <div className="space-y-4">
            <div className="rounded-[18px] bg-slate-950 p-4 text-xs font-mono text-slate-50 overflow-auto max-h-[460px] shadow-[0_14px_28px_rgba(15,23,42,0.12)]">
              <pre>{JSON.stringify(extractedSignal, null, 2)}</pre>
            </div>
            <div className="rounded-[18px] border border-blue-200 bg-blue-50/85 p-4 text-blue-900">
              <h4 className="font-semibold mb-1">Signal Extracted</h4>
              <p className="text-sm">
                Review the extracted structure, then confirm signal to generate script pack.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <StageProgressList
              title="Extraction Progress"
              subtitle="Live workflow checkpoints for the structured signal stage."
              items={progressItems}
            />
            {extractProgress > 0 ? (
              <>
                <Progress value={extractProgress} className="h-2 bg-amber-100 [&>*]:bg-amber-500" />
                {extractionPhaseText ? <p className="text-sm text-slate-700">{extractionPhaseText}</p> : null}
              </>
            ) : null}
          </div>
        )}
        <div className="rounded-[28px] border border-slate-200 bg-slate-50/85 p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_14px_28px_rgba(15,23,42,0.06)]">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-1 px-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Ready to confirm
              </p>
              <p className="text-sm text-slate-700">{signalSummary}</p>
            </div>
            <div className="flex flex-col gap-2 lg:min-w-[320px]">
              <Button
                type="button"
                className={primaryActionClassName}
                onClick={onConfirm}
                disabled={confirmDisabled}
              >
                <span className="space-y-1 text-left">
                  <span className={primaryActionLabelClassName}>
                    Content Signal
                  </span>
                  <span className="block text-base font-semibold">
                    {signalAlreadyConfirmed ? "Confirmed" : "Confirm now"}
                  </span>
                </span>
              </Button>
              <Button
                type="button"
                variant="outline"
                className={`${secondaryActionClassName} w-auto self-start rounded-full px-4 py-2.5 text-sm shadow-none lg:self-end`}
                onClick={onRegenerate}
                disabled={regenerateDisabled}
              >
                Regenerate signal
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
