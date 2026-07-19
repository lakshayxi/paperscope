# Statistics and evidence bundles (Phase 3A)

Two deterministic, offline commands that run against an already-fetched corpus — neither
needs OpenReview or Anthropic credentials. Both are pure functions of their input corpus
plus (for `evidence`) a seed: same corpus + same arguments always produces byte-identical
output, so results are reproducible and diffable across runs.

## `paperscope stats`

```bash
paperscope stats --corpus data/full/iclr.jsonl --output artifacts/statistics
```

Computes deterministic statistics scoped per `(venue_family, venue_year)`, plus a
`(venue_family, "all")` aggregate scope per family across years. Reads **only**
structural/numeric fields (ratings, confidence, decision, counts) — never review or
response text — so it's safe to run against either corpus tier
(`data/full/<family>.jsonl` or `data/public/<family>.jsonl`).

Writes two files into `--output <directory>`:
- `statistics.json` — machine-readable, schema below
- `statistics.md` — the same data as a deterministic Markdown summary (stable table/row
  ordering regardless of input order — see `render_markdown` in
  [`src/paperscope/statistics.py`](../src/paperscope/statistics.py))

### Metrics computed per scope

| Metric | What it measures |
|---|---|
| `forum_count` / `review_count` / `response_count` | raw counts |
| `missing_rate.{paper_title,paper_abstract,decision,review_rating,review_confidence}` | fraction of records/reviews missing that field |
| `rating_distribution_raw` / `confidence_distribution_raw` | histogram keyed by the reported value |
| `rating_distribution_normalized` / `confidence_distribution_normalized` | same, min-max scaled to `[0,1]` and bucketed into deciles |
| `decision_distribution` | histogram of normalized decision categories |
| `rating_decision_crosstab` | joint distribution: rating tercile (low/medium/high, ties lean medium) × decision category |
| `paper_mean_rating` | distribution (count/mean/stdev/median/min/max) of each forum's mean rating across its rated reviews |
| `paper_rating_variance` | same, but population variance per forum (only forums with ≥2 rated reviews) |
| `reviewer_disagreement` | same, but per-forum range (max − min); plus a `{0, 1-2, 3-4, 5+}` histogram bucket |
| `initial_to_final_rating_change` | delta stats over reviews with both an initial and a final rating value |
| `rebuttal_present_rating_change` / `rebuttal_absent_rating_change` | same delta computation, split by whether the forum has ≥1 response note — **observational, not causal** (see Limitations) |

### Every stat's shape

Every entry in `statistics.json["stats"]` is self-describing and independently
interpretable, even copied out of the file on its own:

```json
{
  "metric": "paper_mean_rating",
  "venue_family": "iclr",
  "venue_year": 2026,
  "sample_size": 10,
  "missing_count": 0,
  "value": {"count": 10, "mean": 4.3333, "stdev": 1.3354, "median": 4.0, "min": 2.0, "max": 6.5},
  "corpus_hash": "9222deb94e5619fc",
  "generated_at": "2026-07-18T23:56:36Z",
  "schema_version": 1,
  "observational": false,
  "note": null
}
```

`observational=true` + a non-null `note` mark the two rebuttal-change metrics — read the
note before treating either as evidence that rebuttals move scores.

## `paperscope evidence`

```bash
paperscope evidence --corpus data/full/iclr.jsonl --output artifacts/evidence_bundle.json --seed 42
# optional: --max-items 60 --per-bucket 4 --held-out held_out_forums.json
```

Generates a bounded, seeded evidence bundle for the (future) calibration-generation
phase. **Requires the full-text tier** (`data/full/<family>.jsonl`) — it reads real
review text, which the public tier has already replaced with excerpt hashes; running it
against `data/public/` fails immediately with a clear error (`is_public_tier` check).

### Selection algorithm

