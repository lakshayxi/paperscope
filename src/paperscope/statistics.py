"""Deterministic, venue/year-scoped corpus statistics.

Every computed statistic is self-describing: it carries its own sample size,
missing-value count, venue/year scope, source corpus hash, generation timestamp, and
schema version, so a single `Stat` record copied out of `statistics.json` stays
interpretable without its surrounding file. This mirrors the provenance discipline in
`evidence.py` (see `EvidenceItem`) and in `storage.py`'s manifest.

Nothing here reads review/response *text* -- only structural/numeric fields (ratings,
confidence, decision, counts) -- so `paperscope stats` is safe to run against either
corpus tier (`data/full/` or `data/public/`), unlike `evidence.py` which needs full text.

Rating/confidence "normalized" distributions min-max scale within each venue/year scope
because `Rating.scale_min`/`scale_max` aren't populated by the current OpenReview parsing
(see parsing.py) -- venues report differing raw scales and no per-venue scale metadata is
fetched yet. If scale_min/scale_max are ever populated, normalization prefers them over
this observed-range fallback. Known approximation -- see docs/statistics_and_evidence.md.

Rebuttal-present vs. rebuttal-absent comparisons are correlational, not causal: current
parsing tags every author/committee response note as "rebuttal" (see
`parsing.classify_and_split_children` / `build_forum_record`), so "has a response" is the
best available proxy for "had a rebuttal", not a verified treatment assignment. These
stats are tagged `observational=True` with an explanatory `note`.
"""

from __future__ import annotations

import json
import statistics as pystats
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from paperscope.config import STATS_SCHEMA_VERSION
from paperscope.models import ForumRecord, Review
from paperscope.storage import atomic_write_text

YEAR_ALL = "all"

REBUTTAL_OBSERVATIONAL_NOTE = (
    "Observational, not causal: 'rebuttal-present' means the forum has at least one "
    "response note (current parsing tags all author/committee responses as 'rebuttal', "
    "see parsing.classify_and_split_children); no causal claim about rebuttal "
    "effectiveness is made or supported by this comparison."
)


def iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class Stat:
    metric: str
    venue_family: str
    venue_year: int | str
    sample_size: int
    missing_count: int
    value: object
    corpus_hash: str
    generated_at: str
    schema_version: int = STATS_SCHEMA_VERSION
    observational: bool = False
    note: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _scope_key(record: ForumRecord) -> tuple[str, int | str]:
    year = record.venue_year if record.venue_year is not None else "unspecified"
    return record.venue_family or "unknown", year


def group_by_scope(records: dict[str, ForumRecord]) -> dict[tuple[str, int | str], list[ForumRecord]]:
    """Group forums by (venue_family, venue_year), plus a (family, "all") aggregate
    scope per family so both year-over-year and all-time views are available.
    """
    by_scope: dict[tuple[str, int | str], list[ForumRecord]] = {}
    by_family: dict[str, list[ForumRecord]] = {}
    for record in records.values():
        key = _scope_key(record)
        by_scope.setdefault(key, []).append(record)
        by_family.setdefault(key[0], []).append(record)
    for family, forums in by_family.items():
        by_scope[(family, YEAR_ALL)] = forums
    return by_scope


def _values(items: Iterable, getter: Callable) -> list[float]:
    out = []
    for it in items:
        v = getter(it)
        if v is not None:
            out.append(v)
    return out


def _distribution_summary(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "mean": None, "stdev": None, "median": None, "min": None, "max": None}
    return {
        "count": len(values),
        "mean": round(pystats.mean(values), 4),
        "stdev": round(pystats.pstdev(values), 4) if len(values) > 1 else 0.0,
        "median": round(pystats.median(values), 4),
        "min": min(values),
        "max": max(values),
    }


def _histogram(values: list[float]) -> dict:
    hist: dict[str, int] = {}
    for v in values:
        key = str(v)
        hist[key] = hist.get(key, 0) + 1
    return dict(sorted(hist.items(), key=lambda kv: float(kv[0])))


def _normalized_bucket_histogram(values: list[float]) -> dict:
    """Min-max scale `values` to [0, 1] within this call's population and bucket into
    deciles. See module docstring for why observed-range min-max is the fallback.
    """
    if not values:
        return {}
    lo, hi = min(values), max(values)
    hist = {f"{i / 10:.1f}-{(i + 1) / 10:.1f}": 0 for i in range(10)}
    for v in values:
        normalized = 0.5 if hi == lo else (v - lo) / (hi - lo)
        bucket = min(9, int(normalized * 10))
        key = f"{bucket / 10:.1f}-{(bucket + 1) / 10:.1f}"
        hist[key] += 1
    return hist


