"""Validated skill builder (Phase 4A).

Turns Phase 3's validated structured claims (`generation.py`'s `{"claims": [...]}`
contract) plus the statistics/evidence bundles that grounded them into an installable
Claude Code skill. This module:

- never generates skill content from unvalidated Markdown -- its only inputs are
  claims.json, statistics.json, and evidence.json, all three of which it re-validates
  itself rather than trusting a caller's prior validation run
- makes no LLM or network calls -- it is pure Python string/JSON manipulation over
  already-generated files
- is deterministic: identical inputs (including `generated_at`, if pinned) produce a
  byte-identical build, verified by `content_hash` on the manifest separately from the
  non-deterministic default timestamp
- fails closed: mismatched corpus hashes, wrong schema versions, invalid claims, or a
  claim with no venue attribution in a multi-family build all raise before anything is
  written to `output_dir`
- writes atomically: all output is built in a private temp directory, self-validated,
  and only then swapped into `output_dir` -- a build that raises at any point during
  construction or self-validation leaves `output_dir` exactly as it was before the call
  (see `_atomic_swap`)

See `venue_resolution.py` for the runtime venue-lookup half of this design, and
`docs/skill_building.md` for the end-to-end workflow.
"""

from __future__ import annotations

import json
import os
import shutil
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from paperscope import __version__ as PAPERSCOPE_VERSION
from paperscope import generation as generation_mod
from paperscope import venue_resolution
from paperscope.config import (
    EVIDENCE_SCHEMA_VERSION,
    GENERATION_SCHEMA_VERSION,
    SKILL_NAME,
    SKILL_SCHEMA_VERSION,
    STATS_SCHEMA_VERSION,
)
from paperscope.models import content_hash

GENERIC_UNCALIBRATED = venue_resolution.GENERIC_UNCALIBRATED

# Well-known full names for the venue-family abbreviations already registered in
# config.py's VENUE_GROUPS. Applied automatically to whichever families a given build
# actually covers -- a family absent from the built statistics/evidence never appears in
# the manifest regardless of what's listed here, so this can't advertise an unsupported
# venue on its own (see `_build_manifest`).
KNOWN_VENUE_ALIASES: dict[str, tuple[str, ...]] = {
    "iclr": ("International Conference on Learning Representations",),
    "neurips": ("NeurIPS", "Conference on Neural Information Processing Systems", "NIPS"),
    "icml": ("International Conference on Machine Learning",),
    "cvpr": ("Conference on Computer Vision and Pattern Recognition",),
    "acl": ("Association for Computational Linguistics",),
    "aaai": ("Association for the Advancement of Artificial Intelligence",),
    "kdd": ("Knowledge Discovery and Data Mining",),
}

REVIEW_MODES: dict[str, dict] = {
    "quick": {
        "required_input": "Paper title + abstract",
        "optional_input": "Target venue name",
        "output_depth": (
            "A short calibration snapshot: which accept/reject signals from the loaded "
            "venue reference plausibly apply based on the abstract alone. Not a full review."
        ),
        "limitations": (
            "Abstract-only input cannot support technical-validity, experimental-rigor, "
            "or novelty findings -- those sections are omitted, not guessed at.",
            "Never presented as equivalent to a full-paper review.",
        ),
    },
    "full": {
        "required_input": "Full paper text",
        "optional_input": "Supplementary material, target venue name",
        "output_depth": (
            "Complete structured review: contribution audit, novelty, technical "
            "validity, experimental assessment, strengths/weaknesses, questions for "
            "authors, and a venue-calibrated score with justification."
        ),
        "limitations": (
            "Novelty/related-work claims require an actual literature-search step when "
            "search access exists; otherwise state explicitly that novelty relative to "
            "the literature was not verified. Never invent a closest prior work.",
            "Without supplementary material, state which checks (proofs, extended "
            "results, appendix claims) could not be performed.",
        ),
    },
    "rebuttal": {
        "required_input": "Full paper text + author rebuttal text",
        "optional_input": "Original reviews being responded to, supplementary material",
        "output_depth": (
            "Assessment of whether the rebuttal addresses the reviewed concerns, "
            "grounded only in the loaded venue reference's Rebuttal Effectiveness "
            "section when it contains a non-insufficient-evidence claim."
        ),
        "limitations": (
            "Never states a rebuttal-effectiveness pattern unless the loaded reference "
            "has a validated claim to that effect for the resolved venue -- if that "
            "section is insufficient-evidence, say so instead of falling back to intuition.",
            "Does not predict a specific score change -- only whether named concerns "
            "were addressed.",
        ),
    },
}

