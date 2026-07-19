# Leakage-safe offline evaluation (Phase 4B)

Three deterministic, offline commands (`src/paperscope/evaluation.py`) that score saved
prediction files against a forum-split evaluation dataset. **Nothing here calls an LLM,
touches the network, or constructs an OpenReview client** — see
`tests/test_evaluation.py`'s CLI-level regression tests, which monkeypatch both
`openreview.Client` and `socket.socket` to fail loudly if either is ever touched.
Generating predictions is a manual, external step — this module only prepares the
dataset, validates saved predictions, and computes metrics.

## The manual workflow

```
paperscope prepare-eval --corpus data/full/iclr.jsonl \
                         --calibration-forums artifacts/evidence.json \
                         --output artifacts/eval_dataset --seed 42
# -> generate generic predictions externally (any system, any prompt), save as generic.json
# -> generate PaperScope predictions externally, using IDENTICAL model/settings, save as paperscope.json
paperscope validate-eval --dataset artifacts/eval_dataset \
                          --generic-predictions generic.json \
                          --paperscope-predictions paperscope.json
paperscope evaluate --dataset artifacts/eval_dataset \
                     --generic-predictions generic.json \
                     --paperscope-predictions paperscope.json \
                     --output artifacts/eval_results
```

`evaluate` re-runs every check `validate-eval` runs (it never trusts a prior validation
pass) before computing a single metric — see `run_leakage_validation`.

## Why forum-level splitting

A forum's reviews, rebuttal, and decision are one inseparable unit. If any part of a
forum was used to calibrate PaperScope's venue reference, evaluating on that same forum
would let the system see its own answer key. `prepare-eval` therefore:

1. Loads the frozen calibration forum-ID set **first**, and hashes it (`calibration_hash`)
   before looking at the corpus at all — see `freeze_calibration_hash`.
2. Selects evaluation forums as `corpus forums − calibration forums`, further excluding
   forums with no usable label for either task, or no title/abstract to show a model.
3. Asserts the resulting sets are disjoint as defense-in-depth, on top of the exclusion
   logic already guaranteeing it.

`--calibration-forums` accepts either a plain JSON list of forum IDs, `{"forum_ids":
[...]}`, or an evidence-bundle-shaped manifest (`{"items": [{"forum_id": ...}, ...]}`,
i.e. you can point it directly at the `evidence.json` a venue's skill calibration was
built from).

### What actually guarantees no leakage

In order of strength, these four hold regardless of any other code in this module:

1. **Closed model-input schema** — `ModelInput` has exactly forum_id/venue_family/
   venue_year/title/abstract/input_tier/schema_version. There is no review, rating,
   decision, or rebuttal field on the dataclass at all, so nothing there can leak
   through it by construction.
2. **Separate private labels** — targets live only in `private_labels.jsonl`, a file
   never written into or merged with anything model-visible.
3. **Forum-level disjointness** — calibration and evaluation forum-ID sets are computed
   to be disjoint by construction (calibration is subtracted out before evaluation
   forums are even considered) and re-checked from the files on disk at validate time.
4. **Hash validation** — `model_inputs_hash`/`private_labels_hash`/`calibration_hash`
   are recomputed from the actual files on disk and compared against the recorded
   manifest values, so a stale or hand-edited file is caught rather than trusted.

`check_no_review_leakage` (run automatically inside `prepare-eval`) is a **supplemental**
safeguard on top of the above, not an independent guarantee — it greps each forum's own
review/response/decision text for a long, literal substring match against that same
forum's title/abstract. That catches an accidental literal copy-paste (e.g. a future bug
that pipes review text into `Paper.abstract`), but it cannot detect a paraphrase, a
translation, or a leak arriving through a field this function doesn't know to check. A
clean result from it means "no obvious copy-paste leak was found", not "no leakage is
possible" — the four guarantees above are what actually make that claim.

## Dataset outputs (`prepare-eval`)

| File | Contents |
|---|---|
| `model_inputs.jsonl` | One row per evaluation forum: `forum_id`, `venue_family`, `venue_year`, `title`, `abstract`, `input_tier` (always `"abstract_only"` today — the corpus schema has no full-text field yet), `schema_version`. **No other field can ever appear here** — `ModelInput` is a closed dataclass with exactly these fields. |
| `private_labels.jsonl` | One row per evaluation forum with **both** tasks' targets and eligibility, never intended for model context: `initial_rating_target`/`initial_rating_aggregation`/`initial_rating_n`/`initial_rating_eligible`, `final_decision_target`/`final_decision_raw`/`final_decision_eligible`/`final_decision_excluded_reason`. |
| `split_manifest.json` | `seed`, `max_forums`, `corpus_hash`, `calibration_hash`, the frozen `calibration_forum_ids` list, `eval_forum_count`, `exclusions` (forum_id + reason), `exclusion_counts`, per-venue/year `stratification` for both sets. |
| `evaluation_manifest.json` | `schema_version`, `seed`, `corpus_hash`, `calibration_hash`, `model_inputs_hash`, `private_labels_hash`, `eval_forum_count`, and each task's `target_definition` + `eligible_forum_count`. This is what `evaluate`/`validate-eval` check saved predictions against. |

