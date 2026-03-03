/**
 * TypeScript types matching:
 * - content_signal.schema.json
 * - render_profile.schema.json
 * - scene_plan.schema.json
 */

export type ContentSignalVersion = string; // ^v[0-9]+\.[0-9]+$
export type ClaimId = string; // ^c[0-9]+$
export type ConceptId = string; // ^k[0-9]+$
export type VisualCandidateId = string; // ^v[0-9]+$
export type BeatId = string; // ^b[0-9]+$
export type HexColor = string; // ^#([A-Fa-f0-9]{6})$
export type Hashtag = string; // ^#[A-Za-z0-9_]+$

export interface ContentSignalSource {
  source_id: string;
  source_type: "prompt" | "document" | "url" | "article" | "transcript" | "slides";
  language: string;
  title?: string;
  input_length_tokens: number;
  source_hash?: string;
}

export interface ContentSignalThesis {
  one_liner: string;
  expanded_summary: string;
}

export interface ContentSignalEvidenceSnippet {
  text: string;
  citation?: string;
}

export interface ContentSignalKeyClaim {
  claim_id: ClaimId;
  claim_text: string;
  supporting_points: string[];
  evidence_snippets?: ContentSignalEvidenceSnippet[];
  confidence: number;
}

export interface ContentSignalConcept {
  concept_id: ConceptId;
  label: string;
  definition: string;
  importance: number;
}

export type VisualRecommendedStructure =
  | "flowchart"
  | "timeline"
  | "comparison"
  | "matrix"
  | "process"
  | "architecture"
  | "concept_map"
  | "table";

export interface ContentSignalVisualCandidate {
  candidate_id: VisualCandidateId;
  purpose: string;
  recommended_structure: VisualRecommendedStructure;
  data_points?: string[];
  claim_refs: ClaimId[];
}

export type NarrativeBeatRole =
  | "hook"
  | "context"
  | "problem"
  | "mechanism"
  | "example"
  | "takeaway"
  | "cta";

export interface ContentSignalNarrativeBeat {
  beat_id: BeatId;
  role: NarrativeBeatRole;
  message: string;
  claim_refs: ClaimId[];
}

export interface ContentSignalQuality {
  coverage_score: number;
  ambiguity_score: number;
  hallucination_risk: number;
}

export interface ContentSignal {
  version: ContentSignalVersion;
  source: ContentSignalSource;
  thesis: ContentSignalThesis;
  key_claims: ContentSignalKeyClaim[];
  concepts: ContentSignalConcept[];
  visual_candidates: ContentSignalVisualCandidate[];
  narrative_beats: ContentSignalNarrativeBeat[];
  open_questions?: string[];
  signal_quality: ContentSignalQuality;
}

export type RenderGoal = "teach" | "persuade" | "summarize" | "pitch";
export type AudienceLevel = "beginner" | "intermediate" | "expert";
export type TasteBar = "standard" | "high" | "very_high";
export type VisualMode = "diagram" | "illustration" | "hybrid";
export type ArtifactType =
  | "storyboard_grid"
  | "technical_infographic"
  | "process_diagram"
  | "comparison_one_pager"
  | "slide_thumbnail";
export type Fidelity = "low" | "medium" | "high";
export type Density = "simple" | "standard" | "detailed";
export type PaletteMode = "auto" | "brand" | "custom";
export type AspectRatio = "16:9" | "9:16" | "1:1" | "4:5";

export interface RenderStyle {
  descriptors: string[];
  reference_hint?: string;
  forbidden_styles?: string[];
}

export interface AutoRenderPalette {
  mode: "auto";
  primary?: HexColor;
  secondary?: HexColor;
  accent?: HexColor;
  background?: HexColor;
}

export interface FixedRenderPalette {
  mode: "brand" | "custom";
  primary: HexColor;
  secondary: HexColor;
  accent: HexColor;
  background: HexColor;
}

export type RenderPalette = AutoRenderPalette | FixedRenderPalette;

export interface RenderOutputControls {
  scene_count: number;
  target_duration_sec: number;
  aspect_ratio: AspectRatio;
}

export interface RenderVoiceover {
  enabled: boolean;
  voice_style: string;
  pace_wpm: number;
}

export interface RenderAccessibility {
  high_contrast?: boolean;
  max_on_screen_words?: number;
}

export interface RenderAudience {
  level: AudienceLevel;
  persona: string;
  domain_context?: string;
  taste_bar: TasteBar;
  must_include?: string[];
  must_avoid?: string[];
}

export interface RenderProfile {
  profile_id: string;
  profile_name?: string;
  goal: RenderGoal;
  audience: RenderAudience;
  visual_mode: VisualMode;
  artifact_type?: ArtifactType;
  style: RenderStyle;
  fidelity: Fidelity;
  density: Density;
  palette: RenderPalette;
  output_controls: RenderOutputControls;
  voiceover: RenderVoiceover;
  accessibility?: RenderAccessibility;
}

export interface ScenePlanContentSignalRef {
  source_id: string;
  version: ContentSignalVersion;
}

export interface ScenePlanRenderProfileRef {
  profile_id: string;
}

export interface ScenePlanSummary {
  title: string;
  one_sentence_promise: string;
}

export type SceneVisualKind =
  | "flowchart"
  | "timeline"
  | "comparison"
  | "matrix"
  | "process"
  | "architecture"
  | "concept_map"
  | "illustration";

export interface SceneVisualSpec {
  visual_kind: SceneVisualKind;
  prompt: string;
  negative_prompt?: string;
  key_elements: string[];
  label_text?: string[];
}

export interface SceneAudioSpec {
  voice_style: string;
  pace_wpm: number;
  emphasis_words?: string[];
}

export interface SceneCaptionSpec {
  primary_caption: string;
  hashtags: Hashtag[];
  cta?: string;
}

export interface SceneTiming {
  start_sec: number;
  duration_sec: number;
}

export interface ScenePlanScene {
  scene_id: number;
  beat_ref: BeatId;
  title: string;
  objective: string;
  claim_refs: ClaimId[];
  narration_script: string;
  on_screen_text: string[];
  visual_spec: SceneVisualSpec;
  audio_spec: SceneAudioSpec;
  caption_spec: SceneCaptionSpec;
  timing: SceneTiming;
  acceptance_checks: string[];
}

export interface ScenePlanContinuityChecks {
  terminology_consistent: boolean;
  style_consistent: boolean;
  palette_consistent: boolean;
  notes?: string[];
}

export interface SceneManifestItem {
  scene_id: number;
  image_uri: string;
  audio_uri: string;
}

export interface ScenePlanFinalBundle {
  transcript: string;
  scene_manifest: SceneManifestItem[];
  social_pack: string[];
}

export interface ScenePlan {
  plan_id: string;
  content_signal_ref: ScenePlanContentSignalRef;
  render_profile_ref: ScenePlanRenderProfileRef;
  plan_summary: ScenePlanSummary;
  scenes: ScenePlanScene[];
  continuity_checks: ScenePlanContinuityChecks;
  final_bundle: ScenePlanFinalBundle;
}