INPUT_TIERS: tuple[dict, ...] = (
    {
        "label": "Title + abstract only",
        "note": "Sufficient only for quick mode's calibration snapshot. Never treated as equivalent to a full-paper review.",
    },
    {"label": "Full paper text", "note": "Required for full mode."},
    {
        "label": "Paper + supplementary material",
        "note": "Extends full mode: proofs, extended results, and appendix-only claims become assessable.",
    },
    {"label": "Paper + author rebuttal", "note": "Required for rebuttal mode."},
)

# Fragments lifted from the pre-redesign skill/SKILL.md (now archived under
# references/legacy/) that must never reappear in generated SKILL.md or reference
# content. Matched case-insensitively as substrings against everything except
# references/legacy/*, which is explicitly exempt (see `validate_skill`).
FORBIDDEN_PHRASES: tuple[str, ...] = (
    "area-chair-level experience",
    "actual distribution of accepted",
    "apply iclr conventions as a neutral default",
)


class SkillBuildError(ValueError):
    """Raised when a build cannot proceed -- fail closed, nothing is written."""


@dataclass
class SkillValidationReport:
    violations: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


# --------------------------------------------------------------------------------------
# claims -> per-family attribution
# --------------------------------------------------------------------------------------


def _ref_family(ref: str) -> str | None:
    parts = ref.split("/")
    return parts[0] if len(parts) == 3 and parts[0] else None


def _families_in_scope(statistics_payload: dict, evidence_payload: dict) -> set[str]:
    fams = {s["venue_family"] for s in statistics_payload.get("stats", [])}
    fams |= {i["venue_family"] for i in evidence_payload.get("items", [])}
    return fams


def _assign_claims_to_families(
    claims: list[dict], evidence_by_id: dict, families_in_scope: set[str]
) -> dict[str, list[dict]]:
    by_family: dict[str, list[dict]] = {f: [] for f in families_in_scope}
    errors: list[str] = []

    for claim in claims:
        fams: set[str] = set()
        for ref in claim.get("statistic_refs", []):
            fam = _ref_family(ref)
            if fam:
                fams.add(fam)
        for eid in claim.get("evidence_ids", []):
            item = evidence_by_id.get(eid)
            if item:
                fams.add(item["venue_family"])
        fams &= families_in_scope

        if not fams:
            if len(families_in_scope) == 1:
                fams = set(families_in_scope)
            else:
                errors.append(
                    f"{claim.get('claim_id', '<unknown>')}: has no evidence_ids/statistic_refs "
                    f"tying it to a specific venue family, and this build spans multiple "
                    f"families {sorted(families_in_scope)} -- ambiguous attribution"
                )
                continue

        for fam in fams:
            by_family[fam].append(claim)

    if errors:
        raise SkillBuildError("; ".join(errors))
    return by_family


# --------------------------------------------------------------------------------------
# calibration metadata (deterministic facts derived from statistics.json -- not claims)
# --------------------------------------------------------------------------------------


def _family_calibration_metadata(family: str, statistics_payload: dict) -> dict:
    stats = [s for s in statistics_payload.get("stats", []) if s["venue_family"] == family]
    years = sorted({s["venue_year"] for s in stats if s["venue_year"] != "all"}, key=str)

    def agg(metric: str):
        return next((s for s in stats if s["venue_year"] == "all" and s["metric"] == metric), None)

    forum_count_stat = agg("forum_count")
    review_count_stat = agg("review_count")
    decision_stat = agg("decision_distribution")

    forum_count = forum_count_stat["value"] if forum_count_stat else None
    review_count = review_count_stat["value"] if review_count_stat else None
    decisions_resolved = 0
    if decision_stat:
        decisions_resolved = sum(v for k, v in decision_stat["value"].items() if k != "unknown")

    preliminary = (forum_count is not None and forum_count < 50) or len(years) < 2
    return {
        "years_covered": years,
        "forum_count": forum_count,
        "review_count": review_count,
        "decisions_resolved": decisions_resolved,
        "preliminary": preliminary,
    }


