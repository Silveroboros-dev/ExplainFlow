"use client";

import React from "react";

import { type AgentNote, type AgentNoteType } from "@/components/AgentActivityPanel";
import {
  extractAdvancedWorkflowSignal,
  generateAdvancedWorkflowScriptPack,
  lockAdvancedWorkflowArtifacts,
  lockAdvancedWorkflowRender,
  startAdvancedWorkflow,
} from "@/lib/advanced-api";
import {
  apiErrorMessage,
  asPlannerQaSummary,
  buildAdvancedRenderProfilePayload,
  buildAdvancedSourceManifest,
  deriveSceneCount,
  mapArtifactScope,
  snapshotStatusSummary,
  type AdvancedRenderProfileInput,
  type AdvancedRenderProfileMode,
  type ExtractedSignal,
  type ScriptPackPayload,
  type UploadedSourceAsset,
  type WorkflowSnapshot,
} from "@/lib/advanced";

type SignalStage = "idle" | "sending" | "structuring" | "ready" | "error";
type ScriptPackStage = "idle" | "outlining" | "structuring" | "validating" | "ready" | "error";
type ScriptPresentationMode = "review" | "auto";

type StartStreamOptions = {
  preserveExistingScenes?: boolean;
  preparationMessage?: string;
  startNote?: string;
  gateReadyOverride?: boolean;
};

type StartStreamFn = (
  scriptPackOverride?: ScriptPackPayload | null,
  options?: StartStreamOptions,
) => Promise<void>;

type PushAgentNote = (type: AgentNoteType, stage: string, message: string) => void;

type UseAdvancedWorkflowActionsOptions = {
  apiBase: string;
  sourceDoc: string;
  uploadedSourceAssets: UploadedSourceAsset[];
  hasSourceInput: boolean;
  workflowId: string | null;
  workflowSnapshot: WorkflowSnapshot | null;
  extractedSignal: ExtractedSignal | null;
  scriptPack: ScriptPackPayload | null;
  fidelityPreference: AdvancedRenderProfileMode;
  scriptPresentationMode: ScriptPresentationMode;
  renderProfileInput: AdvancedRenderProfileInput;
  setWorkflowId: React.Dispatch<React.SetStateAction<string | null>>;
  setWorkflowSnapshot: React.Dispatch<React.SetStateAction<WorkflowSnapshot | null>>;
  setAgentNotes: React.Dispatch<React.SetStateAction<AgentNote[]>>;
  setIsExtracting: React.Dispatch<React.SetStateAction<boolean>>;
  setSignalStage: React.Dispatch<React.SetStateAction<SignalStage>>;
  setExtractProgress: React.Dispatch<React.SetStateAction<number>>;
  setError: React.Dispatch<React.SetStateAction<string>>;
  setGenerationError: React.Dispatch<React.SetStateAction<string>>;
  setExtractedSignal: React.Dispatch<React.SetStateAction<ExtractedSignal | null>>;
  setGenerationStatus: React.Dispatch<React.SetStateAction<string>>;
  setFidelityPreference: React.Dispatch<React.SetStateAction<AdvancedRenderProfileMode>>;
  setIsApplyingProfile: React.Dispatch<React.SetStateAction<boolean>>;
  setIsGeneratingScriptPack: React.Dispatch<React.SetStateAction<boolean>>;
  setScriptPresentationMode: React.Dispatch<React.SetStateAction<ScriptPresentationMode>>;
  setActivePanel: React.Dispatch<React.SetStateAction<"source" | "profile" | "signal" | "stream" | "script">>;
  setScriptPack: React.Dispatch<React.SetStateAction<ScriptPackPayload | null>>;
  setExpectedSceneCount: React.Dispatch<React.SetStateAction<number>>;
  setScriptPackStage: React.Dispatch<React.SetStateAction<ScriptPackStage>>;
  setScriptPackProgress: React.Dispatch<React.SetStateAction<number>>;
  clearGeneratedOutputs: () => void;
  startSignalPreviewRun: () => void;
  resetSignalPreviewRun: () => void;
  startScriptPreviewRun: () => void;
  resetScriptPreviewRun: () => void;
  resetStreamPreviewRun: () => void;
  updateWorkflowSnapshot: (snapshot: unknown) => void;
  syncWorkflowUiFromSnapshot: (snapshot: WorkflowSnapshot) => void;
  recoverWorkflowState: (
    workflowIdValue: string,
    options?: { silent?: boolean },
  ) => Promise<WorkflowSnapshot | null>;
  fetchWorkflowSnapshot: (workflowIdValue: string) => Promise<WorkflowSnapshot>;
  fetchWorkflowSignal: (workflowIdValue: string) => Promise<ExtractedSignal>;
  handleUnknownWorkflowError: (
    error: unknown,
    options?: {
      silent?: boolean;
      noteStage?: string;
      noteMessage?: string;
      statusMessage?: string;
    },
  ) => boolean;
  pushAgentNote: PushAgentNote;
  pushPlannerQaNote: (summary: ReturnType<typeof asPlannerQaSummary>) => void;
};

