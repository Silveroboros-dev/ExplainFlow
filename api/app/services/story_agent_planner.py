import json
import math
import re
import time
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.requests import (
    ArtifactName,
    OutlineSchema,
    PlannerQaSummary,
    SceneModuleSchema,
    ScenePlanSchema,
    ScriptPack,
    ScriptPackScene,
)
from app.services.interleaved_parser import (
    extract_anchor_terms,
    normalized_scene_id,
    scene_narration_word_budget,
)
from app.services.story_agent_source_media import evidence_summary_bits

DEFAULT_PLANNER_ARTIFACT_TYPE = "storyboard_grid"


@dataclass(frozen=True)
class SceneBudgetPolicy:
    default: int
    minimum: int
    maximum: int
    derive_from_duration: bool
    expansion_rule: str


@dataclass(frozen=True)
class ArtifactPlanningPolicy:
    artifact_type: str
    planning_mode: str
    script_shape: str
    scene_budget: SceneBudgetPolicy
    salience_pass: str
    forward_pull_pass: str
    planner_focus: tuple[str, ...]
    generator_notes: tuple[str, ...]


class SalienceAssessmentItem(BaseModel):
    candidate_id: str
    candidate_type: str
    content: str
    rating: Literal["CRITICAL", "IMPORTANT", "FLAVOUR"]
    downstream_impact: str
    evidence_quote: str = ""
    overlap_with: list[str] = Field(default_factory=list)


class SalienceAssessmentSchema(BaseModel):
    items: list[SalienceAssessmentItem] = Field(default_factory=list)


class ForwardPullBait(BaseModel):
    content: str = ""
    evidence_quote: str = ""


class ForwardPullHook(BaseModel):
    question: str = ""
    evidence_quote: str = ""


class ForwardPullThreat(BaseModel):
    stake: str
    who_is_at_risk: str = ""
    evidence_quote: str = ""


class ForwardPullReward(BaseModel):
    payoff_signal: str
    likely_location: str = ""
    evidence_quote: str = ""


class ForwardPullPayload(BaseModel):
    theme_or_engine: str
    supporting_instances: list[str] = Field(default_factory=list)


class ForwardPullSchema(BaseModel):
    bait: ForwardPullBait | None = None
    hook: ForwardPullHook | None = None
    threats: list[ForwardPullThreat] = Field(default_factory=list)
    rewards: list[ForwardPullReward] = Field(default_factory=list)
    payloads: list[ForwardPullPayload] = Field(default_factory=list)


@dataclass(frozen=True)
class PlannerEnrichmentContext:
    artifact_policy: ArtifactPlanningPolicy
    thesis: str
    audience_descriptor: str
    claim_ids: tuple[str, ...]
    scene_count: int
    salience_assessment: SalienceAssessmentSchema | None
    forward_pull: ForwardPullSchema | None


@dataclass(frozen=True)
class PlannerIssue:
    severity: str
    code: str
    message: str
    scene_id: str | None = None
    target: str | None = None


@dataclass(frozen=True)
class PlannerValidationReport:
    hard_issues: tuple[PlannerIssue, ...]
    warnings: tuple[PlannerIssue, ...]

    @property
    def has_hard_issues(self) -> bool:
        return bool(self.hard_issues)


ARTIFACT_POLICIES: dict[str, ArtifactPlanningPolicy] = {
    "storyboard_grid": ArtifactPlanningPolicy(
        artifact_type="storyboard_grid",
        planning_mode="sequential",
        script_shape="sequential_storyboard",
        scene_budget=SceneBudgetPolicy(default=4, minimum=3, maximum=8, derive_from_duration=True, expansion_rule="normal"),
        salience_pass="FULL",
        forward_pull_pass="FULL",
        planner_focus=("progression", "scene turns", "coverage", "payoff"),
        generator_notes=("Multi-scene continuity matters.", "Voiceover pacing can drive scene order."),
    ),
    "comparison_one_pager": ArtifactPlanningPolicy(
        artifact_type="comparison_one_pager",
        planning_mode="static",
        script_shape="one_pager_board",
        scene_budget=SceneBudgetPolicy(default=1, minimum=1, maximum=1, derive_from_duration=False, expansion_rule="never"),
        salience_pass="FULL",
        forward_pull_pass="LITE",
        planner_focus=("hook", "modular information hierarchy", "evidence grouping", "synthesis", "dense readable composition"),
        generator_notes=("One canvas only.", "Convert beats into modules, not scenes.", "Do not turn this into a cinematic progression."),
    ),
    "slide_thumbnail": ArtifactPlanningPolicy(
        artifact_type="slide_thumbnail",
        planning_mode="static",
        script_shape="thumbnail_focus",
        scene_budget=SceneBudgetPolicy(default=1, minimum=1, maximum=2, derive_from_duration=False, expansion_rule="variant_only"),
        salience_pass="LITE",
        forward_pull_pass="FULL",
        planner_focus=("hook", "hero frame", "crop safety", "headline area"),
        generator_notes=("Usually one hero frame.", "Second scene is allowed only as a variant."),
    ),
    "technical_infographic": ArtifactPlanningPolicy(
        artifact_type="technical_infographic",
        planning_mode="static",
        script_shape="technical_infographic",
        scene_budget=SceneBudgetPolicy(default=1, minimum=1, maximum=2, derive_from_duration=False, expansion_rule="overview_plus_detail_only"),
        salience_pass="FULL",
        forward_pull_pass="OFF",
        planner_focus=("mechanism clarity", "module grouping", "factual hierarchy"),
        generator_notes=("Prioritize explanatory structure over suspense.", "Two scenes only when overview plus detail is truly needed."),
    ),
    "process_diagram": ArtifactPlanningPolicy(
        artifact_type="process_diagram",
        planning_mode="static",
        script_shape="process_map",
        scene_budget=SceneBudgetPolicy(default=1, minimum=1, maximum=2, derive_from_duration=False, expansion_rule="overview_plus_detail_only"),
        salience_pass="FULL",
        forward_pull_pass="OFF",
        planner_focus=("flow order", "state transitions", "decision points"),
        generator_notes=("Single composed flow is the default.", "Use a second scene only for zoomed detail."),
    ),
}


def resolve_planner_artifact_type(
    *,
    render_profile: dict[str, Any] | None = None,
    artifact_scope: list[ArtifactName] | None = None,
) -> str:
    profile = render_profile or {}
    artifact_type = str(profile.get("artifact_type", "")).strip().lower()
    if artifact_type in ARTIFACT_POLICIES:
        return artifact_type

    scope = set(artifact_scope or [])
    if "storyboard" in scope:
        return "storyboard_grid"
    if "thumbnail" in scope:
        return "slide_thumbnail"
    if scope == {"story_cards", "social_caption"}:
        return "comparison_one_pager"
    return DEFAULT_PLANNER_ARTIFACT_TYPE


def resolve_artifact_policy(
    *,
    render_profile: dict[str, Any] | None = None,
    artifact_scope: list[ArtifactName] | None = None,
) -> ArtifactPlanningPolicy:
    artifact_type = resolve_planner_artifact_type(
        render_profile=render_profile,
        artifact_scope=artifact_scope,
    )
    return ARTIFACT_POLICIES.get(artifact_type, ARTIFACT_POLICIES[DEFAULT_PLANNER_ARTIFACT_TYPE])