By default (`--max-forums` unset) no random sampling happens at all — every eligible
non-calibration forum is included, and `seed` is recorded purely for provenance. Passing
`--max-forums N` caps the evaluation set at `N` forums via `_stratified_subsample`:
deterministic, venue/year-stratified (largest-remainder proportional quota per stratum,
then `random.Random(seed).sample()` within each stratum) — same seed + inputs always
produces the same subset; a different seed generally produces a different one. Forums
dropped by subsampling are recorded in `split_manifest.json`'s `exclusions` with reason
`subsampled_out`, same as any other exclusion reason.

### Exclusion reasons

| Reason | Meaning |
|---|---|
| `in_calibration_set` | Forum is in the frozen calibration set — never eligible for evaluation. |
| `no_usable_labels` | Forum has no initial rating on any review **and** no resolved (accept/reject) decision — nothing to score against either task. |
| `missing_paper_content` | Forum has neither a title nor an abstract to show a model. |

### The two tasks are never conflated

- **Initial-rating prediction** — target is the unweighted mean of every review's
  `initial_rating.value` for the forum (see `INITIAL_RATING_AGGREGATION` /
  `build_private_label`). **Final/revised ratings are never used.** A forum is eligible
  only with ≥1 non-null initial rating.
- **Final-decision prediction** — target is `ForumRecord.decision.normalized`, restricted
  to `{accept, reject}`. **Never derived from a rating threshold.** Withdrawn,
  desk-rejected, and unresolved (`unknown`) forums are excluded from the eligible pool;
  their counts are still recorded (`split_manifest.json` exclusions and each label row's
  `final_decision_excluded_reason`), i.e. reported separately rather than silently dropped
  or folded into the main metric.

Every `PrivateLabel` row carries both tasks' fields independently — a forum can be
eligible for one task and not the other (e.g. withdrawn but rated).

## Prediction file schema

```json
{
  "run": {
    "run_id": "...", "system": "generic | paperscope | baseline", "model": "...",
    "settings": {"...": "..."}, "input_hash": "...", "calibration_hash": "...",
    "created_at": "..."
  },
  "predictions": [
    {
      "forum_id": "...",
      "rating_prediction": 5.5,
      "decision_prediction": "accept",
      "accept_probability": 0.72,
      "reasoning_summary": "..."
    }
  ]
}
```

- `rating_prediction` / `decision_prediction` are independent, optional fields — a
  system may answer one task and not the other.
- `accept_probability` is optional and **never derived from `rating_prediction`** — see
  `test_probability_never_approximated_from_rating_prediction`. Missing it just means
  probability metrics skip that forum, not that one gets estimated.
- `run.input_hash` must equal the dataset's `model_inputs_hash` — proves both systems saw
  the identical model-visible content.
- `run.calibration_hash` must be `"none"` (`paperscope.config.NO_CALIBRATION`) for a
  `generic` run and must equal the dataset's frozen `calibration_hash` for a
  `paperscope` run — **the only intended difference between the two runs.**
- Duplicate or unknown (non-evaluation) `forum_id`s are rejected. Predictions missing for
  some evaluation forums are reported, not rejected — partial coverage is allowed and
  shown in the report.

## `paperscope validate-eval` / leakage validation

Collects **every** violation before failing (matching `evidence.py`/`generation.py`'s
validation style), across:

- **Dataset internal consistency** — recomputes `model_inputs_hash`/`private_labels_hash`
  from the files on disk and compares to `evaluation_manifest.json`; recomputes
  `calibration_hash` from `split_manifest.json`'s own `calibration_forum_ids`; checks
  `calibration_hash`/`corpus_hash`/`seed` agree between the two manifests; re-derives
  calibration/evaluation forum-ID disjointness; rejects any `model_inputs.jsonl` row with
  a field outside the closed schema (defense against a future leak).
- **Prediction schema** — both files independently, per the schema above.
- **Dataset membership** — both files reference only evaluation forum IDs.
- **Run comparability** — model, settings, and input hash must match exactly between the
  generic and PaperScope runs; only `calibration_hash` is allowed (and required) to
  differ, in the specific direction described above; both runs must cover the same
  forum-ID set.

`evaluate` runs this exact same check internally before computing a single metric, so a
skipped or stale `validate-eval` call can't let an invalid comparison through.

## `paperscope evaluate`

