"use client";

import React from "react";

import { type AgentNoteType } from "@/components/AgentActivityPanel";
import { submitAdvancedWorkflowChat } from "@/lib/advanced-api";
import {
  apiErrorMessage,
  asPendingAssistantAction,
  asPlannerQaSummary,
  buildAdvancedSourceManifest,
  deriveSceneCount,
  isUnknownWorkflowMessage,
  mapArtifactScope,
  snapshotStatusSummary,
  type AdvancedPanel,
  type ChatMessage,
  type ChatRole,
  type ExtractedSignal,
  type PendingAssistantAction,
  type ScriptPackPayload,
  type UploadedSourceAsset,
  type WorkflowAgentApiTurn,
  type WorkflowAgentChatResponse,
  type WorkflowSnapshot,
} from "@/lib/advanced";

type PushAgentNote = (type: AgentNoteType, stage: string, message: string) => void;

type UseAdvancedAgentChatOptions = {
  apiBase: string;
  workflowId: string | null;
  workflowSnapshot: WorkflowSnapshot | null;
  activePanel: AdvancedPanel;
  sourceDoc: string;
  uploadedSourceAssets: UploadedSourceAsset[];
  artifactType: string;
  scriptPresentationMode: "review" | "auto";
  chatInput: string;
  chatMessages: ChatMessage[];
  setChatInput: React.Dispatch<React.SetStateAction<string>>;
  setChatMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  setGenerationError: React.Dispatch<React.SetStateAction<string>>;
  setWorkflowId: React.Dispatch<React.SetStateAction<string | null>>;
  setExtractedSignal: React.Dispatch<React.SetStateAction<ExtractedSignal | null>>;
  setSignalStage: React.Dispatch<React.SetStateAction<"idle" | "sending" | "structuring" | "ready" | "error">>;
  setExtractProgress: React.Dispatch<React.SetStateAction<number>>;
  setScriptPack: React.Dispatch<React.SetStateAction<ScriptPackPayload | null>>;
  setExpectedSceneCount: React.Dispatch<React.SetStateAction<number>>;
  setActivePanel: React.Dispatch<React.SetStateAction<AdvancedPanel>>;
  setGenerationStatus: React.Dispatch<React.SetStateAction<string>>;
  buildRenderProfilePayload: () => unknown;
  updateWorkflowSnapshot: (snapshot: unknown) => void;
  resetWorkflowSession: (
    options?: {
      silent?: boolean;
      noteStage?: string;
      noteMessage?: string;
      statusMessage?: string;
    },
  ) => void;
  pushAgentNote: PushAgentNote;
  pushPlannerQaNote: (summary: ReturnType<typeof asPlannerQaSummary>) => void;
};

