"use client";

import React from "react";

import FinalBundle from "@/components/FinalBundle";
import SceneCard from "@/components/SceneCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type AdvancedGeneratedSourceMedia = {
  asset_id: string;
  modality: "audio" | "video" | "image" | "pdf_page";
  claim_refs: string[];
  evidence_refs: string[];
};

type AdvancedGeneratedScene = {
  id: string;
  title?: string;
  text: string;
  imageUrl?: string;
  audioUrl?: string;
  claim_refs?: string[];
  source_media?: AdvancedGeneratedSourceMedia[];
  status: string;
  qa_status?: "PASS" | "WARN" | "FAIL";
  qa_reasons?: string[];
  qa_score?: number;
  qa_word_count?: number;
  auto_retry_count?: number;
  source_proof_warning?: string;
};

type AdvancedGeneratedExplainerSectionProps = {
  scenes: Record<string, AdvancedGeneratedScene>;
  artifactType: string;
  visualMode: string;
  generationError: string;
  fidelityPreference: "preview" | "high";
  isApplyingProfile: boolean;
  isGenerating: boolean;
  isGeneratingScriptPack: boolean;
  topic: string;
  onEnableHighFidelity: () => void;
  onRegenerate: (sceneId: string, newText: string, newImageUrl: string, newAudioUrl: string) => void;
  onOpenEvidence: (sceneId: string, claimRef?: string) => void;
};

export default function AdvancedGeneratedExplainerSection({
  scenes,
  artifactType,
  visualMode,
  generationError,
  fidelityPreference,
  isApplyingProfile,
  isGenerating,
  isGeneratingScriptPack,
  topic,
  onEnableHighFidelity,
  onRegenerate,
  onOpenEvidence,
}: AdvancedGeneratedExplainerSectionProps) {
  const sceneList = Object.values(scenes);
  const hasScenes = sceneList.length > 0;

  return (
    <div className="space-y-6 mt-12">
      {generationError ? (
        <div className="p-4 bg-red-50 text-red-900 rounded-md border border-red-200">
          <h4 className="font-semibold mb-1">Generation Error</h4>
          <p className="text-sm">{generationError}</p>
        </div>
      ) : null}

      {hasScenes ? (
        <h2 className="text-2xl font-bold tracking-tight text-slate-100 mb-6">Generated Explainer</h2>
      ) : null}

      <div className="flex flex-col gap-6">
        {sceneList.map((scene) => (
          <SceneCard
            key={scene.id}
            sceneId={scene.id}
            title={scene.title}
            text={scene.text}
            imageUrl={scene.imageUrl}
            artifactType={artifactType}
            audioUrl={scene.audioUrl}
            visualMode={visualMode}
            onRegenerate={onRegenerate}
            onOpenEvidence={onOpenEvidence}
            claimRefs={scene.claim_refs}
            sourceMedia={scene.source_media}
            status={scene.status}
            qaStatus={scene.qa_status}
            qaReasons={scene.qa_reasons}
            qaScore={scene.qa_score}
            qaWordCount={scene.qa_word_count}
            autoRetryCount={scene.auto_retry_count}
            sourceProofWarning={scene.source_proof_warning}
            audioStatus={isGenerating && !scene.audioUrl ? "Generating..." : "Ready"}
          />
        ))}
      </div>

      {hasScenes ? (
        <>
          {fidelityPreference !== "high" ? (
            <Card className="bg-white text-slate-900 border-slate-300 shadow-md">
              <CardContent className="pt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="font-semibold">Need a higher-quality final bundle?</p>
                  <p className="text-sm text-slate-600">
                    Current run used low-key preview mode for speed. Upgrade the current scene images to 2x high fidelity without changing text.
                  </p>
                </div>
                <Button
                  type="button"
                  onClick={onEnableHighFidelity}
                  disabled={isApplyingProfile || isGenerating || isGeneratingScriptPack}
                >
                  Upscale Bundle Images (2x)
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
              High-fidelity mode is active for this bundle. Text/audio are preserved and scene images use the upscaled assets.
            </div>
          )}
          <FinalBundle
            scenes={scenes}
            topic={topic}
            disabled={isGenerating}
          />
        </>
      ) : null}
    </div>
  );
}
