from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


CheckpointName = Literal[
    "CP1_SIGNAL_READY",
    "CP2_ARTIFACTS_LOCKED",
    "CP3_RENDER_LOCKED",
    "CP4_SCRIPT_LOCKED",
    "CP5_STREAM_COMPLETE",
    "CP6_BUNDLE_FINALIZED",
]

CheckpointStatus = Literal["pending", "passed", "failed", "skipped"]

ArtifactName = Literal[
    "thumbnail",
    "story_cards",
    "storyboard",
    "voiceover",
    "social_caption",
]

EvidenceModality = Literal["text", "audio", "video", "image", "pdf_page"]
RenderStrategy = Literal["generated", "source_media", "hybrid"]

PlannerArtifactType = Literal[
    "storyboard_grid",
    "technical_infographic",
    "process_diagram",
    "comparison_one_pager",
    "slide_thumbnail",
]
PlannerLensMode = Literal["OFF", "LITE", "FULL"]
PlanningMode = Literal["sequential", "static", "micro"]
ScriptShape = Literal[
    "sequential_storyboard",
    "comparison_board",
    "one_pager_board",
    "thumbnail_focus",
    "technical_infographic",
    "process_map",
]

WorkflowPanelName = Literal["source", "profile", "signal", "script", "stream"]
WorkflowAgentAction = Literal[
    "respond",
    "open_panel",
    "extract_signal",
    "apply_render_profile",
    "confirm_signal",
    "generate_script_pack",
    "generate_stream",
]


class SignalExtractionRequest(BaseModel):
    input_text: str = ""
    source_manifest: SourceManifestSchema | None = None
    normalized_source_text: str = ""
    source_text_origin: str | None = None


class RegenerateSceneRequest(BaseModel):
    scene_id: str
    current_text: str
    instruction: str
    visual_mode: str = "illustration"


class WorkflowSceneContextRequest(BaseModel):
    scene_id: str
    title: str = ""
    text: str = ""


class WorkflowSceneRegenerateRequest(BaseModel):
    scene_id: str
    instruction: str
    current_text: str = ""
    prior_scene_context: list[WorkflowSceneContextRequest] = Field(default_factory=list)


class QuickArtifactBlockSchema(BaseModel):
    block_id: str
    label: str
    title: str
    body: str
    bullets: list[str] = Field(default_factory=list)
    visual_direction: str = ""
    image_url: str | None = None
    emphasis: Literal["hook", "core", "proof", "implication", "action"] = "core"
    claim_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    source_media: list["SourceMediaRefSchema"] = Field(default_factory=list)


class QuickReelSegmentSchema(BaseModel):
    segment_id: str
    block_id: str
    title: str
    render_mode: Literal["source_clip", "generated_image", "hybrid"]
    caption_text: str
    claim_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    primary_media: SourceMediaRefSchema | None = None
    fallback_image_url: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    timing_inferred: bool = False


class QuickReelSchema(BaseModel):
    reel_id: str
    title: str
    summary: str
    segments: list[QuickReelSegmentSchema] = Field(default_factory=list)


class QuickVideoSegmentSchema(BaseModel):
    segment_id: str
    block_id: str
    title: str
    caption_text: str
    voiceover_url: str | None = None
    visual_url: str | None = None
    source_video_url: str | None = None
    source_start_ms: int | None = None
    source_end_ms: int | None = None
    duration_ms: int | None = None
    render_mode: Literal["image_only", "image_plus_clip", "clip_only"]


class QuickVideoSchema(BaseModel):
    video_id: str
    status: Literal["ready"] = "ready"
    video_url: str
    duration_ms: int | None = None
    segments: list[QuickVideoSegmentSchema] = Field(default_factory=list)


class QuickArtifactSchema(BaseModel):
    artifact_id: str
    title: str
    subtitle: str
    summary: str
    visual_style: str
    hero_direction: str
    hero_image_url: str | None = None
    reel: QuickReelSchema | None = None
    video: QuickVideoSchema | None = None
    blocks: list[QuickArtifactBlockSchema] = Field(default_factory=list)


class QuickArtifactRequest(BaseModel):
    topic: str
    audience: str
    tone: str = ""
    visual_mode: str = "illustration"
    source_text: str = ""
    source_manifest: SourceManifestSchema | None = None
    normalized_source_text: str = ""
    source_text_origin: str | None = None
    content_signal: dict[str, Any] = Field(default_factory=dict)


class QuickSourceIndexRequest(BaseModel):
    source_text: str = ""
    source_manifest: SourceManifestSchema | None = None
    normalized_source_text: str = ""
    source_text_origin: str | None = None


class QuickReelRequest(BaseModel):
    artifact: QuickArtifactSchema | dict[str, Any]
    source_manifest: SourceManifestSchema | None = None
    content_signal: dict[str, Any] = Field(default_factory=dict)


class QuickVideoRequest(BaseModel):
    artifact: QuickArtifactSchema | dict[str, Any]
    source_manifest: SourceManifestSchema | None = None
    content_signal: dict[str, Any] = Field(default_factory=dict)