# --------------------------------------------------------------------------------------
# per-family reference rendering
# --------------------------------------------------------------------------------------


def render_family_reference(
    family: str,
    claims: list[dict],
    statistics_payload: dict,
    evidence_payload: dict,
    *,
    corpus_hash: str,
) -> str:
    """Renders one venue's calibration reference from already-validated claims only.
    Deterministic: sorted claim order within each section, no timestamp embedded.
    """
    meta = _family_calibration_metadata(family, statistics_payload)
    evidence_by_id = {i["evidence_id"]: i for i in evidence_payload.get("items", [])}

    preliminary_note = (
        "This calibration is based on a small and/or single-year sample -- treat every "
        "claim below as a starting hypothesis, not an established venue norm."
        if meta["preliminary"]
        else "Based on a larger, multi-year sample."
    )

    lines = [
        f"# {family.upper()} venue calibration reference",
        "",
        "**Generated, not hand-written.** Every claim below is machine-validated against "
        "`statistics.json`/`evidence.json` from a real OpenReview corpus by "
        "`paperscope build-skill` (`src/paperscope/skill_builder.py`) -- nothing here was "
        "authored freehand, and a claim only appears if it passed the same structured "
        "validation as `paperscope render` (see `docs/generation.md`).",
        "",
        f"**Preliminary: {'yes' if meta['preliminary'] else 'no'}.** {preliminary_note}",
        "",
        "## Calibration sample",
        "",
        f"- Years covered: {meta['years_covered'] or '(none)'}",
        f"- Forums in sample: {meta['forum_count']}",
        f"- Reviews in sample: {meta['review_count']}",
        f"- Forums with a resolved accept/reject decision: {meta['decisions_resolved']}",
        f"- Source corpus hash: `{corpus_hash}`",
        "",
        "This file makes no accept/reject calibration claim beyond what "
        "`decisions_resolved` above supports -- if that count is 0, nothing below states "
        "or implies an acceptance rate or a score-to-decision threshold.",
        "",
    ]

    by_section: dict[str, list[dict]] = {}
    for claim in claims:
        by_section.setdefault(claim["section"], []).append(claim)

    for section in generation_mod.SECTIONS:
        section_claims = by_section.get(section)
        lines.append(f"## {section.replace('_', ' ').title()}")
        lines.append("")
        if not section_claims:
            lines.append(
                "_Insufficient evidence: no validated claim was generated for this "
                "section from the current corpus._"
            )
            lines.append("")
            continue
        for claim in sorted(section_claims, key=lambda c: c["claim_id"]):
            type_label = generation_mod.CLAIM_TYPE_LABELS.get(claim["claim_type"], claim["claim_type"])
            lines.append(f"### `{claim['claim_id']}` — {type_label}")
            lines.append("")
            lines.append(claim["text"])
            lines.append("")
            lines.append(f"- **Support level:** {claim['support_level']}")
            lines.append(f"- **Year scope:** {claim['year_scope'] or '(none)'}")
            if claim["evidence_ids"]:
                lines.append("- **Evidence:**")
                for eid in claim["evidence_ids"]:
                    item = evidence_by_id.get(eid)
                    if item is None:
                        continue
                    lines.append(f"  - forum `{item['forum_id']}`, note `{item['note_id']}` — {item['source_url']}")
            if claim["statistic_refs"]:
                lines.append("- **Statistics:** " + ", ".join(f"`{r}`" for r in claim["statistic_refs"]))
            lines.append("- **Limitations:**")
            for lim in claim["limitations"]:
                lines.append(f"  - {lim}")
            lines.append("")

    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------------------
# manifest
# --------------------------------------------------------------------------------------