One candidate per `(forum, review)` pair with non-empty excerpt-source text (`review.text`,
else `strengths + weaknesses`, else `summary`). Each candidate is tagged along five axes,
in this fixed order: `decision_bucket` (accepted/rejected/unknown — `desk_reject` folds
into rejected), `rating_bucket` (low/medium/high, via global terciles computed once over
the corpus's rating values — ties lean toward `medium`), `year`, `disagreement_bucket`
(high/low via a per-forum range median split; forums with <2 rated reviews get
`insufficient_data` on this axis only), `rebuttal_bucket` (present/absent, based on
whether the forum has ≥1 response note).

A single `random.Random(seed)` samples up to `--per-bucket` candidates per category
within each axis (category order and candidate pools are always pre-sorted, so the same
seed always draws in the same order). If the union across all axes exceeds
`--max-items`, it's downsampled (with the same seeded RNG) to the bound — **this is a
size cap only, not a rebalancing step**: a capped bundle is not guaranteed to still
represent every stratum evenly.

Same seed ⇒ identical bundle. A different seed generally produces a different one,
*except* when every stratum is small enough that `--per-bucket` never oversubscribes it
— in that case there's nothing for the RNG to choose between, and the bundle is
seed-invariant by construction (this is expected on today's small ICLR sample corpus,
not a bug — see Limitations).

### Every excerpt's shape

```json
{
  "evidence_id": "ev_e6e0a99f8bb7996f",
  "venue_family": "iclr",
  "venue_year": 2026,
  "forum_id": "5HHkCSVHaU",
  "note_id": "dnm2b7cSwM",
  "source_url": "https://openreview.net/forum?id=5HHkCSVHaU",
  "rating_designation": "initial",
  "rating_value": 4.0,
  "decision": "unknown",
  "content_hash": "...",
  "excerpt_text": "...",
  "excerpt_length": 812,
  "corpus_hash": "9222deb94e5619fc",
  "schema_version": 1,
  "strata": {"decision_bucket": "unknown", "rating_bucket": "medium", "year": "2026", "disagreement_bucket": "high", "rebuttal_bucket": "absent"}
}
```

`evidence_id` is a deterministic hash of `(forum_id, note_id, rating_designation)` — it
does **not** depend on the seed, so the same underlying review always gets the same ID
regardless of which run selected it. `content_hash` is the review's full-text hash
(`Review.content_hash`, computed over the untruncated text/strengths/weaknesses/questions),
unaffected by `excerpt_text` truncation — it proves the excerpt points at the correct
source review, not that `excerpt_text` itself is unedited (see Validation).

The bundle file's top level also carries a `bundle_hash` — a hash over the sorted set of
`evidence_id`s in the bundle, distinct from each item's per-excerpt `corpus_hash`. It
changes if the *selected set* of evidence changes (different seed, different bound,
different corpus), but not if only item order or run metadata (timestamp, seed value
itself) changes — a quick way to tell whether two bundles contain the same evidence
without diffing every item.

## Validation

`paperscope evidence` always validates its own output before writing (and
`validate_evidence_bundle` in
[`src/paperscope/evidence.py`](../src/paperscope/evidence.py) is independently callable
against any bundle). It collects **every** violation before raising
`EvidenceValidationError`, rejecting:

- any required provenance field missing (evidence/venue/forum/note IDs, source URL,
  rating designation, decision, content hash, corpus hash)
- duplicate `evidence_id`
- `forum_id` or `note_id` not found in the source corpus
- `content_hash` that doesn't match the source review's hash
- `excerpt_text` that isn't a prefix of the source review's current excerpt text (catches
  a hand-edited excerpt even if `content_hash` was left untouched)
- `venue_family`/`venue_year` that don't match the actual source record (an "unsupported
  venue/year claim" — e.g. a hand-tampered bundle)
- any forum in the bundle that's also in a supplied held-out set (`--held-out`, a JSON
  list of forum IDs) — held-out forums are also excluded from the candidate pool
  up-front during generation, so this check is defense-in-depth, not the only guard

## Limitations

- **Rating/confidence normalization is a scope-local min-max approximation.**
  `Rating.scale_min`/`scale_max` aren't populated by the current OpenReview parsing (see
  `parsing.py`) — venues report differing raw scales and no per-venue scale metadata is
  fetched yet. Normalization falls back to the observed min/max within each scope. If
  scale bounds are ever populated, normalization will prefer them.
- **"Rebuttal-present" is a proxy, not a verified label.** Current parsing tags every
  author/committee response note as `"rebuttal"`
  (`parsing.classify_and_split_children`/`build_forum_record`) — there's no way yet to
  distinguish a real author rebuttal from a general committee comment. "Has ≥1 response"
  is the best available proxy for "had a rebuttal." Both `stats`'s rebuttal-change
  metrics and `evidence`'s `rebuttal_bucket` inherit this limitation; the stats metrics
  are explicitly tagged `observational=true` for this reason.
- **The live corpus (`data/full/iclr.jsonl`) is small and currently single-venue-year.**
  As of this writing it's 10 ICLR 2026 forums with an active (unresolved) review cycle:
  `decision_distribution` is 100% `"unknown"` and `initial_to_final_rating_change` is
  always empty (no revision snapshot has been captured yet). `rating_bucket` and
  `rebuttal_bucket` do have genuine multi-category coverage today; `decision_bucket` and
  `year` do not. This will improve automatically as the scheduled fetch automation
  accumulates more venue-years and review cycles resolve — it's a corpus-maturity
  limitation, not a bug in either module.
- Neither module has been run at a scale where the seeded-sampling and size-cap behavior
  has been stress-tested beyond unit fixtures; see `tests/test_evidence.py` for the
  synthetic oversubscribed-bucket fixture used to validate seed-sensitivity, since the
  real corpus is currently too small for that property to be observable end-to-end.
