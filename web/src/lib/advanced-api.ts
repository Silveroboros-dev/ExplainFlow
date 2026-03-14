import {
  asUploadedSourceAsset,
  createApiRequestError,
  type AdvancedPanel,
  type WorkflowSceneContext,
  type AdvancedSourceManifest,
  type ExtractedSignal,
  type ScriptPackPayload,
  type UploadedSourceAsset,
  type WorkflowAgentApiTurn,
  type WorkflowAgentChatResponse,
  type WorkflowSnapshot,
} from "@/lib/advanced";

export type JsonApiResult<T> = {
  ok: boolean;
  statusCode: number;
  data: T;
};

export type AdvancedWorkflowStartPayload = {
  source_text: string;
  source_manifest?: AdvancedSourceManifest;
};

export type AdvancedWorkflowStartResponse = {
  workflow_id?: string;
  workflow?: WorkflowSnapshot;
  status?: string;
  detail?: string;
  message?: string;
};

export type AdvancedWorkflowExtractResponse = {
  workflow_id?: string;
  workflow?: WorkflowSnapshot;
  status?: string;
  content_signal?: ExtractedSignal | null;
  message?: string;
};

export type AdvancedWorkflowStatusResponse = {
  workflow?: WorkflowSnapshot;
  status?: string;
  detail?: string;
  message?: string;
};

export type AdvancedWorkflowScriptPackResponse = AdvancedWorkflowStatusResponse & {
  script_pack?: ScriptPackPayload | null;
  planner_qa_summary?: unknown;
};

export type AdvancedSourceUploadResult = {
  ok: boolean;
  statusCode: number;
  status?: string;
  detail?: string;
  message?: string;
  assets: UploadedSourceAsset[];
};

export type AdvancedUpscalePayload = {
  scale_factor: number;
  scenes: Array<{
    scene_id: string;
    image_url?: string;
  }>;
};

export type AdvancedUpscaleResponse = {
  status?: string;
  scenes?: unknown[];
  detail?: string;
  message?: string;
};

export type AdvancedAgentChatPayload = {
  message: string;
  context: {
    workflow_id: string | null;
    active_panel: AdvancedPanel;
    source_text: string;
    source_manifest?: AdvancedSourceManifest;
    render_profile: unknown;
    artifact_scope: string[];
    script_presentation_mode: "review" | "auto";
  };
  conversation: WorkflowAgentApiTurn[];
};

export type AdvancedWorkflowSceneRegeneratePayload = {
  scene_id: string;
  instruction: string;
  current_text?: string;
  prior_scene_context?: WorkflowSceneContext[];
};

export type AdvancedWorkflowSceneRegenerateResponse = {
  workflow_id?: string;
  status?: string;
  scene_id?: string;
  text?: string;
  imageUrl?: string;
  audioUrl?: string;
  qa_status?: "PASS" | "WARN" | "FAIL";
  qa_reasons?: string[];
  qa_score?: number;
  qa_word_count?: number;
  auto_retries?: number;
  detail?: string;
  message?: string;
};

const bypassHeaders = (): Record<string, string> => {
  const key = process.env.NEXT_PUBLIC_RATE_LIMIT_BYPASS_KEY;
  return key ? { "X-RateLimit-Bypass": key } : {};
};

const requestJson = async <T>(url: string, init?: RequestInit): Promise<JsonApiResult<T>> => {
  const merged = {
    ...init,
    headers: { ...bypassHeaders(), ...init?.headers },
  };
  const response = await fetch(url, merged);
  const data = await response.json().catch(() => ({} as T));
  return {
    ok: response.ok,
    statusCode: response.status,
    data,
  };
};

const postJson = async <T>(url: string, body?: unknown): Promise<JsonApiResult<T>> => (
  requestJson<T>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
);

export const uploadAdvancedSourceAssets = async (
  apiBase: string,
  formData: FormData,
): Promise<AdvancedSourceUploadResult> => {
  const response = await requestJson<{
    status?: string;
    assets?: unknown[];
    detail?: string;
    message?: string;
  }>(`${apiBase}/api/source-assets/upload`, {
    method: "POST",
    body: formData,
  });

  return {
    ok: response.ok,
    statusCode: response.statusCode,
    status: typeof response.data?.status === "string" ? response.data.status : undefined,
    detail: typeof response.data?.detail === "string" ? response.data.detail : undefined,
    message: typeof response.data?.message === "string" ? response.data.message : undefined,
    assets: Array.isArray(response.data?.assets)
      ? response.data.assets
        .map(asUploadedSourceAsset)
        .filter((asset): asset is UploadedSourceAsset => asset !== null)
      : [],
  };
};

export const startAdvancedWorkflow = async (
  apiBase: string,
  payload: AdvancedWorkflowStartPayload,
): Promise<JsonApiResult<AdvancedWorkflowStartResponse>> => (
  postJson<AdvancedWorkflowStartResponse>(`${apiBase}/api/workflow/start`, payload)
);