REQUIRED_MANIFEST_CONTENT_KEYS: tuple[str, ...] = (
    "skill_schema_version",
    "paperscope_version",
    "supported_venue_families",
    "venues",
    "unsupported_mode",
    "corpus_hash",
    "statistics_hash",
    "evidence_bundle_hash",
    "claims_hash",
    "source_schema_versions",
)


def _build_manifest(
    *,
    families_in_scope: set[str],
    claims_by_family: dict[str, list[dict]],
    statistics_payload: dict,
    evidence_payload: dict,
    reference_hashes: dict[str, str],
    corpus_hash: str,
    statistics_hash: str,
    evidence_bundle_hash: str,
    claims_hash: str,
    generated_at: str,
) -> dict:
    venues: dict[str, dict] = {}
    for family in sorted(families_in_scope):
        meta = _family_calibration_metadata(family, statistics_payload)
        evidence_count = sum(1 for i in evidence_payload.get("items", []) if i["venue_family"] == family)
        venues[family] = {
            "reference": f"references/{family}.md",
            "reference_hash": reference_hashes[family],
            "aliases": list(KNOWN_VENUE_ALIASES.get(family, ())),
            "years_covered": meta["years_covered"],
            "forum_count": meta["forum_count"],
            "review_count": meta["review_count"],
            "evidence_count": evidence_count,
            "decisions_resolved": meta["decisions_resolved"],
            "claim_count": len(claims_by_family.get(family, [])),
            "preliminary": meta["preliminary"],
        }

    content = {
        "skill_schema_version": SKILL_SCHEMA_VERSION,
        "paperscope_version": PAPERSCOPE_VERSION,
        "supported_venue_families": sorted(families_in_scope),
        "venues": venues,
        "unsupported_mode": GENERIC_UNCALIBRATED,
        "corpus_hash": corpus_hash,
        "statistics_hash": statistics_hash,
        "evidence_bundle_hash": evidence_bundle_hash,
        "claims_hash": claims_hash,
        "source_schema_versions": {
            "stats": STATS_SCHEMA_VERSION,
            "evidence": EVIDENCE_SCHEMA_VERSION,
            "generation": GENERATION_SCHEMA_VERSION,
        },
    }
    return {
        "content": content,
        "content_hash": content_hash(json.dumps(content, sort_keys=True)),
        "generated_at": generated_at,
    }


# --------------------------------------------------------------------------------------
# SKILL.md rendering
# --------------------------------------------------------------------------------------


def _wrap(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width) or [""]