def planner_source_text(
    *,
    source_text: str,
    normalized_source_text: str = "",
    content_signal: dict[str, Any],
) -> str:
    if isinstance(source_text, str) and source_text.strip():
        return source_text.strip()[:12000]
    if isinstance(normalized_source_text, str) and normalized_source_text.strip():
        return normalized_source_text.strip()[:12000]

    sections: list[str] = []
    thesis = content_signal.get("thesis", {})
    if isinstance(thesis, dict):
        one_liner = str(thesis.get("one_liner", "")).strip()
        if one_liner:
            sections.append(f"THESIS: {one_liner}")

    key_claims = content_signal.get("key_claims", [])
    if isinstance(key_claims, list) and key_claims:
        sections.append("KEY CLAIMS:")
        for claim in key_claims[:10]:
            if not isinstance(claim, dict):
                continue
            claim_text = str(claim.get("claim_text", "")).strip()
            evidence = claim.get("evidence_snippets", [])
            evidence_bits = evidence_summary_bits(evidence if isinstance(evidence, list) else [])
            line = claim_text
            if evidence_bits:
                line += f" | evidence: {' ; '.join(evidence_bits)}"
            if line:
                sections.append(f"- {line}")

    beats = content_signal.get("narrative_beats", [])
    if isinstance(beats, list) and beats:
        sections.append("NARRATIVE BEATS:")
        for beat in beats[:6]:
            if not isinstance(beat, dict):
                continue
            message = str(beat.get("message", "")).strip()
            role = str(beat.get("role", "")).strip()
            text = f"{role}: {message}".strip(": ")
            if text:
                sections.append(f"- {text}")

    return "\n".join(sections)[:12000]


def normalize_candidate_text(raw_value: Any) -> str:
    return re.sub(r"\s+", " ", str(raw_value or "").strip())


def salience_candidates(
    *,
    content_signal: dict[str, Any],
    mode: str,
    planning_mode: str,
) -> list[dict[str, str]]:
    key_claims = content_signal.get("key_claims", [])
    beats = content_signal.get("narrative_beats", [])
    candidates: list[dict[str, str]] = []

    if isinstance(key_claims, list):
        for index, claim in enumerate(key_claims, start=1):
            if not isinstance(claim, dict):
                continue
            content = normalize_candidate_text(
                claim.get("claim_text") or claim.get("content") or claim.get("summary")
            )
            if not content:
                continue
            candidate_id = str(claim.get("claim_id", "")).strip() or f"claim-{index}"
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "candidate_type": "key_claim",
                    "content": content,
                }
            )

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for candidate in candidates:
        dedupe_key = candidate["content"].lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        deduped.append(candidate)

    if mode == "LITE":
        return deduped[:6]

    if planning_mode == "sequential" and isinstance(beats, list):
        for index, beat in enumerate(beats[:4], start=1):
            if not isinstance(beat, dict):
                continue
            content = normalize_candidate_text(
                beat.get("message") or beat.get("summary") or beat.get("title")
            )
            if not content:
                continue
            dedupe_key = content.lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            candidate_id = str(beat.get("beat_id", "")).strip() or f"beat-{index}"
            deduped.append(
                {
                    "candidate_id": candidate_id,
                    "candidate_type": "narrative_beat",
                    "content": content,
                }
            )

    return deduped


def build_salience_prompt(
    *,
    source_text: str,
    candidates: list[dict[str, str]],
) -> str:
    return (
        "SYSTEM:\n"
        "You are evaluating narrative salience by counterfactual deletion.\n\n"
        "USER:\n"
        "For each candidate signal below, decide how much the story would change if it were removed.\n"
        "Return JSON only.\n\n"
        "Rules:\n"
        "- Use 3 ratings: CRITICAL / IMPORTANT / FLAVOUR.\n"
        "- CRITICAL means removing it breaks causal chain, stakes, or the central explanatory engine.\n"
        "- IMPORTANT means removing it weakens understanding, motivation, or foreshadowing.\n"
        "- FLAVOUR means mostly style, framing, or world texture.\n"
        "- Assume all other candidates remain fixed; evaluate deletion one item at a time.\n"
        "- If two candidates overlap heavily, mention overlap and avoid rating both CRITICAL.\n\n"
        "For each item provide:\n"
        "- candidate_id\n"
        "- candidate_type\n"
        "- content\n"
        "- rating\n"
        "- downstream_impact\n"
        "- evidence_quote (<=12 words)\n"
        "- overlap_with\n\n"
        f"SOURCE:\n{source_text}\n\n"
        f"CANDIDATE SIGNALS:\n{json.dumps(candidates, ensure_ascii=True)}"
    )


def build_forward_pull_prompt(
    *,
    source_text: str,
) -> str:
    return (
        "SYSTEM:\n"
        "You extract forward-pull narrative signals. Do not write prose.\n\n"
        "USER:\n"
        "Using the Bait-Hook-Threat-Reward-Payload lens, extract grounded signals from SOURCE.\n"
        "Definitions:\n"
        "- Bait: first anomaly or promise that grabs attention.\n"
        "- Hook: the main information gap or unresolved question.\n"
        "- Threat: explicit or implicit stakes if unresolved.\n"
        "- Reward: payoff signals such as reveal, reversal, decision, or relief.\n"
        "- Payload: the durable meaning, theme, plot engine, or transformation.\n\n"
        "Rules:\n"
        "- If the source is expository, map hook to the central explanatory gap.\n"
        "- If no real threat exists, return an empty threats list.\n"
        "- If no real reward exists, return an empty rewards list.\n"
        "- Keep everything source-grounded and concise.\n"
        "- Return JSON only.\n\n"
        f"SOURCE:\n{source_text}"
    )


def best_effort_salience_summary(salience: SalienceAssessmentSchema | None) -> str:
    if salience is None or not salience.items:
        return ""

    ranked = sorted(
        salience.items,
        key=lambda item: {"CRITICAL": 0, "IMPORTANT": 1, "FLAVOUR": 2}.get(item.rating, 3),
    )
    lines = ["SALIENCE MAP:"]
    for item in ranked:
        overlap = f" overlap={','.join(item.overlap_with)};" if item.overlap_with else ""
        lines.append(
            f"- {item.candidate_id} [{item.candidate_type}] {item.rating}: {item.content} "
            f"(impact: {item.downstream_impact}; evidence: {item.evidence_quote};{overlap})"
        )
    lines.append(
        "Coverage rule: CRITICAL items are mandatory, IMPORTANT items should be covered if space allows, FLAVOUR items must not displace backbone material."
    )
    return "\n".join(lines)


