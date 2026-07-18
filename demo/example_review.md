# Example: PaperScope review vs. real reviewer excerpts

This demonstrates PaperScope's output on a real ICLR 2026 submission fetched by this
project. Per [`docs/redistribution.md`](../docs/redistribution.md), only short sourced
excerpts from the real reviews are reproduced here — not the full reviews — each
attributed to its OpenReview note ID.

**Paper**: *Can Microcanonical Langevin Dynamics Leverage Mini-Batch Gradient Noise?*
**Forum**: [openreview.net/forum?id=h7qdCvhMdb](https://openreview.net/forum?id=h7qdCvhMdb)
**Venue**: ICLR 2026

---

## Short excerpts from the real reviews (sourced)

> "The techniques of the paper jointly resolve anisotropic noise bias and numerical
> instability, enabling scalable and robust Bayesian inference."
> — Reviewer note [`xk6sXc1N1i`](https://openreview.net/forum?id=h7qdCvhMdb&noteId=xk6sXc1N1i), rating 6, confidence 3

> "The first three pages consist mainly of the introduction and discussion of related
> work. [...] there isn't enough space left in the main paper to adequately present the
> details of the new contributions."
> — Reviewer note [`2LrfLHwXAQ`](https://openreview.net/forum?id=h7qdCvhMdb&noteId=2LrfLHwXAQ), rating 4, confidence 2

> "A key limitation of the paper is that the proposed algorithm currently lacks formal
> convergence guarantees."
> — Reviewer note [`UJAQJEJkpR`](https://openreview.net/forum?id=h7qdCvhMdb&noteId=UJAQJEJkpR), rating 6, confidence 4

Four real reviews on this forum scored 6, 4, 4, 6 (confidence 3, 2, 3, 4).

---

## PaperScope's review (generated with the current, pre-redesign skill)

*Generated from the paper's title/abstract only (Input Tier T1) — this repo doesn't
redistribute full paper PDFs. This is the **v0** skill (`skill/SKILL.md` +
`skill/references/iclr.md` as they exist today); it will be regenerated once the Phase 4
skill redesign (structured, evidence-traced generation) lands.*

> ⚠️ **T1 input** — novelty and contribution assessment are limited without the full
> paper. Sections below reflect only what's inferable from the abstract.

**§1 Contribution Audit** — The paper claims the first systematic study of whether
microcanonical Langevin dynamics (MCLMC) can work with mini-batch gradients instead of
full-batch, identifies two specific failure modes (anisotropic gradient noise,
numerical instability at high dimension), and proposes a preconditioning scheme plus an
adaptive step-size tuner to fix both. ⚠️ Cannot assess whether the claimed novelty holds
against the closest prior stochastic-gradient MCMC work without the full related-work
section.

**§2 Novelty** ⚠️ — Closest prior work is almost certainly SGHMC-family methods (cited
in the abstract as the baseline class). Whether this is a genuinely new failure-mode
diagnosis or an incremental fix to known SGMCMC noise issues can't be determined from
the abstract alone.

**§4 Experimental Assessment** ⚠️ — Abstract claims "consistently outperforms strong
stochastic gradient MCMC baselines" on Bayesian neural networks and other high-dimensional
tasks. Per `skill/references/iclr.md`'s accept-signal pattern on baseline currency:
reviewers expect the *last 2 years* of baselines by name, not just the SGHMC family —
this can't be verified without the full experiments section.

**§9 Score**
```
Score:          T1-limited — a full-tier score requires the paper body, not just the abstract
Confidence:     Low (T1 input)
Recommendation: Cannot responsibly predict accept/reject from an abstract alone
Justification:  The abstract alone doesn't surface the two most decisive ICLR reject
                signals in this project's calibration data — missing recent baselines and
                presentation/space issues — both of which the real reviewers flagged.
```

**§10 Rebuttal Prediction** ⚠️ — Not assessable at T1.

---

## What this demo shows

- PaperScope's v0 skill correctly **refuses to fabricate a confident score from
  insufficient input** rather than guessing — this is existing behavior, not aspirational.
- It still flags a directionally right concern (baseline currency) that one real
  reviewer (`2LrfLHwXAQ`, rating 4) independently raised as a presentation/space issue
  limiting how much substance made it into the paper.
- It does **not** yet cite specific statistics, evidence IDs, or a corpus hash — that
  traceability is exactly what the Phase 4 skill redesign (structured claims JSON →
  validated → deterministically rendered) is meant to add. This file will be refreshed
  once that lands, for a fair before/after comparison.