def _forum_metrics(
    forums: list[ForumRecord], *, corpus_hash: str, generated_at: str, venue_family: str, venue_year: int | str
) -> list[Stat]:
    stats: list[Stat] = []

    def add(metric: str, sample_size: int, missing_count: int, value, *, observational=False, note=None):
        stats.append(
            Stat(
                metric=metric,
                venue_family=venue_family,
                venue_year=venue_year,
                sample_size=sample_size,
                missing_count=missing_count,
                value=value,
                corpus_hash=corpus_hash,
                generated_at=generated_at,
                observational=observational,
                note=note,
            )
        )

    n_forums = len(forums)
    all_reviews: list[Review] = [r for f in forums for r in f.reviews]
    all_responses = [r for f in forums for r in f.responses]

    add("forum_count", n_forums, 0, n_forums)
    add("review_count", n_forums, sum(1 for f in forums if not f.reviews), len(all_reviews))
    add("response_count", n_forums, sum(1 for f in forums if not f.responses), len(all_responses))

    def missing_rate(name: str, denom_items: list, is_missing: Callable):
        missing = sum(1 for it in denom_items if is_missing(it))
        rate = round(missing / len(denom_items), 4) if denom_items else None
        add(f"missing_rate.{name}", len(denom_items), missing, rate)

    missing_rate("paper_title", forums, lambda f: not f.paper.title)
    missing_rate("paper_abstract", forums, lambda f: not f.paper.abstract)
    missing_rate("decision", forums, lambda f: f.decision.normalized in ("", "unknown"))
    missing_rate("review_rating", all_reviews, lambda r: r.initial_rating.value is None)
    missing_rate("review_confidence", all_reviews, lambda r: r.confidence.value is None)

    rating_values = _values(all_reviews, lambda r: r.initial_rating.value)
    add(
        "rating_distribution_raw",
        len(rating_values),
        len(all_reviews) - len(rating_values),
        _histogram(rating_values),
    )
    add(
        "rating_distribution_normalized",
        len(rating_values),
        len(all_reviews) - len(rating_values),
        _normalized_bucket_histogram(rating_values),
    )

    conf_values = _values(all_reviews, lambda r: r.confidence.value)
    add(
        "confidence_distribution_raw",
        len(conf_values),
        len(all_reviews) - len(conf_values),
        _histogram(conf_values),
    )
    add(
        "confidence_distribution_normalized",
        len(conf_values),
        len(all_reviews) - len(conf_values),
        _normalized_bucket_histogram(conf_values),
    )

    decision_hist: dict[str, int] = {}
    for f in forums:
        key = f.decision.normalized or "unknown"
        decision_hist[key] = decision_hist.get(key, 0) + 1
    add("decision_distribution", n_forums, decision_hist.get("unknown", 0), dict(sorted(decision_hist.items())))

    # rating-vs-decision joint distribution, using the same tercile bucketing convention
    # (ties lean toward "medium") as evidence.py's rating_bucket, computed independently
    # here to keep statistics.py and evidence.py decoupled.
    if rating_values:
        sorted_ratings = sorted(rating_values)
        lo_cut = sorted_ratings[len(sorted_ratings) // 3]
        hi_cut = sorted_ratings[(2 * len(sorted_ratings)) // 3]
    else:
        lo_cut = hi_cut = 0.0

    def _rating_tercile(v: float) -> str:
        if v < lo_cut:
            return "low"
        if v > hi_cut:
            return "high"
        return "medium"

    crosstab: dict[str, dict[str, int]] = {}
    for f in forums:
        decision_key = f.decision.normalized or "unknown"
        for r in f.reviews:
            if r.initial_rating.value is None:
                continue
            bucket = _rating_tercile(r.initial_rating.value)
            row = crosstab.setdefault(decision_key, {})
            row[bucket] = row.get(bucket, 0) + 1
    add(
        "rating_decision_crosstab",
        len(rating_values),
        len(all_reviews) - len(rating_values),
        {d: dict(sorted(b.items())) for d, b in sorted(crosstab.items())},
    )

    per_forum_means, per_forum_vars, per_forum_ranges = [], [], []
    forums_with_rating = forums_with_2plus = 0
    for f in forums:
        vals = _values(f.reviews, lambda r: r.initial_rating.value)
        if vals:
            forums_with_rating += 1
            per_forum_means.append(pystats.mean(vals))
        if len(vals) >= 2:
            forums_with_2plus += 1
            per_forum_vars.append(pystats.pvariance(vals))
            per_forum_ranges.append(max(vals) - min(vals))

    add(
        "paper_mean_rating",
        forums_with_rating,
        n_forums - forums_with_rating,
        _distribution_summary(per_forum_means),
    )
    add(
        "paper_rating_variance",
        forums_with_2plus,
        n_forums - forums_with_2plus,
        _distribution_summary(per_forum_vars),
    )

    range_hist = {"0": 0, "1-2": 0, "3-4": 0, "5+": 0}
    for rge in per_forum_ranges:
        if rge == 0:
            range_hist["0"] += 1
        elif rge <= 2:
            range_hist["1-2"] += 1
        elif rge <= 4:
            range_hist["3-4"] += 1
        else:
            range_hist["5+"] += 1
    add(
        "reviewer_disagreement",
        forums_with_2plus,
        n_forums - forums_with_2plus,
        {**_distribution_summary(per_forum_ranges), "histogram": range_hist},
    )

    def rating_change_stat(metric: str, reviews: list[Review], *, observational=False, note=None):
        deltas = [
            r.final_rating.value - r.initial_rating.value
            for r in reviews
            if r.final_rating is not None and r.final_rating.value is not None and r.initial_rating.value is not None
        ]
        add(
            metric,
            len(reviews),
            len(reviews) - len(deltas),
            _distribution_summary(deltas),
            observational=observational,
            note=note,
        )

    rating_change_stat("initial_to_final_rating_change", all_reviews)

    rebuttal_reviews = [r for f in forums if f.responses for r in f.reviews]
    no_rebuttal_reviews = [r for f in forums if not f.responses for r in f.reviews]
    rating_change_stat(
        "rebuttal_present_rating_change", rebuttal_reviews, observational=True, note=REBUTTAL_OBSERVATIONAL_NOTE
    )
    rating_change_stat(
        "rebuttal_absent_rating_change", no_rebuttal_reviews, observational=True, note=REBUTTAL_OBSERVATIONAL_NOTE
    )

    return stats


def compute_all_statistics(
    records: dict[str, ForumRecord], *, corpus_hash: str, generated_at: str | None = None
) -> list[Stat]:
    generated_at = generated_at or iso_now()
    scopes = group_by_scope(records)
    stats: list[Stat] = []
    for family, year in sorted(scopes, key=lambda k: (k[0], str(k[1]))):
        stats.extend(
            _forum_metrics(
                scopes[(family, year)],
                corpus_hash=corpus_hash,
                generated_at=generated_at,
                venue_family=family,
                venue_year=year,
            )
        )
    return stats


def write_statistics_json(path: Path, stats: list[Stat], *, corpus_hash: str, generated_at: str) -> dict:
    payload = {
        "schema_version": STATS_SCHEMA_VERSION,
        "corpus_hash": corpus_hash,
        "generated_at": generated_at,
        "stat_count": len(stats),
        "stats": [s.to_dict() for s in stats],
    }
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True))
    return payload