def forward_pull_guidance(
    *,
    artifact_policy: ArtifactPlanningPolicy,
    forward_pull: ForwardPullSchema | None,
) -> str:
    if forward_pull is None:
        return ""

    lines: list[str] = []
    bait = forward_pull.bait
    hook = forward_pull.hook
    threats = forward_pull.threats
    rewards = forward_pull.rewards
    payloads = forward_pull.payloads

    if bait and bait.content:
        lines.append(f"Bait: {bait.content} | evidence: {bait.evidence_quote}")
    if hook and hook.question:
        lines.append(f"Hook: {hook.question} | evidence: {hook.evidence_quote}")

    if artifact_policy.artifact_type == "comparison_one_pager":
        if payloads:
            lines.append(
                "Use mainly hook and payload in the header and synthesis framing: "
                + "; ".join(payload.theme_or_engine for payload in payloads[:2])
            )
        if threats:
            grounded_threats = [threat.stake for threat in threats[:1] if threat.evidence_quote]
            if grounded_threats:
                lines.append(f"Optional grounded stake framing: {'; '.join(grounded_threats)}")
    elif artifact_policy.artifact_type == "slide_thumbnail":
        if threats:
            lines.append("Use threat only if it sharpens the hook without fabricating drama.")
        if rewards:
            lines.append("Imply one payoff signal visually when it strengthens click-through.")
    elif artifact_policy.planning_mode == "sequential":
        if threats:
            lines.append(
                "Threats: "
                + "; ".join(
                    f"{threat.stake} (risk: {threat.who_is_at_risk}; evidence: {threat.evidence_quote})"
                    for threat in threats[:3]
                )
            )
        if rewards:
            lines.append(
                "Rewards: "
                + "; ".join(
                    f"{reward.payoff_signal} (likely beat: {reward.likely_location}; evidence: {reward.evidence_quote})"
                    for reward in rewards[:3]
                )
            )

    if payloads:
        lines.append(
            "Payloads: " + "; ".join(payload.theme_or_engine for payload in payloads[:3])
        )

    if not lines:
        return ""

    prefix = "FORWARD-PULL MAP:"
    if artifact_policy.forward_pull_pass == "LITE":
        lines.append("Consumption rule: use hook and payload first; ignore threat/reward if they do not fit the artifact.")
    else:
        lines.append("Consumption rule: use these signals to sharpen opener, tension, and payoff while staying source-grounded.")
    return "\n".join([prefix, *lines])


def matchable_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]+", " ", text.lower())).strip()


def text_matches_signal(text: str, signal_text: str) -> bool:
    normalized_text = matchable_text(text)
    normalized_signal = matchable_text(signal_text)
    if not normalized_text or not normalized_signal:
        return False
    if normalized_signal in normalized_text:
        return True

    anchor_terms = extract_anchor_terms(signal_text, limit=6)
    if not anchor_terms:
        anchor_terms = [token for token in normalized_signal.split() if len(token) >= 4][:6]
    if not anchor_terms:
        return False

    matches = sum(
        1 for term in anchor_terms if re.search(rf"\b{re.escape(term.lower())}\b", normalized_text)
    )
    threshold = 1 if len(anchor_terms) <= 2 else 2
    return matches >= threshold


def scene_blob(scene: ScriptPackScene) -> str:
    module_parts: list[str] = []
    for module in scene.modules:
        module_parts.extend(
            [
                module.module_id,
                module.label,
                module.purpose,
                module.content_type,
                module.placement_hint or "",
                *module.claim_refs,
            ]
        )

    parts = [
        scene.title,
        scene.scene_goal,
        scene.narration_focus,
        scene.visual_prompt,
        scene.scene_role or "",
        scene.composition_goal or "",
        scene.layout_template or "",
        scene.focal_subject or "",
        *scene.visual_hierarchy,
        *scene.comparison_axes,
        *scene.flow_steps,
        *module_parts,
        *scene.claim_refs,
    ]
    return " ".join(str(part).strip() for part in parts if str(part).strip())


def scene_covers_signal(
    scene: ScriptPackScene,
    *,
    candidate_id: str = "",
    signal_text: str = "",
    evidence_quote: str = "",
) -> bool:
    if candidate_id and candidate_id in scene.claim_refs:
        return True
    blob = scene_blob(scene)
    if signal_text and text_matches_signal(blob, signal_text):
        return True
    if evidence_quote and text_matches_signal(blob, evidence_quote):
        return True
    return False


def prepend_guidance(text: str, addition: str) -> str:
    clean_addition = addition.strip().rstrip(".")
    clean_text = text.strip()
    if not clean_addition:
        return clean_text
    if text_matches_signal(clean_text, clean_addition):
        return clean_text or clean_addition
    if not clean_text:
        return clean_addition
    return f"{clean_addition}. {clean_text}"


def append_guidance(text: str, addition: str) -> str:
    clean_addition = addition.strip().rstrip(".")
    clean_text = text.strip()
    if not clean_addition:
        return clean_text
    if text_matches_signal(clean_text, clean_addition):
        return clean_text or clean_addition
    if not clean_text:
        return clean_addition
    return f"{clean_text} {clean_addition}."


def append_unique(items: list[str], value: str, *, limit: int | None = None) -> list[str]:
    clean_value = value.strip()
    next_items = [item for item in items if str(item).strip()]
    if not clean_value:
        return next_items
    if any(text_matches_signal(item, clean_value) for item in next_items):
        return next_items[:limit] if limit else next_items
    next_items.append(clean_value)
    return next_items[:limit] if limit else next_items


def prepend_unique(items: list[str], value: str, *, limit: int | None = None) -> list[str]:
    clean_value = value.strip()
    filtered = [
        item
        for item in items
        if str(item).strip() and not text_matches_signal(item, clean_value)
    ]
    if clean_value:
        filtered.insert(0, clean_value)
    return filtered[:limit] if limit else filtered


def short_headline(text: str, *, max_words: int = 8, max_chars: int = 64) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if not cleaned:
        return ""
    words = cleaned.split(" ")
    shortened = " ".join(words[:max_words]).strip()
    if len(shortened) > max_chars:
        shortened = shortened[:max_chars].rsplit(" ", 1)[0].strip() or shortened[:max_chars].strip()
    return shortened.rstrip(".,;:!?")


def critical_salience_items(
    salience: SalienceAssessmentSchema | None,
) -> list[SalienceAssessmentItem]:
    if salience is None:
        return []
    return [item for item in salience.items if item.rating == "CRITICAL"]


def important_salience_items(
    salience: SalienceAssessmentSchema | None,
) -> list[SalienceAssessmentItem]:
    if salience is None:
        return []
    return [item for item in salience.items if item.rating == "IMPORTANT"]


def build_enrichment_context(
    *,
    artifact_policy: ArtifactPlanningPolicy,
    thesis: str,
    audience_descriptor: str,
    claim_ids: list[str],
    scene_count: int,
    salience_assessment: SalienceAssessmentSchema | None,
    forward_pull: ForwardPullSchema | None,
) -> PlannerEnrichmentContext:
    return PlannerEnrichmentContext(
        artifact_policy=artifact_policy,
        thesis=thesis,
        audience_descriptor=audience_descriptor,
        claim_ids=tuple(claim_ids),
        scene_count=scene_count,
        salience_assessment=salience_assessment,
        forward_pull=forward_pull,
    )


