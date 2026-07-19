# PaperScope evaluation report

Generated at: 2026-07-20T00:00:00Z

**Do not claim statistical significance from small samples.** See Warnings below for this run's specific small-sample / single-venue flags.

## Dataset

- Evaluation forums: 8
- Source corpus hash: `9826e6c37894a352`
- Calibration hash (frozen before evaluation forum selection): `09fc62d5e3f62155`
- Model-visible input hash: `76b93a059706d2b3`
- Private label hash: `2f14f941144df1ea`

## Leakage checks

**Passed: yes.**

Checks performed: calibration/evaluation forum-ID disjointness, dataset hash internal consistency, prediction file schema validity, prediction files reference only evaluation forums, and generic/PaperScope run comparability (identical model/settings/input hashes and forum sets, calibration difference only).

## Missing predictions

- Generic: 0 evaluation forum(s) with no prediction
- PaperScope: 0 evaluation forum(s) with no prediction

## Initial-rating prediction

Target: mean_of_initial_ratings. Eligible forums: 8.

| Metric | Generic | PaperScope | Delta (PaperScope − Generic) |
|---|---|---|---|
| Sample size (n) | 8 | 8 | — |
| Coverage | 1.0000 | 1.0000 | — |
| MAE | 1.0042 | 0.1958 | -0.8084 |
| Median absolute error | 1.0167 | 0.2000 | -0.8167 |
| Spearman | 0.8383 | 1.0000 | 0.1617 |

## Final-decision prediction

Eligible forums (resolved accept/reject only): 6.

| Metric | Generic | PaperScope | Delta (PaperScope − Generic) |
|---|---|---|---|
| Sample size (n) | 6 | 6 | — |
| Coverage | 1.0000 | 1.0000 | — |
| Accuracy | 0.5000 | 1.0000 | 0.5000 |
| Precision | 0.5000 | 1.0000 | 0.5000 |
| Recall | 1.0000 | 1.0000 | 0.0000 |
| F1 | 0.6667 | 1.0000 | 0.3333 |

### Confusion matrices

- Generic: `{"accept": {"accept": 3, "reject": 0}, "reject": {"accept": 3, "reject": 0}}`
- PaperScope: `{"accept": {"accept": 3, "reject": 0}, "reject": {"accept": 0, "reject": 3}}`

## Probability calibration

- Generic: not computed (no accept_probability values present)
- PaperScope: not computed (sample_size_below_20 (n=6))

## Metric definitions

- **MAE** / **median absolute error** — mean / median of |predicted rating − target rating| over forums where both a prediction and an initial-rating label exist. Lower is better.
- **Spearman** — rank correlation between predicted and target initial ratings (average-rank ties). Range [-1, 1], higher is better. Requires >= 2 scored forums.
- **Accuracy / precision / recall / F1** — standard binary classification metrics for the final-decision task, positive class = `accept`. Computed only over forums with a resolved (accept/reject) label and a non-null `decision_prediction`.
- **Brier score** — mean squared error between `accept_probability` and the binary accept/reject outcome. Lower is better. Only computed when `accept_probability` is present and the eligible sample size is adequate — never approximated from `rating_prediction`.
- **ECE** — expected calibration error (10 equal-width probability bins). Only computed under the same conditions as Brier score.
- **Coverage** — predicted_count / eligible_forum_count for a task.

## Warnings

- generic/initial_rating: small sample (n=8) -- not sufficient for a statistically significant comparison
- generic/final_decision: small sample (n=6) -- not sufficient for a statistically significant comparison
- paperscope/initial_rating: small sample (n=8) -- not sufficient for a statistically significant comparison
- paperscope/final_decision: small sample (n=6) -- not sufficient for a statistically significant comparison

## Limitations

- Model-visible input is title + abstract only (`input_tier: abstract_only`) -- the current corpus schema does not store full paper text, so no full-text prediction condition exists yet.
- Initial-rating target is an unweighted mean across reviewers; it does not account for reviewer confidence or venue-specific scale differences.
- Small per-venue/year breakdown strata (n < 5) are omitted from the breakdown table, not silently included with a noisy estimate -- see `evaluation_results.json`'s `breakdown_skipped` for what was dropped and why.

