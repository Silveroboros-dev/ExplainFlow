"use client";

import React from "react";
import { AlertTriangle, Clapperboard, Loader2, Mic, PlayCircle, Square, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  QUICK_AUDIENCE_TILES,
  QUICK_PRIMARY_ACTION_CARD_CLASS,
  QUICK_PRIMARY_ACTION_LABEL_CLASS,
  QUICK_TONE_PRESETS,
  QUICK_VISUAL_TILES,
  type UploadedQuickSourceAsset,
  formatMilliseconds,
} from "@/lib/quick";

type QuickSourceFormProps = {
  topic: string;
  audience: string;
  customAudience: string;
  visualMode: string;
  tone: string;
  sourceVideoUrl: string;
  sourceTranscript: string;
  speechError: string;
  isListening: boolean;
  isUploadingSource: boolean;
  isGenerating: boolean;
  generationStatus: string;
  generationError: string;
  uploadedVideoAsset: UploadedQuickSourceAsset | null;
  youtubeSourceAsset: UploadedQuickSourceAsset | null;
  activeSourceAsset: UploadedQuickSourceAsset | null;
  sourceFileInputRef: React.RefObject<HTMLInputElement | null>;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  onToggleVoiceInput: () => void;
  onTopicChange: (value: string) => void;
  onAudienceChange: (value: string) => void;
  onCustomAudienceChange: (value: string) => void;
  onVisualModeChange: (value: string) => void;
  onToneChange: (value: string) => void;
  onSourceVideoUrlChange: (value: string) => void;
  onSourceTranscriptChange: (value: string) => void;
  onVideoAssetUpload: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onRemoveYoutubeSource: () => void;
  onRemoveUploadedVideoAsset: () => void;
};