def validate_script_pack_against_enrichments(
    *,
    script_pack: ScriptPack,
    context: PlannerEnrichmentContext,
) -> PlannerValidationReport:
    hard_issues: list[PlannerIssue] = []
    warnings: list[PlannerIssue] = []
    scenes = list(script_pack.scenes)
    if not scenes:
        return PlannerValidationReport(
            hard_issues=(
                PlannerIssue(
                    severity="hard",
                    code="no_scenes",
                    message="Script pack produced no scenes.",
                ),
            ),
            warnings=(),
        )

    for item in critical_salience_items(context.salience_assessment):
        covered = any(
            scene_covers_signal(
                scene,
                candidate_id=item.candidate_id,
                signal_text=item.content,
                evidence_quote=item.evidence_quote,
            )
            for scene in scenes
        )
        if not covered:
            hard_issues.append(
                PlannerIssue(
                    severity="hard",
                    code="critical_missing",
                    message=f"Critical item {item.candidate_id} is not covered in the script pack.",
                    target=item.candidate_id,
                )
            )

    for item in important_salience_items(context.salience_assessment):
        covered = any(
            scene_covers_signal(
                scene,
                candidate_id=item.candidate_id,
                signal_text=item.content,
                evidence_quote=item.evidence_quote,
            )
            for scene in scenes
        )
        if not covered:
            warnings.append(
                PlannerIssue(
                    severity="warning",
                    code="important_missing",
                    message=f"Important item {item.candidate_id} is not explicitly covered.",
                    target=item.candidate_id,
                )
            )

    forward_pull = context.forward_pull
    if forward_pull is None:
        return PlannerValidationReport(hard_issues=tuple(hard_issues), warnings=tuple(warnings))

    artifact_type = context.artifact_policy.artifact_type
    first_scene = scenes[0]
    last_scene = scenes[-1]

    if context.artifact_policy.planning_mode == "sequential":
        opener_signals = [
            forward_pull.bait.content if forward_pull.bait and forward_pull.bait.content else "",
            forward_pull.hook.question if forward_pull.hook and forward_pull.hook.question else "",
        ]
        if any(signal.strip() for signal in opener_signals):
            opener_ok = any(
                scene_covers_signal(first_scene, signal_text=signal)
                for signal in opener_signals
                if signal.strip()
            )
            if not opener_ok:
                hard_issues.append(
                    PlannerIssue(
                        severity="hard",
                        code="missing_opener_anchor",
                        message="First scene does not express the forward-pull bait or hook.",
                        scene_id=first_scene.scene_id,
                    )
                )
        if first_scene.scene_role != "bait_hook":
            warnings.append(
                PlannerIssue(
                    severity="warning",
                    code="opener_role_mismatch",
                    message="First scene should be tagged as bait_hook.",
                    scene_id=first_scene.scene_id,
                )
            )

        closer_signals = [
            forward_pull.rewards[0].payoff_signal if forward_pull.rewards else "",
            forward_pull.payloads[0].theme_or_engine if forward_pull.payloads else "",
        ]
        if any(signal.strip() for signal in closer_signals):
            closer_ok = any(
                scene_covers_signal(last_scene, signal_text=signal)
                for signal in closer_signals
                if signal.strip()
            )
            if not closer_ok:
                hard_issues.append(
                    PlannerIssue(
                        severity="hard",
                        code="missing_closer_anchor",
                        message="Final scene does not express the reward or payload.",
                        scene_id=last_scene.scene_id,
                    )
                )
        if last_scene.scene_role != "payoff":
            warnings.append(
                PlannerIssue(
                    severity="warning",
                    code="closer_role_mismatch",
                    message="Final scene should be tagged as payoff.",
                    scene_id=last_scene.scene_id,
                )
            )
    elif artifact_type == "comparison_one_pager":
        header_signals = [
            forward_pull.hook.question if forward_pull.hook and forward_pull.hook.question else "",
            forward_pull.payloads[0].theme_or_engine if forward_pull.payloads else "",
        ]
        if any(signal.strip() for signal in header_signals):
            header_ok = any(
                scene_covers_signal(first_scene, signal_text=signal)
                for signal in header_signals
                if signal.strip()
            )
            if not header_ok:
                hard_issues.append(
                    PlannerIssue(
                        severity="hard",
                        code="missing_comparison_header",
                        message="One-pager is missing hook or payload framing in its header or synthesis area.",
                        scene_id=first_scene.scene_id,
                    )
                )
    elif artifact_type == "slide_thumbnail":
        anchor_signals = [
            forward_pull.hook.question if forward_pull.hook and forward_pull.hook.question else "",
            forward_pull.bait.content if forward_pull.bait and forward_pull.bait.content else "",
        ]
        if any(signal.strip() for signal in anchor_signals) and not any(
            scene_covers_signal(first_scene, signal_text=signal)
            for signal in anchor_signals
            if signal.strip()
        ):
            hard_issues.append(
                PlannerIssue(
                    severity="hard",
                    code="missing_thumbnail_anchor",
                    message="Thumbnail scene does not express the dominant bait or hook.",
                    scene_id=first_scene.scene_id,
                )
            )
        if len(first_scene.claim_refs) > 2:
            warnings.append(
                PlannerIssue(
                    severity="warning",
                    code="thumbnail_diffuse",
                    message="Thumbnail should not spread across too many claim refs.",
                    scene_id=first_scene.scene_id,
                )
            )

    return PlannerValidationReport(hard_issues=tuple(hard_issues), warnings=tuple(warnings))


def repair_target_scene(
    scenes: list[ScriptPackScene],
    *,
    artifact_type: str,
    index_hint: int,
) -> ScriptPackScene:
    if artifact_type in {"comparison_one_pager", "slide_thumbnail"} or len(scenes) == 1:
        return scenes[0]
    if artifact_type in {"technical_infographic", "process_diagram"}:
        return scenes[min(index_hint, len(scenes) - 1)]
    middle_scenes = scenes[1:-1] or scenes
    return min(middle_scenes, key=lambda scene: len(scene.claim_refs))