export default function useAdvancedWorkflowActions({
  apiBase,
  sourceDoc,
  uploadedSourceAssets,
  hasSourceInput,
  workflowId,
  workflowSnapshot,
  extractedSignal,
  scriptPack,
  fidelityPreference,
  scriptPresentationMode,
  renderProfileInput,
  setWorkflowId,
  setWorkflowSnapshot,
  setAgentNotes,
  setIsExtracting,
  setSignalStage,
  setExtractProgress,
  setError,
  setGenerationError,
  setExtractedSignal,
  setGenerationStatus,
  setFidelityPreference,
  setIsApplyingProfile,
  setIsGeneratingScriptPack,
  setScriptPresentationMode,
  setActivePanel,
  setScriptPack,
  setExpectedSceneCount,
  setScriptPackStage,
  setScriptPackProgress,
  clearGeneratedOutputs,
  startSignalPreviewRun,
  resetSignalPreviewRun,
  startScriptPreviewRun,
  resetScriptPreviewRun,
  resetStreamPreviewRun,
  updateWorkflowSnapshot,
  syncWorkflowUiFromSnapshot,
  recoverWorkflowState,
  fetchWorkflowSnapshot,
  fetchWorkflowSignal,
  handleUnknownWorkflowError,
  pushAgentNote,
  pushPlannerQaNote,
}: UseAdvancedWorkflowActionsOptions) {
  const buildRenderProfilePayload = (mode: AdvancedRenderProfileMode = fidelityPreference) => (
    buildAdvancedRenderProfilePayload(renderProfileInput, mode)
  );

  const runExtraction = async (options: { armSignalPreview?: boolean } = {}) => {
    if (!hasSourceInput) {
      return false;
    }
    const { armSignalPreview = false } = options;
    const sourceManifest = buildAdvancedSourceManifest(uploadedSourceAssets);
    const canReuseWorkflow = Boolean(
      workflowId
      && workflowSnapshot?.checkpoint_state?.CP1_SIGNAL_READY !== "passed",
    );
    let activeWorkflowId = canReuseWorkflow ? workflowId : null;

    setAgentNotes([]);
    pushAgentNote("info", "Extraction", "Signal extraction started from source material.");
    setIsExtracting(true);
    setSignalStage("sending");
    setExtractProgress(8);
    setError("");
    setGenerationError("");
    setExtractedSignal(null);
    if (armSignalPreview) {
      startSignalPreviewRun();
    } else {
      resetSignalPreviewRun();
    }
    resetScriptPreviewRun();
    resetStreamPreviewRun();
    setGenerationStatus("");
    clearGeneratedOutputs();
    setFidelityPreference("preview");

    try {
      if (!activeWorkflowId) {
        const startResult = await startAdvancedWorkflow(apiBase, {
          source_text: sourceDoc,
          ...(sourceManifest ? { source_manifest: sourceManifest } : {}),
        });
        const startData = startResult.data;
        if (!startResult.ok || startData.status !== "success" || !startData.workflow_id) {
          setError(apiErrorMessage(startData, "Unable to initialize workflow."));
          pushAgentNote("error", "Extraction", "Workflow initialization failed.");
          setSignalStage("error");
          setExtractProgress(0);
          return false;
        }
        activeWorkflowId = startData.workflow_id;
        setWorkflowId(startData.workflow_id);
        if (startData.workflow) {
          updateWorkflowSnapshot(startData.workflow);
          syncWorkflowUiFromSnapshot(startData.workflow);
        } else {
          setWorkflowSnapshot(null);
        }
      }

      const extractResult = await extractAdvancedWorkflowSignal(apiBase, activeWorkflowId, {
        source_text: sourceDoc,
        ...(sourceManifest ? { source_manifest: sourceManifest } : {}),
      });
      const data = extractResult.data;
      if (data.workflow) {
        updateWorkflowSnapshot(data.workflow);
        syncWorkflowUiFromSnapshot(data.workflow);
      }
      if (data.status === "success") {
        setExtractedSignal(data.content_signal ?? null);
        setSignalStage("ready");
        setExtractProgress(100);
        setGenerationStatus(
          data.workflow
            ? snapshotStatusSummary(data.workflow)
            : "Signal extracted. Next: lock artifact scope and render profile.",
        );
        pushAgentNote("checkpoint", "Extraction", "Signal extracted and schema validation passed.");
        return true;
      }

      setError(data.message || "Extraction failed");
      pushAgentNote("error", "Extraction", data.message || "Signal extraction failed.");
      setSignalStage("error");
      setExtractProgress(0);
      return false;
    } catch (err) {
      console.error(err);
      if (activeWorkflowId) {
        const recoveredSnapshot = await recoverWorkflowState(activeWorkflowId, { silent: true });
        if (recoveredSnapshot?.has_signal || recoveredSnapshot?.checkpoint_state?.CP1_SIGNAL_READY === "passed") {
          pushAgentNote("checkpoint", "Extraction", "Recovered extracted signal after a network interruption.");
          setError("");
          return true;
        }
      }
      setError("Network error during extraction");
      pushAgentNote("error", "Extraction", "Network error during signal extraction.");
      setSignalStage("error");
      setExtractProgress(0);
      return false;
    } finally {
      setIsExtracting(false);
    }
  };

  const applyProfileToWorkflow = async (
    mode: AdvancedRenderProfileMode = fidelityPreference,
  ): Promise<WorkflowSnapshot | null> => {
    if (!workflowId) {
      setGenerationStatus("Start with extraction first so a workflow can be created.");
      pushAgentNote("error", "Render Profile", "Cannot lock render profile before workflow start.");
      return null;
    }

    setIsApplyingProfile(true);
    setGenerationError("");
    setGenerationStatus("Locking artifact scope and render profile...");
    pushAgentNote("info", "Render Profile", "Locking artifact scope and render profile for this run.");

    try {
      const artifactScope = mapArtifactScope(renderProfileInput.artifactType);
      const artifactResult = await lockAdvancedWorkflowArtifacts(apiBase, workflowId, artifactScope);
      const artifactData = artifactResult.data;
      if (!artifactResult.ok || artifactData?.status !== "success") {
        const detail = typeof artifactData?.detail === "string"
          ? artifactData.detail
          : (typeof artifactData?.message === "string" ? artifactData.message : "Artifact scope lock failed.");
        setGenerationError(detail);
        pushAgentNote("error", "Render Profile", detail);
        setGenerationStatus("");
        return null;
      }
      if (artifactData.workflow) {
        updateWorkflowSnapshot(artifactData.workflow);
      }

      const renderProfile = buildRenderProfilePayload(mode);
      const renderResult = await lockAdvancedWorkflowRender(apiBase, workflowId, renderProfile);
      const renderData = renderResult.data;
      if (!renderResult.ok || renderData?.status !== "success") {
        const detail = typeof renderData?.detail === "string"
          ? renderData.detail
          : (typeof renderData?.message === "string" ? renderData.message : "Render profile lock failed.");
        setGenerationError(detail);
        pushAgentNote("error", "Render Profile", detail);
        setGenerationStatus("");
        return null;
      }

      const updatedWorkflow = renderData.workflow as WorkflowSnapshot | undefined;
      if (updatedWorkflow) {
        updateWorkflowSnapshot(updatedWorkflow);
      }
      const cp3Status = typeof renderData?.workflow?.checkpoint_state?.CP3_RENDER_LOCKED === "string"
        ? renderData.workflow.checkpoint_state.CP3_RENDER_LOCKED
        : "";
      if (cp3Status === "passed") {
        setGenerationStatus(
          mode === "high"
            ? "High-fidelity profile locked. Current bundle images can now be upscaled without changing the script."
            : "Render profile locked. Continue to signal confirmation and script planning.",
        );
        pushAgentNote("checkpoint", "Render Profile", "Render profile locked and ready.");
      } else {
        setGenerationStatus("Artifacts locked. Render profile queued and will auto-lock when signal extraction completes.");
        pushAgentNote("info", "Render Profile", "Artifacts locked. Render lock is queued until signal is ready.");
      }
      return updatedWorkflow ?? null;
    } catch (err) {
      console.error("Apply profile error:", err);
      const recoveredSnapshot = await recoverWorkflowState(workflowId, { silent: true });
      if (recoveredSnapshot) {
        const cp3Status = recoveredSnapshot.checkpoint_state?.CP3_RENDER_LOCKED;
        if (cp3Status === "passed") {
          setGenerationError("");
          setGenerationStatus(
            mode === "high"
              ? "High-fidelity profile locked. Current bundle images can now be upscaled without changing the script."
              : "Render profile locked. Continue to signal confirmation and script planning.",
          );
          pushAgentNote("checkpoint", "Render Profile", "Recovered render profile lock after a network interruption.");
          return recoveredSnapshot;
        }
        if (recoveredSnapshot.render_profile_queued) {
          setGenerationError("");
          setGenerationStatus("Artifacts locked. Render profile queued and will auto-lock when signal extraction completes.");
          pushAgentNote("info", "Render Profile", "Recovered queued render profile after a network interruption.");
          return recoveredSnapshot;
        }
      }
      setGenerationError("Unable to lock render profile in workflow.");
      pushAgentNote("error", "Render Profile", "Unable to lock render profile in workflow.");
      setGenerationStatus("");
      return null;
    } finally {
      setIsApplyingProfile(false);
    }
  };

  const generateScriptPack = async (
    mode: ScriptPresentationMode = "review",
    options: { onAutoStartStream?: StartStreamFn } = {},
  ) => {
    if (!workflowId) {
      setGenerationStatus("Run extraction first to initialize workflow.");
      pushAgentNote("error", "Script Pack", "Cannot generate script pack before extraction workflow starts.");
      return;
    }
    let currentSnapshot = workflowSnapshot;
    try {
      currentSnapshot = await fetchWorkflowSnapshot(workflowId);
    } catch (snapshotError) {
      if (handleUnknownWorkflowError(snapshotError, { noteStage: "Script Pack" })) {
        return;
      }
      console.error("Script pack snapshot refresh error:", snapshotError);
    }
    if (!currentSnapshot?.ready_for_script_pack) {
      setGenerationStatus("Workflow gate not ready. Lock artifacts and render profile first.");
      pushAgentNote("error", "Script Pack", "Script pack generation blocked by workflow gate.");
      return;
    }

    setIsGeneratingScriptPack(true);
    setScriptPresentationMode(mode);
    setGenerationError("");
    setGenerationStatus(
      mode === "review"
        ? "Preparing script pack for your confirmation..."
        : "Preparing script pack for immediate use...",
    );
    setActivePanel("script");
    setScriptPackStage("outlining");
    setScriptPackProgress(10);
    pushAgentNote(
      "info",
      "Script Pack",
      mode === "review"
        ? "Generating script pack for review."
        : "Generating script pack for immediate streaming.",
    );
    startScriptPreviewRun();
    setScriptPack(null);
    setExpectedSceneCount(0);

    try {
      const scriptPackResult = await generateAdvancedWorkflowScriptPack(apiBase, workflowId);
      const data = scriptPackResult.data;
      if (data?.workflow) {
        updateWorkflowSnapshot(data.workflow);
      }
      if (data?.status === "success" && data?.script_pack) {
        const approvedScriptPack = data.script_pack as ScriptPackPayload;
        setScriptPack(approvedScriptPack);
        setExpectedSceneCount(deriveSceneCount(approvedScriptPack));
        setScriptPackStage("ready");
        setScriptPackProgress(100);
        pushPlannerQaNote(asPlannerQaSummary(data.planner_qa_summary));
        if (mode === "review") {
          setGenerationStatus("Script pack is ready. Review and amend before starting stream generation.");
          setActivePanel("script");
          pushAgentNote("checkpoint", "Script Pack", "Script pack ready for review.");
        } else if (options.onAutoStartStream) {
          setGenerationStatus("Script pack approved. Starting generation stream automatically...");
          setActivePanel("stream");
          pushAgentNote("checkpoint", "Script Pack", "Script pack approved. Starting stream automatically.");
          setIsGeneratingScriptPack(false);
          await options.onAutoStartStream(approvedScriptPack, {
            gateReadyOverride: true,
            preparationMessage: "Script pack approved. Preparing generation pipeline...",
            startNote: "Script pack approved. Generation stream started automatically.",
          });
          return;
        } else {
          setGenerationStatus("Script pack approved. Generation stream is ready to start.");
          setActivePanel("stream");
          pushAgentNote("checkpoint", "Script Pack", "Script pack approved and ready for stream.");
        }
      } else {
        const detail = typeof data?.detail === "string"
          ? data.detail
          : (typeof data?.message === "string" ? data.message : "Script pack generation failed.");
        setScriptPackStage("error");
        setScriptPackProgress(0);
        setGenerationError(detail);
        pushAgentNote("error", "Script Pack", detail);
        setGenerationStatus("");
      }
    } catch (err) {
      console.error("Script pack error:", err);
      const recoveredSnapshot = await recoverWorkflowState(workflowId, { silent: true });
      if (recoveredSnapshot?.has_script_pack) {
        setScriptPackStage("ready");
        setScriptPackProgress(100);
        setGenerationError("");
        if (scriptPack) {
          setExpectedSceneCount(deriveSceneCount(scriptPack));
        }
        if (mode === "review") {
          setGenerationStatus("Script pack is ready. Review and amend before starting stream generation.");
          setActivePanel("script");
        } else {
          setGenerationStatus("Recovered script pack after a network interruption.");
          setActivePanel("script");
        }
        pushAgentNote("checkpoint", "Script Pack", "Recovered script pack after a network interruption.");
        return;
      }
      setScriptPackStage("error");
      setScriptPackProgress(0);
      setGenerationError("Unable to generate script pack.");
      pushAgentNote("error", "Script Pack", "Unable to generate script pack.");
      setGenerationStatus("");
    } finally {
      setIsGeneratingScriptPack(false);
    }
  };

  const confirmSignal = async (options: { onAutoStartStream?: StartStreamFn } = {}) => {
    let currentSnapshot = workflowSnapshot;
    let signalToUse = extractedSignal;

    if (workflowId) {
      try {
        currentSnapshot = await fetchWorkflowSnapshot(workflowId);
      } catch (snapshotError) {
        if (handleUnknownWorkflowError(snapshotError, { noteStage: "Signal" })) {
          return;
        }
        console.error("Signal confirmation snapshot refresh error:", snapshotError);
      }
    }
    if (!signalToUse && workflowId && currentSnapshot?.has_signal) {
      try {
        signalToUse = await fetchWorkflowSignal(workflowId);
        setExtractedSignal(signalToUse);
      } catch (signalError) {
        if (handleUnknownWorkflowError(signalError, { noteStage: "Signal" })) {
          return;
        }
        console.error("Signal confirmation recovery error:", signalError);
      }
    }

    if (!signalToUse) {
      setGenerationStatus("Extract signal first.");
      pushAgentNote("error", "Signal", "Signal confirmation blocked: extract signal first.");
      return;
    }
    if (!currentSnapshot?.ready_for_script_pack) {
      setGenerationStatus("Workflow gate not ready. Lock artifact scope and render profile first.");
      pushAgentNote("error", "Signal", "Signal confirmation blocked by join gate (artifacts/render not locked).");
      return;
    }
    setActivePanel("script");
    setGenerationStatus("Signal confirmed. Generating script pack...");
    pushAgentNote("info", "Signal", "Signal confirmed. Script pack generation started.");
    await generateScriptPack(scriptPresentationMode, options);
  };

  return {
    applyProfileToWorkflow,
    buildRenderProfilePayload,
    confirmSignal,
    generateScriptPack,
    runExtraction,
  };
}