class QuickBlockOverrideRequest(BaseModel):
    topic: str
    audience: str
    tone: str = ""
    visual_mode: str = "illustration"
    artifact: QuickArtifactSchema | dict[str, Any]
    source_manifest: SourceManifestSchema | None = None
    normalized_source_text: str = ""
    source_text_origin: str | None = None
    content_signal: dict[str, Any] = Field(default_factory=dict)
    block_id: str
    instruction: str


class QuickArtifactOverrideRequest(BaseModel):
    topic: str
    audience: str
    tone: str = ""
    visual_mode: str = "illustration"
    artifact: QuickArtifactSchema | dict[str, Any]
    source_manifest: SourceManifestSchema | None = None
    normalized_source_text: str = ""
    source_text_origin: str | None = None
    content_signal: dict[str, Any] = Field(default_factory=dict)
    instruction: str
    anchor_block_id: str | None = None


class SourceAssetSchema(BaseModel):
    asset_id: str
    modality: EvidenceModality
    uri: str | None = None
    mime_type: str | None = None
    title: str | None = None
    duration_ms: int | None = None
    page_index: int | None = None
    width: int | None = None
    height: int | None = None
    transcript_text: str | None = None
    ocr_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceManifestSchema(BaseModel):
    assets: list[SourceAssetSchema] = Field(default_factory=list)


class EvidenceRefSchema(BaseModel):
    evidence_id: str
    asset_id: str
    modality: EvidenceModality
    quote_text: str | None = None
    transcript_text: str | None = None
    visual_context: str | None = None
    speaker: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    timing_inferred: bool = False
    page_index: int | None = None
    bbox_norm: list[float] | None = None
    confidence: float | None = None


class SourceMediaRefSchema(BaseModel):
    asset_id: str
    modality: Literal["audio", "video", "image", "pdf_page"]
    usage: Literal["background", "hero", "proof_clip", "region_crop", "callout"] = "proof_clip"
    claim_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    start_ms: int | None = None
    end_ms: int | None = None
    timing_inferred: bool = False
    page_index: int | None = None
    bbox_norm: list[float] | None = None
    loop: bool = False
    muted: bool = True
    label: str | None = None
    quote_text: str | None = None
    visual_context: str | None = None


class SceneModuleSchema(BaseModel):
    module_id: str
    label: str
    purpose: str
    content_type: str = "support_panel"
    claim_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    source_media: list[SourceMediaRefSchema] = Field(default_factory=list)
    placement_hint: str | None = None


class ScenePlanSchema(BaseModel):
    scene_id: str = Field(description="A unique identifier for the scene, e.g., 'scene-1'")
    title: str = Field(description="The title of the scene")
    narration_focus: str = Field(description="Instructions on what the narration should focus on for this scene")
    visual_prompt: str = Field(
        description=(
            "A detailed image prompt for the scene visual. It must specify subject, style, "
            "composition, and color direction. Keep image text-free."
        )
    )
    claim_refs: list[str] = Field(
        default_factory=list,
        description="List of claim IDs (e.g., 'c1', 'c2') that this scene covers",
    )
    scene_mode: Literal["sequential", "static"] = "sequential"
    scene_role: str | None = None
    composition_goal: str | None = None
    layout_template: str | None = None
    focal_subject: str | None = None
    visual_hierarchy: list[str] = Field(default_factory=list)
    modules: list[SceneModuleSchema] = Field(default_factory=list)
    comparison_axes: list[str] = Field(default_factory=list)
    flow_steps: list[str] = Field(default_factory=list)
    crop_safe_regions: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    source_media: list[SourceMediaRefSchema] = Field(default_factory=list)
    render_strategy: RenderStrategy = "generated"


class OutlineSchema(BaseModel):
    scenes: list[ScenePlanSchema]


class ScriptPackScene(BaseModel):
    scene_id: str
    title: str
    scene_goal: str
    narration_focus: str
    visual_prompt: str
    claim_refs: list[str] = Field(default_factory=list)
    continuity_refs: list[str] = Field(default_factory=list)
    acceptance_checks: list[str] = Field(default_factory=list)
    scene_mode: Literal["sequential", "static"] = "sequential"
    scene_role: str | None = None
    composition_goal: str | None = None
    layout_template: str | None = None
    focal_subject: str | None = None
    visual_hierarchy: list[str] = Field(default_factory=list)
    modules: list[SceneModuleSchema] = Field(default_factory=list)
    comparison_axes: list[str] = Field(default_factory=list)
    flow_steps: list[str] = Field(default_factory=list)
    crop_safe_regions: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    source_media: list[SourceMediaRefSchema] = Field(default_factory=list)
    render_strategy: RenderStrategy = "generated"


class ScriptPack(BaseModel):
    plan_id: str
    plan_summary: str
    audience_descriptor: str
    scene_count: int
    artifact_type: str = "storyboard_grid"
    planning_mode: PlanningMode = "sequential"
    script_shape: str = "sequential_storyboard"
    scene_budget_reason: str | None = None
    salience_mode: PlannerLensMode | None = None
    forward_pull_mode: PlannerLensMode | None = None
    scenes: list[ScriptPackScene]


