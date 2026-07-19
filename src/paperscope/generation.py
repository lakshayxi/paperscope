"""Evidence-grounded structured generation and deterministic rendering (Phase 3B).

The model's *only* output contract is structured JSON (a `{"claims": [...]}` object
matching `response_schema()`), never free-text Markdown -- see `docs/generation.md` for
the full workflow. This module never validates or renders prose; it validates JSON
claims against the statistics/evidence bundles that grounded them, and only a separately
validated claims file may reach the deterministic Markdown renderer.

Primary supported path is manual: `export_prompt()` writes a self-contained bundle
(prompt + statistics + evidence + response schema + manifest) for a human to run through
Claude Code by hand, with the raw JSON response saved back as `claims.json` and then
validated/rendered. `llm_provider.py` (a separate module) is an optional, `anthropic`-
backed automation of just the "ask the model" step. This module (`generation.py`) never
imports `anthropic`, anywhere, so `fetch`/`stats`/`evidence`/`export-prompt`/`render`
never pull it in even transitively -- see tests/test_optional_anthropic.py, which scans
every file in this package for any `anthropic` reference outside `llm_provider.py`.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from paperscope.config import GENERATION_SCHEMA_VERSION
from paperscope.models import content_hash
from paperscope.storage import atomic_write_text

PROMPT_VERSION = "1.0"

# Mirrors skill/references/iclr.md's top-level (## N. ...) section headers, slugified.
# The deterministic renderer groups claims by this field, in this fixed order, rather
# than re-interpreting claim text -- keep in sync if reference-file sections change.
SECTIONS: tuple[str, ...] = (
    "score_calibration",
    "accept_signals",
    "reject_signals",
    "hidden_criteria",
    "reviewer_language_patterns",
    "year_over_year_drift",
    "rebuttal_effectiveness",
)

CLAIM_TYPES: tuple[str, ...] = (
    "deterministic_fact",
    "evidence_excerpt",
    "statistical_pattern",
    "llm_interpretation",
    "insufficient_evidence",
)

# "none" is the valid support_level for insufficient_evidence claims -- there being no
# support is a legitimate, statable outcome, not a validation failure on its own.
SUPPORT_LEVELS: tuple[str, ...] = ("strong", "limited", "single_instance", "none")

_HAS_DIGIT_RE = re.compile(r"\d")
_QUOTE_CHARS = "\"'“”‘’"


class GenerationValidationError(ValueError):
    """Raised with every violation found in a claims payload, one per line."""


def iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# --------------------------------------------------------------------------------------
# statistic_ref resolution: "<venue_family>/<venue_year>/<metric>[.<dotted.path>]"
# venue_year may be "all" to reference the family-wide aggregate scope (statistics.py's
# (family, "all") scope) -- covers every year present for that family, not just one.
# --------------------------------------------------------------------------------------


def _parse_ref(ref: str) -> tuple[str, str, str, str] | None:
    parts = ref.split("/")
    if len(parts) != 3:
        return None
    family, year, metric_and_path = parts
    metric, _, path = metric_and_path.partition(".")
    if not (family and year and metric):
        return None
    return family, year, metric, path


def _index_statistics(statistics_payload: dict) -> dict[tuple[str, str, str], dict]:
    return {
        (s["venue_family"], str(s["venue_year"]), s["metric"]): s
        for s in statistics_payload.get("stats", [])
    }


def _years_by_family(statistics_payload: dict, evidence_payload: dict) -> dict[str, set]:
    years: dict[str, set] = {}
    for s in statistics_payload.get("stats", []):
        if s["venue_year"] != "all":
            years.setdefault(s["venue_family"], set()).add(s["venue_year"])
    for item in evidence_payload.get("items", []):
        if item["venue_year"] != "all":
            years.setdefault(item["venue_family"], set()).add(item["venue_year"])
    return years


def resolve_statistic_ref(ref: str, stats_index: dict) -> tuple[bool, object]:
    """Resolve `ref` against `stats_index` (see `_index_statistics`). Returns
    `(found, value)` -- `found=False` means the ref doesn't resolve, `value` is then
    meaningless. Never raises: an unresolvable ref is data to report, not an exception.
    """
    parsed = _parse_ref(ref)
    if parsed is None:
        return False, None
    family, year, metric, path = parsed
    stat = stats_index.get((family, year, metric))
    if stat is None:
        return False, None
    value = stat["value"]
    if path:
        for key in path.split("."):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return False, None
    return True, value


def _years_covered_by_ref(ref: str, years_by_family: dict[str, set]) -> set:
    parsed = _parse_ref(ref)
    if parsed is None:
        return set()
    family, year, _metric, _path = parsed
    if year == "all":
        return set(years_by_family.get(family, set()))
    try:
        return {int(year)}
    except ValueError:
        return {year}


# --------------------------------------------------------------------------------------
# response schema + prompt export
# --------------------------------------------------------------------------------------


def response_schema() -> dict:
    """JSON Schema for the model's response contract, generated from the same
    SECTIONS/CLAIM_TYPES/SUPPORT_LEVELS constants `validate_claims` checks against, so
    the schema and the validator can't silently drift apart.
    """
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "PaperScope generation response",
        "type": "object",
        "required": ["claims"],
        "additionalProperties": False,
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "claim_id", "section", "claim_type", "text", "evidence_ids",
                        "statistic_refs", "year_scope", "support_level", "limitations",
                    ],
                    "additionalProperties": False,
                    "properties": {
                        "claim_id": {"type": "string", "minLength": 1},
                        "section": {"type": "string", "enum": list(SECTIONS)},
                        "claim_type": {"type": "string", "enum": list(CLAIM_TYPES)},
                        "text": {"type": "string", "minLength": 1},
                        "evidence_ids": {"type": "array", "items": {"type": "string"}},
                        "statistic_refs": {"type": "array", "items": {"type": "string"}},
                        "year_scope": {"type": "array", "items": {"type": "integer"}},
                        "support_level": {"type": "string", "enum": list(SUPPORT_LEVELS)},
                        "limitations": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                    },
                },
            },
        },
    }


def render_prompt(statistics_payload: dict, evidence_payload: dict) -> str:
    """Deterministic: a pure function of its two inputs (no timestamp embedded), so the
    same statistics/evidence pair always produces byte-identical prompt text.
    """
    corpus_hash = statistics_payload.get("corpus_hash", "")
    families = sorted({s["venue_family"] for s in statistics_payload.get("stats", [])})
    scope_lines = []
    for family in families:
        agg = next(
            (s for s in statistics_payload["stats"]
             if s["venue_family"] == family and s["venue_year"] == "all" and s["metric"] == "forum_count"),
            None,
        )
        years = sorted(
            {s["venue_year"] for s in statistics_payload["stats"]
             if s["venue_family"] == family and s["venue_year"] != "all"},
            key=str,
        )
        forum_count = agg["value"] if agg else "unknown"
        scope_lines.append(f"- {family}: {forum_count} forums, years {years}")

    return "\n".join([
        f"# PaperScope generation prompt (v{PROMPT_VERSION})",
        "",
        f"Source corpus hash: `{corpus_hash}`",
        "",
        "## Task",
        "",
        "Using ONLY the data in the accompanying `statistics.json` and `evidence.json` "
        "files (in this same directory), produce venue-calibration claims for a peer-"
        "review reference file. Respond with ONLY a single JSON object matching "
        "`response_schema.json` (also in this directory) -- no Markdown fences, no "
        "commentary before or after it.",
        "",
        "## Corpus scope",
        "",
        *scope_lines,
        "",
        "## Hard constraints",
        "",
        "- Never invent a quotation, excerpt, statistic, or fact not present in "
        "`evidence.json` or `statistics.json`. If you cannot ground a claim, emit an "
        "`insufficient_evidence` claim instead of guessing.",
        "- Every `evidence_excerpt` claim's `text` must be an exact substring of the "
        "`excerpt_text` of one of its cited `evidence_ids`.",
        "- Every claim asserting a number or statistical pattern "
        "(`deterministic_fact` / `statistical_pattern`) must cite at least one "
        "`statistic_refs` entry backing that number -- do not do your own arithmetic.",
        "- `statistic_refs` entries use the format "
        '`"<venue_family>/<venue_year_or_all>/<metric>[.<dotted.path.into.value>]"`, '
        "e.g. `\"iclr/2026/paper_mean_rating.mean\"` or `\"iclr/all/forum_count\"` -- "
        "must resolve to a real entry in `statistics.json`.",
        "- `year_scope` must not exceed what your cited `evidence_ids`/`statistic_refs` "
        "actually cover for that claim.",
        "- Rebuttal-linked statistics in `statistics.json` are marked `observational` -- "
        "never phrase a claim built on them as causal.",
        "- Every claim needs a non-empty `limitations` list and a `support_level` "
        f"from {list(SUPPORT_LEVELS)}.",
        "",
        f"Valid `section` values: {list(SECTIONS)}",
        f"Valid `claim_type` values: {list(CLAIM_TYPES)}",
        "",
        "## Response contract",
        "",
        '{"claims": [{"claim_id": "...", "section": "...", "claim_type": "...", '
        '"text": "...", "evidence_ids": [], "statistic_refs": [], "year_scope": [], '
        '"support_level": "...", "limitations": []}]}',
        "",
    ]) + "\n"


def build_manifest(
    *,
    statistics_payload: dict,
    evidence_payload: dict,
    prompt_version: str = PROMPT_VERSION,
    provider: str | None = None,
    model: str | None = None,
    generation_params: dict | None = None,
    generated_at: str | None = None,
) -> dict:
    """Deterministic `content` (hashable, comparable across runs) kept separate from the
    non-deterministic `generated_at` timestamp -- two runs against identical inputs with
    identical provider/model/params produce an identical `content_hash` even though their
    `generated_at` values differ.
    """
    evidence_bundle_hash = evidence_payload.get("bundle_hash") or content_hash(
        *sorted(i["evidence_id"] for i in evidence_payload.get("items", []))
    )
    content = {
        "corpus_hash": statistics_payload.get("corpus_hash"),
        "evidence_bundle_hash": evidence_bundle_hash,
        "statistics_hash": content_hash(json.dumps(statistics_payload.get("stats", []), sort_keys=True)),
        "prompt_version": prompt_version,
        "schema_version": GENERATION_SCHEMA_VERSION,
        "provider": provider,
        "model": model,
        "generation_params": generation_params or {},
    }
    return {
        "content": content,
        "content_hash": content_hash(json.dumps(content, sort_keys=True)),
        "generated_at": generated_at or iso_now(),
    }


def write_manifest_json(path: Path, manifest: dict) -> None:
    atomic_write_text(path, json.dumps(manifest, indent=2, sort_keys=True))


def export_prompt(*, statistics_path: Path, evidence_path: Path, output_dir: Path, generated_at: str | None = None) -> dict:
    """Writes a self-contained bundle for manual Claude Code use: prompt.md,
    statistics.json, evidence.json, response_schema.json, manifest.json. Requires no API
    key -- this is the primary supported generation path.
    """
    statistics_payload = json.loads(Path(statistics_path).read_text())
    evidence_payload = json.loads(Path(evidence_path).read_text())

    stats_corpus_hash = statistics_payload.get("corpus_hash")
    evidence_corpus_hash = evidence_payload.get("corpus_hash")
    if stats_corpus_hash != evidence_corpus_hash:
        raise ValueError(
            "statistics and evidence inputs come from different corpora "
            f"(corpus_hash {stats_corpus_hash!r} != {evidence_corpus_hash!r})"
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    atomic_write_text(output_dir / "prompt.md", render_prompt(statistics_payload, evidence_payload))
    atomic_write_text(output_dir / "statistics.json", json.dumps(statistics_payload, indent=2, sort_keys=True))
    atomic_write_text(output_dir / "evidence.json", json.dumps(evidence_payload, indent=2, sort_keys=True))
    atomic_write_text(output_dir / "response_schema.json", json.dumps(response_schema(), indent=2, sort_keys=True))

    manifest = build_manifest(
        statistics_payload=statistics_payload, evidence_payload=evidence_payload, generated_at=generated_at
    )
    write_manifest_json(output_dir / "manifest.json", manifest)
    return manifest


# --------------------------------------------------------------------------------------
# structured validation
# --------------------------------------------------------------------------------------


def _strip_quotes(text: str) -> str:
    return text.strip().strip(_QUOTE_CHARS).strip()


def validate_claims(claims_payload: dict, *, statistics_payload: dict, evidence_payload: dict) -> None:
    """Raises GenerationValidationError listing every violation found, or returns None.
    Never partially trusts a claims payload -- see module docstring.
    """
    errors: list[str] = []
    claims = claims_payload.get("claims")
    if not isinstance(claims, list):
        raise GenerationValidationError("claims payload has no 'claims' array")

    evidence_by_id = {item["evidence_id"]: item for item in evidence_payload.get("items", [])}
    stats_index = _index_statistics(statistics_payload)
    years_by_family = _years_by_family(statistics_payload, evidence_payload)
    all_known_years = {y for years in years_by_family.values() for y in years}

    seen_claim_ids: set[str] = set()

    for i, claim in enumerate(claims):
        claim_id = claim.get("claim_id") if isinstance(claim, dict) else None
        label = claim_id or f"<claim #{i}>"

        if not claim_id:
            errors.append(f"{label}: missing claim_id")
        elif claim_id in seen_claim_ids:
            errors.append(f"duplicate claim_id: {claim_id}")
        if claim_id:
            seen_claim_ids.add(claim_id)

        section = claim.get("section")
        if section not in SECTIONS:
            errors.append(f"{label}: unrecognized section {section!r}")

        claim_type = claim.get("claim_type")
        if claim_type not in CLAIM_TYPES:
            errors.append(f"{label}: unrecognized claim_type {claim_type!r}")

        support_level = claim.get("support_level")
        if support_level not in SUPPORT_LEVELS:
            errors.append(f"{label}: missing or invalid support_level {support_level!r}")

        limitations = claim.get("limitations") or []
        if not limitations:
            errors.append(f"{label}: missing limitations")

        text = claim.get("text") or ""
        evidence_ids = claim.get("evidence_ids") or []
        statistic_refs = claim.get("statistic_refs") or []
        year_scope = claim.get("year_scope") or []

        for eid in evidence_ids:
            if eid not in evidence_by_id:
                errors.append(f"{label}: evidence_id {eid!r} not found in evidence bundle")

        claim_ref_years: set = set()
        for ref in statistic_refs:
            ok, _value = resolve_statistic_ref(ref, stats_index)
            if not ok:
                errors.append(f"{label}: statistic_ref {ref!r} does not resolve")
            else:
                claim_ref_years |= _years_covered_by_ref(ref, years_by_family)

        if claim_type == "evidence_excerpt" and not evidence_ids:
            errors.append(f"{label}: evidence_excerpt claim has no evidence_ids")

        if claim_type in ("deterministic_fact", "statistical_pattern") and _HAS_DIGIT_RE.search(text) and not statistic_refs:
            errors.append(f"{label}: numeric/statistical assertion has no statistic_refs")

        if claim_type == "evidence_excerpt" and evidence_ids:
            quoted = _strip_quotes(text)
            found = any(
                quoted and quoted in evidence_by_id[eid]["excerpt_text"]
                for eid in evidence_ids if eid in evidence_by_id
            )
            if not found:
                errors.append(f"{label}: evidence_excerpt text is not a verbatim excerpt from any cited evidence")

        for y in year_scope:
            if y not in all_known_years:
                errors.append(f"{label}: unsupported venue/year scope {y!r}")

        if evidence_ids or statistic_refs:
            evidence_years = {
                evidence_by_id[eid]["venue_year"] for eid in evidence_ids if eid in evidence_by_id
            }
            covered_years = evidence_years | claim_ref_years
            for y in year_scope:
                if y in all_known_years and y not in covered_years:
                    errors.append(f"{label}: claim exceeds its evidence scope for year {y!r}")

    if errors:
        raise GenerationValidationError("; ".join(errors))


# --------------------------------------------------------------------------------------
# deterministic Markdown renderer -- no LLM calls, operates only on validated JSON
# --------------------------------------------------------------------------------------

_CLAIM_TYPE_LABELS = {
    "deterministic_fact": "Deterministic fact",
    "evidence_excerpt": "Evidence excerpt",
    "statistical_pattern": "Observed statistical pattern",
    "llm_interpretation": "Model interpretation",
    "insufficient_evidence": "Insufficient evidence",
}


def render_markdown(claims_payload: dict, statistics_payload: dict, evidence_payload: dict) -> str:
    """Renders validated claims into Markdown, grouped by `section`. Always re-validates
    first -- claims that fail validation raise rather than being silently dropped from
    the rendered output; there is no partial/best-effort rendering path.
    """
    validate_claims(claims_payload, statistics_payload=statistics_payload, evidence_payload=evidence_payload)

    evidence_by_id = {item["evidence_id"]: item for item in evidence_payload.get("items", [])}
    claims = claims_payload["claims"]

    by_section: dict[str, list[dict]] = {}
    for claim in claims:
        by_section.setdefault(claim["section"], []).append(claim)

    lines = [
        "# Generated venue-calibration claims",
        "",
        f"Source corpus hash: `{statistics_payload.get('corpus_hash', '')}`  ",
        f"Claim count: {len(claims)}",
        "",
        "Every claim below passed structured validation: every `evidence_id` and "
        "`statistic_ref` it cites resolves to real, unedited source data, and every "
        "`evidence_excerpt` claim's text is a verbatim quote from its cited excerpt. See "
        "[`docs/generation.md`](../docs/generation.md) for the full claim schema and "
        "validation rules.",
        "",
    ]

    for section in SECTIONS:
        section_claims = by_section.get(section)
        if not section_claims:
            continue
        lines.append(f"## {section.replace('_', ' ').title()}")
        lines.append("")
        for claim in sorted(section_claims, key=lambda c: c["claim_id"]):
            type_label = _CLAIM_TYPE_LABELS.get(claim["claim_type"], claim["claim_type"])
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
                    lines.append(
                        f"  - forum `{item['forum_id']}`, note `{item['note_id']}` — {item['source_url']}"
                    )
            if claim["statistic_refs"]:
                lines.append("- **Statistics:** " + ", ".join(f"`{r}`" for r in claim["statistic_refs"]))
            lines.append("- **Limitations:**")
            for lim in claim["limitations"]:
                lines.append(f"  - {lim}")
            lines.append("")

    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------------------
# provider response parsing -- provider-agnostic, no `anthropic` dependency. The actual
# provider call lives in `llm_provider.py`, a dedicated module so that `anthropic` is
# never referenced anywhere in this file, not even inside a function body -- see
# tests/test_optional_anthropic.py, which scans every file in this package.
# --------------------------------------------------------------------------------------

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_provider_response(raw_text: str) -> dict:
    """Parses a provider's raw text response into the claims JSON contract. Strips a
    single leading/trailing Markdown code fence (models often wrap JSON in ```json ...
    ``` even when told not to) but makes no other attempt to repair malformed JSON -- a
    parse failure here is a real signal about the provider's output, not something to
    silently paper over.
    """
    text = _CODE_FENCE_RE.sub("", raw_text.strip()).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as e:
        raise GenerationValidationError(f"provider response is not valid JSON: {e}") from e
    if not isinstance(payload, dict) or "claims" not in payload:
        raise GenerationValidationError("provider response is missing a top-level 'claims' array")
    if not isinstance(payload["claims"], list):
        raise GenerationValidationError("provider response 'claims' must be a list")
    return payload
