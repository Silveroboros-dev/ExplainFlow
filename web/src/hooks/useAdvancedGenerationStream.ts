"use client";

import React from "react";

import { type AgentNoteType } from "@/components/AgentActivityPanel";
import { openAdvancedWorkflowStream } from "@/lib/advanced-api";
import {
  CHECKPOINT_LABELS,
  asPlannerQaSummary,
  asSourceMedia,
  asSourceMediaList,
  asStringArray,
  deriveSceneCount,
  type SceneQaPayload,
  type SceneQueueItem,
  type SceneViewModel,
  type ScriptPackPayload,
  type SourceMediaViewModel,
  type WorkflowSnapshot,
} from "@/lib/advanced";

type PushAgentNote = (type: AgentNoteType, stage: string, message: string) => void;

type GenerateStreamOptions = {
  preserveExistingScenes?: boolean;
  preparationMessage?: string;
  startNote?: string;
  gateReadyOverride?: boolean;
};

type UseAdvancedGenerationStreamOptions = {
  apiBase: string;
  workflowId: string | null;
  workflowSnapshot: WorkflowSnapshot | null;
  scriptPack: ScriptPackPayload | null;
  setIsGenerating: React.Dispatch<React.SetStateAction<boolean>>;
  setGenerationError: React.Dispatch<React.SetStateAction<string>>;
  setGenerationStatus: React.Dispatch<React.SetStateAction<string>>;
  setExpectedSceneCount: React.Dispatch<React.SetStateAction<number>>;
  setScenes: React.Dispatch<React.SetStateAction<Record<string, SceneViewModel>>>;
  setScriptPack: React.Dispatch<React.SetStateAction<ScriptPackPayload | null>>;
  fullTextBufferRef: React.MutableRefObject<Record<string, string>>;
  startStreamPreviewRun: () => void;
  fetchWorkflowSnapshot: (workflowIdValue: string) => Promise<WorkflowSnapshot>;
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

export default function useAdvancedGenerationStream({
  apiBase,
  workflowId,
  workflowSnapshot,
  scriptPack,
  setIsGenerating,
  setGenerationError,
  setGenerationStatus,
  setExpectedSceneCount,
  setScenes,
  setScriptPack,
  fullTextBufferRef,
  startStreamPreviewRun,
  fetchWorkflowSnapshot,
  handleUnknownWorkflowError,
  pushAgentNote,
  pushPlannerQaNote,
}: UseAdvancedGenerationStreamOptions) {
  const updateSceneMetadata = (
    sceneId: string,
    patch: Partial<SceneViewModel>,
  ) => {
    setScenes((prev) => {
      const existing = prev[sceneId] ?? { id: sceneId, text: "", status: "queued" };
      return {
        ...prev,
        [sceneId]: {
          ...existing,
          ...patch,
        },
      };
    });
  };

  const appendSourceMedia = (sceneId: string, media: SourceMediaViewModel) => {
    setScenes((prev) => {
      const existing = prev[sceneId] ?? { id: sceneId, text: "", status: "queued" };
      const currentMedia = Array.isArray(existing.source_media) ? existing.source_media : [];
      const existingIndex = currentMedia.findIndex((item) => (
        item.asset_id === media.asset_id
        && item.start_ms === media.start_ms
        && item.end_ms === media.end_ms
        && item.usage === media.usage
        && (
          item.url === media.url
          || (
            item.original_url === media.original_url
            && item.page_index === media.page_index
          )
          || (
            item.evidence_refs.length > 0
            && media.evidence_refs.length > 0
            && item.evidence_refs.some((ref) => media.evidence_refs.includes(ref))
          )
        )
      ));
      const nextMedia = [...currentMedia];
      if (existingIndex >= 0) {
        const prior = nextMedia[existingIndex];
        nextMedia[existingIndex] = {
          ...prior,
          ...media,
          claim_refs: Array.from(new Set([...(prior.claim_refs ?? []), ...(media.claim_refs ?? [])])),
          evidence_refs: Array.from(new Set([...(prior.evidence_refs ?? []), ...(media.evidence_refs ?? [])])),
        };
      } else {
        nextMedia.push(media);
      }
      return {
        ...prev,
        [sceneId]: {
          ...existing,
          source_media: nextMedia,
          evidence_refs: Array.from(new Set([...(existing.evidence_refs ?? []), ...media.evidence_refs])),
        },
      };
    });
  };

  const handleRegenerateScene = (
    sceneId: string,
    newText: string,
    newImageUrl: string,
    newAudioUrl: string,
  ) => {
    fullTextBufferRef.current[sceneId] = newText;
    setScenes((prev) => ({
      ...prev,
      [sceneId]: {
        ...prev[sceneId],
        text: "",
        imageUrl: newImageUrl,
        audioUrl: newAudioUrl,
        status: "ready",
      },
    }));
  };

  const refreshWorkflowSnapshot = async () => {
    if (!workflowId) {
      return;
    }
    try {
      await fetchWorkflowSnapshot(workflowId);
    } catch (snapshotError) {
      handleUnknownWorkflowError(snapshotError, { silent: true, noteStage: "Generation" });
    }
  };

  const handleGenerateStream = async (
    scriptPackOverride?: ScriptPackPayload | null,
    options: GenerateStreamOptions = {},
  ) => {
    if (!workflowId) {
      setGenerationStatus("Run extraction first to initialize workflow.");
      pushAgentNote("error", "Generation", "Cannot start generation before extraction workflow starts.");
      return;
    }
    const {
      preserveExistingScenes = false,
      preparationMessage = "Preparing generation pipeline...",
      startNote = "Interleaved generation stream started.",
      gateReadyOverride = false,
    } = options;
    if (!gateReadyOverride && !workflowSnapshot?.ready_for_stream) {
      setGenerationStatus("Workflow gate not ready for stream. Confirm script pack first.");
      pushAgentNote("error", "Generation", "Generation blocked by workflow gate (script pack not locked).");
      return;
    }

    setIsGenerating(true);
    setGenerationError("");
    setGenerationStatus(preparationMessage);
    startStreamPreviewRun();
    setExpectedSceneCount(deriveSceneCount(scriptPackOverride ?? scriptPack ?? null));
    if (!preserveExistingScenes) {
      setScenes({});
    }
    fullTextBufferRef.current = {};
    pushAgentNote("info", "Generation", startNote);

    try {
      const response = await openAdvancedWorkflowStream(
        apiBase,
        workflowId,
        scriptPackOverride ?? scriptPack ?? undefined,
      );

      if (!response.body) throw new Error("ReadableStream not supported in this browser.");

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let currentEvent = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.substring(7).trim();
          } else if (line.startsWith("data: ")) {
            const dataStr = line.substring(6).trim();
            if (!dataStr) continue;

            try {
              const parsedData: unknown = JSON.parse(dataStr);
              if (!parsedData || typeof parsedData !== "object") continue;
              const data = parsedData as Record<string, unknown>;

              if (currentEvent === "scene_queue_ready") {
                const initialScenes: Record<string, SceneViewModel> = {};
                const queueScenes = Array.isArray(data.scenes) ? data.scenes : [];
                queueScenes.forEach((scene) => {
                  if (!scene || typeof scene !== "object") return;
                  const sceneItem = scene as SceneQueueItem;
                  if (!sceneItem.scene_id) return;
                  initialScenes[sceneItem.scene_id] = {
                    id: sceneItem.scene_id,
                    title: sceneItem.title,
                    claim_refs: sceneItem.claim_refs,
                    evidence_refs: sceneItem.evidence_refs,
                    render_strategy: sceneItem.render_strategy,
                    expected_source_media_count: sceneItem.source_media_count,
                    text: "",
                    status: "queued",
                  };
                  fullTextBufferRef.current[sceneItem.scene_id] = sceneItem.narration_focus || "";
                });
                setExpectedSceneCount(queueScenes.length);
                setScenes(initialScenes);
                pushAgentNote(
                  "info",
                  "Planning",
                  `Scene queue ready with ${Object.keys(initialScenes).length} scenes.`,
                );
              } else if (currentEvent === "script_pack_ready") {
                const rawPack = data.script_pack;
                if (rawPack && typeof rawPack === "object") {
                  const streamScriptPack = rawPack as ScriptPackPayload;
                  setScriptPack(streamScriptPack);
                  setExpectedSceneCount(deriveSceneCount(streamScriptPack));
                  pushAgentNote("checkpoint", "Script Pack", "Script pack received in stream context.");
                }
                pushPlannerQaNote(asPlannerQaSummary(data.planner_qa_summary));
              } else if (currentEvent === "scene_start") {
                const sceneId = typeof data.scene_id === "string" ? data.scene_id : "";
                if (!sceneId) continue;
                fullTextBufferRef.current[sceneId] = "";
                if (typeof data.title === "string" && data.title.trim()) {
                  setGenerationStatus(`Generating ${data.title}...`);
                  pushAgentNote("info", sceneId, `Generating ${data.title}.`);
                }
                const patch: Partial<SceneViewModel> = {
                  claim_refs: asStringArray(data.claim_refs),
                  evidence_refs: asStringArray(data.evidence_refs),
                  render_strategy: data.render_strategy === "generated" || data.render_strategy === "source_media" || data.render_strategy === "hybrid"
                    ? data.render_strategy
                    : undefined,
                  source_media: asSourceMediaList(data.source_media),
                  source_proof_warning: undefined,
                  status: "generating",
                };
                if (typeof data.title === "string" && data.title.trim()) {
                  patch.title = data.title;
                }
                updateSceneMetadata(sceneId, patch);
              } else if (currentEvent === "story_text_delta") {
                const sceneId = typeof data.scene_id === "string" ? data.scene_id : "";
                if (!sceneId) continue;
                const delta = typeof data.delta === "string" ? data.delta : "";
                fullTextBufferRef.current[sceneId] = (fullTextBufferRef.current[sceneId] || "") + delta;
              } else if (currentEvent === "diagram_ready") {
                const sceneId = typeof data.scene_id === "string" ? data.scene_id : "";
                if (!sceneId) continue;
                updateSceneMetadata(sceneId, { imageUrl: typeof data.url === "string" ? data.url : undefined });
              } else if (currentEvent === "audio_ready") {
                const sceneId = typeof data.scene_id === "string" ? data.scene_id : "";
                if (!sceneId) continue;
                updateSceneMetadata(sceneId, { audioUrl: typeof data.url === "string" ? data.url : undefined });
              } else if (currentEvent === "source_media_ready") {
                const sceneId = typeof data.scene_id === "string" ? data.scene_id : "";
                if (!sceneId) continue;
                const sourceMedia = asSourceMedia(data);
                if (!sourceMedia) continue;
                appendSourceMedia(sceneId, sourceMedia);
                updateSceneMetadata(sceneId, { source_proof_warning: undefined });
              } else if (currentEvent === "source_media_warning") {
                const sceneId = typeof data.scene_id === "string" ? data.scene_id : "";
                const message = typeof data.message === "string" ? data.message.trim() : "";
                if (!sceneId || !message) continue;
                updateSceneMetadata(sceneId, { source_proof_warning: message });
                pushAgentNote("qa", sceneId, message);
              } else if (currentEvent === "qa_status") {
                const qa = data as unknown as SceneQaPayload;
                if (!qa.scene_id) continue;
                updateSceneMetadata(qa.scene_id, {
                  qa_status: qa.status,
                  qa_reasons: Array.isArray(qa.reasons) ? qa.reasons : [],
                  qa_score: typeof qa.score === "number" ? qa.score : undefined,
                  qa_word_count: typeof qa.word_count === "number" ? qa.word_count : undefined,
                  status: qa.status === "FAIL" ? "qa-failed" : "generating",
                });
                const qaReason = Array.isArray(qa.reasons) && qa.reasons.length > 0 ? qa.reasons[0] : "Quality check updated.";
                pushAgentNote("qa", qa.scene_id, `QA ${qa.status}: ${qaReason}`);
              } else if (currentEvent === "qa_retry") {
                const sceneId = typeof data.scene_id === "string" ? data.scene_id : "";
                if (!sceneId) continue;
                setScenes((prev) => {
                  const existing = prev[sceneId] ?? { id: sceneId, text: "", status: "queued" };
                  return {
                    ...prev,
                    [sceneId]: {
                      ...existing,
                      status: "retrying",
                      auto_retry_count: (existing.auto_retry_count ?? 0) + 1,
                    },
                  };
                });
                pushAgentNote("qa", sceneId, "QA requested a retry for this scene.");
              } else if (currentEvent === "scene_retry_reset") {
                const sceneId = typeof data.scene_id === "string" ? data.scene_id : "";
                if (!sceneId) continue;
                fullTextBufferRef.current[sceneId] = "";
                updateSceneMetadata(sceneId, {
                  text: "",
                  imageUrl: undefined,
                  audioUrl: undefined,
                  status: "generating",
                });
              } else if (currentEvent === "scene_done") {
                const sceneId = typeof data.scene_id === "string" ? data.scene_id : "";
                if (!sceneId) continue;
                const qaStatus = typeof data.qa_status === "string" ? data.qa_status : "";
                const autoRetries = typeof data.auto_retries === "number" ? data.auto_retries : undefined;
                setScenes((prev) => {
                  const existing = prev[sceneId] ?? { id: sceneId, text: "", status: "queued" };
                  const sourceMediaCount = Array.isArray(existing.source_media) ? existing.source_media.length : 0;
                  const expectedSourceMediaCount = existing.expected_source_media_count ?? 0;
                  const nextWarning = (
                    (expectedSourceMediaCount > 0 || (existing.evidence_refs?.length ?? 0) > 0)
                    && sourceMediaCount === 0
                    && !existing.source_proof_warning
                  )
                    ? "Source proof was planned for this scene, but no resolved proof links were attached."
                    : existing.source_proof_warning;
                  return {
                    ...prev,
                    [sceneId]: {
                      ...existing,
                      status: qaStatus === "FAIL" ? "qa-failed" : "ready",
                      auto_retry_count: autoRetries,
                      source_proof_warning: nextWarning,
                    },
                  };
                });
                if (qaStatus) {
                  pushAgentNote("info", sceneId, `Scene done with QA ${qaStatus}.`);
                }
              } else if (currentEvent === "status") {
                if (typeof data.message === "string" && data.message.trim()) {
                  setGenerationStatus(data.message);
                  pushAgentNote("info", "Agent", data.message);
                }
              } else if (currentEvent === "checkpoint") {
                const checkpoint = typeof data.checkpoint === "string" ? data.checkpoint : "";
                const status = typeof data.status === "string" ? data.status : "";
                if (checkpoint && status) {
                  setGenerationStatus(`${checkpoint}: ${status}`);
                  const checkpointLabel = CHECKPOINT_LABELS[checkpoint] ?? checkpoint;
                  const normalizedStatus = status.toUpperCase();
                  pushAgentNote(
                    normalizedStatus === "FAILED" ? "error" : "checkpoint",
                    "Checkpoint",
                    `${checkpointLabel}: ${normalizedStatus}`,
                  );
                }
              } else if (currentEvent === "final_bundle_ready") {
                setGenerationStatus("");
                setIsGenerating(false);
                const traceabilityRaw = data.claim_traceability;
                if (traceabilityRaw && typeof traceabilityRaw === "object") {
                  const traceability = traceabilityRaw as {
                    claims_total?: number;
                    claims_referenced?: number;
                    evidence_total?: number;
                    evidence_referenced?: number;
                  };
                  if (typeof traceability.claims_total === "number" && typeof traceability.claims_referenced === "number") {
                    pushAgentNote(
                      "trace",
                      "Traceability",
                      typeof traceability.evidence_total === "number" && typeof traceability.evidence_referenced === "number"
                        ? `Claims covered: ${traceability.claims_referenced}/${traceability.claims_total}. Evidence linked: ${traceability.evidence_referenced}/${traceability.evidence_total}.`
                        : `Claims covered: ${traceability.claims_referenced}/${traceability.claims_total}.`,
                    );
                  }
                }
                pushAgentNote("checkpoint", "Generation", "Final bundle ready.");
                await refreshWorkflowSnapshot();
              } else if (currentEvent === "error") {
                setGenerationError(typeof data.error === "string" ? data.error : "Generation failed.");
                pushAgentNote("error", "Generation", typeof data.error === "string" ? data.error : "Generation failed.");
                setGenerationStatus("");
                setIsGenerating(false);
                await refreshWorkflowSnapshot();
              }
            } catch (error) {
              console.error("Error parsing SSE data:", error);
            }
          }
        }
      }
    } catch (error) {
      console.error("Stream error:", error);
      setGenerationError("Unable to connect to generation stream.");
      pushAgentNote("error", "Generation", "Unable to connect to generation stream.");
      setGenerationStatus("");
    } finally {
      await refreshWorkflowSnapshot();
      setIsGenerating(false);
    }
  };

  return {
    handleGenerateStream,
    handleRegenerateScene,
  };
}
