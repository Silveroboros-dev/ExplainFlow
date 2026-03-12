"use client";

import React from "react";
import { Loader2, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";

type UploadedAdvancedSourceAsset = {
  asset_id: string;
  modality: "audio" | "image" | "pdf_page" | "video";
  mime_type?: string;
  title?: string;
  page_index?: number;
  duration_ms?: number;
};

type AdvancedSourcePanelProps = {
  sourceDoc: string;
  uploadedSourceAssets: UploadedAdvancedSourceAsset[];
  isUploadingAssets: boolean;
  isExtracting: boolean;
  hasSourceInput: boolean;
  extractProgress: number;
  extractProgressMessage: string;
  errorMessage: string;
  sourceAssetsInputRef: React.RefObject<HTMLInputElement | null>;
  primaryActionClassName: string;
  primaryActionLabelClassName: string;
  secondaryActionClassName: string;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  onSourceDocChange: (value: string) => void;
  onSourceAssetUpload: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onRemoveUploadedSourceAsset: (assetId: string) => void;
  onCollapse: () => void;
  formatDuration: (value?: number) => string;
};

export default function AdvancedSourcePanel({
  sourceDoc,
  uploadedSourceAssets,
  isUploadingAssets,
  isExtracting,
  hasSourceInput,
  extractProgress,
  extractProgressMessage,
  errorMessage,
  sourceAssetsInputRef,
  primaryActionClassName,
  primaryActionLabelClassName,
  secondaryActionClassName,
  onSubmit,
  onSourceDocChange,
  onSourceAssetUpload,
  onRemoveUploadedSourceAsset,
  onCollapse,
  formatDuration,
}: AdvancedSourcePanelProps) {
  return (
    <Card className="bg-white text-slate-900 backdrop-blur-xl shadow-xl border-slate-300/70">
      <CardHeader>
        <CardTitle className="text-slate-900">1. Source Material</CardTitle>
        <CardDescription className="text-slate-600">
          Start with source text, uploaded source assets, or both. Images and audio can flow into claim-level proof links; PDFs are accepted for extraction and page-linked proof viewing with matched excerpts when available; short videos are supported with transcript-first extraction.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="high-contrast-form-labels space-y-6">
          <div className="space-y-2">
            <Label htmlFor="sourceDoc">Document Text</Label>
            <Textarea
              id="sourceDoc"
              value={sourceDoc}
              onChange={(event) => onSourceDocChange(event.target.value)}
              placeholder="Paste long document here..."
              className="min-h-[280px] text-base bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
            />
            <p className="text-xs text-slate-500">
              Optional when uploaded assets already contain the source material. For video, paste transcript or captions here if the clip is longer than 2 minutes. Use page-image uploads if you want crop-level proof on slides; PDFs now add page-linked excerpts when local text matching succeeds.
            </p>
          </div>
          <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
                    <Upload className="h-5 w-5" />
                  </span>
                  <div>
                    <Label className="text-base text-slate-900">Source Assets</Label>
                    <p className="text-xs uppercase tracking-[0.14em] text-slate-500">
                      PDFs, images, audio, video
                    </p>
                  </div>
                </div>
                <p className="text-sm leading-6 text-slate-600">
                  Upload proof-backed source files. PDFs drive extraction and page-linked proof, per-page images still give the tightest crop-level evidence, and videos use transcript as the truth layer while frames resolve on-screen references and proof clips.
                </p>
                <div className="flex flex-wrap gap-2">
                  {["image", "audio", "video", "pdf"].map((kind) => (
                    <span
                      key={kind}
                      className="inline-flex rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600"
                    >
                      {kind}
                    </span>
                  ))}
                </div>
              </div>
              <div className="space-y-2 sm:min-w-[220px]">
                <Input
                  id="sourceAssets"
                  ref={sourceAssetsInputRef}
                  type="file"
                  accept="image/*,audio/*,video/*,application/pdf"
                  multiple
                  onChange={onSourceAssetUpload}
                  disabled={isUploadingAssets || isExtracting}
                  className="sr-only"
                />
                <Button
                  type="button"
                  className="w-full"
                  variant="outline"
                  disabled={isUploadingAssets || isExtracting}
                  onClick={() => sourceAssetsInputRef.current?.click()}
                >
                  {isUploadingAssets ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Uploading...
                    </>
                  ) : (
                    "Choose Source Files"
                  )}
                </Button>
                <p className="text-xs text-slate-500">
                  {uploadedSourceAssets.length > 0
                    ? `${uploadedSourceAssets.length} asset${uploadedSourceAssets.length === 1 ? "" : "s"} attached`
                    : "No assets attached yet"}
                </p>
              </div>
            </div>
            {isUploadingAssets ? (
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <Loader2 className="h-4 w-4 animate-spin" />
                Uploading source assets...
              </div>
            ) : null}
            {uploadedSourceAssets.length > 0 ? (
              <div className="space-y-2">
                {uploadedSourceAssets.map((asset) => (
                  <div
                    key={asset.asset_id}
                    className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0 space-y-1">
                      <span className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">
                        {asset.modality}
                      </span>
                      <p className="truncate text-sm font-medium text-slate-900">
                        {asset.title || asset.asset_id}
                      </p>
                      <p className="text-xs text-slate-500">
                        {asset.mime_type ? `${asset.mime_type}` : "Source asset"}
                        {typeof asset.page_index === "number" ? ` • page ${asset.page_index}` : ""}
                        {typeof asset.duration_ms === "number" ? ` • ${formatDuration(asset.duration_ms)}` : ""}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="border-slate-300"
                      onClick={() => onRemoveUploadedSourceAsset(asset.asset_id)}
                    >
                      Remove
                    </Button>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Button
              type="submit"
              className={primaryActionClassName}
              disabled={!hasSourceInput || isExtracting || isUploadingAssets}
              size="lg"
            >
              <span className="flex w-full items-center justify-between gap-4">
                <span className="space-y-1 text-left">
                  <span className={primaryActionLabelClassName}>
                    Primary Action
                  </span>
                  <span className="block text-base font-semibold">
                    {isExtracting
                      ? "Extracting Signal..."
                      : isUploadingAssets
                        ? "Uploading Assets..."
                        : "Extract Content Signal"}
                  </span>
                </span>
                {(isExtracting || isUploadingAssets) ? (
                  <Loader2 className="h-5 w-5 animate-spin text-slate-100" />
                ) : null}
              </span>
            </Button>
            <Button
              type="button"
              variant="outline"
              className={secondaryActionClassName}
              onClick={onCollapse}
            >
              <span className="space-y-1 text-left">
                <span className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Secondary Action
                </span>
                <span className="block text-base font-semibold">Collapse Window</span>
              </span>
            </Button>
          </div>
          {(isExtracting || extractProgress > 0) ? (
            <div className="space-y-2">
              <Progress value={extractProgress} className="h-2 bg-amber-100 [&>*]:bg-amber-500" />
              <p className="text-xs text-slate-600">{extractProgressMessage}</p>
            </div>
          ) : null}
          {errorMessage ? <p className="text-red-500 text-sm font-medium">{errorMessage}</p> : null}
        </form>
      </CardContent>
    </Card>
  );
}
