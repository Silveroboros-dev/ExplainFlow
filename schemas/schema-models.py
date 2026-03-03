"""Pydantic v2 models matching the JSON schemas in this folder."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


VersionStr = Annotated[str, StringConstraints(pattern=r"^v[0-9]+\.[0-9]+$")]
ClaimId = Annotated[str, StringConstraints(pattern=r"^c[0-9]+$")]
ConceptId = Annotated[str, StringConstraints(pattern=r"^k[0-9]+$")]
VisualCandidateId = Annotated[str, StringConstraints(pattern=r"^v[0-9]+$")]
BeatId = Annotated[str, StringConstraints(pattern=r"^b[0-9]+$")]
HexColor = Annotated[str, StringConstraints(pattern=r"^#([A-Fa-f0-9]{6})$")]
Hashtag = Annotated[str, StringConstraints(pattern=r"^#[A-Za-z0-9_]+$")]


class ContentSignalSource(StrictModel):
    source_id: Annotated[str, StringConstraints(min_length=1)]
    source_type: Literal["prompt", "document", "url", "article", "transcript", "slides"]
    language: Annotated[str, StringConstraints(min_length=2, max_length=10)]
    title: str | None = None
    input_length_tokens: int = Field(ge=1)
    source_hash: str | None = None


class ContentSignalThesis(StrictModel):
    one_liner: Annotated[str, StringConstraints(min_length=10, max_length=220)]
    expanded_summary: Annotated[str, StringConstraints(min_length=40)]


class ContentSignalEvidenceSnippet(StrictModel):
    text: Annotated[str, StringConstraints(min_length=4)]
    citation: str | None = None


class ContentSignalKeyClaim(StrictModel):
    claim_id: ClaimId
    claim_text: Annotated[str, StringConstraints(min_length=8)]
    supporting_points: list[Annotated[str, StringConstraints(min_length=4)]] = Field(min_length=1)
    evidence_snippets: list[ContentSignalEvidenceSnippet] | None = None
    confidence: float = Field(ge=0, le=1)


class ContentSignalConcept(StrictModel):
    concept_id: ConceptId
    label: Annotated[str, StringConstraints(min_length=2)]
    definition: Annotated[str, StringConstraints(min_length=6)]
    importance: int = Field(ge=1, le=5)


class ContentSignalVisualCandidate(StrictModel):
    candidate_id: VisualCandidateId
    purpose: Annotated[str, StringConstraints(min_length=4)]
    recommended_structure: Literal[
        "flowchart",
        "timeline",
        "comparison",
        "matrix",
        "process",
        "architecture",
        "concept_map",
        "table",
    ]
    data_points: list[Annotated[str, StringConstraints(min_length=2)]] | None = None
    claim_refs: list[ClaimId] = Field(min_length=1)


class ContentSignalNarrativeBeat(StrictModel):
    beat_id: BeatId
    role: Literal["hook", "context", "problem", "mechanism", "example", "takeaway", "cta"]
    message: Annotated[str, StringConstraints(min_length=8)]
    claim_refs: list[ClaimId]


class ContentSignalQuality(StrictModel):
    coverage_score: float = Field(ge=0, le=1)
    ambiguity_score: float = Field(ge=0, le=1)
    hallucination_risk: float = Field(ge=0, le=1)


class ContentSignal(StrictModel):
    version: VersionStr
    source: ContentSignalSource
    thesis: ContentSignalThesis
    key_claims: list[ContentSignalKeyClaim] = Field(min_length=1)
    concepts: list[ContentSignalConcept] = Field(min_length=1)
    visual_candidates: list[ContentSignalVisualCandidate] = Field(min_length=1)
    narrative_beats: list[ContentSignalNarrativeBeat] = Field(min_length=3, max_length=8)
    open_questions: list[str] | None = None
    signal_quality: ContentSignalQuality


class RenderStyle(StrictModel):
    descriptors: list[Annotated[str, StringConstraints(min_length=2, max_length=30)]] = Field(
        min_length=1, max_length=5
    )
    reference_hint: str | None = None
    forbidden_styles: list[Annotated[str, StringConstraints(min_length=2)]] | None = None


class RenderPalette(StrictModel):
    mode: Literal["auto", "brand", "custom"]
    primary: HexColor | None = None
    secondary: HexColor | None = None
    accent: HexColor | None = None
    background: HexColor | None = None

    @model_validator(mode="after")
    def validate_palette_colors(self) -> "RenderPalette":
        if self.mode in {"brand", "custom"}:
            missing = [
                name
                for name in ("primary", "secondary", "accent", "background")
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(
                    "palette colors are required for mode "
                    f"{self.mode}: missing {', '.join(missing)}"
                )
        return self


class RenderOutputControls(StrictModel):
    scene_count: int = Field(ge=3, le=8)
    target_duration_sec: int = Field(ge=30, le=300)
    aspect_ratio: Literal["16:9", "9:16", "1:1", "4:5"]


class RenderVoiceover(StrictModel):
    enabled: bool
    voice_style: Annotated[str, StringConstraints(min_length=2)]
    pace_wpm: int = Field(ge=90, le=190)


class RenderAccessibility(StrictModel):
    high_contrast: bool | None = None
    max_on_screen_words: int | None = Field(default=None, ge=4, le=30)


class RenderAudience(StrictModel):
    level: Literal["beginner", "intermediate", "expert"]
    persona: Annotated[str, StringConstraints(min_length=2, max_length=80)]
    domain_context: Annotated[str, StringConstraints(min_length=2, max_length=120)] | None = None
    taste_bar: Literal["standard", "high", "very_high"]
    must_include: list[Annotated[str, StringConstraints(min_length=3)]] | None = Field(
        default=None, max_length=8
    )
    must_avoid: list[Annotated[str, StringConstraints(min_length=3)]] | None = Field(
        default=None, max_length=8
    )


class RenderProfile(StrictModel):
    profile_id: Annotated[str, StringConstraints(min_length=1)]
    profile_name: str | None = None
    goal: Literal["teach", "persuade", "summarize", "pitch"]
    audience: RenderAudience
    visual_mode: Literal["diagram", "illustration", "hybrid"]
    artifact_type: Literal[
        "storyboard_grid",
        "technical_infographic",
        "process_diagram",
        "comparison_one_pager",
        "slide_thumbnail",
    ] | None = None
    style: RenderStyle
    fidelity: Literal["low", "medium", "high"]
    density: Literal["simple", "standard", "detailed"]
    palette: RenderPalette
    output_controls: RenderOutputControls
    voiceover: RenderVoiceover
    accessibility: RenderAccessibility | None = None


class ScenePlanContentSignalRef(StrictModel):
    source_id: Annotated[str, StringConstraints(min_length=1)]
    version: VersionStr


class ScenePlanRenderProfileRef(StrictModel):
    profile_id: Annotated[str, StringConstraints(min_length=1)]


class ScenePlanSummary(StrictModel):
    title: Annotated[str, StringConstraints(min_length=4)]
    one_sentence_promise: Annotated[str, StringConstraints(min_length=10)]


class SceneVisualSpec(StrictModel):
    visual_kind: Literal[
        "flowchart",
        "timeline",
        "comparison",
        "matrix",
        "process",
        "architecture",
        "concept_map",
        "illustration",
    ]
    prompt: Annotated[str, StringConstraints(min_length=12)]
    negative_prompt: str | None = None
    key_elements: list[Annotated[str, StringConstraints(min_length=2)]] = Field(min_length=1)
    label_text: list[str] | None = None


class SceneAudioSpec(StrictModel):
    voice_style: Annotated[str, StringConstraints(min_length=2)]
    pace_wpm: int = Field(ge=90, le=190)
    emphasis_words: list[Annotated[str, StringConstraints(min_length=2)]] | None = None


class SceneCaptionSpec(StrictModel):
    primary_caption: Annotated[str, StringConstraints(min_length=10)]
    hashtags: list[Hashtag] = Field(min_length=1)
    cta: str | None = None


class SceneTiming(StrictModel):
    start_sec: float = Field(ge=0)
    duration_sec: float = Field(gt=0)


class ScenePlanScene(StrictModel):
    scene_id: int = Field(ge=1)
    beat_ref: BeatId
    title: Annotated[str, StringConstraints(min_length=3)]
    objective: Annotated[str, StringConstraints(min_length=8)]
    claim_refs: list[ClaimId] = Field(min_length=1)
    narration_script: Annotated[str, StringConstraints(min_length=20)]
    on_screen_text: list[Annotated[str, StringConstraints(min_length=1)]]
    visual_spec: SceneVisualSpec
    audio_spec: SceneAudioSpec
    caption_spec: SceneCaptionSpec
    timing: SceneTiming
    acceptance_checks: list[Annotated[str, StringConstraints(min_length=4)]] = Field(min_length=1)


class ScenePlanContinuityChecks(StrictModel):
    terminology_consistent: bool
    style_consistent: bool
    palette_consistent: bool
    notes: list[str] | None = None


class SceneManifestItem(StrictModel):
    scene_id: int = Field(ge=1)
    image_uri: Annotated[str, StringConstraints(min_length=1)]
    audio_uri: Annotated[str, StringConstraints(min_length=1)]


class ScenePlanFinalBundle(StrictModel):
    transcript: Annotated[str, StringConstraints(min_length=20)]
    scene_manifest: list[SceneManifestItem] = Field(min_length=1)
    social_pack: list[Annotated[str, StringConstraints(min_length=10)]]


class ScenePlan(StrictModel):
    plan_id: Annotated[str, StringConstraints(min_length=1)]
    content_signal_ref: ScenePlanContentSignalRef
    render_profile_ref: ScenePlanRenderProfileRef
    plan_summary: ScenePlanSummary
    scenes: list[ScenePlanScene] = Field(min_length=3, max_length=8)
    continuity_checks: ScenePlanContinuityChecks
    final_bundle: ScenePlanFinalBundle