class AdvancedStreamRequest(BaseModel):
    source_text: str = ""
    source_manifest: SourceManifestSchema | None = None
    normalized_source_text: str = ""
    source_text_origin: str | None = None
    content_signal: dict[str, Any] = Field(default_factory=dict)
    render_profile: dict[str, Any] = Field(default_factory=dict)
    script_pack: dict[str, Any] | None = None
    script_pack_source_media_enriched: bool = False
    artifact_scope: list[ArtifactName] = Field(default_factory=list)


class ScriptPackRequest(BaseModel):
    source_text: str = ""
    source_manifest: SourceManifestSchema | None = None
    normalized_source_text: str = ""
    source_text_origin: str | None = None
    content_signal: dict[str, Any] = Field(default_factory=dict)
    render_profile: dict[str, Any] = Field(default_factory=dict)
    artifact_scope: list[ArtifactName] = Field(default_factory=list)


class WorkflowStartRequest(BaseModel):
    source_text: str = ""
    source_manifest: SourceManifestSchema | None = None
    normalized_source_text: str = ""
    source_text_origin: str | None = None


class WorkflowArtifactLockRequest(BaseModel):
    artifact_scope: list[ArtifactName]


class WorkflowRenderLockRequest(BaseModel):
    render_profile: dict[str, Any] = Field(default_factory=dict)


class WorkflowProfileApplyRequest(BaseModel):
    artifact_scope: list[ArtifactName]
    render_profile: dict[str, Any] = Field(default_factory=dict)


class WorkflowStreamRequest(BaseModel):
    script_pack: dict[str, Any] | None = None


class FinalBundleSceneAsset(BaseModel):
    scene_id: str
    title: str | None = None
    text: str = ""
    overlay_text: str | None = None
    image_url: str | None = None
    audio_url: str | None = None


class FinalBundleExportRequest(BaseModel):
    topic: str = ""
    scenes: list[FinalBundleSceneAsset] = Field(default_factory=list)


class AdvancedVideoExportRequest(BaseModel):
    topic: str = ""
    scenes: list[FinalBundleSceneAsset] = Field(default_factory=list)


class FinalBundleUpscaleSceneRequest(BaseModel):
    scene_id: str
    image_url: str | None = None


class FinalBundleUpscaleRequest(BaseModel):
    scenes: list[FinalBundleUpscaleSceneRequest] = Field(default_factory=list)
    scale_factor: Literal[2, 4] = 2


class PlannerQaSummary(BaseModel):
    mode: Literal["direct", "repaired", "replanned"]
    summary: str
    initial_hard_issue_count: int = 0
    initial_warning_count: int = 0
    final_warning_count: int = 0
    repair_applied: bool = False
    replan_attempted: bool = False
    details: list[str] = Field(default_factory=list)


class CheckpointRecord(BaseModel):
    checkpoint: CheckpointName
    status: CheckpointStatus
    timestamp_utc: str
    details: dict[str, Any] = Field(default_factory=dict)


class SceneTraceRecord(BaseModel):
    scene_id: str
    scene_trace_id: str
    claim_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    render_strategy: RenderStrategy | None = None
    media_asset_ids: list[str] = Field(default_factory=list)
    qa_history: list[dict[str, Any]] = Field(default_factory=list)
    retries_used: int = 0
    word_count: int = 0


class TraceEnvelope(BaseModel):
    trace_id: str
    run_id: str
    flow: str
    started_at_utc: str
    artifact_scope: list[ArtifactName] = Field(default_factory=list)
    checkpoints: list[CheckpointRecord] = Field(default_factory=list)
    scenes: list[SceneTraceRecord] = Field(default_factory=list)


class WorkflowAgentChatTurn(BaseModel):
    role: Literal["user", "agent", "system"]
    text: str


class WorkflowAgentChatContext(BaseModel):
    workflow_id: str | None = None
    active_panel: WorkflowPanelName | None = None
    source_text: str = ""
    source_manifest: SourceManifestSchema | None = None
    normalized_source_text: str = ""
    source_text_origin: str | None = None
    render_profile: dict[str, Any] = Field(default_factory=dict)
    artifact_scope: list[ArtifactName] = Field(default_factory=list)
    script_presentation_mode: Literal["auto", "review"] = "auto"


class WorkflowAgentChatRequest(BaseModel):
    message: str
    context: WorkflowAgentChatContext = Field(default_factory=WorkflowAgentChatContext)
    conversation: list[WorkflowAgentChatTurn] = Field(default_factory=list)


class WorkflowAgentUiDirective(BaseModel):
    active_panel: WorkflowPanelName | None = None
    start_stream: bool = False


class WorkflowAgentChatResponse(BaseModel):
    status: Literal["success", "error"] = "success"
    assistant_message: str
    selected_action: WorkflowAgentAction = "respond"
    requires_confirmation: bool = False
    workflow_id: str | None = None
    workflow: dict[str, Any] | None = None
    content_signal: dict[str, Any] | None = None
    script_pack: dict[str, Any] | None = None
    planner_qa_summary: PlannerQaSummary | None = None
    ui: WorkflowAgentUiDirective = Field(default_factory=WorkflowAgentUiDirective)
    message: str | None = None