def render_skill_md(manifest_content: dict) -> str:
    families = manifest_content["supported_venue_families"]
    families_csv = ", ".join(families) if families else "(none yet)"

    description = (
        "A venue-calibrated ML paper reviewer built from validated, evidence-traced "
        "claims generated from real OpenReview peer-review data. Use when the user "
        "wants to review, critique, evaluate, or grade an ML/AI research paper. "
        f"Supports only the venues listed in manifest.json's supported_venue_families -- "
        f"currently: {families_csv}. For any other venue, or when none is named, this "
        f"skill runs in {GENERIC_UNCALIBRATED} mode: general reviewing judgment only, "
        "explicitly not calibrated to that venue's real review patterns. Load "
        "manifest.json first to see which venue references actually exist before "
        "claiming a venue-specific calibration."
    )

    frontmatter_lines = [
        "---",
        f"name: {SKILL_NAME}",
        "description: >",
        *(f"  {line}" for line in _wrap(description, 88)),
        "metadata:",
        f'  paperscope_skill_schema_version: "{manifest_content["skill_schema_version"]}"',
        f'  supported_venue_families: "{families_csv}"',
        "---",
        "",
    ]

    mode_rows = "\n".join(
        f"| {name} | {m['required_input']} | {m['optional_input']} | {m['output_depth']} |"
        for name, m in REVIEW_MODES.items()
    )
    mode_limitation_blocks = "\n\n".join(
        f"**{name}**:\n" + "\n".join(f"- {lim}" for lim in m["limitations"])
        for name, m in REVIEW_MODES.items()
    )
    tier_rows = "\n".join(f"| {t['label']} | {t['note']} |" for t in INPUT_TIERS)

    body_lines = [
        "# PaperScope reviewer",
        "",
        "This skill packages **validated, evidence-traced** venue-calibration claims -- "
        "generated by `paperscope build-skill` from real OpenReview review data, never "
        "hand-written and never LLM free-text. See `manifest.json` for the exact "
        "provenance (corpus/statistics/evidence/claims hashes, sample sizes, years "
        "covered) behind every reference file in `references/`.",
        "",
        "## What this skill does NOT do",
        "",
        "- It does not claim deep committee-chair reviewing seniority or promise to "
        "reproduce real reviewer behavior exactly -- every claim in a venue reference is "
        "one of: a deterministic fact, an observed statistical pattern, a verbatim "
        "evidence excerpt, a model interpretation, or an explicit insufficient-evidence "
        "statement. Read a claim's `claim_type` and `support_level` before treating it "
        "as established.",
        "- It does not claim to know the true accept/reject rate or score distribution "
        "for any venue unless a reference's calibration sample has resolved decisions -- "
        "check `decisions_resolved` in `manifest.json` before stating an acceptance "
        "threshold.",
        "- It never silently substitutes another venue's conventions (for example "
        "ICLR's) when the requested venue is unsupported. Unsupported venues get "
        f"`{GENERIC_UNCALIBRATED}` mode, stated explicitly to the user.",
        "- `references/legacy/` contains archival, hand-written, unverified calibration "
        "notes from before this skill was redesigned. **Never load anything from "
        "`references/legacy/` as part of a review** -- it exists for historical "
        "continuity only and was never validated against the claim schema this skill "
        "now requires.",
        "",
        "## Step 0 -- resolve the venue, then load its reference",
        "",
        "1. Read `manifest.json`. Its `content.venues` map is the *only* source of "
        "truth for which venue families have a validated reference and where it lives.",
        "2. Match the user's stated venue (exact family name or a declared alias in "
        "`manifest.json`) against `content.venues`.",
        "   - **Exact match to one family** -> load `references/<family>.md`. This is "
        "`supported` mode.",
        f"   - **No match** -> `{GENERIC_UNCALIBRATED}` mode (below). Never substitute a "
        "different venue's reference.",
        "   - **Matches more than one family** (should not happen if the manifest is "
        "valid -- `paperscope validate-skill` checks for alias collisions) -> ask the "
        "user to clarify which venue they mean rather than guessing.",
        "3. State which mode you're in before writing any review content.",
        "",
        f"### `{GENERIC_UNCALIBRATED}` mode",
        "",
        "Used whenever the venue is unstated, unrecognized, or not yet in "
        "`manifest.json`. Apply general ML-reviewing judgment only. Tell the user "
        'explicitly: "No venue-calibrated reference is available for <venue> -- this '
        'review uses general reviewing judgment, not data calibrated to that venue\'s '
        'real review patterns." Never silently apply another venue\'s conventions.',
        "",
        "## Step 1 -- pick a review mode",
        "",
        "| Mode | Required input | Optional input | Output depth |",
        "|---|---|---|---|",
        mode_rows,
        "",
        "Per-mode limitations:",
        "",
        mode_limitation_blocks,
        "",
        "Input tiers (never treat a lower tier as equivalent to a higher one):",
        "",
        "| Tier | Note |",
        "|---|---|",
        tier_rows,
        "",
        "## Step 2 -- write the review",
        "",
        "Structure the review around the loaded venue reference's sections (Score "
        "Calibration, Accept Signals, Reject Signals, Hidden Criteria, Reviewer "
        "Language Patterns, Year Over Year Drift, Rebuttal Effectiveness). For any "
        'section marked "Insufficient evidence" in the loaded reference, say so '
        "explicitly rather than filling the gap with generic intuition presented as "
        "calibrated.",
        "",
        "### Novelty and related-work claims",
        "",
        "- If you have literature-search access, use it before making a novelty claim "
        "-- name the specific prior work found and how the paper differs from it.",
        "- If you do not have literature-search access, state explicitly that novelty "
        "relative to the literature was not verified. **Never invent a closest-prior-"
        "work citation.**",
        "",
        "### Rebuttal mode specifics",
        "",
        "Only state a rebuttal-effectiveness pattern if the loaded reference's "
        "`Rebuttal Effectiveness` section contains a non-insufficient-evidence claim "
        "for the resolved venue. Otherwise say plainly that no rebuttal-effectiveness "
        "pattern is supported by the current data.",
        "",
        "## Provenance",
        "",
        "Every fact in `references/<family>.md` traces to `manifest.json`'s recorded "
        "`corpus_hash` / `statistics_hash` / `evidence_bundle_hash` / `claims_hash`. Run "
        "`paperscope validate-skill --path <this directory>` to re-verify those hashes "
        "and the manifest's internal consistency at any time.",
        "",
    ]

    return "\n".join(frontmatter_lines) + "\n".join(body_lines) + "\n"