export default function QuickSourceForm({
  topic,
  audience,
  customAudience,
  visualMode,
  tone,
  sourceVideoUrl,
  sourceTranscript,
  speechError,
  isListening,
  isUploadingSource,
  isGenerating,
  generationStatus,
  generationError,
  uploadedVideoAsset,
  youtubeSourceAsset,
  activeSourceAsset,
  sourceFileInputRef,
  onSubmit,
  onToggleVoiceInput,
  onTopicChange,
  onAudienceChange,
  onCustomAudienceChange,
  onVisualModeChange,
  onToneChange,
  onSourceVideoUrlChange,
  onSourceTranscriptChange,
  onVideoAssetUpload,
  onRemoveYoutubeSource,
  onRemoveUploadedVideoAsset,
}: QuickSourceFormProps) {
  const showUploadedVideoWithoutTranscriptWarning = Boolean(
    uploadedVideoAsset
    && !sourceTranscript.trim(),
  );

  return (
    <Card className="bg-white text-slate-900 backdrop-blur-xl shadow-xl border-slate-300/70">
      <CardHeader>
        <CardTitle className="text-slate-900">Quick Generate</CardTitle>
        <CardDescription className="text-slate-600">Enter a topic and style to generate a complete visual explainer instantly.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="high-contrast-form-labels grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2 md:col-span-2">
            <div className="flex items-center justify-between gap-3">
              <Label htmlFor="topic">Prompt</Label>
              <Button
                type="button"
                variant={isListening ? "default" : "outline"}
                size="sm"
                onClick={onToggleVoiceInput}
                className="shrink-0"
              >
                {isListening ? (
                  <>
                    <Square className="mr-2 h-4 w-4" />
                    Stop Listening
                  </>
                ) : (
                  <>
                    <Mic className="mr-2 h-4 w-4" />
                    Voice Prompt
                  </>
                )}
              </Button>
            </div>
            <Input
              id="topic"
              value={topic}
              onChange={(event) => onTopicChange(event.target.value)}
              placeholder="Create visuals that explain [topic/problem] for [audience], tone [tone]."
              required
              className="text-lg bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
            />
            <p className="text-xs text-slate-600">
              Example: &quot;Create visuals explaining model context protocols for PMs, tone practical and clear.&quot;
            </p>
            {speechError ? (
              <p className="text-xs text-rose-600 font-medium">{speechError}</p>
            ) : null}
          </div>

          <div className="space-y-4 md:col-span-2 rounded-[28px] border border-slate-200 bg-slate-50/90 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-slate-700 shadow-[0_10px_24px_rgba(15,23,42,0.08)]">
                  <Clapperboard className="h-5 w-5" />
                </span>
                <div className="space-y-1">
                  <Label className="text-sm font-semibold text-slate-900">Source Video or YouTube URL (Optional)</Label>
                  <p className="max-w-2xl text-sm leading-6 text-slate-600">
                    Quick can index an uploaded clip or a YouTube URL, use transcript/captions as the truth layer, and reuse clip-backed proof inside the HTML artifact.
                  </p>
                </div>
              </div>
              <input
                ref={sourceFileInputRef}
                type="file"
                accept="video/*"
                className="hidden"
                onChange={onVideoAssetUpload}
              />
              <Button
                type="button"
                variant="outline"
                className="rounded-full"
                onClick={() => sourceFileInputRef.current?.click()}
                disabled={isUploadingSource}
              >
                {isUploadingSource ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Upload className="mr-2 h-4 w-4" />
                )}
                {uploadedVideoAsset ? "Replace Video" : "Upload Video"}
              </Button>
            </div>

            <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
              <div className="space-y-2">
                <Label htmlFor="sourceVideoUrl">YouTube URL</Label>
                <div className="flex gap-3">
                  <Input
                    id="sourceVideoUrl"
                    value={sourceVideoUrl}
                    onChange={(event) => onSourceVideoUrlChange(event.target.value)}
                    placeholder="https://www.youtube.com/watch?v=..."
                    className="bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
                  />
                  {sourceVideoUrl.trim() ? (
                    <Button
                      type="button"
                      variant="outline"
                      className="shrink-0 rounded-full"
                      onClick={onRemoveYoutubeSource}
                    >
                      Clear
                    </Button>
                  ) : null}
                </div>
                <p className="text-xs leading-5 text-slate-600">
                  First version: YouTube URLs work only with pasted transcript or subtitles. ExplainFlow does not download the video.
                </p>
                <Label htmlFor="sourceTranscript">Transcript or Captions</Label>
                <Textarea
                  id="sourceTranscript"
                  value={sourceTranscript}
                  onChange={(event) => onSourceTranscriptChange(event.target.value)}
                  placeholder="Paste transcript or captions here. Required for YouTube URLs and for videos longer than 2 minutes."
                  className="min-h-[148px] bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
                />
                <p className="text-xs leading-5 text-slate-600">
                  ExplainFlow uses transcript text as the main truth layer, then consults video frames only for “this chart,” “as you can see,” clip-worthy moments, and proof playback.
                </p>
              </div>

              <div className="space-y-3 rounded-[24px] border border-slate-200 bg-white p-4">
                <div className="flex items-center gap-3">
                  <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-100 text-slate-700">
                    <PlayCircle className="h-5 w-5" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-slate-900">Video Constraints</p>
                    <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Quick v1</p>
                  </div>
                </div>
                <div className="space-y-2 text-sm leading-6 text-slate-600">
                  <p>Uploaded videos up to 2 minutes work without transcript.</p>
                  <p>Uploaded videos up to 10 minutes require transcript or captions.</p>
                  <p>YouTube URLs require transcript or subtitles and stay transcript-first.</p>
                </div>
                {showUploadedVideoWithoutTranscriptWarning ? (
                  <div className="rounded-[20px] border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
                    <div className="flex items-start gap-3">
                      <span className="inline-flex h-9 w-9 items-center justify-center rounded-2xl bg-white text-amber-600">
                        <AlertTriangle className="h-4.5 w-4.5" />
                      </span>
                      <div className="space-y-1">
                        <p className="font-semibold">Transcript recommended for image generation</p>
                        <p className="leading-6 text-amber-900/90">
                          Local video without transcript can still produce a Quick artifact, but generated images may be sparse and the
                          final delivery may lean on source-backed reels instead.
                        </p>
                      </div>
                    </div>
                  </div>
                ) : null}
                {youtubeSourceAsset ? (
                  <div className="space-y-3 rounded-[20px] border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                            YouTube
                          </span>
                        </div>
                        <p className="text-sm font-medium text-slate-900">{youtubeSourceAsset.title || "YouTube source"}</p>
                      </div>
                    </div>
                    {youtubeSourceAsset.embed_url ? (
                      <iframe
                        title="YouTube source preview"
                        src={youtubeSourceAsset.embed_url}
                        className="h-[220px] w-full rounded-2xl border border-slate-200 bg-slate-950"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowFullScreen
                      />
                    ) : null}
                  </div>
                ) : uploadedVideoAsset ? (
                  <div className="space-y-3 rounded-[20px] border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                            Video
                          </span>
                          {uploadedVideoAsset.duration_ms ? (
                            <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                              {formatMilliseconds(uploadedVideoAsset.duration_ms)}
                            </span>
                          ) : null}
                        </div>
                        <p className="text-sm font-medium text-slate-900">{uploadedVideoAsset.title || "Uploaded video"}</p>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="rounded-full text-slate-500"
                        onClick={onRemoveUploadedVideoAsset}
                      >
                        Remove
                      </Button>
                    </div>
                    <video
                      controls
                      preload="metadata"
                      className="w-full rounded-2xl border border-slate-200 bg-slate-950"
                      src={uploadedVideoAsset.uri}
                    />
                  </div>
                ) : (
                  <div className="rounded-[20px] border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">
                    No source video attached yet. Quick will still work from the prompt alone, or from a YouTube URL plus transcript.
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-3 md:col-span-2">
            <Label>Target Audience</Label>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
              {QUICK_AUDIENCE_TILES.map((tile) => {
                const isSelected = audience === tile.value;
                const Icon = tile.icon;
                return (
                  <button
                    key={tile.value}
                    type="button"
                    onClick={() => onAudienceChange(tile.value)}
                    className={`rounded-[24px] border p-4 text-left transition-all duration-200 ${
                      tile.baseClassName
                    } ${isSelected ? tile.selectedClassName : 'hover:-translate-y-0.5 hover:shadow-[0_12px_24px_rgba(15,23,42,0.08)]'}`}
                  >
                    <div className="mb-4 flex items-center gap-3">
                      <span
                        className={`inline-flex h-11 w-11 items-center justify-center rounded-2xl ${
                          isSelected ? tile.selectedIconClassName : tile.iconClassName
                        }`}
                      >
                        <Icon className="h-5 w-5" />
                      </span>
                      <div>
                        <p className="font-semibold">{tile.title}</p>
                        <p className="text-[11px] uppercase tracking-[0.14em] text-slate-600">
                          {isSelected ? "Selected" : "Tap to select"}
                        </p>
                      </div>
                    </div>
                    <p className="text-sm leading-6 text-slate-700/90">{tile.description}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {audience === "Other" ? (
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="customAudience">Specify Audience</Label>
              <Input
                id="customAudience"
                value={customAudience}
                onChange={(event) => onCustomAudienceChange(event.target.value)}
                placeholder="e.g. 5-year old children, investors..."
                required
                className="bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
              />
            </div>
          ) : null}

          <div className="space-y-3 md:col-span-2">
            <Label>Visual Style</Label>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
              {QUICK_VISUAL_TILES.map((tile) => {
                const isSelected = visualMode === tile.value;
                const Icon = tile.icon;
                return (
                  <button
                    key={tile.value}
                    type="button"
                    onClick={() => onVisualModeChange(tile.value)}
                    className={`rounded-[24px] border p-4 text-left transition-all duration-200 ${
                      tile.baseClassName
                    } ${isSelected ? tile.selectedClassName : 'hover:-translate-y-0.5 hover:shadow-[0_12px_24px_rgba(15,23,42,0.08)]'}`}
                  >
                    <div className="mb-4 flex items-center gap-3">
                      <span
                        className={`inline-flex h-11 w-11 items-center justify-center rounded-2xl ${
                          isSelected ? tile.selectedIconClassName : tile.iconClassName
                        }`}
                      >
                        <Icon className="h-5 w-5" />
                      </span>
                      <div>
                        <p className="font-semibold">{tile.title}</p>
                        <p className="text-[11px] uppercase tracking-[0.14em] text-slate-600">
                          {isSelected ? "Selected" : "Tap to select"}
                        </p>
                      </div>
                    </div>
                    <p className="text-sm leading-6 text-slate-700/90">{tile.description}</p>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-2 md:col-span-2">
            <Label htmlFor="tone">Tone of Voice (Optional)</Label>
            <Input
              id="tone"
              value={tone}
              onChange={(event) => onToneChange(event.target.value)}
              placeholder="e.g. Engaging, Professional, Humorous"
              className="bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
            />
            <div className="flex flex-wrap gap-2 pt-1">
              {QUICK_TONE_PRESETS.map((preset) => {
                const isSelected = tone.trim().toLowerCase() === preset.toLowerCase();
                return (
                  <button
                    key={preset}
                    type="button"
                    onClick={() => onToneChange(preset)}
                    className={`rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.12em] transition-colors ${
                      isSelected
                        ? 'border-slate-900 bg-slate-900 text-white'
                        : 'border-slate-300 bg-slate-50 text-slate-700 hover:border-slate-400 hover:bg-slate-100'
                    }`}
                  >
                    {preset}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="md:col-span-2 pt-4">
            <Button
              type="submit"
              className={QUICK_PRIMARY_ACTION_CARD_CLASS}
              disabled={isGenerating || isUploadingSource}
              size="lg"
            >
              <span className="flex w-full items-center justify-between gap-4">
                <span className="space-y-1 text-left">
                  <span className={QUICK_PRIMARY_ACTION_LABEL_CLASS}>
                    Primary Action
                  </span>
                  <span className="block text-base font-semibold">
                    {isGenerating ? "Generating Quick Artifact..." : "Generate Quick Artifact"}
                  </span>
                </span>
                {isGenerating ? (
                  <Loader2 className="h-5 w-5 animate-spin text-slate-100" />
                ) : null}
              </span>
            </Button>
          </div>

          {(generationStatus || generationError || isGenerating) ? (
            <div className="md:col-span-2 space-y-2">
              {generationStatus ? (
                <p className="text-sm text-blue-700 font-medium">{generationStatus}</p>
              ) : null}
              {isGenerating ? (
                <div className="flex items-center gap-2 text-xs text-slate-600">
                  <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                  <span>
                    {activeSourceAsset
                      ? `Indexing transcript-backed ${activeSourceAsset.provider === "youtube" ? "YouTube" : "video"} context, then building lightweight artifact blocks.`
                      : "Generating lightweight artifact blocks for immediate rendering."}
                  </span>
                </div>
              ) : null}
              {generationError ? (
                <p className="text-sm text-rose-600 font-medium">{generationError}</p>
              ) : null}
            </div>
          ) : null}
        </form>
      </CardContent>
    </Card>
  );
}
