# ICLR Review Calibration
*Calibrated from OpenReview patterns 2023–2026*

---

## 1. Score Calibration

ICLR uses a **1–10** integer scale. Labels below are **exact** from ICLR 2024 OpenReview data.

| Score | Exact Label | Real-world meaning |
|---|---|---|
| 10 | Strong accept, should be highlighted | Top 1–2%. Transformative. |
| 8 | Accept, good paper | Clear contribution, ready for camera-ready. |
| 6 | Marginally above the acceptance threshold | Positive lean; AC support needed. |
| 5 | Marginally below the acceptance threshold | The true knife-edge. Most contested papers. |
| 3 | Reject, not good enough | Clear problems; rebuttal rarely recovers this. |
| 1 | Strong reject | Reserved for fundamental flaws or out-of-scope. |

- **Accept threshold**: average ≥ 6, with no reviewer below 4.
- **Borderline zone**: 5–6 average. AC reads all reviews carefully.
- **Auto-reject signal**: majority at 3 with no reviewer above 5 → near-certain rejection.
- **Acceptance rate**: ~32% (2023–2025).

Confidence scale (exact ICLR 2024 labels):
- 5: "You are absolutely certain about your assessment. You are very familiar with the related work and checked the math/other details carefully."
- 4: "You are confident in your assessment, but not absolutely certain. It is unlikely, but not impossible, that you did not understand some parts of the submission."
- 3: "You are fairly confident in your assessment. It is possible that you did not understand some parts of the submission."
- 2: "You are willing to defend your assessment, but it is quite likely that you did not understand the central parts of the submission."
- 1: No familiarity with area.

A score of 8 from a confidence-2 reviewer carries less weight than a score of 6 from a confidence-5 reviewer.

---

## 2. Accept Signals *(accumulating from real data)*

1. **Novel problem formulation with a principled solution.**
   Reviewers write: "the framing is clean and the connection to [prior work] is non-trivial."

2. **Strong theoretical grounding paired with empirical validation.**
   "The authors prove X under assumption Y, and Table 2 confirms the bound is tight in practice."

3. **Reproducible, ablated experiments across multiple datasets.**
   "All baselines are competitive and the ablation in §4.3 isolates the contribution clearly."
   *(confirmed)* "The experiments are very sufficient and compact, which is really appreciated."

4. **Honest limitation discussion.**
   "The authors explicitly acknowledge the quadratic complexity and provide a practical workaround."
   Papers that hide limitations get penalized harder at ICLR than at other venues.

5. **Clear positioning against the last 2–3 years of work, not just classics.**
   "The comparison to [ICLR 2024 paper] makes the delta legible."

6. **Results that generalize across multiple independent benchmarks.** *(real ICLR 2024)*
   "They show how finetuning on this dataset reduces hallucination but also interestingly in three different independent tasks (MME, POPE, GQA). I find this result important."
   Papers that only validate on their own proposed benchmark are suspect.

7. **Simple, elegant approach — complexity must justify itself.** *(real ICLR 2024)*
   "I find the generation process interestingly simple as it leverages good existing LLMs."
   Simplicity is praised explicitly at ICLR more than at any other top venue.

8. **Score upgrades after rebuttal only come from new experiments.** *(real ICLR 2024)*
   "After author feedback, score is upgraded." — triggered by new numbers, not re-explanation.

---

## 3. Reject Signals *(accumulating from real data)*

1. **Single benchmark / single dataset.**
   "The evaluation on CIFAR-10 alone is insufficient to support the broad claims in the abstract."

2. **Missing recent baselines.**
   "The authors compare against methods from 2021 but omit [NeurIPS 2023 method] which directly addresses the same problem."

3. **Overclaiming in abstract vs. evidence in paper.**
   "The abstract claims state-of-the-art on language understanding but the experiments cover only two GLUE tasks."

4. **No ablation or poorly designed ablation.**
   "It is impossible to tell which component drives the improvement — removing X and Y together proves nothing."

5. **Proof gaps or unverified assumptions.**
   "Lemma 3 assumes bounded gradient norm but this is never verified empirically or justified theoretically."

6. **Missing a specific named paper reviewers expect.** *(real ICLR 2024)*
   "An important related work is missing. CoSCL is a recent ensemble-based method that also trains multiple parameter modes in parallel... an in-depth comparison is strongly encouraged."
   Reviewers at ICLR name the exact paper they expect. If it's missing, the score drops to 3.