# --------------------------------------------------------------------------------------
# frontmatter parsing (minimal, sufficient for our own generator's output -- not a
# general YAML parser)
# --------------------------------------------------------------------------------------


def _parse_frontmatter_block(fm_text: str) -> dict:
    result: dict = {}
    lines = fm_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line or line[0] in " \t" or ":" not in line:
            i += 1
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest in (">", "|"):
            block: list[str] = []
            i += 1
            while i < len(lines) and (lines[i].startswith("  ") or not lines[i].strip()):
                block.append(lines[i][2:] if lines[i].startswith("  ") else "")
                i += 1
            result[key] = " ".join(x.strip() for x in block if x.strip())
            continue
        result[key] = rest.strip('"')
        i += 1
    return result


def split_frontmatter(text: str) -> tuple[dict | None, str]:
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, text
    return _parse_frontmatter_block(text[4:end]), text[end + 5 :]


# --------------------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------------------


def _load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def _check_schema_versions(statistics_payload: dict, evidence_payload: dict) -> None:
    errors = []
    if statistics_payload.get("schema_version") != STATS_SCHEMA_VERSION:
        errors.append(
            f"statistics schema_version {statistics_payload.get('schema_version')!r} "
            f"!= expected {STATS_SCHEMA_VERSION}"
        )
    if evidence_payload.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        errors.append(
            f"evidence schema_version {evidence_payload.get('schema_version')!r} "
            f"!= expected {EVIDENCE_SCHEMA_VERSION}"
        )
    if errors:
        raise SkillBuildError("; ".join(errors))