### Initial-rating metrics
MAE, median absolute error, Spearman correlation (pure-Python rank correlation, average
ranks for ties — no `numpy`/`scipy` dependency), prediction coverage
(`predicted_count / eligible_forum_count`), and a per-`(venue_family, venue_year)`
breakdown — strata under `EVAL_MIN_BREAKDOWN_N` (5) forums are reported as
`breakdown_skipped` with a reason, not silently included.

### Final-decision metrics
Accuracy, precision, recall, F1 (positive class `accept`), confusion matrix, coverage,
and the same per-venue/year breakdown treatment.

### Probability metrics
Brier score and expected calibration error (10 equal-width bins), computed **only** when
`accept_probability` is present for at least `EVAL_MIN_PROBABILITY_N` (20) eligible
forums; otherwise `"computed": false` with an explicit `reason` — never a fabricated or
approximated number.

### Outputs

- `evaluation_results.json` — generic/paperscope/baseline scores side by side, `deltas`
  (paperscope − generic, for the metrics where that's meaningful), `leakage_checks`,
  `missing_predictions`, and small-sample/single-venue `warnings`.
- `evaluation_report.md` — the same data as Markdown: sample sizes, exclusions, missing
  predictions, metric definitions, leakage-check results, every corpus/split/calibration
  hash, limitations, whether probability metrics were computed and why not if skipped,
  and warnings. Deterministic for identical `results` input.

Neither file claims statistical significance — the report opens with an explicit
"do not claim statistical significance from small samples" line, and per-metric warnings
fire under `EVAL_SMALL_SAMPLE_WARNING_N` (20) or when the evaluation set covers a single
venue family.

## Replicated ICLR 2024 pilot results

PaperScope was evaluated in two disjoint ICLR 2024 abstract-only pilots using the same
frozen 40-forum calibration set (`calibration_hash=0fe31f889fd66235`).

The two conditions used the same model and recorded settings:

- Model: Sonnet 5
- Input: title and abstract only
- Effort: high
- Generation mode: Claude Code subscription
- Generic condition: no venue calibration reference
- PaperScope condition: frozen ICLR calibration reference

| Run | Rating n | Resolved decision n | Generic MAE | PaperScope MAE | Generic Spearman | PaperScope Spearman | Generic accuracy | PaperScope accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Run 1 | 25 | 15 | 1.4833 | 1.1487 | 0.3680 | 0.5404 | 0.6000 | 0.8000 |
| Run 2 | 25 | 20 | 1.1687 | 0.9260 | 0.4361 | 0.5946 | 0.6500 | 0.7500 |

Across both runs:

- Rating-eligible forums: **50**
- Generic weighted MAE: **1.3260**
- PaperScope weighted MAE: **1.0374**
- Relative MAE reduction: **21.8%**
- Resolved decision forums: **35**
- Generic decision accuracy: **62.9%**
- PaperScope decision accuracy: **77.1%**
- Generic false accepts: **9**
- PaperScope false accepts: **2**

PaperScope consistently reduced rating error, improved rank correlation, and reduced
false accepts. The trade-off was lower acceptance recall: pooled false rejects increased
from 4 to 6.

Probability calibration did not improve in Run 2, the only run large enough for the
configured probability metrics: Brier score changed from 0.1864 to 0.1874 and ECE from
0.2935 to 0.3090.

These are descriptive pilot results, not claims of statistical significance or
cross-venue generalization. Both prediction conditions were generated manually in
separate fresh Claude Code sessions. Claude Code subscription runs do not expose a
controllable temperature or guarantee API-level deterministic reproduction.


## Reviewer-aggregate baseline (optional)

`compute_reviewer_aggregate_baseline` derives a naive constant baseline —
every evaluation forum gets the same predicted rating (calibration-set mean initial
rating) and the same predicted decision (calibration-set majority accept/reject) —
**strictly from calibration-set aggregates, never from an evaluation forum's own true
label.** It's a plain function you can call to write a `baseline_predictions.json`
alongside the dataset; pass it to `evaluate --baseline-predictions` to include a third
column in the report. Not run automatically by `prepare-eval`.

## Limitations

- Model-visible input is title + abstract only (`input_tier: "abstract_only"`) — the
  current corpus schema (`Paper` in `models.py`) has no full-text field, so there is no
  full-paper-text evaluation condition yet.
- By default, every eligible non-calibration forum is included. When
  `--max-forums` is provided, PaperScope performs deterministic, venue/year-stratified
  subsampling using the recorded seed.
- Initial-rating target is an unweighted mean across reviewers — it does not account for
  reviewer confidence or per-venue scale differences (the same known approximation as
  `statistics.py`'s normalized rating distributions).
- Metrics are descriptive comparisons on whatever corpus was fetched — small and/or
  single-venue samples are flagged, never presented as a statistically significant
  benchmark result.
