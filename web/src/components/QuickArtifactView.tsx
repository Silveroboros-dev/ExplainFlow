"use client";

import { ChevronRight, PanelTop, PlayCircle, Wand2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  type QuickArtifact,
  type QuickSourceMedia,
  type UploadedQuickSourceAsset,
  formatTimeRangeLabel,
} from "@/lib/quick";

type QuickArtifactViewProps = {
  artifact: QuickArtifact;
  activeSourceAsset: UploadedQuickSourceAsset | null;
  resolveSourceMediaUrl: (media: QuickSourceMedia) => string | null;
  onOpenBlockOverride: (blockId: string) => void;
};

export default function QuickArtifactView({
  artifact,
  activeSourceAsset,
  resolveSourceMediaUrl,
  onOpenBlockOverride,
}: QuickArtifactViewProps) {
  return (
    <>
      <div className="grid gap-5 lg:grid-cols-2">
        {artifact.blocks.map((block, index) => {
          const primaryBlockMedia = block.source_media[0] ?? null;
          const primaryBlockMediaUrl = primaryBlockMedia ? resolveSourceMediaUrl(primaryBlockMedia) : null;
          return (
            <Card key={block.block_id} className="overflow-hidden border-white/15 bg-white/95 text-slate-900 shadow-[0_20px_44px_rgba(15,23,42,0.18)]">
              <CardContent className="space-y-5 p-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline" className="rounded-full border-slate-300 text-[11px] uppercase tracking-[0.16em] text-slate-500">
                        {block.label}
                      </Badge>
                      <Badge className="rounded-full bg-slate-100 text-slate-700 hover:bg-slate-100">
                        {block.emphasis}
                      </Badge>
                    </div>
                    <h3 className="text-xl font-semibold text-slate-950">
                      {index + 1}. {block.title}
                    </h3>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="gap-2 rounded-full"
                    onClick={() => onOpenBlockOverride(block.block_id)}
                  >
                    <Wand2 className="h-4 w-4" />
                    Direct Block
                  </Button>
                </div>

                {(block.image_url || primaryBlockMediaUrl) ? (
                  <div className="rounded-[22px] border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-center gap-2">
                      <PanelTop className="h-4 w-4 text-slate-700" />
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                        {block.image_url ? "Block Visual" : primaryBlockMedia?.modality === "video" ? "Source Clip" : "Source Visual"}
                      </p>
                    </div>
                    {block.image_url ? (
                      <div className="mt-3 overflow-hidden rounded-[18px] border border-slate-200 bg-slate-950">
                        <img
                          src={block.image_url}
                          alt={block.title}
                          className="h-[220px] w-full object-cover"
                        />
                      </div>
                    ) : primaryBlockMediaUrl && primaryBlockMedia?.modality === "video" ? (
                      <div className="mt-3 overflow-hidden rounded-[18px] border border-slate-200 bg-slate-950">
                        {activeSourceAsset?.provider === "youtube" ? (
                          <iframe
                            title={`${block.title} source visual`}
                            src={primaryBlockMediaUrl}
                            className="h-[220px] w-full"
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                            allowFullScreen
                          />
                        ) : (
                          <video
                            controls
                            preload="metadata"
                            className="h-[220px] w-full object-cover"
                            src={primaryBlockMediaUrl}
                          />
                        )}
                      </div>
                    ) : null}
                  </div>
                ) : null}

                <p className="text-sm leading-7 text-slate-700">{block.body}</p>

                {block.bullets.length > 0 ? (
                  <div className="space-y-2">
                    {block.bullets.map((bullet) => (
                      <div key={bullet} className="flex items-start gap-2 text-sm leading-6 text-slate-600">
                        <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                        <span>{bullet}</span>
                      </div>
                    ))}
                  </div>
                ) : null}

                {(!block.image_url || block.claim_refs.length > 0) ? (
                  <div className="rounded-[22px] border border-slate-200 bg-slate-50 p-4">
                    {!block.image_url ? (
                      <>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Visual Direction</p>
                        <p className="mt-2 text-sm leading-6 text-slate-700">{block.visual_direction}</p>
                      </>
                    ) : null}
                    {block.claim_refs.length > 0 ? (
                      <div className={block.image_url ? "" : "mt-3"}>
                        <div className="flex flex-wrap gap-2">
                          {block.claim_refs.map((claimRef) => (
                            <Badge key={claimRef} variant="outline" className="rounded-full border-slate-300 text-slate-600">
                              {claimRef}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : null}

                {block.source_media.length > 0 ? (
                  <div className="rounded-[22px] border border-emerald-200 bg-emerald-50/70 p-4">
                    <div className="flex items-center gap-2">
                      <PlayCircle className="h-4 w-4 text-emerald-700" />
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-700">
                        Source Proof
                      </p>
                    </div>
                    <div className="mt-3 space-y-4">
                      {block.source_media.map((media) => {
                        const mediaUrl = resolveSourceMediaUrl(media);
                        const rangeLabel = formatTimeRangeLabel(media.start_ms, media.end_ms);
                        return (
                          <div key={`${block.block_id}-${media.asset_id}-${media.start_ms ?? "start"}`} className="space-y-3 rounded-[18px] border border-emerald-200 bg-white p-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-emerald-700">
                                {media.modality === "video" ? "Clip" : media.modality}
                              </span>
                              {rangeLabel ? (
                                <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                                  {rangeLabel}
                                </span>
                              ) : null}
                            </div>
                            {media.label ? (
                              <p className="text-sm font-medium text-slate-900">{media.label}</p>
                            ) : null}
                            {media.visual_context ? (
                              <p className="text-sm leading-6 text-slate-600">{media.visual_context}</p>
                            ) : media.quote_text ? (
                              <p className="text-sm leading-6 text-slate-600">{media.quote_text}</p>
                            ) : null}
                            {media.modality === "video" && mediaUrl ? (
                              activeSourceAsset?.provider === "youtube" ? (
                                <iframe
                                  title={`${block.title} source clip`}
                                  src={mediaUrl}
                                  className="h-[220px] w-full rounded-2xl border border-emerald-200 bg-slate-950"
                                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                  allowFullScreen
                                />
                              ) : (
                                <video
                                  controls
                                  preload="metadata"
                                  className="w-full rounded-2xl border border-emerald-200 bg-slate-950"
                                  src={mediaUrl}
                                />
                              )
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </>
  );
}
