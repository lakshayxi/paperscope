> **ARCHIVAL -- NOT LOADED AT RUNTIME.** This file predates the Phase 4A skill redesign and is hand-written, unvalidated prose -- it was never checked against the structured claim schema (`generation.py`) that every current `references/<family>.md` file now passes through. It contains claims this project no longer stands behind verbatim, including unqualified "actual distribution" and "area-chair-level experience" framing. Kept only for historical continuity per the project's no-delete policy -- see `skill/references/legacy/README.md`. The active skill (`skill/SKILL.md`) never loads anything from this directory.

---

# NeurIPS Review Calibration
*Calibrated from OpenReview patterns 2023–2025*

---

## 1. Score Calibration

NeurIPS uses a **1–10** integer scale (same as ICLR numerically, but culture differs).

| Score | Label | Real-world meaning |
|---|---|---|
| 9–10 | Strong Accept | Landmark paper. Extremely rare (~1%). |
| 7–8 | Accept | Solid, camera-ready with minor revisions. Top ~20%. |
| 6 | Weak Accept | Positive lean. Needs AC support to get through. |
| **5** | **Borderline** | **Default score for "not sure yet." Very common first-round score.** |
| 4 | Weak Reject | Fixable in principle but reviewers rarely change from here. |
| 2–3 | Reject | Clear issues; rebuttal unlikely to help. |
| 1 | Strong Reject | Used sparingly, signals fundamental unsoundness. |

- **Accept threshold**: average ≥ 6, ideally with all reviewers ≥ 5.
- **Borderline zone**: 5–6 average with high variance = AC decision.
- **Acceptance rate**: ~25–26% (2023–2025).
- NeurIPS has a **2-phase review**: initial scores → author rebuttal → discussion → final scores. Score changes of ±1 are common; ±2 happens but is notable.

---

## 2. Top 5 Accept Signals

1. **Theoretical depth with tight proofs.**
   "The convergence analysis is rigorous and the bound in Theorem 2 is essentially tight given the lower bound in Appendix B."
   NeurIPS rewards theory more consistently than ICLR.

2. **Well-controlled large-scale experiments.**
   "The authors sweep over 5 seeds, report confidence intervals, and include statistical significance tests — this is the level of rigor we should expect."

3. **A surprising or counterintuitive result, well-explained.**
   "The finding that [X] actually hurts performance under distribution shift is surprising and the paper makes a convincing case for why."

4. **Connection to adjacent fields (optimization, statistics, information theory).**
   "The reduction to mirror descent is elegant and immediately suggests extensions."

5. **Clear exposition of what fails and why.**
   "The negative result in §5 is as valuable as the positive results — it closes off an obvious direction."

---

## 3. Top 5 Reject Signals

1. **Weak theoretical justification for empirical method.**
   "The paper proposes a heuristic and evaluates it empirically, but there is no analysis of why it works. This is not sufficient for NeurIPS."

2. **Missing error bars and statistical significance.**
   "Table 1 reports mean performance with no variance estimate across runs. It is impossible to assess reliability."

3. **Overly narrow problem setting.**
   "The method is evaluated exclusively on synthetic data, and the gap to real-world applicability is never addressed."

4. **Incremental improvement framed as a new paradigm.**
   "The proposed 'framework' is essentially [prior work] with a different loss term. The 0.3% improvement does not justify a full paper."

5. **Related work misses key references from last 2 years.**
   "The authors cite [2019 paper] as the closest work, but [NeurIPS 2023] and [ICML 2024] directly address the same problem with stronger results."

---

## 4. Hidden Criteria

- **Theory is expected even for empirical papers.** NeurIPS reviewers almost always ask "can you provide any theoretical justification?" If your paper is purely empirical, pre-empt this in the paper. "We leave formal analysis to future work" is acceptable only if the empirical evidence is overwhelming.
- **Scalability questions are default.** Reviewers will ask about computational complexity, GPU hours, and parameter count. Papers that don't report this upfront lose a half-point on average.
- **Novelty bar is high relative to acceptance rate.** NeurIPS gets ~12,000 submissions. A technically correct but "expected" result is not enough. The "so what?" must be answered in the intro.

---

## 5. Reviewer Language Patterns

**Accept-tier reviewers use:**
- "The theoretical contribution is non-trivial and..."
- "The experimental setup is careful: multiple seeds, held-out test sets, and..."
- "I was initially skeptical of [X] but the ablation in §4 addresses my concern..."
- "The paper makes a clear and falsifiable claim..."
- "This result has implications beyond the immediate setting because..."

**Reject-tier reviewers use:**
- "The paper lacks theoretical justification for..."
- "The comparison is unfair because the proposed method uses more [data/compute/parameters]..."
- "The improvement is marginal and within the noise of..."
- "It is unclear how this scales to..."
- "The paper reads as a straightforward application of [existing technique] to [new domain]..."

---

## 6. Year-over-Year Drift (2023–2025)

- **2023**: First year with large LLM papers dominating. Reviewers split on whether "prompt engineering" papers belong at NeurIPS. Many borderline LLM papers got in on novelty of scale; the bar for non-LLM papers was held constant or raised.
- **2024**: Backlash against scale-only contributions. "We trained a bigger model" without mechanistic insight increasingly scored 4–5. Interpretability and formal verification of ML systems rose in reviewer interest.
- **2025**: "Responsible AI" section of checklist formally weighted. Papers on fairness, privacy, and robustness no longer get a free pass on technical depth — the technical bar for these areas was raised to match other subfields. Ethics section reviewers added to contentious papers.

---

## 7. Rebuttal Effectiveness

**What raises scores:**
- New experiments that directly address the reviewer's named concern — especially ablations or comparisons to the specific missing baseline.
- Clarifying a theorem statement that was misread, with a clear pointer to the relevant line.
- Showing that a claimed "missing baseline" actually performs worse (with numbers).

**What has no effect:**
- Promising additional results after the deadline: "We will include this in the final version."
- Long responses to score-3 reviewers who engaged superficially — they rarely come back.
- Disagreeing with a reviewer's taste ("We believe our contribution is significant") without new evidence.

**Fatal flaws no rebuttal fixes:**
- Proof error in a theory paper — if a reviewer finds a hole, the score will not recover.
- Baseline known to outperform the proposed method (if a reviewer reproduces it).
- Ethical concern about dataset provenance or potential misuse with no mitigation.
- Core claim contradicted by a reviewer's own experiment.