def repair_script_pack_from_enrichments(
    *,
    script_pack: ScriptPack,
    context: PlannerEnrichmentContext,
) -> ScriptPack:
    repaired = script_pack.model_copy(deep=True)
    scenes = list(repaired.scenes)
    if not scenes:
        return repaired

    artifact_type = context.artifact_policy.artifact_type

    for index, item in enumerate(critical_salience_items(context.salience_assessment)):
        if any(
            scene_covers_signal(
                scene,
                candidate_id=item.candidate_id,
                signal_text=item.content,
                evidence_quote=item.evidence_quote,
            )
            for scene in scenes
        ):
            continue

        target_scene = repair_target_scene(
            scenes,
            artifact_type=artifact_type,
            index_hint=index,
        )
        if item.candidate_id in context.claim_ids and item.candidate_id not in target_scene.claim_refs:
            target_scene.claim_refs.append(item.candidate_id)

        if artifact_type == "comparison_one_pager":
            target_scene.visual_hierarchy = append_unique(target_scene.visual_hierarchy, item.content)
            target_scene.modules.append(
                SceneModuleSchema(
                    module_id=f"critical-{len(target_scene.modules) + 1}",
                    label=item.content[:80],
                    purpose="Cover a mandatory one-pager module.",
                    content_type="claim_cluster",
                    claim_refs=[item.candidate_id] if item.candidate_id in context.claim_ids else [],
                )
            )
            target_scene.narration_focus = prepend_guidance(target_scene.narration_focus, item.content)
        elif artifact_type == "slide_thumbnail":
            target_scene.focal_subject = target_scene.focal_subject or item.content
            target_scene.visual_hierarchy = prepend_unique(
                target_scene.visual_hierarchy,
                item.content,
                limit=3,
            )
            target_scene.narration_focus = prepend_guidance(target_scene.narration_focus, item.content)
            target_scene.claim_refs = target_scene.claim_refs[:2]
        elif artifact_type == "technical_infographic":
            target_scene.visual_hierarchy = append_unique(target_scene.visual_hierarchy, item.content)
            target_scene.modules.append(
                SceneModuleSchema(
                    module_id=f"critical-{len(target_scene.modules) + 1}",
                    label=item.content[:80],
                    purpose="Represent a mandatory mechanism component.",
                    content_type="claim_cluster",
                    claim_refs=[item.candidate_id] if item.candidate_id in context.claim_ids else [],
                )
            )
            target_scene.narration_focus = append_guidance(target_scene.narration_focus, item.content)
        elif artifact_type == "process_diagram":
            target_scene.flow_steps = append_unique(target_scene.flow_steps, item.content)
            target_scene.modules.append(
                SceneModuleSchema(
                    module_id=f"critical-{len(target_scene.modules) + 1}",
                    label=item.content[:80],
                    purpose="Represent a mandatory process step.",
                    content_type="process_step",
                    claim_refs=[item.candidate_id] if item.candidate_id in context.claim_ids else [],
                )
            )
            target_scene.narration_focus = append_guidance(target_scene.narration_focus, item.content)
        else:
            target_scene.narration_focus = append_guidance(target_scene.narration_focus, item.content)

    forward_pull = context.forward_pull
    if forward_pull is None:
        return repaired

    first_scene = scenes[0]
    if context.artifact_policy.planning_mode == "sequential":
        first_scene.scene_role = "bait_hook"
        if forward_pull.bait and forward_pull.bait.content:
            first_scene.title = (
                first_scene.title
                if text_matches_signal(first_scene.title, forward_pull.bait.content)
                else (
                    forward_pull.bait.content[:96]
                    if "scene" in first_scene.title.lower() or "opening" in first_scene.title.lower()
                    else first_scene.title
                )
            )
            first_scene.narration_focus = prepend_guidance(
                first_scene.narration_focus,
                forward_pull.bait.content,
            )
        if forward_pull.hook and forward_pull.hook.question:
            first_scene.narration_focus = prepend_guidance(
                first_scene.narration_focus,
                f"Driving question: {forward_pull.hook.question}",
            )

        last_scene = scenes[-1]
        last_scene.scene_role = "payoff"
        if forward_pull.rewards:
            last_scene.narration_focus = append_guidance(
                last_scene.narration_focus,
                forward_pull.rewards[0].payoff_signal,
            )
        if forward_pull.payloads:
            last_scene.narration_focus = append_guidance(
                last_scene.narration_focus,
                f"End on {forward_pull.payloads[0].theme_or_engine}",
            )
    elif artifact_type == "comparison_one_pager":
        if forward_pull.hook and forward_pull.hook.question:
            first_scene.title = forward_pull.hook.question[:100]
            first_scene.narration_focus = prepend_guidance(
                first_scene.narration_focus,
                forward_pull.hook.question,
            )
        if forward_pull.payloads:
            payload_text = forward_pull.payloads[0].theme_or_engine
            first_scene.scene_goal = append_guidance(
                first_scene.scene_goal,
                f"Land the synthesis on {payload_text}",
            )
            first_scene.visual_hierarchy = append_unique(
                first_scene.visual_hierarchy,
                "synthesis panel",
            )
        if not first_scene.modules:
            first_scene.modules.extend(
                [
                    SceneModuleSchema(
                        module_id="hook-header",
                        label="Hook Header",
                        purpose="Open with the core framing question or promise.",
                        content_type="hero",
                        claim_refs=first_scene.claim_refs[:1],
                        placement_hint="top band",
                    ),
                    SceneModuleSchema(
                        module_id="core-module-1",
                        label="Core Module",
                        purpose="Explain the most important source-grounded idea.",
                        content_type="claim_cluster",
                        claim_refs=first_scene.claim_refs[:2],
                        placement_hint="main body",
                    ),
                    SceneModuleSchema(
                        module_id="synthesis-panel",
                        label="Synthesis",
                        purpose="Land the final takeaway or durable meaning of the board.",
                        content_type="support_panel",
                        claim_refs=first_scene.claim_refs[-2:],
                        placement_hint="bottom band",
                    ),
                ]
            )
    elif artifact_type == "slide_thumbnail":
        anchor_signal = ""
        if forward_pull.hook and forward_pull.hook.question and len(forward_pull.hook.question.split()) <= 10:
            anchor_signal = forward_pull.hook.question
        elif forward_pull.bait and forward_pull.bait.content:
            anchor_signal = forward_pull.bait.content
        if anchor_signal:
            first_scene.title = short_headline(anchor_signal, max_words=8, max_chars=56) or first_scene.title
            first_scene.focal_subject = anchor_signal
            first_scene.visual_hierarchy = prepend_unique(
                first_scene.visual_hierarchy,
                anchor_signal,
                limit=3,
            )
        if forward_pull.hook and forward_pull.hook.question:
            first_scene.narration_focus = prepend_guidance(
                first_scene.narration_focus,
                forward_pull.hook.question,
            )
        first_scene.claim_refs = first_scene.claim_refs[:2]

    return repaired


def outline_snapshot_from_script_pack(script_pack: ScriptPack) -> list[dict[str, Any]]:
    return [
        {
            "scene_id": scene.scene_id,
            "title": scene.title,
            "narration_focus": scene.narration_focus,
            "visual_prompt": scene.visual_prompt,
            "claim_refs": scene.claim_refs,
            "scene_mode": scene.scene_mode,
            "scene_role": scene.scene_role,
            "composition_goal": scene.composition_goal,
            "layout_template": scene.layout_template,
            "focal_subject": scene.focal_subject,
            "visual_hierarchy": scene.visual_hierarchy,
            "comparison_axes": scene.comparison_axes,
            "flow_steps": scene.flow_steps,
            "crop_safe_regions": scene.crop_safe_regions,
            "evidence_refs": scene.evidence_refs,
            "source_media": [item.model_dump() for item in scene.source_media],
            "render_strategy": scene.render_strategy,
        }
        for scene in script_pack.scenes
    ]


def build_replan_directives(
    *,
    report: PlannerValidationReport,
    script_pack: ScriptPack,
) -> str:
    hard_lines = "\n".join(f"- {issue.message}" for issue in report.hard_issues[:8])
    draft_snapshot = json.dumps(
        outline_snapshot_from_script_pack(script_pack),
        ensure_ascii=True,
    )
    return (
        "REVISION REQUIRED:\n"
        "The previous outline failed these mandatory checks:\n"
        f"{hard_lines}\n"
        "Keep the same artifact type and scene count. Return a full corrected outline only.\n"
        f"PREVIOUS DRAFT:\n{draft_snapshot}"
    )


