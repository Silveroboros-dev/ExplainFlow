"use client";

import React from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

type AdvancedContentSignalPanelProps = {
  extractedSignal: unknown;
  showTypingPreview: boolean;
  extractProgress: number;
  extractionPhaseText: string;
  typedExplainer: string;
  typedPreview: string;
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
  showTypingPreview,
  extractProgress,
  extractionPhaseText,
  typedExplainer,
  typedPreview,
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
        {extractedSignal && !showTypingPreview ? (
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
        ) : showTypingPreview ? (
          <div className="space-y-4">
            <Progress value={extractProgress} className="h-2 bg-amber-100 [&>*]:bg-amber-500" />
            <p className="text-sm text-slate-700">{extractionPhaseText}</p>
            <div className="p-4 bg-amber-50 text-amber-950 rounded-md border border-amber-200">
              <h4 className="font-semibold mb-2">Extracting Structured Signal...</h4>
              <p className="text-sm whitespace-pre-wrap font-mono leading-6">
                {typedExplainer}
                <span className="animate-pulse">|</span>
              </p>
            </div>
            <div className="bg-slate-900 text-slate-50 p-4 rounded-md overflow-auto max-h-[360px] text-xs font-mono">
              <pre>
                {typedPreview}
                <span className="animate-pulse">|</span>
              </pre>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center text-slate-400 border-2 border-dashed border-slate-300 rounded-md p-8 min-h-[240px]">
            <p className="text-center font-medium">Signal not started yet.</p>
            <p className="text-center text-sm mt-1">Open Source Material stage and run extraction first.</p>
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
