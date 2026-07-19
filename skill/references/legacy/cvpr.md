> **ARCHIVAL -- NOT LOADED AT RUNTIME.** This file predates the Phase 4A skill redesign and is hand-written, unvalidated prose -- it was never checked against the structured claim schema (`generation.py`) that every current `references/<family>.md` file now passes through. It contains claims this project no longer stands behind verbatim, including unqualified "actual distribution" and "area-chair-level experience" framing. Kept only for historical continuity per the project's no-delete policy -- see `skill/references/legacy/README.md`. The active skill (`skill/SKILL.md`) never loads anything from this directory.

---

# CVPR / ICCV / ECCV Review Calibration
*Calibrated from OpenReview patterns 2023–2025*

---

## 1. Score Calibration

CVPR/ICCV/ECCV use a **1–6** integer scale (distinct from ML venue 1–10 scales).

| Score | Label | Real-world meaning |
|---|---|---|
| 6 | Strong Accept | Top-tier result. Oral candidate. <5% of accepts. |
| 5 | Accept | Solid paper, poster acceptance. Top ~20%. |
| 4 | Weak Accept | Borderline-positive. AC discretion. |
| **3** | **Borderline / Weak Reject** | **The most contested score. High AC workload here.** |
| 2 | Reject | Clear problems; rebuttal rarely helps. |
| 1 | Strong Reject | Out-of-scope, plagiarism, or fundamental flaw. |

- **Accept threshold**: average ≥ 4.0, no reviewer at 1.
- **Borderline zone**: 3–4 average with mixed reviewers. AC decision.
- **Acceptance rate**: CVPR ~23–25%, ICCV ~26%, ECCV ~27%.
- Confidence: 1 (no expertise) → 5 (expert). Low-confidence scores carry less weight in AC decisions.

**Key difference from ML venues**: The 1–6 scale compresses the range. A score of 3 at CVPR is roughly equivalent to a 5 at NeurIPS — it does not mean "mediocre," it means "I need to be convinced."

---

## 2. Top 5 Accept Signals

1. **Strong quantitative improvement on a recognized benchmark.**
   "The proposed method achieves +2.3 AP on COCO val, which is significant given the saturated state of this benchmark."
   Vision reviewers trust numbers more than prose.

2. **A new capability that prior methods demonstrably cannot do.**
   "Figure 5 shows failure cases of [prior SOTA] that the proposed method handles correctly — this is qualitatively distinct, not just quantitatively better."

3. **Clean ablation isolating the proposed component.**
   "Row 4 of Table 3 removes only the proposed module and drops 3.1 AP — the contribution is clearly load-bearing."

4. **Generalization across datasets or tasks.**
   "The method is evaluated on COCO, LVIS, and Objects365 — breadth is sufficient to support the claim."

5. **Efficient method with competitive or better accuracy.**
   "At 30 FPS on a V100 with ResNet-50 backbone, the method is practical for deployment — the speed-accuracy curve in Fig. 6 tells the whole story."

---

## 3. Top 5 Reject Signals

1. **Single dataset evaluation with large performance claims.**
   "The paper claims 'state-of-the-art performance' based on results on a single dataset. This is not convincing."

2. **Missing comparison to the current SOTA.**
   "The proposed method is not compared to [CVPR 2024 paper], which directly addresses the same problem and reports higher numbers."

3. **Incremental architecture change without insight.**
   "The paper replaces the attention mechanism in [prior work] with a different variant and reports a small improvement. The insight behind this choice is not explained."

4. **Unfair baseline comparisons.**
   "The proposed method uses a larger backbone than the compared methods. The comparison is not controlled."

5. **No failure analysis or qualitative results.**
   "There are no failure cases or qualitative examples showing where the method breaks down. Qualitative analysis is expected for a vision paper."

---

## 4. Hidden Criteria

- **Visualization quality is a real factor.** Unlike ML venues, CVPR reviewers pay attention to figures. Blurry visualizations, inconsistent color maps, or figures that don't clearly support the claims will cost 0.5 points. A great Figure 1 that immediately shows the problem and solution is worth spending time on.
- **Backbone fairness is policed aggressively.** Any experiment using a larger or newer backbone than the baseline must be explicitly flagged and matched. This is the single most common "unfair comparison" complaint at CVPR.
- **Workshop papers at CVPR/ICCV count against novelty.** If the paper is an extension of a workshop paper, reviewers will check whether the delta is sufficient for a main conference paper. "This extends our CVPR workshop paper by adding X" requires X to be substantial.

---

## 5. Reviewer Language Patterns

**Accept-tier reviewers use:**
- "The method is clearly better than prior work on [specific benchmark] and the ablation is convincing..."
- "The qualitative results in Figure X demonstrate a genuine qualitative improvement..."
- "The proposed module is simple but effective, which I consider a strength..."
- "The speed-accuracy tradeoff is favorable compared to [baseline]..."
- "The paper addresses a practical limitation of [prior work] that the community has noticed..."

**Reject-tier reviewers use:**
- "The improvement over [prior work] is marginal and may not be statistically significant..."
- "The method is not compared to [recent paper] which achieves better results..."
- "The ablation study is incomplete — it is unclear which component is responsible for the gain..."
- "The paper is an incremental extension of [prior work] without sufficient novelty..."
- "The backbone used is larger than the compared methods, making the comparison unfair..."

---

## 6. Year-over-Year Drift (2023–2025)

- **CVPR 2023**: First major year post-ViT dominance. Transformer-based methods were no longer novel — reviewers started asking "why Transformer specifically?" rather than accepting it as a contribution. Pure architecture papers faced higher bar.
- **CVPR 2024**: Diffusion models saturated the generation track. "We apply diffusion to [X]" needed a strong task-specific contribution. Recognition and detection papers returned to prominence as the "safe" track. Efficiency papers gained traction with reviewers citing real-world deployment needs.
- **CVPR 2025**: Multimodal (vision-language) papers now evaluated against the LLM-era baselines. "CLIP-based" is not SOTA. Papers must compare against GPT-4V, LLaVA, or equivalent. Video understanding papers increasingly expected to address temporal consistency, not just per-frame accuracy.

**ICCV vs CVPR nuance**: ICCV (odd years) tends to be slightly more theory-tolerant than CVPR. Papers with novel loss function analyses or geometric reasoning do slightly better at ICCV. ECCV (even years, European) shows more tolerance for applications papers and medical imaging crossovers.

---

## 7. Rebuttal Effectiveness

**What raises scores:**
- Providing the missing comparison with the specific paper/method a reviewer named.
- Adding a controlled experiment that matches backbone/compute of baselines.
- Providing a qualitative figure that the reviewer said was missing.

**What has no effect:**
- Saying "we will add comparisons in the final version" — CVPR rebuttals must include actual numbers, not promises.
- Lengthy explanations of why the missing comparison is "not fair" — run it and show it.
- Arguing about whether your improvement is "significant" without statistical tests.

**Fatal flaws no rebuttal fixes:**
- An existing published method that already achieves better results (if a reviewer finds it).
- Backbone mismatch that explains the entire performance gap.
- Dataset overlap between training and test sets (data leakage).
- Failure to cite a concurrent work that makes the contribution redundant.
