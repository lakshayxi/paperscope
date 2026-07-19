# ICLR venue calibration reference

**Generated, not hand-written.** Every claim below is machine-validated against `statistics.json`/`evidence.json` from a real OpenReview corpus by `paperscope build-skill` (`src/paperscope/skill_builder.py`) -- nothing here was authored freehand, and a claim only appears if it passed the same structured validation as `paperscope render` (see `docs/generation.md`).

**Preliminary: yes.** This calibration is based on a small and/or single-year sample -- treat every claim below as a starting hypothesis, not an established venue norm.

## Calibration sample

- Years covered: [2026]
- Forums in sample: 10
- Reviews in sample: 37
- Forums with a resolved accept/reject decision: 0
- Source corpus hash: `9222deb94e5619fc`

This file makes no accept/reject calibration claim beyond what `decisions_resolved` above supports -- if that count is 0, nothing below states or implies an acceptance rate or a score-to-decision threshold.

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

### `hidden_criteria_topic_importance_not_sufficient` — Model interpretation

In this small sample, both low-rated reviews cited here open by acknowledging the paper addresses an important topic before raising concerns -- suggesting topic importance alone does not carry a rating in reviewers' eyes when other concerns (novelty, missing comparisons) are present.

- **Support level:** limited
- **Year scope:** [2026]
- **Evidence:**
  - forum `7QjQ1mpNMX`, note `Y0M7kTngcK` — https://openreview.net/forum?id=7QjQ1mpNMX
  - forum `FGkknrhv09`, note `dk5qk2JQi4` — https://openreview.net/forum?id=FGkknrhv09
- **Limitations:**
  - Based on only 2 of 37 reviews in a 10-forum sample -- an interpretive pattern, not a validated corpus-wide finding.

## Reviewer Language Patterns

### `reviewer_language_no_data_yet` — Insufficient evidence

No accept/reject-labeled reviewer language pattern can be supported yet, since no forum in this sample has a resolved decision.

- **Support level:** none
- **Year scope:** (none)
- **Limitations:**
  - Distinguishing accept-tier vs. reject-tier reviewer phrasing requires resolved decisions to label reviews by outcome; this sample's decisions are 100% unresolved.

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

