"use client";

import { Clapperboard, Download, Loader2, PlayCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  type PlaylistPresentationMode,
  type QuickReel,
  type QuickReelSegment,
  type QuickSourceMedia,
  type QuickVideo,
  type UploadedQuickSourceAsset,
  formatMilliseconds,
  formatTimeRangeLabel,
} from "@/lib/quick";

type QuickReelViewProps = {
  activeReel: QuickReel | null;
  activeVideo: QuickVideo | null;
  activeSourceAsset: UploadedQuickSourceAsset | null;
  isBuildingReel: boolean;
  reelError: string;
  videoError: string;
  selectedPlaylistSegmentIds: string[];
  playablePlaylistSegmentsCount: number;
  unmuteLocalSourceClips: boolean;
  isRenderingVideo: boolean;
  isDownloadingVideo: boolean;
  playlistPresentationOverrides: Record<string, PlaylistPresentationMode>;
  onTogglePlaylistSegment: (segmentId: string) => void;
  onSetPlaylistPresentationMode: (segmentId: string, mode: PlaylistPresentationMode) => void;
  onSetUnmuteLocalSourceClips: (checked: boolean) => void;
  onOpenPlaylist: () => void;
  onGenerateVideo: () => void;
  onDownloadVideo: () => void;
  resolveSourceMediaUrl: (media: QuickSourceMedia) => string | null;
  hasPlayableSourceForSegment: (segment: QuickReelSegment) => boolean;
  hasGeneratedFrameForSegment: (segment: QuickReelSegment) => boolean;
};