def build_planner_qa_summary(
    *,
    initial_report: PlannerValidationReport,
    final_report: PlannerValidationReport,
    repair_applied: bool,
    replan_attempted: bool,
) -> PlannerQaSummary:
    if replan_attempted:
        mode: Literal["direct", "repaired", "replanned"] = "replanned"
        summary = "Planner used one constrained replan after mandatory checks still failed."
    elif repair_applied:
        mode = "repaired"
        summary = "Planner applied deterministic repairs before locking the script pack."
    else:
        mode = "direct"
        summary = "Planner locked the script pack directly with no mandatory fixes."

    details: list[str] = []
    if initial_report.hard_issues:
        details.append(f"Initial mandatory issues: {len(initial_report.hard_issues)}.")
    if initial_report.warnings:
        details.append(f"Initial warnings: {len(initial_report.warnings)}.")
    if repair_applied:
        details.append("Coverage and structural hooks were repaired before final lock.")
    if replan_attempted:
        details.append("One constrained replan was requested with explicit failure notes.")
    if final_report.warnings:
        details.append(f"Final warnings remaining: {len(final_report.warnings)}.")
        details.extend(issue.message for issue in final_report.warnings[:2])

    return PlannerQaSummary(
        mode=mode,
        summary=summary,
        initial_hard_issue_count=len(initial_report.hard_issues),
        initial_warning_count=len(initial_report.warnings),
        final_warning_count=len(final_report.warnings),
        repair_applied=repair_applied,
        replan_attempted=replan_attempted,
        details=details[:4],
    )


def should_split_static_artifact(
    *,
    content_signal: dict[str, Any],
    artifact_type: str,
) -> bool:
    if artifact_type not in {"technical_infographic", "process_diagram"}:
        return False

    beats = content_signal.get("narrative_beats", [])
    claims = content_signal.get("key_claims", [])
    if not isinstance(beats, list) or not isinstance(claims, list):
        return False

    if artifact_type == "technical_infographic":
        return len(claims) >= 6 and len(beats) >= 4
    return len(beats) >= 5 and len(claims) >= 4


def derive_scene_count(
    *,
    artifact_policy: ArtifactPlanningPolicy,
    content_signal: dict[str, Any],
    render_profile: dict[str, Any],
    audience_level: str,
) -> tuple[int, str]:
    artifact_type = artifact_policy.artifact_type
    scene_budget = artifact_policy.scene_budget
    if artifact_policy.planning_mode != "sequential":
        if artifact_type == "comparison_one_pager":
            return 1, "Comparison one-pagers always plan as one dense composed scene."
        if artifact_type == "slide_thumbnail":
            return 1, "Slide thumbnails default to one hero frame; variants are optional and off by default."
        if should_split_static_artifact(
            content_signal=content_signal,
            artifact_type=artifact_type,
        ):
            return 2, "Source naturally splits into overview and detail, so the static artifact uses two panels."
        return scene_budget.default, "Static artifacts stay dense rather than expanding with duration."

    output_controls = render_profile.get("output_controls", {})
    target_duration = output_controls.get("target_duration_sec", 60)
    density = str(render_profile.get("density", "standard")).lower()
    sec_per_scene = 10 if density == "detailed" else (18 if density == "simple" else 14)

    base_scenes = math.ceil(target_duration / sec_per_scene)
    claims = content_signal.get("key_claims", [])
    claims_count = len(claims) if isinstance(claims, list) else 0
    if claims_count > 5:
        base_scenes += 1
    if audience_level == "beginner":
        base_scenes -= 1

    scene_count = max(scene_budget.minimum, min(base_scenes, scene_budget.maximum))
    reason = (
        f"Sequential scene budget derived from target_duration_sec={target_duration}, "
        f"density={density}, claims={claims_count}, audience_level={audience_level}."
    )
    return scene_count, reason


def default_scene_role(idx: int, total: int) -> str:
    if total <= 1:
        return "payload"
    if idx == 1:
        return "bait_hook"
    if idx == total:
        return "payoff"
    if idx == 2:
        return "setup"
    if idx == total - 1:
        return "stakes"
    return "turn"


def default_layout_template(
    *,
    artifact_type: str,
    scene_index: int,
    scene_count: int,
) -> str | None:
    if artifact_type == "comparison_one_pager":
        return "modular_poster"
    if artifact_type == "slide_thumbnail":
        return "hero_thumbnail" if scene_index == 1 else "thumbnail_variant"
    if artifact_type == "technical_infographic":
        return "layered_mechanism" if scene_count == 1 or scene_index == 1 else "detail_callout"
    if artifact_type == "process_diagram":
        return "process_flow" if scene_count == 1 or scene_index == 1 else "zoom_detail"
    return None


def fallback_scene_plan(
    *,
    idx: int,
    scene_count: int,
    thesis: str,
    artifact_policy: ArtifactPlanningPolicy,
    claim_ids: list[str],
) -> ScenePlanSchema:
    shared_claim_refs = claim_ids[: min(4, len(claim_ids))]
    if artifact_policy.artifact_type == "comparison_one_pager":
        return ScenePlanSchema(
            scene_id=f"scene-{idx}",
            title="One-Pager Board",
            narration_focus=f"Guide the viewer through the core modules and takeaway inside {thesis}.",
            visual_prompt=(
                "A single dense editorial-style one-pager board with modular sections, "
                "clear hierarchy, strong containers, diagrams, callouts, and no reliance on tiny image text."
            ),
            claim_refs=shared_claim_refs,
            scene_mode="static",
            composition_goal="Compose one publish-ready poster-style information board.",
            layout_template="modular_poster",
            visual_hierarchy=["hook header", "core modules", "evidence/data callouts", "synthesis panel"],
            modules=[
                SceneModuleSchema(
                    module_id="hook-header",
                    label="Hook Header",
                    purpose="Open with the core framing question or promise.",
                    content_type="hero",
                    claim_refs=shared_claim_refs[:1],
                    placement_hint="top band",
                ),
                SceneModuleSchema(
                    module_id="core-module-1",
                    label="Core Module",
                    purpose="Explain the most important source-grounded idea.",
                    content_type="claim_cluster",
                    claim_refs=shared_claim_refs[:2],
                    placement_hint="upper-left body",
                ),
                SceneModuleSchema(
                    module_id="evidence-callout",
                    label="Evidence Callout",
                    purpose="Anchor the board in source-grounded evidence or key support points.",
                    content_type="callout",
                    claim_refs=shared_claim_refs[1:3],
                    placement_hint="side rail",
                ),
                SceneModuleSchema(
                    module_id="synthesis-panel",
                    label="Synthesis",
                    purpose="Land the final takeaway or durable meaning of the board.",
                    content_type="support_panel",
                    claim_refs=shared_claim_refs[-2:],
                    placement_hint="bottom band",
                ),
            ],
        )
    if artifact_policy.artifact_type == "slide_thumbnail":
        return ScenePlanSchema(
            scene_id=f"scene-{idx}",
            title="Hero Thumbnail",
            narration_focus=f"Land the hook for {thesis} in one instantly readable hero frame.",
            visual_prompt=(
                "A bold thumbnail-style hero frame with one dominant subject, strong silhouette, "
                "high contrast, a reserved headline-safe area, one supporting context cue, and no generic abstract symbols."
            ),
            claim_refs=claim_ids[:1],
            scene_mode="static",
            composition_goal="Create a single hero frame that reads instantly at small size and supports future headline overlay.",
            layout_template="hero_thumbnail" if idx == 1 else "thumbnail_variant",
            focal_subject=thesis,
            visual_hierarchy=["headline-safe hook zone", "hero subject", "supporting context cue"],
            crop_safe_regions=["top-left headline zone", "center hero safe area"],
        )
    if artifact_policy.artifact_type == "technical_infographic":
        title = "System Overview" if idx == 1 else "Mechanism Detail"
        return ScenePlanSchema(
            scene_id=f"scene-{idx}",
            title=title,
            narration_focus=f"Explain the core mechanism behind {thesis} with structured clarity.",
            visual_prompt="A clean technical infographic with layered modules, annotations implied visually, and no image text.",
            claim_refs=shared_claim_refs,
            scene_mode="static",
            composition_goal="Organize the mechanism into a structured explanatory board.",
            layout_template="layered_mechanism" if idx == 1 else "detail_callout",
            visual_hierarchy=["system overview", "core mechanism", "supporting detail"],
        )
    if artifact_policy.artifact_type == "process_diagram":
        title = "Process Flow" if idx == 1 else "Flow Detail"
        return ScenePlanSchema(
            scene_id=f"scene-{idx}",
            title=title,
            narration_focus=f"Walk through the process logic of {thesis} in the correct order.",
            visual_prompt="A clear process diagram showing stages, transitions, and decision points without text labels inside the image.",
            claim_refs=shared_claim_refs,
            scene_mode="static",
            composition_goal="Map the process as a single readable flow.",
            layout_template="process_flow" if idx == 1 else "zoom_detail",
            flow_steps=["entry", "transition", "outcome"] if idx == 1 else ["detail focus", "state change"],
            visual_hierarchy=["entry state", "core steps", "outcome"],
        )

    return ScenePlanSchema(
        scene_id=f"scene-{idx}",
        title=f"Explainer Point {idx}",
        narration_focus=f"Further detail on {thesis}.",
        visual_prompt="A relevant educational visual.",
        claim_refs=claim_ids[max(0, idx - 1): max(0, idx - 1) + 2],
        scene_mode="sequential",
        scene_role=default_scene_role(idx, scene_count),
    )