def _format_value(value) -> str:
    text = json.dumps(value, sort_keys=isinstance(value, dict))
    return text.replace("|", "\\|")


def render_markdown(stats: list[Stat], *, corpus_hash: str, generated_at: str) -> str:
    """Render a deterministic Markdown summary. Stable for a given `stats` list
    regardless of its input order -- scopes and metrics are both sorted before render.
    """
    by_scope: dict[tuple[str, int | str], dict[str, Stat]] = {}
    for s in stats:
        by_scope.setdefault((s.venue_family, s.venue_year), {})[s.metric] = s

    lines = [
        "# Corpus statistics",
        "",
        f"Schema version: {STATS_SCHEMA_VERSION}  ",
        f"Source corpus hash: `{corpus_hash}`  ",
        f"Generated at: {generated_at}",
        "",
        "Deterministic output of `paperscope stats` — see "
        "[`docs/statistics_and_evidence.md`](../docs/statistics_and_evidence.md) for "
        "schema and limitations. Rebuttal-related rows marked *(observational)* are "
        "correlational, not causal — see the row's `note` field in `statistics.json`.",
        "",
    ]
    for family, year in sorted(by_scope, key=lambda k: (k[0], str(k[1]))):
        metrics = by_scope[(family, year)]
        lines.append(f"## {family} / {year}")
        lines.append("")
        lines.append("| Metric | Sample size | Missing | Value |")
        lines.append("|---|---|---|---|")
        for metric in sorted(metrics):
            s = metrics[metric]
            flag = " *(observational)*" if s.observational else ""
            lines.append(f"| {metric}{flag} | {s.sample_size} | {s.missing_count} | {_format_value(s.value)} |")
        lines.append("")
    return "\n".join(lines) + "\n"
