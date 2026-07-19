"""Leakage-safe, offline evaluation harness for saved prediction files (Phase 4B).

Scope, deliberately: this module never calls an LLM/API, never constructs an
OpenReview client, and never imports `anthropic` (see
`tests/test_optional_anthropic.py`, which scans every file in this package). It turns a
full corpus into a forum-split evaluation dataset (`prepare_eval`), validates saved
prediction files against that dataset and against each other for leakage/comparability
(`run_leakage_validation`), and scores them (`evaluate`). Generating predictions is an
external, manual step -- see `docs/evaluation.md`.

Three ideas run through every function here:

1. **Split by forum, never by review.** A forum's reviews/rebuttal/decision are one
   inseparable unit; if a forum is used for calibration, it is never in the evaluation
   set, and vice versa. `select_evaluation_forums` enforces this and `validate_dataset`
   re-derives the split from the frozen calibration ID list to catch tampering.
2. **Model-visible content is a closed schema.** `ModelInput` has exactly
   forum_id/venue_family/venue_year/title/abstract/input_tier/schema_version -- no
   review text, rating, decision, or rebuttal field exists on the dataclass at all, so
   there is no field to accidentally leak through. `check_no_review_leakage` is a
   second, independent check: it greps each forum's own review/response/decision text
   against its own title+abstract as a build-time safety net, not the primary control.
3. **Every violation is collected, not just the first.** Matching `evidence.py` and
   `generation.py`'s validation style: `*ValidationError` messages list every problem
   found in one payload, and `run_leakage_validation` collects across dataset
   consistency, prediction schema, dataset membership, and cross-run comparability
   before raising once.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from paperscope.config import (
    EVAL_MIN_BREAKDOWN_N,
    EVAL_MIN_PROBABILITY_N,
    EVAL_SMALL_SAMPLE_WARNING_N,
    EVALUATION_SCHEMA_VERSION,
    NO_CALIBRATION,
)
from paperscope.models import ForumRecord, content_hash
from paperscope.storage import atomic_write_text, load_corpus

RESOLVED_DECISIONS: tuple[str, ...] = ("accept", "reject")
UNRESOLVED_DECISION_REASONS: dict[str, str] = {
    "unknown": "unresolved",
    "": "unresolved",
    "withdrawn": "withdrawn",
    "desk_reject": "desk_reject",
}
INITIAL_RATING_AGGREGATION = "mean_of_initial_ratings"
INPUT_TIER_ABSTRACT_ONLY = "abstract_only"

VALID_SYSTEMS: tuple[str, ...] = ("generic", "paperscope", "baseline")
REQUIRED_RUN_FIELDS: tuple[str, ...] = (
    "run_id", "system", "model", "settings", "input_hash", "calibration_hash", "created_at",
)
MODEL_INPUT_ALLOWED_FIELDS = frozenset(
    {"forum_id", "venue_family", "venue_year", "title", "abstract", "input_tier", "schema_version"}
)


def iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class EvaluationDatasetError(ValueError):
    """Raised with every violation found while preparing a dataset, or with a single
    fail-closed reason (empty calibration set, empty corpus, etc)."""


class EvaluationValidationError(ValueError):
    """Raised with every violation found across dataset consistency, prediction schema,
    dataset membership, and generic/PaperScope comparability -- see
    `run_leakage_validation`."""


# ----------------------------------------------------------------------------------------
# dataset records
# ----------------------------------------------------------------------------------------


@dataclass
class ModelInput:
    """Model-visible content only. No other field may ever be added to this dataclass --
    see the module docstring's point 2. `input_tier` is always `"abstract_only"` today
    because `Paper` (models.py) has no full-text field yet; the field exists so a future
    corpus schema with full paper text doesn't require a new dataset schema version.
    """

    forum_id: str
    venue_family: str
    venue_year: int | str | None
    title: str
    abstract: str
    input_tier: str = INPUT_TIER_ABSTRACT_ONLY
    schema_version: int = EVALUATION_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PrivateLabel:
    """Ground truth, kept in a file never intended for model context. Both tasks' labels
    live on one record per forum (not two files) so a forum's eligibility for each task
    stays next to the value -- see the module docstring's point 1 on why a forum's data
    is one inseparable unit.
    """

    forum_id: str
    venue_family: str
    venue_year: int | str | None
    initial_rating_target: float | None
    initial_rating_aggregation: str
    initial_rating_n: int
    initial_rating_eligible: bool
    final_decision_target: str | None  # "accept" | "reject" | None
    final_decision_raw: str
    final_decision_eligible: bool
    final_decision_excluded_reason: str | None
    schema_version: int = EVALUATION_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


def _venue_year_key(record: ForumRecord) -> int | str:
    return record.venue_year if record.venue_year is not None else "unspecified"


def build_model_input(record: ForumRecord) -> ModelInput:
    return ModelInput(
        forum_id=record.forum_id,
        venue_family=record.venue_family or "unknown",
        venue_year=_venue_year_key(record),
        title=record.paper.title or "",
        abstract=record.paper.abstract or "",
    )


def build_private_label(record: ForumRecord) -> PrivateLabel:
    rating_values = [
        r.initial_rating.value for r in record.reviews if r.initial_rating.value is not None
    ]
    initial_rating_target = round(sum(rating_values) / len(rating_values), 4) if rating_values else None

    normalized = record.decision.normalized or ""
    final_decision_eligible = normalized in RESOLVED_DECISIONS
    final_decision_target = normalized if final_decision_eligible else None
    excluded_reason = None if final_decision_eligible else UNRESOLVED_DECISION_REASONS.get(normalized, "unresolved")

    return PrivateLabel(
        forum_id=record.forum_id,
        venue_family=record.venue_family or "unknown",
        venue_year=_venue_year_key(record),
        initial_rating_target=initial_rating_target,
        initial_rating_aggregation=INITIAL_RATING_AGGREGATION,
        initial_rating_n=len(rating_values),
        initial_rating_eligible=bool(rating_values),
        final_decision_target=final_decision_target,
        final_decision_raw=record.decision.raw_text or "",
        final_decision_eligible=final_decision_eligible,
        final_decision_excluded_reason=excluded_reason,
    )


# ----------------------------------------------------------------------------------------
# calibration freeze + forum-level split
# ----------------------------------------------------------------------------------------


def load_calibration_forum_ids(path: Path) -> set[str]:
    """Accepts either a plain JSON list of forum IDs, `{"forum_ids": [...]}`, or an
    evidence-bundle-shaped manifest (`{"items": [{"forum_id": ...}, ...]}`, as written by
    `evidence.write_evidence_bundle`) -- covers both a hand-written forum list and reusing
    the actual evidence bundle a venue's calibration was built from.
    """
    data = json.loads(Path(path).read_text())
    if isinstance(data, list):
        raw_ids = data
    elif isinstance(data, dict) and "forum_ids" in data:
        raw_ids = data["forum_ids"]
    elif isinstance(data, dict) and "items" in data:
        raw_ids = [item.get("forum_id") for item in data["items"]]
    else:
        raise EvaluationDatasetError(
            f"{path}: unrecognized calibration-forums format -- expected a JSON list, "
            '{"forum_ids": [...]}, or an evidence bundle with an "items" array'
        )
    ids = {i for i in raw_ids if isinstance(i, str) and i}
    if not ids:
        raise EvaluationDatasetError(f"{path}: calibration forum set is empty")
    return ids


def freeze_calibration_hash(calibration_forum_ids: set[str]) -> str:
    return content_hash(*sorted(calibration_forum_ids))


@dataclass
class SplitResult:
    eval_forum_ids: list[str]
    exclusions: list[dict]  # [{"forum_id":..., "reason":...}]


def select_evaluation_forums(
    records: dict[str, ForumRecord], calibration_forum_ids: set[str]
) -> SplitResult:
    """Selects the evaluation forum set from `records`, deduplicated by construction
    (`records` is already keyed by forum_id). A forum is excluded, in priority order, for:
    being in the frozen calibration set, having no usable label for either task, or having
    no title/abstract to show a model at all. Never overlaps `calibration_forum_ids` --
    `prepare_eval` asserts this again after the fact as defense-in-depth.
    """
    eval_ids: list[str] = []
    exclusions: list[dict] = []

    for forum_id in sorted(records):
        record = records[forum_id]
        if forum_id in calibration_forum_ids:
            exclusions.append({"forum_id": forum_id, "reason": "in_calibration_set"})
            continue
        label = build_private_label(record)
        if not (label.initial_rating_eligible or label.final_decision_eligible):
            exclusions.append({"forum_id": forum_id, "reason": "no_usable_labels"})
            continue
        if not (record.paper.title or record.paper.abstract):
            exclusions.append({"forum_id": forum_id, "reason": "missing_paper_content"})
            continue
        eval_ids.append(forum_id)

    return SplitResult(eval_forum_ids=eval_ids, exclusions=exclusions)


def check_no_review_leakage(records: dict[str, ForumRecord], model_inputs: list[ModelInput]) -> list[str]:
    """Greps each forum's own review/response/decision text against its own visible
    title+abstract. A real leak (e.g. a future bug that pipes review text into `Paper`)
    would show up as a long, literal substring match -- short common phrases are not
    checked (`_MIN_LEAK_LEN`) to avoid false positives on generic wording.
    """
    _MIN_LEAK_LEN = 25
    errors: list[str] = []
    for mi in model_inputs:
        record = records.get(mi.forum_id)
        if record is None:
            continue
        visible = f"{mi.title}\n{mi.abstract}".lower()
        for review in record.reviews:
            for field_name in ("text", "strengths", "weaknesses", "questions", "summary"):
                text = getattr(review, field_name, "")
                if isinstance(text, str) and len(text) >= _MIN_LEAK_LEN and text.lower() in visible:
                    errors.append(f"{mi.forum_id}: review.{field_name} text leaked into model-visible input")
        for response in record.responses:
            if len(response.text) >= _MIN_LEAK_LEN and response.text.lower() in visible:
                errors.append(f"{mi.forum_id}: response/rebuttal text leaked into model-visible input")
        decision_text = record.decision.raw_text or ""
        if len(decision_text) >= _MIN_LEAK_LEN and decision_text.lower() in visible:
            errors.append(f"{mi.forum_id}: decision text leaked into model-visible input")
    return errors


# ----------------------------------------------------------------------------------------
# reviewer-aggregate baseline (section 6) -- calibration-set aggregates only, never an
# eval forum's own true label
# ----------------------------------------------------------------------------------------


def compute_reviewer_aggregate_baseline(
    records: dict[str, ForumRecord],
    calibration_forum_ids: set[str],
    eval_forum_ids: list[str],
    *,
    run_id: str = "baseline_reviewer_aggregate",
    created_at: str | None = None,
) -> dict | None:
    """A naive constant baseline: every eval forum gets the same rating/decision
    prediction, both derived only from calibration-set aggregate statistics (mean
    initial rating, majority decision) -- never from that eval forum's own reviewer data.
    Returns None if none of `calibration_forum_ids` are present in `records` (nothing to
    aggregate from), since a baseline built from zero calibration forums as if it means
    something would be worse than no baseline at all.
    """
    calibration_records = [records[fid] for fid in calibration_forum_ids if fid in records]
    if not calibration_records:
        return None

    rating_values = [
        r.initial_rating.value
        for record in calibration_records
        for r in record.reviews
        if r.initial_rating.value is not None
    ]
    mean_rating = round(sum(rating_values) / len(rating_values), 4) if rating_values else None

    decision_counts: dict[str, int] = {}
    for record in calibration_records:
        normalized = record.decision.normalized or ""
        if normalized in RESOLVED_DECISIONS:
            decision_counts[normalized] = decision_counts.get(normalized, 0) + 1
    majority_decision = max(decision_counts, key=decision_counts.get) if decision_counts else None

    predictions = [
        {
            "forum_id": fid,
            "rating_prediction": mean_rating,
            "decision_prediction": majority_decision,
            "accept_probability": None,
            "reasoning_summary": (
                "Constant baseline: calibration-set mean initial rating / majority "
                "decision, independent of this forum's own (unseen) labels."
            ),
        }
        for fid in sorted(eval_forum_ids)
    ]
    return {
        "run": {
            "run_id": run_id,
            "system": "baseline",
            "model": "reviewer_aggregate_baseline",
            "settings": {
                "calibration_forum_count": len(calibration_records),
                "mean_initial_rating": mean_rating,
                "majority_decision": majority_decision,
            },
            "input_hash": NO_CALIBRATION,
            "calibration_hash": freeze_calibration_hash(calibration_forum_ids),
            "created_at": created_at or iso_now(),
        },
        "predictions": predictions,
    }


# ----------------------------------------------------------------------------------------
# prepare-eval
# ----------------------------------------------------------------------------------------


def _jsonl_text(rows: list[dict]) -> str:
    lines = [json.dumps(r, sort_keys=True) for r in rows]
    return "\n".join(lines) + ("\n" if lines else "")


def _stratify(records: dict[str, ForumRecord], forum_ids: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for fid in forum_ids:
        record = records.get(fid)
        if record is None:
            continue
        key = f"{record.venue_family or 'unknown'}/{_venue_year_key(record)}"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def prepare_eval(
    *,
    corpus_path: Path,
    calibration_forums_path: Path,
    output_dir: Path,
    seed: int,
    generated_at: str | None = None,
) -> dict:
    """Builds a leakage-safe evaluation dataset at `output_dir`. Freezes the calibration
    forum set (hashes it) *before* selecting evaluation forums, per the module's point 1
    -- the calibration set comes from an external, already-produced file (e.g. the
    evidence bundle a venue's skill calibration was built from), so this ordering can't
    be gamed by picking eval forums first and calling the leftovers "calibration".
    Deterministic for the same seed + inputs: no random sampling happens (every eligible
    non-calibration forum is included), `seed` is recorded for reproducibility and future
    extensibility, and every list is written in sorted order.
    """
    records = load_corpus(Path(corpus_path))
    if not records:
        raise EvaluationDatasetError(f"no records found in corpus {corpus_path}")

    calibration_forum_ids = load_calibration_forum_ids(Path(calibration_forums_path))
    calibration_hash = freeze_calibration_hash(calibration_forum_ids)

    split = select_evaluation_forums(records, calibration_forum_ids)
    if not split.eval_forum_ids:
        raise EvaluationDatasetError(
            "no evaluation forums remain after excluding the calibration set and forums "
            "with insufficient labels -- see exclusions for reasons"
        )
    overlap = set(split.eval_forum_ids) & calibration_forum_ids
    if overlap:
        raise EvaluationDatasetError(f"calibration/evaluation overlap survived selection: {sorted(overlap)}")

    model_inputs = [build_model_input(records[fid]) for fid in split.eval_forum_ids]
    private_labels = [build_private_label(records[fid]) for fid in split.eval_forum_ids]

    leak_errors = check_no_review_leakage(records, model_inputs)
    if leak_errors:
        raise EvaluationDatasetError("; ".join(leak_errors))

    generated_at = generated_at or iso_now()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_inputs_text = _jsonl_text([mi.to_dict() for mi in model_inputs])
    private_labels_text = _jsonl_text([pl.to_dict() for pl in private_labels])
    atomic_write_text(output_dir / "model_inputs.jsonl", model_inputs_text)
    atomic_write_text(output_dir / "private_labels.jsonl", private_labels_text)

    from paperscope.storage import corpus_hash as compute_corpus_hash

    src_corpus_hash = compute_corpus_hash(records)

    exclusion_counts: dict[str, int] = {}
    for e in split.exclusions:
        exclusion_counts[e["reason"]] = exclusion_counts.get(e["reason"], 0) + 1

    calibration_in_corpus = [fid for fid in sorted(calibration_forum_ids) if fid in records]
    split_manifest = {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "seed": seed,
        "corpus_hash": src_corpus_hash,
        "calibration_hash": calibration_hash,
        "calibration_forum_ids": sorted(calibration_forum_ids),
        "calibration_forum_count": len(calibration_forum_ids),
        "calibration_forums_found_in_corpus": len(calibration_in_corpus),
        "eval_forum_count": len(split.eval_forum_ids),
        "disjoint": True,
        "exclusions": split.exclusions,
        "exclusion_counts": exclusion_counts,
        "stratification": {
            "calibration": _stratify(records, calibration_in_corpus),
            "evaluation": _stratify(records, split.eval_forum_ids),
        },
        "generated_at": generated_at,
    }
    atomic_write_text(output_dir / "split_manifest.json", json.dumps(split_manifest, indent=2, sort_keys=True))

    initial_rating_eligible = sum(1 for pl in private_labels if pl.initial_rating_eligible)
    final_decision_eligible = sum(1 for pl in private_labels if pl.final_decision_eligible)
    evaluation_manifest = {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "seed": seed,
        "corpus_hash": src_corpus_hash,
        "calibration_hash": calibration_hash,
        "model_inputs_hash": content_hash(model_inputs_text),
        "private_labels_hash": content_hash(private_labels_text),
        "eval_forum_count": len(split.eval_forum_ids),
        "tasks": {
            "initial_rating": {
                "target_definition": (
                    "Unweighted arithmetic mean of every review's initial_rating.value "
                    "for the forum (final/revised ratings are never used). A forum is "
                    "eligible only if at least one review has a non-null initial rating."
                ),
                "aggregation": INITIAL_RATING_AGGREGATION,
                "eligible_forum_count": initial_rating_eligible,
            },
            "final_decision": {
                "target_definition": (
                    "ForumRecord.decision.normalized, restricted to {accept, reject}. "
                    "Never derived from a rating threshold. Withdrawn, desk-rejected, and "
                    "unresolved (unknown) forums are excluded from the eligible pool; "
                    "counts are still reported (see split_manifest.json exclusions and "
                    "each private_labels.jsonl row's final_decision_excluded_reason)."
                ),
                "eligible_forum_count": final_decision_eligible,
            },
        },
        "generated_at": generated_at,
    }
    atomic_write_text(
        output_dir / "evaluation_manifest.json", json.dumps(evaluation_manifest, indent=2, sort_keys=True)
    )

    return evaluation_manifest


# ----------------------------------------------------------------------------------------
# prediction schema validation
# ----------------------------------------------------------------------------------------


def validate_prediction_schema(payload: dict) -> list[str]:
    """Schema-level checks on one prediction file in isolation: required run fields,
    valid system/decision/probability values, duplicate forum_ids within the file.
    Never raises -- returns every violation found for the caller to collect.
    """
    errors: list[str] = []
    run = payload.get("run")
    if not isinstance(run, dict):
        return ["prediction file missing a 'run' object"]

    for f in REQUIRED_RUN_FIELDS:
        if f not in run or run[f] in (None, ""):
            errors.append(f"run.{f} is missing or empty")
    if run.get("system") is not None and run.get("system") not in VALID_SYSTEMS:
        errors.append(f"run.system {run.get('system')!r} is not one of {VALID_SYSTEMS}")
    if "settings" in run and not isinstance(run["settings"], dict):
        errors.append("run.settings must be an object")

    predictions = payload.get("predictions")
    if not isinstance(predictions, list):
        errors.append("prediction file has no 'predictions' array")
        return errors

    seen_ids: set[str] = set()
    for i, p in enumerate(predictions):
        if not isinstance(p, dict):
            errors.append(f"<prediction #{i}>: not an object")
            continue
        fid = p.get("forum_id")
        label = fid or f"<prediction #{i}>"
        if not fid:
            errors.append(f"{label}: missing forum_id")
        elif fid in seen_ids:
            errors.append(f"duplicate forum_id in predictions: {fid}")
        if fid:
            seen_ids.add(fid)

        rating = p.get("rating_prediction")
        if rating is not None and not isinstance(rating, (int, float)):
            errors.append(f"{label}: rating_prediction must be numeric or null")

        decision = p.get("decision_prediction")
        if decision is not None and decision not in RESOLVED_DECISIONS:
            errors.append(f"{label}: decision_prediction must be one of {RESOLVED_DECISIONS} or null")

        prob = p.get("accept_probability")
        if prob is not None:
            if not isinstance(prob, (int, float)) or isinstance(prob, bool) or not (0.0 <= prob <= 1.0):
                errors.append(f"{label}: accept_probability must be a number in [0, 1] or null")

    return errors


def validate_predictions_against_dataset(
    payload: dict, eval_forum_ids: set[str]
) -> tuple[list[str], list[str]]:
    """Returns `(errors, missing_forum_ids)`. `errors` are fatal (unknown/extra forum
    IDs -- a prediction file must reference only evaluation forums). `missing_forum_ids`
    is informational, not fatal: predictions may legitimately cover a subset.
    """
    errors: list[str] = []
    predicted_ids = {p["forum_id"] for p in payload.get("predictions", []) if isinstance(p, dict) and p.get("forum_id")}
    unknown = sorted(predicted_ids - eval_forum_ids)
    if unknown:
        errors.append(f"prediction file references {len(unknown)} forum_id(s) outside the evaluation set: {unknown[:10]}")
    missing = sorted(eval_forum_ids - predicted_ids)
    return errors, missing


def validate_run_comparability(
    generic_payload: dict, paperscope_payload: dict, *, dataset_model_inputs_hash: str, dataset_calibration_hash: str
) -> list[str]:
    """Section 4's 'the only intended difference is the PaperScope calibration
    reference': every other run field must match exactly, and each run's
    `calibration_hash` must be consistent with its own system (generic: no calibration;
    paperscope: the dataset's frozen hash).
    """
    errors: list[str] = []
    g, p = generic_payload.get("run", {}), paperscope_payload.get("run", {})

    if g.get("system") != "generic":
        errors.append(f"generic predictions file's run.system is {g.get('system')!r}, expected 'generic'")
    if p.get("system") != "paperscope":
        errors.append(f"paperscope predictions file's run.system is {p.get('system')!r}, expected 'paperscope'")
    if g.get("model") != p.get("model"):
        errors.append(f"model mismatch: generic={g.get('model')!r} vs paperscope={p.get('model')!r}")
    if g.get("settings") != p.get("settings"):
        errors.append("settings mismatch between generic and paperscope runs")
    if g.get("input_hash") != p.get("input_hash"):
        errors.append("input_hash mismatch between generic and paperscope runs")
    if g.get("input_hash") != dataset_model_inputs_hash:
        errors.append("generic run.input_hash does not match this dataset's model_inputs_hash")
    if p.get("input_hash") != dataset_model_inputs_hash:
        errors.append("paperscope run.input_hash does not match this dataset's model_inputs_hash")
    if g.get("calibration_hash") not in (None, NO_CALIBRATION):
        errors.append(
            f"generic run.calibration_hash should be {NO_CALIBRATION!r} (no calibration used), "
            f"got {g.get('calibration_hash')!r}"
        )
    if p.get("calibration_hash") != dataset_calibration_hash:
        errors.append(
            "paperscope run.calibration_hash does not match this dataset's frozen calibration_hash "
            "-- calibration reference is not comparable to what the eval set actually froze"
        )

    g_ids = {pr.get("forum_id") for pr in generic_payload.get("predictions", []) if isinstance(pr, dict)}
    p_ids = {pr.get("forum_id") for pr in paperscope_payload.get("predictions", []) if isinstance(pr, dict)}
    if g_ids != p_ids:
        errors.append("generic and paperscope prediction runs cover different forum_id sets")

    return errors


# ----------------------------------------------------------------------------------------
# dataset-internal consistency (recompute every hash from the files on disk)
# ----------------------------------------------------------------------------------------


def validate_dataset_consistency(dataset_dir: Path) -> list[str]:
    dataset_dir = Path(dataset_dir)
    errors: list[str] = []

    try:
        manifest = json.loads((dataset_dir / "evaluation_manifest.json").read_text())
    except (OSError, json.JSONDecodeError) as e:
        return [f"cannot read evaluation_manifest.json: {e}"]
    try:
        split = json.loads((dataset_dir / "split_manifest.json").read_text())
    except (OSError, json.JSONDecodeError) as e:
        return [f"cannot read split_manifest.json: {e}"]

    try:
        model_inputs_text = (dataset_dir / "model_inputs.jsonl").read_text()
        private_labels_text = (dataset_dir / "private_labels.jsonl").read_text()
    except OSError as e:
        return [f"cannot read dataset jsonl files: {e}"]

    if content_hash(model_inputs_text) != manifest.get("model_inputs_hash"):
        errors.append("model_inputs.jsonl content hash does not match evaluation_manifest.json (tampered or stale)")
    if content_hash(private_labels_text) != manifest.get("private_labels_hash"):
        errors.append("private_labels.jsonl content hash does not match evaluation_manifest.json (tampered or stale)")

    for key in ("calibration_hash", "corpus_hash", "seed"):
        if manifest.get(key) != split.get(key):
            errors.append(f"{key} mismatch between evaluation_manifest.json ({manifest.get(key)!r}) and split_manifest.json ({split.get(key)!r})")

    calibration_ids = set(split.get("calibration_forum_ids", []))
    recomputed_cal_hash = freeze_calibration_hash(calibration_ids)
    if recomputed_cal_hash != split.get("calibration_hash"):
        errors.append("calibration_hash does not match the recorded calibration_forum_ids (tampered split_manifest.json)")

    model_input_rows = [json.loads(line) for line in model_inputs_text.splitlines() if line.strip()]
    eval_ids = {row.get("forum_id") for row in model_input_rows}
    overlap = eval_ids & calibration_ids
    if overlap:
        errors.append(f"calibration/evaluation forum_id overlap detected: {sorted(overlap)[:10]}")

    for row in model_input_rows:
        extra = set(row) - MODEL_INPUT_ALLOWED_FIELDS
        if extra:
            errors.append(f"model_inputs.jsonl row {row.get('forum_id')!r} has disallowed fields {sorted(extra)} (possible label leakage)")

    return errors


@dataclass
class LeakageReport:
    violations: list[str] = field(default_factory=list)
    missing_generic_predictions: list[str] = field(default_factory=list)
    missing_paperscope_predictions: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


def run_leakage_validation(
    dataset_dir: Path, generic_predictions_path: Path, paperscope_predictions_path: Path
) -> LeakageReport:
    """Runs every leakage/comparability check from section 4, collecting every violation
    rather than stopping at the first. Used by both `paperscope validate-eval` and
    internally by `evaluate` (which never trusts a prior validate-eval run)."""
    dataset_dir = Path(dataset_dir)
    violations = list(validate_dataset_consistency(dataset_dir))

    manifest = json.loads((dataset_dir / "evaluation_manifest.json").read_text())
    model_input_rows = [
        json.loads(line) for line in (dataset_dir / "model_inputs.jsonl").read_text().splitlines() if line.strip()
    ]
    eval_forum_ids = {row["forum_id"] for row in model_input_rows}

    generic_payload = json.loads(Path(generic_predictions_path).read_text())
    paperscope_payload = json.loads(Path(paperscope_predictions_path).read_text())

    violations.extend(f"generic predictions: {e}" for e in validate_prediction_schema(generic_payload))
    violations.extend(f"paperscope predictions: {e}" for e in validate_prediction_schema(paperscope_payload))

    g_errors, g_missing = validate_predictions_against_dataset(generic_payload, eval_forum_ids)
    p_errors, p_missing = validate_predictions_against_dataset(paperscope_payload, eval_forum_ids)
    violations.extend(f"generic predictions: {e}" for e in g_errors)
    violations.extend(f"paperscope predictions: {e}" for e in p_errors)

    violations.extend(
        validate_run_comparability(
            generic_payload,
            paperscope_payload,
            dataset_model_inputs_hash=manifest.get("model_inputs_hash"),
            dataset_calibration_hash=manifest.get("calibration_hash"),
        )
    )

    return LeakageReport(
        violations=violations, missing_generic_predictions=g_missing, missing_paperscope_predictions=p_missing
    )


# ----------------------------------------------------------------------------------------
# metrics -- pure functions, no numpy/scipy dependency
# ----------------------------------------------------------------------------------------


def mean_absolute_error(pairs: list[tuple[float, float]]) -> float | None:
    if not pairs:
        return None
    return round(sum(abs(pred - actual) for actual, pred in pairs) / len(pairs), 4)


def median_absolute_error(pairs: list[tuple[float, float]]) -> float | None:
    if not pairs:
        return None
    errs = sorted(abs(pred - actual) for actual, pred in pairs)
    n = len(errs)
    mid = n // 2
    median = errs[mid] if n % 2 else (errs[mid - 1] + errs[mid]) / 2
    return round(median, 4)


def _rank(values: list[float]) -> list[float]:
    """Average-rank ranking (1-indexed), stable under ties -- see spearman_correlation."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def pearson_correlation(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return None
    return cov / (var_x * var_y) ** 0.5


def spearman_correlation(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 2:
        return None
    actual = [a for a, _p in pairs]
    predicted = [p for _a, p in pairs]
    r = pearson_correlation(_rank(actual), _rank(predicted))
    return round(r, 4) if r is not None else None


def confusion_matrix(pairs: list[tuple[str, str]]) -> dict[str, dict[str, int]]:
    cm = {"accept": {"accept": 0, "reject": 0}, "reject": {"accept": 0, "reject": 0}}
    for actual, predicted in pairs:
        cm[actual][predicted] += 1
    return cm


def classification_metrics(cm: dict[str, dict[str, int]]) -> dict:
    tp, fn = cm["accept"]["accept"], cm["accept"]["reject"]
    fp, tn = cm["reject"]["accept"], cm["reject"]["reject"]
    total = tp + fn + fp + tn
    accuracy = round((tp + tn) / total, 4) if total else None
    precision = round(tp / (tp + fp), 4) if (tp + fp) else None
    recall = round(tp / (tp + fn), 4) if (tp + fn) else None
    if precision is None or recall is None:
        f1 = None
    elif precision + recall == 0:
        f1 = 0.0
    else:
        f1 = round(2 * precision * recall / (precision + recall), 4)
    return {"accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1}


def brier_score(pairs: list[tuple[int, float]]) -> float | None:
    """`pairs` are (actual_binary, predicted_probability)."""
    if not pairs:
        return None
    return round(sum((prob - actual) ** 2 for actual, prob in pairs) / len(pairs), 4)


def expected_calibration_error(pairs: list[tuple[int, float]], n_bins: int = 10) -> float | None:
    if not pairs:
        return None
    bins: list[list[tuple[int, float]]] = [[] for _ in range(n_bins)]
    for actual, prob in pairs:
        idx = min(n_bins - 1, int(prob * n_bins))
        bins[idx].append((actual, prob))
    n = len(pairs)
    ece = 0.0
    for b in bins:
        if not b:
            continue
        confidence = sum(prob for _a, prob in b) / len(b)
        accuracy = sum(a for a, _p in b) / len(b)
        ece += (len(b) / n) * abs(accuracy - confidence)
    return round(ece, 4)


# ----------------------------------------------------------------------------------------
# evaluate
# ----------------------------------------------------------------------------------------


def _load_dataset(dataset_dir: Path) -> tuple[dict, list[dict], list[dict]]:
    dataset_dir = Path(dataset_dir)
    manifest = json.loads((dataset_dir / "evaluation_manifest.json").read_text())
    model_inputs = [
        json.loads(line) for line in (dataset_dir / "model_inputs.jsonl").read_text().splitlines() if line.strip()
    ]
    labels = [
        json.loads(line) for line in (dataset_dir / "private_labels.jsonl").read_text().splitlines() if line.strip()
    ]
    return manifest, model_inputs, labels


def _breakdown(
    rows: list[tuple[str, int | str, float, float]], metric_fn, min_n: int
) -> tuple[list[dict], list[dict]]:
    """`rows` are (venue_family, venue_year, actual, predicted). Groups by
    (venue_family, venue_year); strata below `min_n` are reported as skipped, not
    silently dropped -- see section 7's exclusion-transparency requirement."""
    by_scope: dict[tuple[str, int | str], list[tuple[float, float]]] = {}
    for family, year, actual, predicted in rows:
        by_scope.setdefault((family, year), []).append((actual, predicted))

    included, skipped = [], []
    for (family, year), pairs in sorted(by_scope.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        if len(pairs) < min_n:
            skipped.append({"venue_family": family, "venue_year": year, "n": len(pairs), "reason": f"sample_size_below_{min_n}"})
            continue
        included.append({"venue_family": family, "venue_year": year, "n": len(pairs), **metric_fn(pairs)})
    return included, skipped


def _initial_rating_metrics(labels: list[dict], predictions_by_forum: dict[str, dict]) -> dict:
    eligible = [pl for pl in labels if pl["initial_rating_eligible"]]
    pairs_with_scope: list[tuple[str, int | str, float, float]] = []
    for pl in eligible:
        pred = predictions_by_forum.get(pl["forum_id"])
        if pred is None or pred.get("rating_prediction") is None:
            continue
        pairs_with_scope.append((pl["venue_family"], pl["venue_year"], pl["initial_rating_target"], pred["rating_prediction"]))

    pairs = [(a, p) for _f, _y, a, p in pairs_with_scope]
    n_eligible, n_predicted = len(eligible), len(pairs)

    def metric_fn(ps):
        return {
            "mae": mean_absolute_error(ps),
            "median_absolute_error": median_absolute_error(ps),
            "spearman": spearman_correlation(ps),
        }

    breakdown, breakdown_skipped = _breakdown(pairs_with_scope, metric_fn, EVAL_MIN_BREAKDOWN_N)

    return {
        "aggregation": INITIAL_RATING_AGGREGATION,
        "eligible_forum_count": n_eligible,
        "predicted_count": n_predicted,
        "coverage": round(n_predicted / n_eligible, 4) if n_eligible else None,
        "sample_size": n_predicted,
        **metric_fn(pairs),
        "breakdown": breakdown,
        "breakdown_skipped": breakdown_skipped,
    }


def _final_decision_metrics(labels: list[dict], predictions_by_forum: dict[str, dict]) -> dict:
    eligible = [pl for pl in labels if pl["final_decision_eligible"]]
    pairs_with_scope: list[tuple[str, int | str, str, str]] = []
    for pl in eligible:
        pred = predictions_by_forum.get(pl["forum_id"])
        if pred is None or pred.get("decision_prediction") is None:
            continue
        pairs_with_scope.append((pl["venue_family"], pl["venue_year"], pl["final_decision_target"], pred["decision_prediction"]))

    pairs = [(a, p) for _f, _y, a, p in pairs_with_scope]
    n_eligible, n_predicted = len(eligible), len(pairs)

    def metric_fn(ps):
        return classification_metrics(confusion_matrix(ps))

    breakdown, breakdown_skipped = _breakdown(pairs_with_scope, metric_fn, EVAL_MIN_BREAKDOWN_N)

    return {
        "eligible_forum_count": n_eligible,
        "predicted_count": n_predicted,
        "coverage": round(n_predicted / n_eligible, 4) if n_eligible else None,
        "sample_size": n_predicted,
        **classification_metrics(confusion_matrix(pairs)),
        "confusion_matrix": confusion_matrix(pairs),
        "breakdown": breakdown,
        "breakdown_skipped": breakdown_skipped,
    }


def _probability_metrics(labels: list[dict], predictions_by_forum: dict[str, dict]) -> dict:
    eligible = [pl for pl in labels if pl["final_decision_eligible"]]
    pairs: list[tuple[int, float]] = []
    for pl in eligible:
        pred = predictions_by_forum.get(pl["forum_id"])
        if pred is None:
            continue
        prob = pred.get("accept_probability")
        # Never approximate a probability from rating_prediction/decision_prediction --
        # a missing accept_probability means this forum contributes nothing here, full stop.
        if prob is None:
            continue
        actual = 1 if pl["final_decision_target"] == "accept" else 0
        pairs.append((actual, prob))

    if not pairs:
        return {"computed": False, "reason": "no accept_probability values present", "sample_size": 0, "brier_score": None, "ece": None}
    if len(pairs) < EVAL_MIN_PROBABILITY_N:
        return {
            "computed": False,
            "reason": f"sample_size_below_{EVAL_MIN_PROBABILITY_N} (n={len(pairs)})",
            "sample_size": len(pairs),
            "brier_score": None,
            "ece": None,
        }
    return {
        "computed": True,
        "reason": None,
        "sample_size": len(pairs),
        "brier_score": brier_score(pairs),
        "ece": expected_calibration_error(pairs),
    }


def score_predictions(labels: list[dict], predictions_payload: dict) -> dict:
    predictions_by_forum = {p["forum_id"]: p for p in predictions_payload.get("predictions", []) if p.get("forum_id")}
    return {
        "run": predictions_payload.get("run", {}),
        "initial_rating": _initial_rating_metrics(labels, predictions_by_forum),
        "final_decision": _final_decision_metrics(labels, predictions_by_forum),
        "probability": _probability_metrics(labels, predictions_by_forum),
    }


_DELTA_METRICS: dict[str, tuple[str, ...]] = {
    "initial_rating": ("mae", "median_absolute_error", "spearman"),
    "final_decision": ("accuracy", "precision", "recall", "f1"),
    "probability": ("brier_score", "ece"),
}


def _compute_deltas(generic_scores: dict, paperscope_scores: dict) -> dict:
    deltas: dict[str, dict] = {}
    for task, metric_names in _DELTA_METRICS.items():
        deltas[task] = {}
        for name in metric_names:
            g_val = generic_scores[task].get(name)
            p_val = paperscope_scores[task].get(name)
            deltas[task][name] = round(p_val - g_val, 4) if isinstance(g_val, (int, float)) and isinstance(p_val, (int, float)) else None
    return deltas


def _warnings_for(scores: dict, system_name: str, eval_forum_venues: set[str]) -> list[str]:
    warnings: list[str] = []
    for task in ("initial_rating", "final_decision"):
        n = scores[task]["sample_size"]
        if 0 < n < EVAL_SMALL_SAMPLE_WARNING_N:
            warnings.append(f"{system_name}/{task}: small sample (n={n}) -- not sufficient for a statistically significant comparison")
    if len(eval_forum_venues) <= 1:
        venue = next(iter(eval_forum_venues), "unknown")
        warnings.append(f"evaluation set covers a single venue family ({venue!r}) -- results may not generalize across venues")
    return warnings


def evaluate(
    *,
    dataset_dir: Path,
    generic_predictions_path: Path,
    paperscope_predictions_path: Path,
    output_dir: Path,
    baseline_predictions_path: Path | None = None,
    generated_at: str | None = None,
) -> dict:
    """Validates (never trusting a prior `validate-eval` run) then scores both prediction
    files, writing `evaluation_results.json` and `evaluation_report.md` to `output_dir`.
    Raises `EvaluationValidationError` (with every violation collected) if leakage
    validation fails -- metrics are never computed over an unvalidated pair of runs.
    """
    dataset_dir = Path(dataset_dir)
    report = run_leakage_validation(dataset_dir, generic_predictions_path, paperscope_predictions_path)
    if not report.ok:
        raise EvaluationValidationError("; ".join(report.violations))

    manifest, model_inputs, labels = _load_dataset(dataset_dir)
    generic_payload = json.loads(Path(generic_predictions_path).read_text())
    paperscope_payload = json.loads(Path(paperscope_predictions_path).read_text())

    generic_scores = score_predictions(labels, generic_payload)
    paperscope_scores = score_predictions(labels, paperscope_payload)
    baseline_scores = None
    if baseline_predictions_path is not None:
        baseline_payload = json.loads(Path(baseline_predictions_path).read_text())
        baseline_scores = score_predictions(labels, baseline_payload)

    eval_forum_venues = {mi["venue_family"] for mi in model_inputs}
    warnings = (
        _warnings_for(generic_scores, "generic", eval_forum_venues)
        + _warnings_for(paperscope_scores, "paperscope", eval_forum_venues)
    )

    generated_at = generated_at or iso_now()
    results = {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "dataset": {
            "model_inputs_hash": manifest["model_inputs_hash"],
            "private_labels_hash": manifest["private_labels_hash"],
            "calibration_hash": manifest["calibration_hash"],
            "corpus_hash": manifest["corpus_hash"],
            "eval_forum_count": manifest["eval_forum_count"],
        },
        "generic": generic_scores,
        "paperscope": paperscope_scores,
        "baseline": baseline_scores,
        "deltas": _compute_deltas(generic_scores, paperscope_scores),
        "leakage_checks": {"passed": report.ok, "violations": report.violations},
        "missing_predictions": {
            "generic": report.missing_generic_predictions,
            "paperscope": report.missing_paperscope_predictions,
        },
        "warnings": warnings,
        "generated_at": generated_at,
    }

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output_dir / "evaluation_results.json", json.dumps(results, indent=2, sort_keys=True))
    atomic_write_text(output_dir / "evaluation_report.md", render_report(results))

    return results


# ----------------------------------------------------------------------------------------
# deterministic Markdown report
# ----------------------------------------------------------------------------------------

_METRIC_DEFINITIONS = [
    "**MAE** / **median absolute error** — mean / median of |predicted rating − target rating| over forums where both a prediction and an initial-rating label exist. Lower is better.",
    "**Spearman** — rank correlation between predicted and target initial ratings (average-rank ties). Range [-1, 1], higher is better. Requires >= 2 scored forums.",
    "**Accuracy / precision / recall / F1** — standard binary classification metrics for the final-decision task, positive class = `accept`. Computed only over forums with a resolved (accept/reject) label and a non-null `decision_prediction`.",
    "**Brier score** — mean squared error between `accept_probability` and the binary accept/reject outcome. Lower is better. Only computed when `accept_probability` is present and the eligible sample size is adequate — never approximated from `rating_prediction`.",
    "**ECE** — expected calibration error (10 equal-width probability bins). Only computed under the same conditions as Brier score.",
    "**Coverage** — predicted_count / eligible_forum_count for a task.",
]


def _fmt(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _render_side_by_side(task: str, generic: dict, paperscope: dict, deltas: dict, rows: list[tuple[str, str]]) -> list[str]:
    lines = ["| Metric | Generic | PaperScope | Delta (PaperScope − Generic) |", "|---|---|---|---|"]
    for label, key in rows:
        lines.append(f"| {label} | {_fmt(generic.get(key))} | {_fmt(paperscope.get(key))} | {_fmt(deltas.get(key))} |")
    return lines


def render_report(results: dict) -> str:
    """Deterministic given `results` -- no timestamp-dependent branching beyond the
    `generated_at` line itself."""
    ds = results["dataset"]
    generic, paperscope = results["generic"], results["paperscope"]
    deltas = results["deltas"]
    leakage = results["leakage_checks"]

    lines = [
        "# PaperScope evaluation report",
        "",
        f"Generated at: {results['generated_at']}",
        "",
        "**Do not claim statistical significance from small samples.** See Warnings below "
        "for this run's specific small-sample / single-venue flags.",
        "",
        "## Dataset",
        "",
        f"- Evaluation forums: {ds['eval_forum_count']}",
        f"- Source corpus hash: `{ds['corpus_hash']}`",
        f"- Calibration hash (frozen before evaluation forum selection): `{ds['calibration_hash']}`",
        f"- Model-visible input hash: `{ds['model_inputs_hash']}`",
        f"- Private label hash: `{ds['private_labels_hash']}`",
        "",
        "## Leakage checks",
        "",
        f"**Passed: {'yes' if leakage['passed'] else 'no'}.**",
    ]
    if leakage["violations"]:
        lines.append("")
        for v in leakage["violations"]:
            lines.append(f"- {v}")
    lines += [
        "",
        "Checks performed: calibration/evaluation forum-ID disjointness, dataset hash "
        "internal consistency, prediction file schema validity, prediction files "
        "reference only evaluation forums, and generic/PaperScope run comparability "
        "(identical model/settings/input hashes and forum sets, calibration difference "
        "only).",
        "",
        "## Missing predictions",
        "",
        f"- Generic: {len(results['missing_predictions']['generic'])} evaluation forum(s) with no prediction",
        f"- PaperScope: {len(results['missing_predictions']['paperscope'])} evaluation forum(s) with no prediction",
        "",
        "## Initial-rating prediction",
        "",
        f"Target: {generic['initial_rating']['aggregation']}. Eligible forums: "
        f"{generic['initial_rating']['eligible_forum_count']}.",
        "",
        *_render_side_by_side(
            "initial_rating", generic["initial_rating"], paperscope["initial_rating"], deltas["initial_rating"],
            [
                ("Sample size (n)", "sample_size"),
                ("Coverage", "coverage"),
                ("MAE", "mae"),
                ("Median absolute error", "median_absolute_error"),
                ("Spearman", "spearman"),
            ],
        ),
        "",
        "## Final-decision prediction",
        "",
        f"Eligible forums (resolved accept/reject only): {generic['final_decision']['eligible_forum_count']}.",
        "",
        *_render_side_by_side(
            "final_decision", generic["final_decision"], paperscope["final_decision"], deltas["final_decision"],
            [
                ("Sample size (n)", "sample_size"),
                ("Coverage", "coverage"),
                ("Accuracy", "accuracy"),
                ("Precision", "precision"),
                ("Recall", "recall"),
                ("F1", "f1"),
            ],
        ),
        "",
        "### Confusion matrices",
        "",
        f"- Generic: `{json.dumps(generic['final_decision']['confusion_matrix'], sort_keys=True)}`",
        f"- PaperScope: `{json.dumps(paperscope['final_decision']['confusion_matrix'], sort_keys=True)}`",
        "",
        "## Probability calibration",
        "",
    ]
    for name, scores in (("Generic", generic), ("PaperScope", paperscope)):
        prob = scores["probability"]
        if prob["computed"]:
            lines.append(f"- {name}: Brier score = {_fmt(prob['brier_score'])}, ECE = {_fmt(prob['ece'])} (n={prob['sample_size']})")
        else:
            lines.append(f"- {name}: not computed ({prob['reason']})")
    lines += [
        "",
        "## Metric definitions",
        "",
        *(f"- {d}" for d in _METRIC_DEFINITIONS),
        "",
        "## Warnings",
        "",
    ]
    if results["warnings"]:
        lines += [f"- {w}" for w in results["warnings"]]
    else:
        lines.append("- (none)")
    lines += [
        "",
        "## Limitations",
        "",
        "- Model-visible input is title + abstract only (`input_tier: abstract_only`) -- "
        "the current corpus schema does not store full paper text, so no full-text "
        "prediction condition exists yet.",
        "- Initial-rating target is an unweighted mean across reviewers; it does not "
        "account for reviewer confidence or venue-specific scale differences.",
        "- Small per-venue/year breakdown strata (n < 5) are omitted from the breakdown "
        "table, not silently included with a noisy estimate -- see "
        "`evaluation_results.json`'s `breakdown_skipped` for what was dropped and why.",
        "",
    ]
    return "\n".join(lines) + "\n"