export default function QuickReelView({
  activeReel,
  activeVideo,
  activeSourceAsset,
  isBuildingReel,
  reelError,
  videoError,
  selectedPlaylistSegmentIds,
  playablePlaylistSegmentsCount,
  unmuteLocalSourceClips,
  isRenderingVideo,
  isDownloadingVideo,
  playlistPresentationOverrides,
  onTogglePlaylistSegment,
  onSetPlaylistPresentationMode,
  onSetUnmuteLocalSourceClips,
  onOpenPlaylist,
  onGenerateVideo,
  onDownloadVideo,
  resolveSourceMediaUrl,
  hasPlayableSourceForSegment,
  hasGeneratedFrameForSegment,
}: QuickReelViewProps) {
  return (
    <div className="space-y-5">
      {isBuildingReel ? (
        <Card className="border-white/15 bg-white/95 text-slate-900 shadow-[0_20px_44px_rgba(15,23,42,0.18)]">
          <CardContent className="flex items-center gap-3 p-6 text-sm text-slate-600">
            <Loader2 className="h-5 w-5 animate-spin text-slate-700" />
            Building Proof Reel from the current quick blocks.
          </CardContent>
        </Card>
      ) : null}

      {reelError ? (
        <Card className="border-rose-200 bg-rose-50 text-rose-900 shadow-[0_20px_44px_rgba(15,23,42,0.12)]">
          <CardContent className="p-6 text-sm font-medium">{reelError}</CardContent>
        </Card>
      ) : null}

      {videoError ? (
        <Card className="border-rose-200 bg-rose-50 text-rose-900 shadow-[0_20px_44px_rgba(15,23,42,0.12)]">
          <CardContent className="p-6 text-sm font-medium">{videoError}</CardContent>
        </Card>
      ) : null}

      {activeReel ? (
        <>
          <Card className="overflow-hidden border-white/15 bg-white/95 text-slate-900 shadow-[0_20px_44px_rgba(15,23,42,0.18)]">
            <CardContent className="space-y-3 p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge className="rounded-full bg-slate-900 text-white hover:bg-slate-900">
                    Proof Reel v1
                  </Badge>
                  <Badge variant="outline" className="rounded-full border-slate-300 text-slate-600">
                    {activeReel.segments.length} Segments
                  </Badge>
                  {activeVideo?.duration_ms ? (
                    <Badge variant="outline" className="rounded-full border-slate-300 text-slate-600">
                      {formatMilliseconds(activeVideo.duration_ms)}
                    </Badge>
                  ) : null}
                  <Badge variant="outline" className="rounded-full border-slate-300 text-slate-600">
                    Selected {selectedPlaylistSegmentIds.length}/{activeReel.segments.length}
                  </Badge>
                  <label
                    className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-medium ${
                      activeSourceAsset?.provider === "upload"
                        ? "border-slate-300 bg-slate-50 text-slate-700"
                        : "border-slate-200 bg-slate-100 text-slate-400"
                    }`}
                  >
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
                      checked={unmuteLocalSourceClips}
                      onChange={(event) => onSetUnmuteLocalSourceClips(event.target.checked)}
                      disabled={activeSourceAsset?.provider !== "upload"}
                    />
                    Unmute Local Source Clips
                  </label>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    size="sm"
                    className="gap-2 rounded-full"
                    onClick={onOpenPlaylist}
                    disabled={isBuildingReel || !playablePlaylistSegmentsCount}
                  >
                    <PlayCircle className="h-4 w-4" />
                    Play Source Reel ({playablePlaylistSegmentsCount} items)
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="gap-2 rounded-full"
                    onClick={onGenerateVideo}
                    disabled={isBuildingReel || isRenderingVideo}
                  >
                    {isRenderingVideo ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Rendering MP4...
                      </>
                    ) : (
                      <>
                        <Clapperboard className="h-4 w-4" />
                        Generate MP4
                      </>
                    )}
                  </Button>
                </div>
              </div>
              <div>
                <h3 className="text-2xl font-semibold text-slate-950">{activeReel.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">{activeReel.summary}</p>
                {activeSourceAsset?.provider === "youtube" ? (
                  <p className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    MP4 export used generated visuals only; source clip intercuts currently support uploaded local video.
                  </p>
                ) : null}
              </div>
            </CardContent>
          </Card>

          {activeVideo?.video_url ? (
            <Card className="overflow-hidden border-white/15 bg-white/95 text-slate-900 shadow-[0_20px_44px_rgba(15,23,42,0.18)]">
              <CardContent className="space-y-4 p-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                      Quick MP4
                    </p>
                    <h3 className="text-xl font-semibold text-slate-950">Rendered Explainer</h3>
                  </div>
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition-colors hover:border-slate-400 hover:text-slate-950"
                    onClick={onDownloadVideo}
                    disabled={isDownloadingVideo}
                  >
                    {isDownloadingVideo ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Downloading...
                      </>
                    ) : (
                      <>
                        <Download className="h-4 w-4" />
                        Download MP4
                      </>
                    )}
                  </button>
                </div>
                <video
                  controls
                  preload="metadata"
                  className="w-full rounded-[22px] border border-slate-200 bg-slate-950"
                  src={activeVideo.video_url}
                />
              </CardContent>
            </Card>
          ) : null}

          <div className="space-y-5">
            {activeReel.segments.map((segment, index) => {
              const segmentMediaUrl = segment.primary_media ? resolveSourceMediaUrl(segment.primary_media) : null;
              const segmentRangeLabel = formatTimeRangeLabel(segment.start_ms, segment.end_ms);
              return (
                <Card key={segment.segment_id} className="overflow-hidden border-white/15 bg-white/95 text-slate-900 shadow-[0_20px_44px_rgba(15,23,42,0.18)]">
                  <CardContent className="space-y-5 p-6">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="outline" className="rounded-full border-slate-300 text-[11px] uppercase tracking-[0.16em] text-slate-500">
                            Segment {index + 1}
                          </Badge>
                          <Badge className="rounded-full bg-slate-100 text-slate-700 hover:bg-slate-100">
                            {segment.render_mode.replace("_", " ")}
                          </Badge>
                          {segmentRangeLabel ? (
                            <Badge variant="outline" className="rounded-full border-slate-300 text-slate-600">
                              {segmentRangeLabel}
                            </Badge>
                          ) : null}
                          {segment.timing_inferred ? (
                            <Badge variant="outline" className="rounded-full border-amber-300 text-amber-700">
                              Timing Inferred
                            </Badge>
                          ) : null}
                        </div>
                        <h3 className="text-xl font-semibold text-slate-950">{segment.title}</h3>
                      </div>
                      <label className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
                          checked={selectedPlaylistSegmentIds.includes(segment.segment_id)}
                          onChange={() => onTogglePlaylistSegment(segment.segment_id)}
                        />
                        Include in Playlist
                      </label>
                      <div className="inline-flex rounded-full border border-slate-200 bg-slate-50 p-1">
                        {([
                          { value: "auto", label: "Auto", disabled: false },
                          { value: "source", label: "Source", disabled: !hasPlayableSourceForSegment(segment) },
                          { value: "image", label: "Image", disabled: !hasGeneratedFrameForSegment(segment) },
                        ] satisfies Array<{ value: PlaylistPresentationMode; label: string; disabled: boolean }>).map((option) => {
                          const activeMode = playlistPresentationOverrides[segment.segment_id] ?? "auto";
                          return (
                            <button
                              key={option.value}
                              type="button"
                              disabled={option.disabled}
                              onClick={() => onSetPlaylistPresentationMode(segment.segment_id, option.value)}
                              className={`rounded-full px-3 py-2 text-xs font-semibold transition-colors ${
                                activeMode === option.value
                                  ? "bg-slate-900 text-white"
                                  : option.disabled
                                    ? "cursor-not-allowed text-slate-300"
                                    : "text-slate-600 hover:bg-white hover:text-slate-950"
                              }`}
                            >
                              {option.label}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {(segment.render_mode === "source_clip" || segment.render_mode === "hybrid") && segment.primary_media ? (
                      <div className="rounded-[22px] border border-slate-200 bg-slate-50 p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Source Clip
                        </p>
                        {segmentMediaUrl && segment.primary_media.modality === "video" ? (
                          <div className="mt-3 overflow-hidden rounded-[18px] border border-slate-200 bg-slate-950">
                            {activeSourceAsset?.provider === "youtube" ? (
                              <iframe
                                title={`${segment.title} proof reel clip`}
                                src={segmentMediaUrl}
                                className="h-[240px] w-full"
                                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                allowFullScreen
                              />
                            ) : (
                              <video
                                controls
                                preload="metadata"
                                className="h-[240px] w-full object-cover"
                                src={segmentMediaUrl}
                              />
                            )}
                          </div>
                        ) : null}
                        {segment.primary_media.label ? (
                          <p className="mt-3 text-sm leading-6 text-slate-600">{segment.primary_media.label}</p>
                        ) : null}
                      </div>
                    ) : null}

                    {(segment.render_mode === "generated_image" || segment.render_mode === "hybrid") && segment.fallback_image_url ? (
                      <div className="rounded-[22px] border border-slate-200 bg-slate-50 p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Generated Frame
                        </p>
                        <div className="mt-3 overflow-hidden rounded-[18px] border border-slate-200 bg-slate-950">
                          <img
                            src={segment.fallback_image_url}
                            alt={segment.title}
                            className="h-[240px] w-full object-cover"
                          />
                        </div>
                      </div>
                    ) : null}

                    <div className="rounded-[22px] border border-slate-200 bg-slate-50 p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                        Caption
                      </p>
                      <p className="mt-2 text-sm leading-7 text-slate-700">{segment.caption_text}</p>
                      {segment.claim_refs.length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {segment.claim_refs.map((claimRef) => (
                            <Badge key={claimRef} variant="outline" className="rounded-full border-slate-300 text-slate-600">
                              {claimRef}
                            </Badge>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </>
      ) : null}
    </div>
  );
}
