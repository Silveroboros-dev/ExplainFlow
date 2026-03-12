"use client";

import React from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

type ProofSourceMedia = {
  modality: "audio" | "video" | "image" | "pdf_page";
  url: string;
  original_url?: string;
  start_ms?: number;
  end_ms?: number;
  page_index?: number;
  label?: string;
  matched_excerpt?: string;
  line_start?: number;
  line_end?: number;
  quote_text?: string;
  visual_context?: string;
  evidence_refs: string[];
};

type EvidenceViewerState = {
  sceneTitle?: string;
  claimRef?: string;
  media: ProofSourceMedia;
};

type AdvancedProofDialogProps = {
  evidenceViewer: EvidenceViewerState | null;
  onClose: () => void;
};

const formatMilliseconds = (value?: number): string => {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return "";
  const totalSeconds = Math.floor(value / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
};

const withMediaFragment = (url: string, startMs?: number, endMs?: number): string => {
  if (!url || typeof startMs !== "number") return url;
  const startSeconds = Math.max(0, Math.floor(startMs / 1000));
  const endSeconds = typeof endMs === "number" ? Math.max(startSeconds + 1, Math.floor(endMs / 1000)) : undefined;
  return endSeconds ? `${url}#t=${startSeconds},${endSeconds}` : `${url}#t=${startSeconds}`;
};

const withPdfPageFragment = (url: string, pageIndex?: number): string => {
  if (!url || typeof pageIndex !== "number" || !Number.isFinite(pageIndex)) return url;
  const pageNumber = Math.max(1, Math.trunc(pageIndex));
  return `${url}#page=${pageNumber}`;
};

export default function AdvancedProofDialog({ evidenceViewer, onClose }: AdvancedProofDialogProps) {
  return (
    <Dialog open={Boolean(evidenceViewer)} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="bg-white text-slate-900 border-slate-300 max-w-3xl">
        <DialogHeader>
          <DialogTitle>{evidenceViewer?.sceneTitle ? `${evidenceViewer.sceneTitle} Proof` : "Source Proof"}</DialogTitle>
          <DialogDescription className="text-slate-700">
            {evidenceViewer?.claimRef
              ? `Showing linked source evidence for ${evidenceViewer.claimRef}.`
              : "Showing the strongest linked source proof for this scene."}
          </DialogDescription>
        </DialogHeader>
        {evidenceViewer?.media ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              {evidenceViewer.media.modality === "audio" ? (
                <audio
                  key={`${evidenceViewer.media.url}-${evidenceViewer.media.start_ms ?? 0}-${evidenceViewer.media.end_ms ?? 0}`}
                  controls
                  src={withMediaFragment(
                    evidenceViewer.media.url,
                    evidenceViewer.media.start_ms,
                    evidenceViewer.media.end_ms,
                  )}
                  className="w-full"
                />
              ) : evidenceViewer.media.modality === "pdf_page"
                && (
                  evidenceViewer.media.url.toLowerCase().includes(".pdf")
                  || evidenceViewer.media.original_url?.toLowerCase().includes(".pdf")
                ) ? (
                <div className="rounded-md border border-slate-200 bg-white px-5 py-6">
                  <p className="text-sm font-semibold text-slate-900">PDF proof opens in a new tab</p>
                  <p className="mt-2 text-sm leading-6 text-slate-700">
                    Inline PDF viewing can fail in deployed environments. Open the source proof directly to jump to the linked page.
                  </p>
                  {(evidenceViewer.media.original_url || evidenceViewer.media.url) ? (
                    <div className="mt-4">
                      <Button type="button" variant="outline" className="border-slate-300" asChild>
                        <a
                          href={withPdfPageFragment(
                            evidenceViewer.media.original_url || evidenceViewer.media.url,
                            evidenceViewer.media.page_index,
                          )}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {typeof evidenceViewer.media.page_index === "number"
                            ? `View Source Proof (Page ${evidenceViewer.media.page_index})`
                            : "View Source Proof"}
                        </a>
                      </Button>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="overflow-hidden rounded-md border border-slate-200 bg-white">
                  <img
                    src={evidenceViewer.media.url}
                    alt={evidenceViewer.media.label || "Source proof"}
                    className="w-full h-auto object-contain"
                  />
                </div>
              )}
            </div>
            <div className="grid gap-2 text-sm text-slate-700">
              {evidenceViewer.media.label ? (
                <p><span className="font-semibold text-slate-900">Label:</span> {evidenceViewer.media.label}</p>
              ) : null}
              <p><span className="font-semibold text-slate-900">Type:</span> {evidenceViewer.media.modality}</p>
              {typeof evidenceViewer.media.page_index === "number" ? (
                <p><span className="font-semibold text-slate-900">Page:</span> {evidenceViewer.media.page_index}</p>
              ) : null}
              {typeof evidenceViewer.media.line_start === "number" ? (
                <p>
                  <span className="font-semibold text-slate-900">Lines:</span> {evidenceViewer.media.line_start}
                  {typeof evidenceViewer.media.line_end === "number" && evidenceViewer.media.line_end !== evidenceViewer.media.line_start
                    ? `-${evidenceViewer.media.line_end}`
                    : ""}
                </p>
              ) : null}
              {typeof evidenceViewer.media.start_ms === "number" ? (
                <p>
                  <span className="font-semibold text-slate-900">Time:</span> {formatMilliseconds(evidenceViewer.media.start_ms)}
                  {typeof evidenceViewer.media.end_ms === "number" ? ` - ${formatMilliseconds(evidenceViewer.media.end_ms)}` : ""}
                </p>
              ) : null}
              {evidenceViewer.media.matched_excerpt ? (
                <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Matched Excerpt</p>
                  <p className="mt-2 text-sm leading-6 text-slate-800">{evidenceViewer.media.matched_excerpt}</p>
                </div>
              ) : null}
              {evidenceViewer.media.quote_text ? (
                <p><span className="font-semibold text-slate-900">Quote:</span> {evidenceViewer.media.quote_text}</p>
              ) : null}
              {evidenceViewer.media.visual_context ? (
                <p><span className="font-semibold text-slate-900">Visual Context:</span> {evidenceViewer.media.visual_context}</p>
              ) : null}
              {evidenceViewer.media.evidence_refs.length > 0 ? (
                <p><span className="font-semibold text-slate-900">Evidence Refs:</span> {evidenceViewer.media.evidence_refs.join(", ")}</p>
              ) : null}
            </div>
            <DialogFooter className="gap-2">
              {(evidenceViewer.media.original_url || evidenceViewer.media.url) ? (
                <Button type="button" variant="outline" className="border-slate-300" asChild>
                  <a
                    href={evidenceViewer.media.modality === "pdf_page"
                      ? withPdfPageFragment(
                        evidenceViewer.media.original_url || evidenceViewer.media.url,
                        evidenceViewer.media.page_index,
                      )
                      : (evidenceViewer.media.original_url || evidenceViewer.media.url)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {evidenceViewer.media.modality === "pdf_page" ? "Open PDF Source" : "Open Original Asset"}
                  </a>
                </Button>
              ) : null}
              <Button type="button" onClick={onClose}>Close</Button>
            </DialogFooter>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
