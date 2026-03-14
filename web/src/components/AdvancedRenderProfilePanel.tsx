"use client";

import React from "react";
import { Loader2, type LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type RenderProfileTile = {
  value: string;
  title: string;
  description: string;
  icon: LucideIcon;
  baseClassName: string;
  selectedClassName: string;
  iconClassName: string;
  selectedIconClassName: string;
};

type SelectionTileGroupProps = {
  label: string;
  tiles: RenderProfileTile[];
  selectedValue: string;
  columnsClassName: string;
  tileClassName: string;
  tileHoverClassName: string;
  onSelect: (value: string) => void;
};

type AdvancedRenderProfilePanelProps = {
  profileStep: string;
  renderProfileSteps: string[];
  renderProfileStepLabels: Record<string, string>;
  artifactTiles: RenderProfileTile[];
  visualModeTiles: RenderProfileTile[];
  audienceLevelTiles: RenderProfileTile[];
  densityTiles: RenderProfileTile[];
  tasteBarTiles: RenderProfileTile[];
  artifactType: string;
  visualMode: string;
  audienceLevel: string;
  audiencePersona: string;
  domainContext: string;
  density: string;
  tasteBar: string;
  mustIncludeText: string;
  mustAvoidText: string;
  currentSelectionLabel: string;
  canMoveProfileBack: boolean;
  canMoveProfileNext: boolean;
  isApplyingProfile: boolean;
  applyDisabled: boolean;
  primaryActionClassName: string;
  primaryActionLabelClassName: string;
  secondaryActionClassName: string;
  tileClassName: string;
  tileHoverClassName: string;
  onProfileStepChange: (value: string) => void;
  onArtifactTypeChange: (value: string) => void;
  onVisualModeChange: (value: string) => void;
  onAudienceLevelChange: (value: string) => void;
  onAudiencePersonaChange: (value: string) => void;
  onDomainContextChange: (value: string) => void;
  onDensityChange: (value: string) => void;
  onTasteBarChange: (value: string) => void;
  onMustIncludeTextChange: (value: string) => void;
  onMustAvoidTextChange: (value: string) => void;
  onProfileStepBack: () => void;
  onProfileStepNext: () => void;
  onApply: () => void;
  onCollapse: () => void;
};

function SelectionTileGroup({
  label,
  tiles,
  selectedValue,
  columnsClassName,
  tileClassName,
  tileHoverClassName,
  onSelect,
}: SelectionTileGroupProps) {
  return (
    <div className="space-y-2.5">
      <Label>{label}</Label>
      <div className={columnsClassName}>
        {tiles.map((tile) => {
          const isSelected = selectedValue === tile.value;
          const Icon = tile.icon;
          return (
            <button
              key={tile.value}
              type="button"
              onClick={() => onSelect(tile.value)}
              className={`${tileClassName} ${tile.baseClassName} ${isSelected ? tile.selectedClassName : tileHoverClassName}`}
            >
              <div className="mb-3 flex items-center gap-3">
                <span
                  className={`inline-flex h-10 w-10 items-center justify-center rounded-2xl ${
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
              <p className="text-[13px] leading-5 text-slate-700/90">{tile.description}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function AdvancedRenderProfilePanel({
  profileStep,
  renderProfileSteps,
  renderProfileStepLabels,
  artifactTiles,
  visualModeTiles,
  audienceLevelTiles,
  densityTiles,
  tasteBarTiles,
  artifactType,
  visualMode,
  audienceLevel,
  audiencePersona,
  domainContext,
  density,
  tasteBar,
  mustIncludeText,
  mustAvoidText,
  currentSelectionLabel,
  canMoveProfileBack,
  canMoveProfileNext,
  isApplyingProfile,
  applyDisabled,
  primaryActionClassName,
  primaryActionLabelClassName,
  secondaryActionClassName,
  tileClassName,
  tileHoverClassName,
  onProfileStepChange,
  onArtifactTypeChange,
  onVisualModeChange,
  onAudienceLevelChange,
  onAudiencePersonaChange,
  onDomainContextChange,
  onDensityChange,
  onTasteBarChange,
  onMustIncludeTextChange,
  onMustAvoidTextChange,
  onProfileStepBack,
  onProfileStepNext,
  onApply,
  onCollapse,
}: AdvancedRenderProfilePanelProps) {
  const profileSummary = `${currentSelectionLabel} · ${audienceLevel} audience · ${tasteBar.replaceAll("_", " ")} taste`;

  return (
    <Card className="flex h-full flex-col bg-white/95 text-slate-900 backdrop-blur-xl shadow-[0_20px_40px_rgba(15,23,42,0.08)] border-slate-300/70">
      <CardHeader className="pb-3">
        <CardTitle className="text-slate-900">2. Render Profile</CardTitle>
        <CardDescription className="text-slate-600">
          Set output intent while extraction runs. The profile is split into four deliberate choices.
        </CardDescription>
      </CardHeader>
      <CardContent className="high-contrast-form-labels flex flex-1 flex-col space-y-4 overflow-hidden">
        <Tabs value={profileStep} onValueChange={onProfileStepChange} className="flex min-h-0 flex-1 flex-col space-y-3 overflow-hidden">
          <TabsList className="grid w-full grid-cols-2 md:grid-cols-4">
            {renderProfileSteps.map((step) => (
              <TabsTrigger key={step} value={step}>
                {renderProfileStepLabels[step] ?? step}
              </TabsTrigger>
            ))}
          </TabsList>

          <TabsContent value="output" className="mt-0 min-h-0 flex-1 space-y-3 overflow-y-auto pr-2">
            <p className="text-sm text-slate-600">Question 1: What output format and visual mode should the agent optimize for?</p>
            <SelectionTileGroup
              label="Artifact Type"
              tiles={artifactTiles}
              selectedValue={artifactType}
              columnsClassName="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3"
              tileClassName={tileClassName}
              tileHoverClassName={tileHoverClassName}
              onSelect={onArtifactTypeChange}
            />
            <SelectionTileGroup
              label="Visual Mode"
              tiles={visualModeTiles}
              selectedValue={visualMode}
              columnsClassName="grid grid-cols-1 gap-3 lg:grid-cols-3"
              tileClassName={tileClassName}
              tileHoverClassName={tileHoverClassName}
              onSelect={onVisualModeChange}
            />
            <div className="rounded-[20px] border border-slate-200 bg-slate-50/80 px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Current Selection</p>
              <p className="mt-2 text-sm text-slate-700">{currentSelectionLabel}</p>
            </div>
          </TabsContent>

          <TabsContent value="audience" className="mt-0 min-h-0 flex-1 space-y-3 overflow-y-auto pr-2">
            <p className="text-sm text-slate-600">Question 2: Who is this explainer for?</p>
            <SelectionTileGroup
              label="Audience Level"
              tiles={audienceLevelTiles}
              selectedValue={audienceLevel}
              columnsClassName="grid grid-cols-1 gap-3 lg:grid-cols-3"
              tileClassName={tileClassName}
              tileHoverClassName={tileHoverClassName}
              onSelect={onAudienceLevelChange}
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="audiencePersona">Audience Persona</Label>
                <Input
                  id="audiencePersona"
                  value={audiencePersona}
                  onChange={(event) => onAudiencePersonaChange(event.target.value)}
                  placeholder="e.g. Product manager, data journalist, startup founder"
                  className="bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="domainContext">Domain Context (Optional)</Label>
              <Input
                id="domainContext"
                value={domainContext}
                onChange={(event) => onDomainContextChange(event.target.value)}
                placeholder="e.g. B2B SaaS roadmap decisions"
                className="bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
              />
            </div>
          </TabsContent>

          <TabsContent value="style" className="mt-0 min-h-0 flex-1 space-y-3 overflow-y-auto pr-2">
            <p className="text-sm text-slate-600">Question 3: What quality and density should visuals and narration target?</p>
            <SelectionTileGroup
              label="Information Density"
              tiles={densityTiles}
              selectedValue={density}
              columnsClassName="grid grid-cols-1 gap-3 lg:grid-cols-3"
              tileClassName={tileClassName}
              tileHoverClassName={tileHoverClassName}
              onSelect={onDensityChange}
            />
            <SelectionTileGroup
              label="Taste Bar"
              tiles={tasteBarTiles}
              selectedValue={tasteBar}
              columnsClassName="grid grid-cols-1 gap-3 lg:grid-cols-3"
              tileClassName={tileClassName}
              tileHoverClassName={tileHoverClassName}
              onSelect={onTasteBarChange}
            />
            <div className="rounded-[18px] border border-blue-200 bg-blue-50/85 p-3 text-sm text-blue-900">
              Low-key preview is always enabled for speed. You can request a high-fidelity rerun at Final Bundle stage.
            </div>
          </TabsContent>

          <TabsContent value="constraints" className="mt-0 min-h-0 flex-1 space-y-3 overflow-y-auto pr-2">
            <p className="text-sm text-slate-600">Question 4: What should always be included, and what must be avoided?</p>
            <div className="space-y-2">
              <Label htmlFor="mustInclude">Must Include (Optional)</Label>
              <Input
                id="mustInclude"
                value={mustIncludeText}
                onChange={(event) => onMustIncludeTextChange(event.target.value)}
                placeholder="Comma-separated, e.g. business tradeoffs, clean hierarchy"
                className="bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mustAvoid">Must Avoid (Optional)</Label>
              <Input
                id="mustAvoid"
                value={mustAvoidText}
                onChange={(event) => onMustAvoidTextChange(event.target.value)}
                placeholder="Comma-separated, e.g. typical AI-generated gibberish, very abstract speculation"
                className="bg-white text-slate-900 border-slate-300 placeholder:text-slate-500"
              />
            </div>
          </TabsContent>
        </Tabs>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Button
            type="button"
            variant="outline"
            className="w-full border-slate-300"
            onClick={onProfileStepBack}
            disabled={!canMoveProfileBack}
          >
            Previous Question
          </Button>
          <Button
            type="button"
            variant="outline"
            className="w-full border-slate-300"
            onClick={onProfileStepNext}
            disabled={!canMoveProfileNext}
          >
            {canMoveProfileNext ? "Next Question" : "All Questions Answered"}
          </Button>
        </div>

        <div className="rounded-[28px] border border-slate-200 bg-slate-50/85 p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_14px_28px_rgba(15,23,42,0.06)]">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-1 px-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Ready to lock
              </p>
              <p className="text-sm text-slate-700">{profileSummary}</p>
            </div>
            <div className="flex flex-col gap-2 lg:min-w-[320px]">
              <Button
                type="button"
                className={primaryActionClassName}
                onClick={onApply}
                disabled={isApplyingProfile || applyDisabled}
              >
                <span className="flex w-full items-center justify-between gap-4">
                  <span className="space-y-1 text-left">
                    <span className={primaryActionLabelClassName}>
                      Render Profile
                    </span>
                    <span className="block text-base font-semibold">
                      {isApplyingProfile ? "Locking..." : "Apply now"}
                    </span>
                  </span>
                  {isApplyingProfile ? (
                    <Loader2 className="h-5 w-5 animate-spin text-slate-100" />
                  ) : null}
                </span>
              </Button>
              <Button
                type="button"
                variant="outline"
                className={`${secondaryActionClassName} w-auto self-start rounded-full px-4 py-2.5 text-sm shadow-none lg:self-end`}
                onClick={onCollapse}
              >
                Hide panel
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