export const extractAdvancedWorkflowSignal = async (
  apiBase: string,
  workflowId: string,
  payload: AdvancedWorkflowStartPayload,
): Promise<JsonApiResult<AdvancedWorkflowExtractResponse>> => (
  postJson<AdvancedWorkflowExtractResponse>(`${apiBase}/api/workflow/${workflowId}/extract-signal`, payload)
);

export const fetchAdvancedWorkflowSnapshot = async (
  apiBase: string,
  workflowId: string,
): Promise<WorkflowSnapshot> => {
  const response = await requestJson<WorkflowSnapshot>(`${apiBase}/api/workflow/${workflowId}`);
  if (!response.ok) {
    throw createApiRequestError(response.data, "Unable to load workflow state.", response.statusCode);
  }
  return response.data;
};

export const fetchAdvancedWorkflowSignal = async (
  apiBase: string,
  workflowId: string,
): Promise<ExtractedSignal> => {
  const response = await requestJson<{
    status?: string;
    content_signal?: ExtractedSignal;
    detail?: string;
    message?: string;
  }>(`${apiBase}/api/workflow/${workflowId}/content-signal`);
  if (!response.ok || response.data?.status !== "success" || !response.data?.content_signal) {
    throw createApiRequestError(response.data, "Unable to load extracted signal.", response.statusCode);
  }
  return response.data.content_signal;
};

export const fetchAdvancedWorkflowScriptPack = async (
  apiBase: string,
  workflowId: string,
): Promise<ScriptPackPayload> => {
  const response = await requestJson<{
    status?: string;
    script_pack?: ScriptPackPayload;
    detail?: string;
    message?: string;
  }>(`${apiBase}/api/workflow/${workflowId}/script-pack`);
  if (!response.ok || response.data?.status !== "success" || !response.data?.script_pack) {
    throw createApiRequestError(response.data, "Unable to load script pack.", response.statusCode);
  }
  return response.data.script_pack;
};

export const lockAdvancedWorkflowArtifacts = async (
  apiBase: string,
  workflowId: string,
  artifactScope: string[],
): Promise<JsonApiResult<AdvancedWorkflowStatusResponse>> => (
  postJson<AdvancedWorkflowStatusResponse>(`${apiBase}/api/workflow/${workflowId}/lock-artifacts`, {
    artifact_scope: artifactScope,
  })
);

export const lockAdvancedWorkflowRender = async (
  apiBase: string,
  workflowId: string,
  renderProfile: unknown,
): Promise<JsonApiResult<AdvancedWorkflowStatusResponse>> => (
  postJson<AdvancedWorkflowStatusResponse>(`${apiBase}/api/workflow/${workflowId}/lock-render`, {
    render_profile: renderProfile,
  })
);

export const applyAdvancedWorkflowProfile = async (
  apiBase: string,
  workflowId: string,
  artifactScope: string[],
  renderProfile: unknown,
): Promise<JsonApiResult<AdvancedWorkflowStatusResponse>> => (
  postJson<AdvancedWorkflowStatusResponse>(`${apiBase}/api/workflow/${workflowId}/apply-profile`, {
    artifact_scope: artifactScope,
    render_profile: renderProfile,
  })
);

export const generateAdvancedWorkflowScriptPack = async (
  apiBase: string,
  workflowId: string,
): Promise<JsonApiResult<AdvancedWorkflowScriptPackResponse>> => (
  postJson<AdvancedWorkflowScriptPackResponse>(`${apiBase}/api/workflow/${workflowId}/generate-script-pack`)
);

export const upscaleAdvancedFinalBundle = async (
  apiBase: string,
  payload: AdvancedUpscalePayload,
): Promise<JsonApiResult<AdvancedUpscaleResponse>> => (
  postJson<AdvancedUpscaleResponse>(`${apiBase}/api/final-bundle/upscale`, payload)
);

export const openAdvancedWorkflowStream = async (
  apiBase: string,
  workflowId: string,
  scriptPack?: ScriptPackPayload | null,
): Promise<Response> => (
  fetch(`${apiBase}/api/workflow/${workflowId}/generate-stream`, {
    method: "POST",
    headers: { ...bypassHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({
      script_pack: scriptPack ?? undefined,
    }),
  })
);

export const regenerateAdvancedWorkflowScene = async (
  apiBase: string,
  workflowId: string,
  payload: AdvancedWorkflowSceneRegeneratePayload,
): Promise<JsonApiResult<AdvancedWorkflowSceneRegenerateResponse>> => (
  postJson<AdvancedWorkflowSceneRegenerateResponse>(
    `${apiBase}/api/workflow/${workflowId}/regenerate-scene`,
    payload,
  )
);

export const submitAdvancedWorkflowChat = async (
  apiBase: string,
  payload: AdvancedAgentChatPayload,
): Promise<JsonApiResult<WorkflowAgentChatResponse>> => (
  postJson<WorkflowAgentChatResponse>(`${apiBase}/api/workflow/agent/chat`, payload)
);
