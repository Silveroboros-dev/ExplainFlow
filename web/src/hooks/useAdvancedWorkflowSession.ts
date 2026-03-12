"use client";

import React from "react";

import { type AgentNoteType } from "@/components/AgentActivityPanel";
import useAdvancedWorkflowStorage from "@/hooks/useAdvancedWorkflowStorage";
import {
  fetchAdvancedWorkflowScriptPack,
  fetchAdvancedWorkflowSignal,
  fetchAdvancedWorkflowSnapshot,
} from "@/lib/advanced-api";
import {
  ADVANCED_WORKFLOW_STORAGE_KEY,
  EXPIRED_WORKFLOW_MESSAGE,
  deriveSceneCount,
  isUnknownWorkflowError,
  snapshotStatusSummary,
  type ActionDialogStage,
  type AdvancedPanel,
  type EvidenceViewerState,
  type ExtractedSignal,
  type SceneViewModel,
  type ScriptPackPayload,
  type WorkflowSnapshot,
} from "@/lib/advanced";

type SignalStage = "idle" | "sending" | "structuring" | "ready" | "error";
type ScriptPackStage = "idle" | "outlining" | "structuring" | "validating" | "ready" | "error";
type PushAgentNote = (type: AgentNoteType, stage: string, message: string) => void;
type SnapshotSyncOptions = {
  syncPanel?: boolean;
};

type UseAdvancedWorkflowSessionOptions = {
  apiBase: string;
  workflowId: string | null;
  setWorkflowId: React.Dispatch<React.SetStateAction<string | null>>;
  setWorkflowSnapshot: React.Dispatch<React.SetStateAction<WorkflowSnapshot | null>>;
  setExtractedSignal: React.Dispatch<React.SetStateAction<ExtractedSignal | null>>;
  setSignalStage: React.Dispatch<React.SetStateAction<SignalStage>>;
  setExtractProgress: React.Dispatch<React.SetStateAction<number>>;
  setError: React.Dispatch<React.SetStateAction<string>>;
  setGenerationError: React.Dispatch<React.SetStateAction<string>>;
  setGenerationStatus: React.Dispatch<React.SetStateAction<string>>;
  setIsExtracting: React.Dispatch<React.SetStateAction<boolean>>;
  setIsApplyingProfile: React.Dispatch<React.SetStateAction<boolean>>;
  setIsGeneratingScriptPack: React.Dispatch<React.SetStateAction<boolean>>;
  setIsGenerating: React.Dispatch<React.SetStateAction<boolean>>;
  setActionDialogStage: React.Dispatch<React.SetStateAction<ActionDialogStage | null>>;
  setShowAmendHelp: React.Dispatch<React.SetStateAction<boolean>>;
  setActivePanel: React.Dispatch<React.SetStateAction<AdvancedPanel>>;
  setScriptPack: React.Dispatch<React.SetStateAction<ScriptPackPayload | null>>;
  setScriptPackStage: React.Dispatch<React.SetStateAction<ScriptPackStage>>;
  setScriptPackProgress: React.Dispatch<React.SetStateAction<number>>;
  setScenes: React.Dispatch<React.SetStateAction<Record<string, SceneViewModel>>>;
  setExpectedSceneCount: React.Dispatch<React.SetStateAction<number>>;
  setEvidenceViewer: React.Dispatch<React.SetStateAction<EvidenceViewerState | null>>;
  fullTextBufferRef: React.MutableRefObject<Record<string, string>>;
  resetSignalPreviewRun: () => void;
  resetScriptPreviewRun: () => void;
  resetStreamPreviewRun: () => void;
  pushAgentNote: PushAgentNote;
  storageKey?: string;
};

