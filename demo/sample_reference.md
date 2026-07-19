**This is a worked example, not a production reference file.** It's the real,
unedited output of `paperscope render` against
[`demo/sample_claims.json`](sample_claims.json) — 9 hand-authored claims, grounded
against and passing structured validation against the real (but small, single-year,
still-unresolved) ICLR 2026 sample corpus already used elsewhere in `demo/`. It
illustrates every `claim_type` (`deterministic_fact`, `evidence_excerpt`,
`statistical_pattern`, `llm_interpretation`, `insufficient_evidence`) and shows the
renderer refusing to smooth over a small sample: two sections explicitly state
`insufficient_evidence` rather than fabricate a claim the data doesn't support. See
[`docs/generation.md`](../docs/generation.md) for the full workflow and schema.

`demo/sample_evidence.json`'s excerpts are trimmed to the same ~280-char
redistribution-conscious cap used by `data/public/` (see
[`docs/redistribution.md`](../docs/redistribution.md)), shorter than the 600-char bound
`paperscope evidence` normally uses locally — evidence bundles are otherwise local-only
and never committed; this demo bundle is a hand-curated exception scoped to exactly the
excerpts these 9 claims cite.

---

# Generated venue-calibration claims

Source corpus hash: `9222deb94e5619fc`  
Claim count: 9

Every claim below passed structured validation: every `evidence_id` and `statistic_ref` it cites resolves to real, unedited source data, and every `evidence_excerpt` claim's text is a verbatim quote from its cited excerpt. See [`docs/generation.md`](../docs/generation.md) for the full claim schema and validation rules.

## Score Calibration

### `score_mean_rating` — Deterministic fact

Across this sample, the paper-level mean initial rating is 4.33 (population stdev 1.34, n=10 forums).

- **Support level:** limited
- **Year scope:** [2026]
- **Statistics:** `iclr/2026/paper_mean_rating.mean`
- **Limitations:**
  - Computed over only 10 forums from a single, still-active review cycle -- not a stable venue-wide baseline yet.

### `score_rating_decision_crosstab` — Observed statistical pattern

Of 37 individual reviewer ratings, 8 fall in the low tercile, 17 in the medium tercile, and 12 in the high tercile; none of the 10 forums have a posted decision yet.

- **Support level:** limited
- **Year scope:** [2026]
- **Statistics:** `iclr/2026/rating_decision_crosstab`, `iclr/2026/decision_distribution`
- **Limitations:**
  - Decisions are 100% unresolved in this sample (active review cycle) -- this describes reviewer ratings only, not accept/reject outcomes.

## Accept Signals

### `accept_signal_addresses_clear_gap` — Evidence excerpt

The findings are valuable, particularly that CoT can *increase* hallucinations on HSS tasks  and that standard RAG provides no consistent benefit, highlighting the unique challenges of this domain.

- **Support level:** single_instance
- **Year scope:** [2026]
- **Evidence:**
  - forum `iQsKotob31`, note `QRC3A5I9VH` — https://openreview.net/forum?id=iQsKotob31
- **Limitations:**
  - A single reviewer's assessment (initial rating 6/10), not a corpus-wide pattern.

### `accept_signal_novel_simple_idea` — Evidence excerpt

This is a simple and novel idea: the model becomes active, inspects its current memory/state and accordingly constructs the context to operate on using pre-defined tools.

- **Support level:** single_instance
- **Year scope:** [2026]
- **Evidence:**
  - forum `GymjF88oGQ`, note `pQ56bGnGwK` — https://openreview.net/forum?id=GymjF88oGQ
- **Limitations:**
  - A single reviewer's assessment of a single paper (initial rating 8/10), not a corpus-wide pattern.

## Reject Signals

### `reject_signal_missing_baseline` — Evidence excerpt

The comparison primarily focuses on outcome-based versus rubric-based rewards, but an important baseline, generative rewards, is missing.

- **Support level:** single_instance
- **Year scope:** [2026]
- **Evidence:**
  - forum `FGkknrhv09`, note `dk5qk2JQi4` — https://openreview.net/forum?id=FGkknrhv09
- **Limitations:**
  - A single reviewer's assessment (initial rating 2/10), not a corpus-wide pattern.

### `reject_signal_unclear_added_value` — Evidence excerpt

It is challenging to identify sufficient additional value that this paper contributes to the existing literature.

- **Support level:** single_instance
- **Year scope:** [2026]
- **Evidence:**
  - forum `7QjQ1mpNMX`, note `Y0M7kTngcK` — https://openreview.net/forum?id=7QjQ1mpNMX
- **Limitations:**
  - A single reviewer's assessment (initial rating 2/10), not a corpus-wide pattern.

## Hidden Criteria

### `hidden_criteria_missing_baseline_pattern` — Model interpretation

In this small sample, both low-rated reviews cited here criticize the paper for not sufficiently distinguishing itself from -- or comparing against -- existing work, suggesting reviewers weigh differentiation from prior work heavily even when a method is technically sound.

- **Support level:** limited
- **Year scope:** [2026]
- **Evidence:**
  - forum `7QjQ1mpNMX`, note `Y0M7kTngcK` — https://openreview.net/forum?id=7QjQ1mpNMX
  - forum `FGkknrhv09`, note `dk5qk2JQi4` — https://openreview.net/forum?id=FGkknrhv09
- **Limitations:**
  - Based on only 2 of 37 reviews in a 10-forum sample -- an interpretive pattern, not a validated corpus-wide finding.

## Year Over Year Drift

### `year_over_year_drift_no_data_yet` — Insufficient evidence

This sample covers only ICLR 2026, so no year-over-year drift claim can be supported yet.

- **Support level:** none
- **Year scope:** (none)
- **Limitations:**
  - A drift claim requires at least two venue-years of comparable statistics; this corpus currently has one.

## Rebuttal Effectiveness

### `rebuttal_effectiveness_no_data_yet` — Insufficient evidence

No initial-to-final rating changes have been captured for this sample yet, so no claim about rebuttal effectiveness can be supported.

- **Support level:** none
- **Year scope:** (none)
- **Limitations:**
  - The review cycle is still active and no revised-score snapshot has been fetched yet; see statistics.json's initial_to_final_rating_change (count=0).