export default function useAdvancedAgentChat({
  apiBase,
  workflowId,
  workflowSnapshot,
  activePanel,
  sourceDoc,
  uploadedSourceAssets,
  artifactType,
  scriptPresentationMode,
  chatInput,
  chatMessages,
  setChatInput,
  setChatMessages,
  setGenerationError,
  setWorkflowId,
  setExtractedSignal,
  setSignalStage,
  setExtractProgress,
  setScriptPack,
  setExpectedSceneCount,
  setActivePanel,
  setGenerationStatus,
  buildRenderProfilePayload,
  updateWorkflowSnapshot,
  resetWorkflowSession,
  pushAgentNote,
  pushPlannerQaNote,
}: UseAdvancedAgentChatOptions) {
  const [pendingAssistantAction, setPendingAssistantAction] = React.useState<PendingAssistantAction | null>(null);

  const pushChatMessage = (role: ChatRole, text: string) => {
    const message: ChatMessage = {
      id: `chat-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      role,
      text,
      timestamp: Date.now(),
    };
    setChatMessages((prev) => {
      const withoutSameRole = prev.filter((item) => item.role !== role);
      const next = [...withoutSameRole, message].sort((a, b) => a.timestamp - b.timestamp);
      return next.slice(-2);
    });
  };

  const handleChatCommand = async (rawInput: string) => {
    const message = rawInput.trim();
    if (!message) return;

    const conversation: WorkflowAgentApiTurn[] = chatMessages.slice(-10).map((turn) => ({
      role: turn.role === "agent" ? "agent" : turn.role === "system" ? "system" : "user",
      text: turn.text,
    }));

    try {
      setPendingAssistantAction(null);
      setGenerationError("");
      const agentResult = await submitAdvancedWorkflowChat(apiBase, {
        message,
        context: {
          workflow_id: workflowId,
          active_panel: activePanel,
          source_text: sourceDoc,
          source_manifest: buildAdvancedSourceManifest(uploadedSourceAssets),
          render_profile: buildRenderProfilePayload(),
          artifact_scope: mapArtifactScope(artifactType),
          script_presentation_mode: scriptPresentationMode,
        },
        conversation,
      });
      const data = agentResult.data as WorkflowAgentChatResponse;
      if (!agentResult.ok) {
        const detail = apiErrorMessage(data, "Agent request failed.");
        if (isUnknownWorkflowMessage(detail)) {
          resetWorkflowSession({ noteStage: "Agent" });
          return;
        }
        setGenerationError(detail);
        pushAgentNote("error", "Agent", detail);
        return;
      }
      const returnedWorkflow = data.workflow && typeof data.workflow === "object"
        ? data.workflow as WorkflowSnapshot
        : null;

      if (typeof data.workflow_id === "string") {
        setWorkflowId(data.workflow_id);
      }
      if (returnedWorkflow) {
        updateWorkflowSnapshot(returnedWorkflow);
        if (returnedWorkflow.has_signal === false && !data.content_signal) {
          setExtractedSignal(null);
          setSignalStage(
            returnedWorkflow.checkpoint_state?.CP1_SIGNAL_READY === "failed" ? "error" : "idle",
          );
        }
        if (returnedWorkflow.has_script_pack === false && !data.script_pack) {
          setScriptPack(null);
          setExpectedSceneCount(0);
        }
      }
      if (data.content_signal && typeof data.content_signal === "object") {
        setExtractedSignal(data.content_signal);
        setSignalStage("ready");
        setExtractProgress(100);
      }
      let scriptPackOverride: ScriptPackPayload | null = null;
      if (data.script_pack && typeof data.script_pack === "object") {
        scriptPackOverride = data.script_pack as ScriptPackPayload;
        setScriptPack(scriptPackOverride);
        setExpectedSceneCount(deriveSceneCount(scriptPackOverride));
      }
      pushPlannerQaNote(asPlannerQaSummary(data.planner_qa_summary));
      const pendingAction = asPendingAssistantAction(data);
      if (pendingAction) {
        setPendingAssistantAction(pendingAction);
      } else if (data.ui?.active_panel) {
        setActivePanel(data.ui.active_panel);
      }
      if (typeof data.assistant_message === "string" && data.assistant_message.trim()) {
        pushChatMessage("agent", data.assistant_message.trim());
      }

      const detail = typeof data.message === "string"
        ? data.message
        : "";
      if (detail) {
        setGenerationError(detail);
        pushAgentNote("error", "Agent", detail);
      } else if (!pendingAction) {
        const nextStatus = snapshotStatusSummary(returnedWorkflow ?? workflowSnapshot);
        if (nextStatus) {
          setGenerationStatus(nextStatus);
        }
      }
    } catch (error) {
      console.error("Agent chat error:", error);
      setGenerationError("Unable to contact agent.");
      setPendingAssistantAction(null);
      pushAgentNote("error", "Agent", "Unable to contact agent.");
    }
  };

  const handleChatSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const text = chatInput.trim();
    if (!text) return;
    pushChatMessage("user", text);
    setChatInput("");
    await handleChatCommand(text);
  };

  return {
    handleChatSubmit,
    pendingAssistantAction,
    dismissPendingAssistantAction: () => setPendingAssistantAction(null),
  };
}
