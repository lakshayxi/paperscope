> **ARCHIVAL -- NOT LOADED AT RUNTIME.** This file predates the Phase 4A skill redesign and is hand-written, unvalidated prose -- it was never checked against the structured claim schema (`generation.py`) that every current `references/<family>.md` file now passes through. It contains claims this project no longer stands behind verbatim, including unqualified "actual distribution" and "area-chair-level experience" framing. Kept only for historical continuity per the project's no-delete policy -- see `skill/references/legacy/README.md`. The active skill (`skill/SKILL.md`) never loads anything from this directory.

---

# ICML / TMLR Review Calibration
*Calibrated from OpenReview patterns 2023–2025 (ICML) and TMLR rolling*

---

## 1. Score Calibration

### ICML (2023–2025)

ICML uses a **1–10** scale.

| Score | Label | Real-world meaning |
|---|---|---|
| 9–10 | Strong Accept | Outstanding. <2% of accepts. |
| 7–8 | Accept | Solid contribution, ready for camera-ready. Top ~25%. |
| 6 | Weak Accept | Positive lean; AC support needed. |
| **5** | **Borderline** | **Common starting point. High variance here.** |
| 4 | Weak Reject | Identifiable gaps; revision needed but not guaranteed to help. |
| 2–3 | Reject | Fundamental issues. |
| 1 | Strong Reject | Rarely used; reserved for clearly out-of-scope or fraudulent work. |

- **Accept threshold**: average ≥ 6, no reviewer below 4.
- **Acceptance rate**: ~27% (2023–2025).
- ICML has historically been slightly more permissive than NeurIPS on theory depth but stricter on empirical breadth.

### TMLR (Rolling)

TMLR uses a different model — **no accept/reject by score**, but a certification decision:

| Decision | Meaning |
|---|---|
| Accept | Sound, reproducible, makes a contribution. No "impact" bar. |
| Accept with minor revisions | Small fixes needed; action editor decides. |
| Major revisions | Significant work needed; re-review cycle. |
| Reject | Fundamental flaw or out-of-scope. |

TMLR explicitly does **not** require novelty to be "significant" — correctness and soundness are sufficient. This is the key cultural difference from ICML.

---

## 2. Top 5 Accept Signals (ICML)

1. **Clean algorithm with clear complexity analysis.**
   "The proposed method has O(n log n) complexity vs O(n²) for the baseline, and the proof is in the appendix."

2. **Multiple datasets across different domains.**
   "The evaluation covers vision, language, and tabular data — the generalization is credible."

3. **Well-motivated theoretical underpinning.**
   "The connection to PAC-Bayes in §3 explains why the method works and suggests when it will fail."

4. **Honest comparison including failure modes.**
   "Table 3 shows the method underperforms on long-tail distributions — this is acknowledged and analyzed."

5. **Positioning that makes the contribution crisp.**
   "The key distinction from [prior work] is X, which the authors demonstrate matters in §4."

---

## 3. Top 5 Reject Signals (ICML)

1. **No code or reproducibility information.**
   "The method has many hyperparameters and there is no code or detailed configuration — results cannot be verified."

2. **Experiments only on toy or synthetic data.**
   "The theory is evaluated on a 2D Gaussian mixture model. Whether this scales to real problems is entirely unclear."

3. **Overcomplicated method solving a simple problem.**
   "The proposed 8-component pipeline achieves 0.5% improvement over a single fine-tuned baseline. The added complexity is unjustified."

4. **Missing ablation on the core claimed component.**
   "The paper claims the key contribution is the attention mechanism in §3.2, but there is no ablation removing just that component."

5. **Unclear relationship to optimization landscape or generalization.**
   "For a paper claiming to improve training stability, there is no loss curve analysis or discussion of convergence."

---

## 4. Hidden Criteria

- **ICML reviewers are optimization-aware by default.** Even vision or NLP papers get asked about loss landscape, convergence, and learning rate sensitivity. Pre-empt this.
- **The "simplicity premium" is strong at ICML.** Methods that are simpler than expected for the gain are rewarded. Reviewers write "I appreciate the elegance" as a genuine score driver.
- **TMLR: correctness > novelty, always.** A correctly proven result about a narrow problem will be accepted; a flashy empirical claim without solid baselines will not. This is the inverse of NeurIPS culture.

---

## 5. Reviewer Language Patterns

**Accept-tier reviewers use:**
- "The algorithm is simple to implement and the gains are consistent across settings..."
- "The theoretical analysis clearly explains the empirical behaviour..."
- "The ablation in Table 4 convincingly isolates the proposed component..."
- "The paper fills a genuine gap in the literature on..."
- "The connection to [related framework] is insightful and..."

**Reject-tier reviewers use:**
- "The method is complex and the marginal improvement over [simpler baseline] is hard to justify..."
- "The evaluation is limited to [single benchmark/dataset]..."
- "The reproducibility is a concern given the lack of..."
- "The proposed approach feels like a combination of [X] and [Y] without a unifying insight..."
- "I am not convinced the gains will hold outside of the specific setting evaluated..."

---

## 6. Year-over-Year Drift (2023–2025)

- **2023**: Last year of the "one-track" format. Large-scale training papers dominated; reviewers showed leniency toward empirical LLM work with shallow theory. Foundation model papers scored well even with narrow evals.
- **2024**: Adoption of area tracks created topic-specific reviewer pools. NLP-area reviewers applied tighter NLP-specific baselines. Reproducibility checks became enforced in author checklist, not advisory.
- **2025**: "Evaluation quality" emerged as an explicit AC criterion. Papers with cherry-picked benchmarks started getting lower meta-review scores even when individual reviewer scores were moderate. Efficiency (FLOPs per point of improvement) increasingly mentioned in reviews.

---

## 7. Rebuttal Effectiveness

**What raises scores:**
- Providing the missing ablation with numbers during the rebuttal period (ICML explicitly allows new experiments in rebuttals).
- Pointing to a specific section that addresses a reviewer's concern they missed — ICML reviewers re-read more carefully than at other venues.
- Showing that the "missing baseline" is already in the paper under a different name.

**What has no effect:**
- Arguing about whether your contribution "counts" as novel without providing new evidence.
- Responding to all reviewers with the same boilerplate acknowledgment.
- Promising a cleaned-up appendix — reviewers don't score appendices.

**Fatal flaws no rebuttal fixes:**
- An incorrect proof (if a reviewer identifies the flaw precisely).
- Systematic data leakage in experiments.
- A simpler unreported baseline that matches or exceeds the proposed method's results.
- Claims of state-of-the-art that are contradicted by a concurrent public paper.

---

## TMLR-Specific Notes

- There is **no deadline pressure** — reviewers take 2–3 months. Expect detailed, line-by-line reviews.
- The action editor (AE) has significant discretion; a strong AE can override a mediocre review.
- Reproducibility is near-mandatory: if you don't have code, expect a "major revisions" requesting it.
- **Scope creep in rebuttals is penalized.** If you revise the paper significantly beyond fixing reviewers' requests, the AE may ask for another round of review, delaying acceptance.