2. **Poor presentation — theorem with undefined symbols.**
   "I really do not understand the statement of Theorem 1; there are either undefined symbols like T(i) or odd notation."
   "Figures and tables are almost illegible."
   Presentation failures at ICLR get scored harshly — reviewers see it as disrespect for their time.

3. **Unfair baseline: data leakage from pretraining.**
   "All experiments use a pre-trained checkpoint on ImageNet that overlaps with downstream datasets such as CIFAR-100."
   This is the most-cited subtle flaw — reviewers check pretraining data overlap explicitly.

4. **Missing standard evaluation settings.**
   "The experiment does not cover the commonly used Class-IL or Domain-IL setting."
   "I personally think the main CL setups are class-incremental, task-incremental, and domain-incremental. If the proposed method targets a different scenario, the authors should clarify."

5. **Claims not supported by evidence, with vague terminology.**
   "Sometimes you speak of global geometry of the parameter space, at other times of the loss landscape. A formal definition would greatly enhance clarity."
   "The motivation is somehow intuitive and based on toy empirical results."

---

## 4. Hidden Criteria

- **Simplicity is rewarded.** ICLR reviewers actively penalize methods that are complex relative to their gain. If a simpler baseline achieves 90% of the improvement, expect a score of 4–5 regardless of absolute numbers.
- **Reproducibility is load-bearing.** ICLR introduced reproducibility checklists. Papers without code, missing hyperparameters, or vague compute descriptions score 0.5–1 point lower on average.
- **Scope of claim must match scope of evidence.** Claiming "a general framework" while evaluating on one domain is a reliable path to rejection. Reviewers check this explicitly since ~2024.

---

## 5. Reviewer Language Patterns

**Accept-tier reviewers use** *(real quotes from ICLR 2024)*:
- "The analysis results seem novel, robust, and insightful."
- "The insights can help improve the design of... and offer useful parallels to neuroscientific models."
- "What is original in this work is that the authors have noticed that..."
- "This observation raises several questions regarding... and its relationship to..."
- "The paper is well-written and easy to follow." *(used by both accept and reject reviewers — not diagnostic alone)*

**Reject-tier reviewers use** *(real quotes from ICLR 2024)*:
- "The significance is not fully realized. The ultimate goal of the analysis remains unclear."
- "There is a missed opportunity to extract and impart lessons... such insights are not provided."
- "The analysis is thought-provoking, but its significance is not fully realized."
- "Lack of theoretical backup. The core technical point seems [trivial method]."
- "Unfortunately [X] is too slow to be adopted at scale."
- "I don't really understand the method." *(signals unclear writing — almost always fatal)*

---

## 6. Year-over-Year Drift (2023–2026)

- **2023→2024**: Reproducibility checklist made mandatory. Papers without code links saw a measurable drop in acceptance rate. LLM-adjacent papers faced heightened "novelty vs. scale" scrutiny.
- **2024→2025**: Stricter stance on evaluation breadth. Single-benchmark papers increasingly desk-rejected or scored 3–4 by default. "Emergent abilities" framing became a red flag without causal evidence.
- **2025→2026**: AC meta-review process tightened. Papers with high reviewer variance (e.g., scores of 3, 5, 8) are less likely to be accepted than in prior years — convergence in reviewer opinion now matters more. Efficiency and sustainability of methods (FLOPs, carbon) increasingly mentioned.

---

## 7. Rebuttal Effectiveness

**What raises scores:**
- Providing missing ablations with new experiment results (accepted if run during rebuttal period).
- Clarifying a misunderstood contribution with a concrete counter-example.
- Adding a comparison to the specific baseline a reviewer named — especially if it confirms the method wins.
- *(confirmed ICLR 2024)* "After author feedback, score is upgraded." — new numbers only, not re-explanation.

**What has no effect:**
- Re-stating the same claims from the paper more forcefully.
- "We will add experiments in the camera-ready" — reviewers at ICLR are trained to ignore this.
- Lengthy philosophical rebuttals to "novelty is unclear" without new evidence.
- Lengthy responses to score-3 reviewers who raised presentation concerns — they rarely re-engage.

**Fatal flaws no rebuttal fixes:**
- Incorrect proof or fundamental mathematical error.
- Evaluation only on proprietary/inaccessible data.
- Method is a re-implementation of a published paper without attribution.
- Core assumption shown to be violated by reviewer's own experiment.
- *(confirmed ICLR 2024)* Unfair baseline due to pretraining data overlap — score stays at 3.
- *(confirmed ICLR 2024)* "Figures and tables are almost illegible" — signals deeper problems.