export default function useAdvancedWorkflowSession({
  apiBase,
  workflowId,
  setWorkflowId,
  setWorkflowSnapshot,
  setExtractedSignal,
  setSignalStage,
  setExtractProgress,
  setError,
  setGenerationError,
  setGenerationStatus,
  setIsExtracting,
  setIsApplyingProfile,
  setIsGeneratingScriptPack,
  setIsGenerating,
  setActionDialogStage,
  setShowAmendHelp,
  setActivePanel,
  setScriptPack,
  setScriptPackStage,
  setScriptPackProgress,
  setScenes,
  setExpectedSceneCount,
  setEvidenceViewer,
  fullTextBufferRef,
  resetSignalPreviewRun,
  resetScriptPreviewRun,
  resetStreamPreviewRun,
  pushAgentNote,
  storageKey = ADVANCED_WORKFLOW_STORAGE_KEY,
}: UseAdvancedWorkflowSessionOptions) {
  const clearPersistedWorkflowId = () => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.removeItem(storageKey);
  };

  const resetWorkflowSession = (
    options: {
      silent?: boolean;
      noteStage?: string;
      noteMessage?: string;
      statusMessage?: string;
    } = {},
  ) => {
    const {
      silent = false,
      noteStage = "Recovery",
      noteMessage = EXPIRED_WORKFLOW_MESSAGE,
      statusMessage = EXPIRED_WORKFLOW_MESSAGE,
    } = options;
    clearPersistedWorkflowId();
    setWorkflowId(null);
    setWorkflowSnapshot(null);
    setExtractedSignal(null);
    setSignalStage("idle");
    setExtractProgress(0);
    setScriptPack(null);
    setScriptPackStage("idle");
    setScriptPackProgress(0);
    setScenes({});
    setExpectedSceneCount(0);
    setEvidenceViewer(null);
    setError("");
    setGenerationError("");
    setGenerationStatus(statusMessage);
    setIsExtracting(false);
    setIsApplyingProfile(false);
    setIsGeneratingScriptPack(false);
    setIsGenerating(false);
    setActionDialogStage(null);
    setShowAmendHelp(false);
    setActivePanel("source");
    fullTextBufferRef.current = {};
    resetSignalPreviewRun();
    resetScriptPreviewRun();
    resetStreamPreviewRun();
    if (!silent) {
      pushAgentNote("error", noteStage, noteMessage);
    }
  };

  const handleUnknownWorkflowError = (
    error: unknown,
    options: {
      silent?: boolean;
      noteStage?: string;
      noteMessage?: string;
      statusMessage?: string;
    } = {},
  ): boolean => {
    if (!isUnknownWorkflowError(error)) {
      return false;
    }
    resetWorkflowSession(options);
    return true;
  };

  const updateWorkflowSnapshot = (snapshot: unknown) => {
    if (!snapshot || typeof snapshot !== "object") return;
    const candidate = snapshot as WorkflowSnapshot;
    if (!candidate.workflow_id || typeof candidate.workflow_id !== "string") return;
    setWorkflowSnapshot(candidate);
    setWorkflowId(candidate.workflow_id);
  };

  const syncWorkflowUiFromSnapshot = (
    snapshot: WorkflowSnapshot,
    options: SnapshotSyncOptions = {},
  ) => {
    const { syncPanel = true } = options;
    const checkpoints = snapshot.checkpoint_state ?? {};
    if (checkpoints.CP1_SIGNAL_READY === "passed" || snapshot.has_signal) {
      setSignalStage("ready");
      setExtractProgress(100);
      setError("");
    } else if (checkpoints.CP1_SIGNAL_READY === "failed") {
      setSignalStage("error");
      setExtractProgress(0);
    }

    if (syncPanel) {
      if (checkpoints.CP6_BUNDLE_FINALIZED === "passed" || checkpoints.CP5_STREAM_COMPLETE === "passed") {
        setActivePanel("stream");
      } else if (snapshot.has_script_pack) {
        setActivePanel("script");
      } else if (snapshot.ready_for_script_pack || snapshot.has_render_profile || snapshot.render_profile_queued) {
        setActivePanel("signal");
      } else if (snapshot.workflow_id) {
        setActivePanel("profile");
      }
    }

    setGenerationStatus(snapshotStatusSummary(snapshot));
  };

  const loadWorkflowSnapshot = async (
    workflowIdValue: string,
    options: SnapshotSyncOptions = {},
  ): Promise<WorkflowSnapshot> => {
    const snapshot = await fetchAdvancedWorkflowSnapshot(apiBase, workflowIdValue);
    updateWorkflowSnapshot(snapshot);
    syncWorkflowUiFromSnapshot(snapshot, { syncPanel: options.syncPanel ?? false });
    const streamFailed = snapshot.checkpoint_state?.CP5_STREAM_COMPLETE === "failed"
      || snapshot.checkpoint_state?.CP6_BUNDLE_FINALIZED === "failed";
    if (streamFailed && typeof snapshot.last_error === "string" && snapshot.last_error.trim()) {
      setGenerationError(snapshot.last_error);
    } else if (
      snapshot.checkpoint_state?.CP5_STREAM_COMPLETE === "passed"
      || snapshot.checkpoint_state?.CP6_BUNDLE_FINALIZED === "passed"
    ) {
      setGenerationError("");
    }
    return snapshot;
  };

  const loadWorkflowSignal = async (workflowIdValue: string): Promise<ExtractedSignal> => (
    fetchAdvancedWorkflowSignal(apiBase, workflowIdValue)
  );

  const loadWorkflowScriptPack = async (workflowIdValue: string): Promise<ScriptPackPayload> => (
    fetchAdvancedWorkflowScriptPack(apiBase, workflowIdValue)
  );

  const recoverWorkflowState = async (
    workflowIdValue: string,
    options: { silent?: boolean } = {},
  ): Promise<WorkflowSnapshot | null> => {
    const { silent = false } = options;

    try {
      const snapshot = await loadWorkflowSnapshot(workflowIdValue, { syncPanel: true });
      if (snapshot.has_signal) {
        try {
          const recoveredSignal = await loadWorkflowSignal(workflowIdValue);
          setExtractedSignal(recoveredSignal);
        } catch (signalError) {
          console.warn("Signal recovery error:", signalError);
        }
      }
      if (snapshot.has_script_pack) {
        try {
          const recoveredScriptPack = await loadWorkflowScriptPack(workflowIdValue);
          setScriptPack(recoveredScriptPack);
          setExpectedSceneCount(deriveSceneCount(recoveredScriptPack));
          setScriptPackStage("ready");
          setScriptPackProgress(100);
        } catch (scriptPackError) {
          console.warn("Script pack recovery error:", scriptPackError);
        }
      } else {
        setExpectedSceneCount(0);
        setScriptPackStage("idle");
        setScriptPackProgress(0);
      }
      if (!silent) {
        pushAgentNote("info", "Recovery", "Recovered workflow state from the latest saved checkpoint.");
      }
      return snapshot;
    } catch (recoveryError) {
      if (handleUnknownWorkflowError(recoveryError, { silent, noteStage: "Recovery" })) {
        return null;
      }
      console.error("Workflow recovery error:", recoveryError);
      if (!silent) {
        pushAgentNote("error", "Recovery", "Unable to recover saved workflow state.");
      }
      return null;
    }
  };

  useAdvancedWorkflowStorage({
    workflowId,
    storageKey,
    recoverWorkflow: (storedWorkflowId) => recoverWorkflowState(storedWorkflowId, { silent: true }),
  });

  return {
    fetchWorkflowSignal: loadWorkflowSignal,
    fetchWorkflowSnapshot: loadWorkflowSnapshot,
    handleUnknownWorkflowError,
    recoverWorkflowState,
    resetWorkflowSession,
    syncWorkflowUiFromSnapshot,
    updateWorkflowSnapshot,
  };
}
