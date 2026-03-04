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


class SignalExtractionRequest(BaseModel):
    input_text: str


class RegenerateSceneRequest(BaseModel):
    scene_id: str
    current_text: str
    instruction: str
    visual_mode: str = "illustration"


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


class ScriptPack(BaseModel):
    plan_id: str
    plan_summary: str
    audience_descriptor: str
    scene_count: int
    scenes: list[ScriptPackScene]


class AdvancedStreamRequest(BaseModel):
    content_signal: dict[str, Any] = Field(default_factory=dict)
    render_profile: dict[str, Any] = Field(default_factory=dict)
    script_pack: dict[str, Any] | None = None
    artifact_scope: list[ArtifactName] = Field(default_factory=list)


class ScriptPackRequest(BaseModel):
    content_signal: dict[str, Any] = Field(default_factory=dict)
    render_profile: dict[str, Any] = Field(default_factory=dict)
    artifact_scope: list[ArtifactName] = Field(default_factory=list)


class WorkflowStartRequest(BaseModel):
    source_text: str


class WorkflowArtifactLockRequest(BaseModel):
    artifact_scope: list[ArtifactName]


class WorkflowRenderLockRequest(BaseModel):
    render_profile: dict[str, Any] = Field(default_factory=dict)


class WorkflowStreamRequest(BaseModel):
    script_pack: dict[str, Any] | None = None


class CheckpointRecord(BaseModel):
    checkpoint: CheckpointName
    status: CheckpointStatus
    timestamp_utc: str
    details: dict[str, Any] = Field(default_factory=dict)


class SceneTraceRecord(BaseModel):
    scene_id: str
    scene_trace_id: str
    claim_refs: list[str] = Field(default_factory=list)
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