def normalize_scene_plans(
    *,
    parsed_scenes: list[ScenePlanSchema],
    target_scene_count: int,
    thesis: str,
    artifact_policy: ArtifactPlanningPolicy,
    claim_ids: list[str],
) -> list[ScenePlanSchema]:
    scenes = list(parsed_scenes[:target_scene_count])
    while len(scenes) < target_scene_count:
        idx = len(scenes) + 1
        scenes.append(
            fallback_scene_plan(
                idx=idx,
                scene_count=target_scene_count,
                thesis=thesis,
                artifact_policy=artifact_policy,
                claim_ids=claim_ids,
            )
        )

    normalized: list[ScenePlanSchema] = []
    for idx, scene in enumerate(scenes, start=1):
        scene_mode = "static" if artifact_policy.planning_mode != "sequential" else "sequential"
        normalized.append(
            scene.model_copy(
                update={
                    "scene_mode": scene_mode,
                    "scene_role": scene.scene_role
                    or (
                        default_scene_role(idx, len(scenes))
                        if artifact_policy.planning_mode == "sequential"
                        else None
                    ),
                    "layout_template": scene.layout_template
                    or default_layout_template(
                        artifact_type=artifact_policy.artifact_type,
                        scene_index=idx,
                        scene_count=len(scenes),
                    ),
                }
            )
        )
    return normalized


def build_script_pack_prompt(
    *,
    thesis: str,
    concepts: list[Any],
    beats: list[Any],
    key_claims: list[Any],
    visual_candidates: list[Any],
    audience_descriptor: str,
    taste_bar: str,
    must_include: list[str],
    must_avoid: list[str],
    artifact_policy: ArtifactPlanningPolicy,
    scene_count: int,
    salience_summary: str = "",
    forward_pull_guidance: str = "",
    repair_directives: str = "",
) -> str:
    prompt = (
        "SYSTEM:\n"
        "You are planning an ExplainFlow script pack.\n"
        "Return only valid JSON matching the provided schema.\n"
        "Do not add markdown or commentary.\n\n"
        "USER:\n"
        f"Artifact type: {artifact_policy.artifact_type}\n"
        f"Planning mode: {artifact_policy.planning_mode}\n"
        f"Script shape: {artifact_policy.script_shape}\n"
        f"Audience persona: {audience_descriptor}\n"
        f"Taste bar: {taste_bar}\n"
        f"Target scene count: {scene_count}\n"
        f"Core thesis: {thesis}\n"
        f"Concepts: {json.dumps(concepts[:10], ensure_ascii=True)}\n"
        f"Narrative beats: {json.dumps(beats[:10], ensure_ascii=True)}\n"
        f"Key claims: {json.dumps(key_claims[:8], ensure_ascii=True)}\n"
        f"Visual candidates: {json.dumps(visual_candidates[:8], ensure_ascii=True)}\n"
        f"Planner focus: {', '.join(artifact_policy.planner_focus)}.\n"
        f"Generation notes: {' '.join(artifact_policy.generator_notes)}\n"
    )
    if salience_summary:
        prompt += f"{salience_summary}\n"
    if forward_pull_guidance:
        prompt += f"{forward_pull_guidance}\n"

    if artifact_policy.planning_mode == "sequential":
        prompt += (
            "Create a scene-by-scene storyboard outline with progression across the full pack.\n"
            "Use scene_mode='sequential'. Provide scene_role values such as bait_hook, setup, turn, stakes, payoff.\n"
            "Ensure each scene has a descriptive title, a clear narration_focus, and a detailed visual_prompt.\n"
            "Map CRITICAL salience items across the pack before anything else.\n"
        )
    elif artifact_policy.artifact_type == "comparison_one_pager":
        prompt += (
            "Create exactly one static scene for a dense one-pager board.\n"
            "Do not create a narrative sequence or multiple scenes.\n"
            "Use scene_mode='static' and include composition_goal, layout_template, visual_hierarchy, and modules.\n"
            "Convert narrative beats into modules inside one board rather than separate scenes.\n"
            "Turn CRITICAL salience items into mandatory module content, evidence callouts, or synthesis content.\n"
            "Use hook and payload to shape the title, opening impression, and synthesis panel.\n"
            "Use visual_candidates only when their claim_refs align with the selected modules.\n"
            "Choose a layout_template such as modular_poster, editorial_grid, layered_explainer, or radial_overview.\n"
            "Create a board with 4 to 7 modules such as hook_header, core_module, evidence_callout, process_strip, definition_box, data_panel, or synthesis_panel.\n"
            "Keep narration_focus centered on how to read the board and what takeaway it lands, not on voiceover progression.\n"
            "Ensure visual_prompt describes one composed poster canvas with clear module zones, visual hierarchy, and a strong synthesis area.\n"
            "Prefer dense structure and readability over dramatic progression.\n"
            "Do not rely on dense tiny text inside the image; use clear zones, containers, icons, charts, diagrams, and strong layout instead.\n"
        )
    elif artifact_policy.artifact_type == "slide_thumbnail":
        prompt += (
            "Create a single static thumbnail concept, not a storyboard sequence.\n"
            "Do not create multiple scenes unless a variant is explicitly required.\n"
            "Use scene_mode='static' and include composition_goal, layout_template, focal_subject, crop_safe_regions, and visual_hierarchy.\n"
            "Choose one dominant hook and one dominant focal subject rather than spreading across multiple beats or claims.\n"
            "Use the strongest bait or hook as the thumbnail anchor.\n"
            "Use threat only if it sharpens curiosity without fabricating drama.\n"
            "Use reward only if it implies a clear payoff at a glance.\n"
            "Design for instant readability at small size.\n"
            "Reserve a clean headline-safe area and ensure strong crop safety.\n"
            "Favor silhouette clarity, contrast, one hero subject, and one supporting context cue.\n"
            "Avoid dense informational layouts, multi-panel structures, or poster-like composition.\n"
            "Keep the title short, punchy, and headline-like rather than explanatory.\n"
            "Ensure visual_prompt describes one bold hero frame with a clear focal hierarchy and click-through energy.\n"
        )
    elif artifact_policy.artifact_type == "technical_infographic":
        prompt += (
            "Create a static technical infographic plan. Use one scene unless overview plus detail is clearly necessary.\n"
            "Use scene_mode='static' and include composition_goal, layout_template, and visual_hierarchy.\n"
            "Threat and reward framing should be ignored unless they are directly explanatory and source-grounded.\n"
        )
    elif artifact_policy.artifact_type == "process_diagram":
        prompt += (
            "Create a static process-map plan. Use one scene unless overview plus detail is clearly necessary.\n"
            "Use scene_mode='static' and include composition_goal, layout_template, flow_steps, and visual_hierarchy.\n"
            "Prioritize ordered process logic over suspense framing.\n"
        )

    if must_include:
        prompt += f"Must include: {', '.join(must_include)}.\n"
    if must_avoid:
        prompt += f"Must avoid: {', '.join(must_avoid)}.\n"
    if repair_directives:
        prompt += f"{repair_directives}\n"
    return prompt


