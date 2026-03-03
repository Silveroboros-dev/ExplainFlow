from typing import Any

from pydantic import BaseModel, Field


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


class ScriptPackRequest(BaseModel):
    content_signal: dict[str, Any] = Field(default_factory=dict)
    render_profile: dict[str, Any] = Field(default_factory=dict)
