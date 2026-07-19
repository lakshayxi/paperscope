# Corpus statistics — ICLR

**This is a snapshot, not live statistics.** The table below is the real, unedited
output of `paperscope stats --corpus data/full/iclr.jsonl --output <dir>` run against
one fetch batch — it will look different (larger, more venue-years, more decisions
resolved) by the time you check this repo's `data` branch. Re-run the command yourself
against a fresh corpus to get current numbers; see
[`docs/statistics_and_evidence.md`](../docs/statistics_and_evidence.md) for the full
schema, every metric's definition, and known limitations (in particular: `iclr / 2026`
and `iclr / all` are identical below only because this sample corpus has just one
venue-year so far — that's a corpus limitation, not a bug in the `all`-aggregate scope).

# Corpus statistics

Schema version: 1  
Source corpus hash: `9222deb94e5619fc`  
Generated at: 2026-07-19T00:00:57Z

Deterministic output of `paperscope stats` — see
[`docs/statistics_and_evidence.md`](../docs/statistics_and_evidence.md) for schema and
limitations. Rebuttal-related rows marked *(observational)* are correlational, not
causal — see the row's `note` field in `statistics.json`.

## iclr / 2026

| Metric | Sample size | Missing | Value |
|---|---|---|---|
| confidence_distribution_normalized | 37 | 0 | {"0.0-0.1": 3, "0.1-0.2": 0, "0.2-0.3": 0, "0.3-0.4": 13, "0.4-0.5": 0, "0.5-0.6": 0, "0.6-0.7": 18, "0.7-0.8": 0, "0.8-0.9": 0, "0.9-1.0": 3} |
| confidence_distribution_raw | 37 | 0 | {"2.0": 3, "3.0": 13, "4.0": 18, "5.0": 3} |
| decision_distribution | 10 | 10 | {"unknown": 10} |
| forum_count | 10 | 0 | 10 |
| initial_to_final_rating_change | 37 | 37 | {"count": 0, "max": null, "mean": null, "median": null, "min": null, "stdev": null} |
| missing_rate.decision | 10 | 10 | 1.0 |
| missing_rate.paper_abstract | 10 | 0 | 0.0 |
| missing_rate.paper_title | 10 | 0 | 0.0 |
| missing_rate.review_confidence | 37 | 0 | 0.0 |
| missing_rate.review_rating | 37 | 0 | 0.0 |
| paper_mean_rating | 10 | 0 | {"count": 10, "max": 6.5, "mean": 4.3333, "median": 4.0, "min": 2.0, "stdev": 1.3354} |
| paper_rating_variance | 10 | 0 | {"count": 10, "max": 2.75, "mean": 1.4389, "median": 1.5, "min": 0.0, "stdev": 0.9597} |
| rating_decision_crosstab | 37 | 0 | {"unknown": {"high": 12, "low": 8, "medium": 17}} |
| rating_distribution_normalized | 37 | 0 | {"0.0-0.1": 8, "0.1-0.2": 0, "0.2-0.3": 0, "0.3-0.4": 17, "0.4-0.5": 0, "0.5-0.6": 0, "0.6-0.7": 8, "0.7-0.8": 0, "0.8-0.9": 0, "0.9-1.0": 4} |
| rating_distribution_raw | 37 | 0 | {"2.0": 8, "4.0": 17, "6.0": 8, "8.0": 4} |
| rebuttal_absent_rating_change *(observational)* | 8 | 8 | {"count": 0, "max": null, "mean": null, "median": null, "min": null, "stdev": null} |
| rebuttal_present_rating_change *(observational)* | 29 | 29 | {"count": 0, "max": null, "mean": null, "median": null, "min": null, "stdev": null} |
| response_count | 10 | 2 | 110 |
| review_count | 10 | 0 | 37 |
| reviewer_disagreement | 10 | 0 | {"count": 10, "histogram": {"0": 2, "1-2": 3, "3-4": 5, "5+": 0}, "max": 4.0, "mean": 2.6, "median": 3.0, "min": 0.0, "stdev": 1.562} |

## iclr / all

| Metric | Sample size | Missing | Value |
|---|---|---|---|
| confidence_distribution_normalized | 37 | 0 | {"0.0-0.1": 3, "0.1-0.2": 0, "0.2-0.3": 0, "0.3-0.4": 13, "0.4-0.5": 0, "0.5-0.6": 0, "0.6-0.7": 18, "0.7-0.8": 0, "0.8-0.9": 0, "0.9-1.0": 3} |
| confidence_distribution_raw | 37 | 0 | {"2.0": 3, "3.0": 13, "4.0": 18, "5.0": 3} |
| decision_distribution | 10 | 10 | {"unknown": 10} |
| forum_count | 10 | 0 | 10 |
| initial_to_final_rating_change | 37 | 37 | {"count": 0, "max": null, "mean": null, "median": null, "min": null, "stdev": null} |
| missing_rate.decision | 10 | 10 | 1.0 |
| missing_rate.paper_abstract | 10 | 0 | 0.0 |
| missing_rate.paper_title | 10 | 0 | 0.0 |
| missing_rate.review_confidence | 37 | 0 | 0.0 |
| missing_rate.review_rating | 37 | 0 | 0.0 |
| paper_mean_rating | 10 | 0 | {"count": 10, "max": 6.5, "mean": 4.3333, "median": 4.0, "min": 2.0, "stdev": 1.3354} |
| paper_rating_variance | 10 | 0 | {"count": 10, "max": 2.75, "mean": 1.4389, "median": 1.5, "min": 0.0, "stdev": 0.9597} |
| rating_decision_crosstab | 37 | 0 | {"unknown": {"high": 12, "low": 8, "medium": 17}} |
| rating_distribution_normalized | 37 | 0 | {"0.0-0.1": 8, "0.1-0.2": 0, "0.2-0.3": 0, "0.3-0.4": 17, "0.4-0.5": 0, "0.5-0.6": 0, "0.6-0.7": 8, "0.7-0.8": 0, "0.8-0.9": 0, "0.9-1.0": 4} |
| rating_distribution_raw | 37 | 0 | {"2.0": 8, "4.0": 17, "6.0": 8, "8.0": 4} |
| rebuttal_absent_rating_change *(observational)* | 8 | 8 | {"count": 0, "max": null, "mean": null, "median": null, "min": null, "stdev": null} |
| rebuttal_present_rating_change *(observational)* | 29 | 29 | {"count": 0, "max": null, "mean": null, "median": null, "min": null, "stdev": null} |
| response_count | 10 | 2 | 110 |
| review_count | 10 | 0 | 37 |
| reviewer_disagreement | 10 | 0 | {"count": 10, "histogram": {"0": 2, "1-2": 3, "3-4": 5, "5+": 0}, "max": 4.0, "mean": 2.6, "median": 3.0, "min": 0.0, "stdev": 1.562} |

Source: `data/full/iclr.jsonl`, computed by
[`src/paperscope/statistics.py`](../src/paperscope/statistics.py) via `paperscope stats`.