def _write_skill_tree(
    tmp_dir: Path,
    *,
    statistics_payload: dict,
    evidence_payload: dict,
    claims_by_family: dict[str, list[dict]],
    families_in_scope: set[str],
    corpus_hash: str,
    claims_hash: str,
    statistics_hash: str,
    evidence_bundle_hash: str,
    generated_at: str,
) -> None:
    references_dir = tmp_dir / "references"
    references_dir.mkdir(parents=True, exist_ok=True)

    reference_hashes: dict[str, str] = {}
    for family in sorted(families_in_scope):
        md = render_family_reference(
            family, claims_by_family.get(family, []), statistics_payload, evidence_payload,
            corpus_hash=corpus_hash,
        )
        path = references_dir / f"{family}.md"
        path.write_text(md)
        reference_hashes[family] = content_hash(md)

    manifest = _build_manifest(
        families_in_scope=families_in_scope,
        claims_by_family=claims_by_family,
        statistics_payload=statistics_payload,
        evidence_payload=evidence_payload,
        reference_hashes=reference_hashes,
        corpus_hash=corpus_hash,
        statistics_hash=statistics_hash,
        evidence_bundle_hash=evidence_bundle_hash,
        claims_hash=claims_hash,
        generated_at=generated_at,
    )
    (tmp_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    (tmp_dir / "SKILL.md").write_text(render_skill_md(manifest["content"]))


def _copy_legacy_forward(existing_output_dir: Path, tmp_dir: Path) -> None:
    """Carries `references/legacy/` forward unchanged across rebuilds. It is never
    generated or modified by the builder -- see the module docstring and
    `docs/skill_building.md`'s legacy-isolation section.
    """
    existing_legacy = Path(existing_output_dir) / "references" / "legacy"
    if existing_legacy.is_dir():
        shutil.copytree(existing_legacy, tmp_dir / "references" / "legacy")


def _atomic_swap(tmp_dir: Path, output_dir: Path) -> None:
    if not output_dir.exists():
        os.rename(tmp_dir, output_dir)
        return
    backup = output_dir.parent / f"{output_dir.name}.prev{os.getpid()}"
    if backup.exists():
        shutil.rmtree(backup)
    os.rename(output_dir, backup)
    try:
        os.rename(tmp_dir, output_dir)
    except Exception:
        os.rename(backup, output_dir)
        raise
    else:
        shutil.rmtree(backup, ignore_errors=True)


def build_skill(
    *,
    claims_path: Path,
    statistics_path: Path,
    evidence_path: Path,
    output_dir: Path,
    generated_at: str | None = None,
) -> dict:
    """Builds a validated skill at `output_dir` from Phase 3 claims/statistics/evidence.
    Returns the written manifest.json payload. Raises `SkillBuildError` /
    `generation.GenerationValidationError` and leaves `output_dir` untouched on failure
    -- see the module docstring for the full fail-closed/atomicity contract.
    """
    claims_payload = _load_json(claims_path)
    statistics_payload = _load_json(statistics_path)
    evidence_payload = _load_json(evidence_path)

    _check_schema_versions(statistics_payload, evidence_payload)

    stats_corpus_hash = statistics_payload.get("corpus_hash")
    evidence_corpus_hash = evidence_payload.get("corpus_hash")
    if not stats_corpus_hash or stats_corpus_hash != evidence_corpus_hash:
        raise SkillBuildError(
            "statistics and evidence inputs come from different corpora "
            f"(corpus_hash {stats_corpus_hash!r} != {evidence_corpus_hash!r})"
        )

    # Re-validate: never trust a claims file just because it parses as JSON, even if it
    # claims to already be validated.
    generation_mod.validate_claims(
        claims_payload, statistics_payload=statistics_payload, evidence_payload=evidence_payload
    )

    families_in_scope = _families_in_scope(statistics_payload, evidence_payload)
    if not families_in_scope:
        raise SkillBuildError("statistics/evidence contain no venue_family scope -- nothing to build")

    evidence_by_id = {i["evidence_id"]: i for i in evidence_payload.get("items", [])}
    claims_by_family = _assign_claims_to_families(claims_payload["claims"], evidence_by_id, families_in_scope)

    generated_at = generated_at or generation_mod.iso_now()
    claims_hash = content_hash(json.dumps(claims_payload, sort_keys=True))
    statistics_hash = content_hash(json.dumps(statistics_payload.get("stats", []), sort_keys=True))
    evidence_bundle_hash = evidence_payload.get("bundle_hash") or content_hash(
        *sorted(i["evidence_id"] for i in evidence_payload.get("items", []))
    )

    output_dir = Path(output_dir)
    tmp_dir = output_dir.parent / f"{output_dir.name}.tmp{os.getpid()}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)

    try:
        _write_skill_tree(
            tmp_dir,
            statistics_payload=statistics_payload,
            evidence_payload=evidence_payload,
            claims_by_family=claims_by_family,
            families_in_scope=families_in_scope,
            corpus_hash=stats_corpus_hash,
            claims_hash=claims_hash,
            statistics_hash=statistics_hash,
            evidence_bundle_hash=evidence_bundle_hash,
            generated_at=generated_at,
        )
        _copy_legacy_forward(output_dir, tmp_dir)
        report = validate_skill(tmp_dir)
        if not report.ok:
            raise SkillBuildError("built skill failed self-validation: " + "; ".join(report.violations))
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

    _atomic_swap(tmp_dir, output_dir)
    return _load_json(output_dir / "manifest.json")


# --------------------------------------------------------------------------------------
# validate
# --------------------------------------------------------------------------------------


def _validate_manifest_schema(manifest: dict) -> list[str]:
    errors: list[str] = []
    if "content" not in manifest or "content_hash" not in manifest or "generated_at" not in manifest:
        return ["manifest.json missing top-level content/content_hash/generated_at"]

    content = manifest["content"]
    for key in REQUIRED_MANIFEST_CONTENT_KEYS:
        if key not in content:
            errors.append(f"manifest.json content missing required key {key!r}")

    recomputed = content_hash(json.dumps(content, sort_keys=True))
    if recomputed != manifest.get("content_hash"):
        errors.append("manifest.json content_hash does not match its own content (tampered manifest)")

    if content.get("skill_schema_version") != SKILL_SCHEMA_VERSION:
        errors.append(
            f"manifest skill_schema_version {content.get('skill_schema_version')!r} "
            f"!= expected {SKILL_SCHEMA_VERSION}"
        )
    return errors


def validate_skill(path: Path) -> SkillValidationReport:
    """Collects every violation found rather than stopping at the first -- see the CLI's
    `paperscope validate-skill` for the reporting surface.
    """
    path = Path(path)
    violations: list[str] = []

    skill_md_path = path / "SKILL.md"
    manifest_path = path / "manifest.json"

    if not skill_md_path.exists():
        violations.append("missing SKILL.md")
    if not manifest_path.exists():
        violations.append("missing manifest.json")
    if violations:
        return SkillValidationReport(violations)

    skill_md_text = skill_md_path.read_text()
    frontmatter, body = split_frontmatter(skill_md_text)
    if frontmatter is None:
        violations.append("SKILL.md has no valid frontmatter block")
        frontmatter = {}

    name = frontmatter.get("name")
    if name != SKILL_NAME:
        violations.append(f"SKILL.md frontmatter name {name!r} != expected {SKILL_NAME!r}")
    description = frontmatter.get("description")
    if not description or not str(description).strip():
        violations.append("SKILL.md frontmatter missing non-empty description")
    elif len(str(description)) > 1024:
        violations.append("SKILL.md frontmatter description exceeds 1024 chars")

    manifest = None
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as e:
        violations.append(f"manifest.json is not valid JSON: {e}")

    if manifest is not None:
        violations.extend(_validate_manifest_schema(manifest))
        content = manifest.get("content", {})
        venues = content.get("venues", {})

        supported = set(content.get("supported_venue_families", []))
        if supported != set(venues.keys()):
            violations.append("supported_venue_families does not match venues map keys")

        for family, entry in sorted(venues.items()):
            ref_rel = entry.get("reference", "")
            if not ref_rel or "legacy" in Path(ref_rel).parts:
                violations.append(f"venue {family!r} manifest reference points into legacy/: {ref_rel!r}")
                continue
            ref_path = path / ref_rel
            if not ref_path.exists():
                violations.append(f"venue {family!r} declares reference {ref_rel!r} which does not exist")
                continue
            text = ref_path.read_text()
            actual_hash = content_hash(text)
            if actual_hash != entry.get("reference_hash"):
                violations.append(
                    f"venue {family!r} reference hash mismatch (tampered or stale): "
                    f"expected {entry.get('reference_hash')!r}, got {actual_hash!r}"
                )
            if entry.get("forum_count") is None:
                violations.append(f"venue {family!r} manifest missing forum_count calibration metadata")
            expected_corpus_marker = f"`{content.get('corpus_hash')}`"
            if expected_corpus_marker not in text:
                violations.append(f"venue {family!r} reference does not embed the manifest's corpus_hash")

        violations.extend(f"manifest alias collision: {c}" for c in venue_resolution.find_alias_collisions(venues))

    if GENERIC_UNCALIBRATED not in skill_md_text:
        violations.append(f"SKILL.md does not define {GENERIC_UNCALIBRATED} (unsupported-venue) mode")

    lowered_body = skill_md_text.lower()
    for mode_name in REVIEW_MODES:
        if mode_name not in lowered_body:
            violations.append(f"SKILL.md does not mention required review mode {mode_name!r}")

    scanned_text = skill_md_text
    references_dir = path / "references"
    if references_dir.exists():
        for md_file in sorted(references_dir.glob("*.md")):  # non-recursive: skips legacy/
            scanned_text += "\n" + md_file.read_text()
    lowered_scanned = scanned_text.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lowered_scanned:
            violations.append(f"forbidden overclaim phrase found: {phrase!r}")

    return SkillValidationReport(violations=violations)
