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
  return (
    <Card className="bg-white text-slate-900 backdrop-blur-xl shadow-xl border-slate-300/70">
      <CardHeader>
        <CardTitle className="text-slate-900">3. Content Signal</CardTitle>
        <CardDescription className="text-slate-600">Style-agnostic structured extraction from the source document.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {extractedSignal ? (
          <div className="space-y-4">
            <div className="bg-slate-900 text-slate-50 p-4 rounded-md overflow-auto max-h-[460px] text-xs font-mono">
              <pre>{JSON.stringify(extractedSignal, null, 2)}</pre>
            </div>
            <div className="p-4 bg-blue-50 text-blue-900 rounded-md border border-blue-200">
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
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
          <Button
            type="button"
            className={primaryActionClassName}
            onClick={onConfirm}
            disabled={confirmDisabled}
          >
            <span className="space-y-1 text-left">
              <span className={primaryActionLabelClassName}>
                Primary Action
              </span>
              <span className="block text-base font-semibold">
                {signalAlreadyConfirmed ? "Signal Confirmed" : "Confirm Signal"}
              </span>
            </span>
          </Button>
          <Button
            type="button"
            variant="outline"
            className={secondaryActionClassName}
            onClick={onRegenerate}
            disabled={regenerateDisabled}
          >
            <span className="space-y-1 text-left">
              <span className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Secondary Action
              </span>
              <span className="block text-base font-semibold">Regenerate Signal</span>
            </span>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