def compile_script_pack(
    *,
    plan_id: str,
    thesis: str,
    audience_descriptor: str,
    scenes: list[ScenePlanSchema],
    must_include: list[str],
    must_avoid: list[str],
    artifact_policy: ArtifactPlanningPolicy,
    scene_budget_reason: str,
) -> ScriptPack:
    script_scenes: list[ScriptPackScene] = []

    for idx, scene in enumerate(scenes, start=1):
        scene_id = normalized_scene_id(scene.scene_id, idx)
        title = (scene.title or f"Scene {idx}").strip()
        narration_focus = (scene.narration_focus or f"Explain core point {idx} about {thesis}.").strip()
        visual_prompt = (
            scene.visual_prompt
            or "Generate a precise educational visual that supports the narration."
        ).strip()
        claim_refs = [ref for ref in scene.claim_refs if isinstance(ref, str) and ref.strip()]
        scene_mode = "static" if artifact_policy.planning_mode != "sequential" else "sequential"
        continuity_refs: list[str] = []
        if idx > 1:
            if scene_mode == "sequential":
                continuity_refs.append(f"Maintain continuity from scene-{idx - 1}.")
            else:
                continuity_refs.append(f"Preserve the same composition language from scene-{idx - 1}.")
        continuity_refs.extend(extract_anchor_terms(title, limit=2))

        min_words, max_words = scene_narration_word_budget(
            scene_mode=scene_mode,
            layout_template=scene.layout_template,
            artifact_type=artifact_policy.artifact_type,
        )
        acceptance_checks = [
            f"Narration is between {min_words} and {max_words} words.",
            "Narration is plain spoken prose with no labels or markdown.",
            "Visual and narration align with the stated scene focus.",
        ]
        if scene_mode == "static":
            acceptance_checks.append("Treat this as a single composed canvas, not a cinematic beat sequence.")
        if artifact_policy.artifact_type == "comparison_one_pager":
            acceptance_checks.append("Keep the one-pager modular structure legible, dense, and publish-ready.")
        if artifact_policy.artifact_type == "slide_thumbnail":
            acceptance_checks.append("Ensure the image reads instantly and stays strong at small size.")
        if artifact_policy.artifact_type in {"technical_infographic", "process_diagram"}:
            acceptance_checks.append("Prioritize structural clarity over dramatic escalation.")
        if must_include:
            acceptance_checks.append(
                f"Prefer these audience cues: {', '.join(must_include[:4])}."
            )
        if must_avoid:
            acceptance_checks.append(
                f"Avoid these patterns: {', '.join(must_avoid[:4])}."
            )

        if scene_mode == "sequential":
            scene_goal = f"Deliver scene {idx} of the explainer clearly for {audience_descriptor}."
        else:
            scene_goal = (
                f"Compose scene {idx} as a single {artifact_policy.script_shape.replace('_', ' ')} "
                f"for {audience_descriptor}."
            )

        script_scenes.append(
            ScriptPackScene(
                scene_id=scene_id,
                title=title,
                scene_goal=scene_goal,
                narration_focus=narration_focus,
                visual_prompt=visual_prompt,
                claim_refs=claim_refs,
                continuity_refs=continuity_refs,
                acceptance_checks=acceptance_checks,
                scene_mode=scene_mode,
                scene_role=scene.scene_role,
                composition_goal=scene.composition_goal,
                layout_template=scene.layout_template
                or default_layout_template(
                    artifact_type=artifact_policy.artifact_type,
                    scene_index=idx,
                    scene_count=len(scenes),
                ),
                focal_subject=scene.focal_subject,
                visual_hierarchy=scene.visual_hierarchy,
                modules=scene.modules,
                comparison_axes=scene.comparison_axes,
                flow_steps=scene.flow_steps,
                crop_safe_regions=scene.crop_safe_regions,
                evidence_refs=scene.evidence_refs,
                source_media=scene.source_media,
                render_strategy=scene.render_strategy,
            )
        )

    if artifact_policy.planning_mode == "sequential":
        plan_summary = f"{thesis} explained through {len(script_scenes)} cohesive scenes."
    elif artifact_policy.artifact_type == "comparison_one_pager":
        plan_summary = f"{thesis} organized into a single one-pager board."
    elif artifact_policy.artifact_type == "slide_thumbnail":
        plan_summary = f"{thesis} condensed into {len(script_scenes)} thumbnail concept."
    elif artifact_policy.artifact_type == "technical_infographic":
        plan_summary = f"{thesis} structured as a technical infographic."
    else:
        plan_summary = f"{thesis} mapped as a static process-focused explainer."

    return ScriptPack(
        plan_id=plan_id,
        plan_summary=plan_summary,
        audience_descriptor=audience_descriptor,
        scene_count=len(script_scenes),
        artifact_type=artifact_policy.artifact_type,
        planning_mode=artifact_policy.planning_mode,
        script_shape=artifact_policy.script_shape,
        scene_budget_reason=scene_budget_reason,
        salience_mode=artifact_policy.salience_pass,
        forward_pull_mode=artifact_policy.forward_pull_pass,
        scenes=script_scenes,
    )


def outline_to_script_pack(
    *,
    outline_text: str,
    scene_count: int,
    thesis: str,
    audience_descriptor: str,
    artifact_policy: ArtifactPlanningPolicy,
    claim_ids: list[str],
    must_include: list[str],
    must_avoid: list[str],
    scene_budget_reason: str,
) -> ScriptPack:
    parsed_outline = OutlineSchema.model_validate_json(outline_text)
    scenes = normalize_scene_plans(
        parsed_scenes=parsed_outline.scenes,
        target_scene_count=scene_count,
        thesis=thesis,
        artifact_policy=artifact_policy,
        claim_ids=claim_ids,
    )
    return compile_script_pack(
        plan_id=f"script-pack-{int(time.time())}",
        thesis=thesis,
        audience_descriptor=audience_descriptor,
        scenes=scenes,
        must_include=must_include,
        must_avoid=must_avoid,
        artifact_policy=artifact_policy,
        scene_budget_reason=scene_budget_reason,
    )
