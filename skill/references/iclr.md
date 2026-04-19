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

9. **Neat unifying idea with solid theory can get through even with weak experiments.** *(real ICLR 2024)*
   "The idea is very neat and the theory seems well-executed." → scored 6 despite qualitative-only experiments.
   A genuinely clean theoretical contribution buys leniency on empirical evaluation — but only if the theory is airtight.

10. **Empirical study without a new technique can be accepted if findings are timely, surprising, and comprehensive.** *(real ICLR 2024)*
    Retrieval-augmented generation vs. long-context LLMs paper scored 6,8,6,8,6,8 (avg 7.0, accepted) despite reviewers explicitly noting "limited novelty" and "does not introduce any new technique."
    What carried it: (a) timely question with practical stakes, (b) contradicted a prior paper's conclusions with better-controlled experiments, (c) 7 tasks × large 70B models, (d) findings were genuinely surprising.
    Empirical papers need all four — timely + comprehensive + surprising + well-controlled. Missing any one of these lands at 5–6.

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
   "An important related work is missing. CoSCL is a recent ensemble-based method... an in-depth comparison is strongly encouraged."
   Reviewers name the exact paper they expect. Missing it drops the score to 3.

7. **Poor presentation — undefined symbols, illegible figures.** *(real ICLR 2024)*
   "I really do not understand the statement of Theorem 1; there are undefined symbols like T(i)."
   "Figures and tables are almost illegible."
   Presentation failures are scored harshly — reviewers see it as disrespect for their time.

8. **Inaccessible writing — even technically solid work gets rejected.** *(real ICLR 2024)*
   "The results are important enough that the paper ought to be substantially rewritten and resubmitted. I cannot recommend acceptance in the current form."
   "In its current form, it is inaccessible even to experts, leave alone non-experts."
   A technically correct paper with unreadable notation will score 3 regardless of results.

9. **Unfair baseline: data leakage from pretraining.** *(real ICLR 2024)*
   "All experiments use a pre-trained checkpoint on ImageNet that overlaps with downstream datasets such as CIFAR-100."
   Reviewers check pretraining data overlap explicitly — this is the most common subtle flaw.

10. **Missing standard evaluation settings.** *(real ICLR 2024)*
    "The experiment does not cover the commonly used Class-IL or Domain-IL setting."

11. **Extension papers need strong novelty — "not a surprise" is fatal.** *(real ICLR 2024)*
    "It's not a surprise that Eq 4 can generalize these, and this is not new."
    Papers framed as unifications or generalizations must show the generalization itself is hard and novel.

12. **Informal language in formal writing.** *(real ICLR 2024)*
    "The usage of contractions like 'don't' and 'won't' is not suitable for formal writing."
    Cited explicitly as a weakness — signals the paper was rushed.

13. **Core argument not convincingly justified — reviewer can't trace theory to claim.** *(real ICLR 2024)*
    "I cannot tell how the high variance is connected to the generalization of diffusion models."
    "The mathematical derivation looks like heuristics instead of rigorous proof."
    For theory papers: if the causal chain from result → claim is unclear, the score lands at 3–5 regardless of technical correctness.

14. **Qualitative-only experiments.** *(real ICLR 2024)*
    "The empirical evaluation is solely qualitative, which makes it impossible to assess whether there is a benefit."
    "The results are entirely qualitative (meaning they can be easily cherrypicked)."
    Seen across both rejected (3) and borderline accepted (6) papers — always cited as a weakness. Always add quantitative comparisons.

16. **Experiments only on synthetic or single toy dataset — fatal for applied ML.** *(real ICLR 2024)*
    "The comparison with baselines is carried out solely on a synthetic dataset, ColorMNIST."
    "It seems necessary to consider experiments on fairness datasets (e.g., COMPAS, Adult) commonly used in the fairness literature."
    Every subfield has canonical benchmarks. Missing them signals the authors don't know the field.

17. **Subfield-specific required benchmarks not included.** *(real ICLR 2024)*
    - Fairness: CelebA, COMPAS, Adult + Demographic Parity / Equalized Odds metrics
    - GNN robustness: adaptive attacks, white-box + black-box, poison + evasion attacks
    Reviewers list the exact missing benchmarks. Include them or explicitly justify why they're excluded.

18. **Proof errors early in paper cause reviewers to stop reading entirely.** *(real ICLR 2024)*
    "I ceased my examination of the subsequent proofs due to the glaring inadequacies in the mathematical statements presented thus far."
    One bad theorem early kills the entire technical credibility of the paper.

19. **Missing punctuation after equations cited as unprofessional.** *(real ICLR 2024)*
    "A glaring oversight is the absence of punctuation marks following ALL equations throughout the document."
    Seen in multiple papers — equations must end with period or comma like prose.

20. **"Essentially the same as prior work" = novelty rejection.** *(real ICLR 2024)*
    "The FAREContrast objective function is essentially the same as the one described at [prior work]."
    Reviewers will find the closest prior work and do a line-by-line comparison. Differences must be explicit.

21. **Method complexity must match the stated goal — contradiction is fatal.** *(real ICLR 2024)*
    Graph coarsening paper claimed to scale to large graphs but had O(n²k) complexity and was only tested on small graphs — reviewers cited this directly as a fatal flaw.
    "The proposed method is tested only on small graphs, which contradicts the motivation for graph coarsening."
    If your paper's motivation is scalability, your method's complexity and your benchmark graphs must both reflect that.

22. **Citing a paper in related work but not comparing to it = guaranteed reviewer callout.** *(real ICLR 2024)*
    "Kumar 2023 is mentioned in Section 2.2 but no empirical comparison is provided."
    Reviewers read your related work section and cross-check every cited method against your experiments. If you cite it, compare to it — or explicitly state why comparison is infeasible.

23. **Method being slower than baseline in any setting must be addressed head-on.** *(real ICLR 2024)*
    Graph coarsening paper showed the method was slower than training on the original graph in some configurations — reviewers penalized this without mercy.
    If speed comparisons are unflattering in any setting, either exclude that setting with justification, or address it directly in the limitations section.

15. **Framework/unification papers must justify advantage over existing frameworks.** *(real ICLR 2024)*
    "The work does not introduce a new concept and is a formulation of existing concepts into an existing framework."
    "Data dependent coupling was already introduced in Flow-Matching, which is an essentially equivalent framework."
    Reviewers will find the closest equivalent framework and ask: what does this add? Answer it explicitly in the paper.

24. **Novel contribution must be written as equations — prose description alone is insufficient.** *(real ICLR 2026)*
    TopoGuide (3D molecule finetuning) scored 2,2,2,8 (avg 3.5) partly because: "the paper only provides two known formulas in the preliminaries section and offers no expressions for its own methodology, especially for the loss function. A mere textual description is insufficient."
    If your method has a loss function, an objective, or a core operation — write the equation. Reviewers treat missing math as a signal the method is underspecified.

25. **Background section bloat at the expense of methodology = flagged explicitly.** *(real ICLR 2026)*
    "The paper dedicates an excessive amount of space (Section 3) to preliminary discussions of well-known concepts... In contrast, the core methodology (Section 4) is rushed and lacks crucial technical details."
    Space is zero-sum. If preliminaries run long and methodology is thin, reviewers notice and interpret it as the contribution being weak.

26. **Assembly of existing components without a unifying conceptual advance = engineering, not research.** *(real ICLR 2026)*
    C2Seg (medical segmentation) scored 6,4,2,4 (avg 4.0): "The paper assembles several established components — soft contrastive learning, dual-path attention, and nonlinear gating — without offering a cohesive conceptual advance or deeper theoretical insight."
    Combining three things that individually work is not a contribution unless you explain what only the combination enables.

27. **Trendy component (KAN, Mamba, etc.) added without domain-specific justification gets penalized.** *(real ICLR 2026)*
    "The motivation for using KAN is not convincing. The paper does not explain why a spline-based gating function is needed or what specific limitation of existing nonlinearities it solves."
    "Table 3 even shows pure KAN encoder performs worse than hybrid, contradicting claims about superior nonlinear modeling."
    Adding a trending architecture block without proving it addresses a specific limitation will be called out. If you use KAN/Mamba/etc., show what breaks without it.

28. **Medical AI papers: narrow domain scope (e.g., single pathology) blocks acceptance.** *(real ICLR 2026)*
    C2Seg used only two COVID chest datasets: "The experimental scope is narrow... both tasks are limited to binary lesion segmentation. This setup is not representative of real clinical scenarios."
    Reviewers expect evaluation across multiple organs, modalities, and anatomies. COVID-only or single-disease papers must explicitly argue why generalization claims hold.

29. **Missing comparisons to recent domain-specific baselines = score 2–4.** *(real ICLR 2026)*
    Medical segmentation paper omitted: LLaVA-Med, BiomedCLIP, SAM-Med, MedSAM. Reviewer listed them by name.
    Every subfield now has a set of "expected recent baselines." Missing them signals the authors don't follow the field. Check the last 2 years of the target venue for methods on the same task.

30. **Small gain relative to added complexity must be justified.** *(real ICLR 2026)*
    "The reported performance improvements are modest (~1–2% Dice) compared with the additional complexity introduced by multi-stage training and multiple attention and gating modules. The computational cost–benefit trade-off is not justified."
    If your improvement is single-digit percentage, you need either an efficiency argument or a theoretical explanation for why even small gains matter for the application.

31. **Extreme reviewer score variance (e.g., 2,2,2,8) is a rejection signal in 2026.** *(real ICLR 2026)*
    TopoGuide received three 2s from confidence-4/5 reviewers and one 8 from a confidence-3 reviewer. The outlier 8 did not rescue the paper.
    Per the 2025→2026 drift: AC meta-review now weights reviewer confidence when scores diverge. A single outlier high score from a low-confidence reviewer carries little weight against consensus from high-confidence reviewers.

32. **Proof error = score 2 regardless of other merits — and multiple reviewers will independently find it.** *(real ICLR 2026)*
    IDEA (Bayesian optimization) scored 2,2,2,2. Theorem 1's convergence proof was wrong: the regret bound reduced to O(N) (linear), meaning the algorithm doesn't converge. Three separate reviewers caught this independently without coordinating.
    One reviewer wrote: "making the bound linear and thus trivial. An algorithm with linear regret does no better than just a naive strategy of constantly selecting the same point — linear regret means the algorithm does not converge."
    A single broken theorem early in the paper ends the review. Verify every proof step produces the correct asymptotic before submission.

33. **Inconsistent notation throughout a paper = reviewer distrust, not just minor polish.** *(real ICLR 2026)*
    IDEA switched between f(x,ξ), y(x), and f(x) for the same function; used N and n interchangeably for sample count; used k and k₀ for the same kernel. Reviewers flagged this explicitly as a sign the paper was not carefully prepared, not just a cosmetic issue.
    Notation inconsistency signals the paper hasn't been read end-to-end by the authors. Do a full symbol audit before submission.

34. **Experimental setup that exceeds realistic use-case budgets invalidates conclusions.** *(real ICLR 2026)*
    IDEA used 4000 warm-up queries to estimate noise before the BO algorithm even starts — "that typically already exceeds the budgets we have in BO, raising concerns as to how realistic this problem setting really is."
    If your method requires more setup cost than a practitioner would have for the full task, reviewers will call it out as an unfair baseline.

35. **Results without statistical significance markers are treated as inconclusive.** *(real ICLR 2026)*
    "In almost all experiments, the shaded areas overlap meaning that the differences between the algorithms are not statistically significant."
    Overlapping confidence intervals with no p-values = reviewers assume null result. Report std devs, CIs, and p-values; if CIs overlap, address it directly.

36. **Evaluation metrics that match your training objectives = circular evaluation.** *(real ICLR 2026)*
    KTGen (tabular generation) was penalized because its main fidelity metrics (KL divergence, Wasserstein per column, KS) directly correspond to the losses it was trained to minimize — naturally inflating reported numbers.
    "The main fidelity metrics directly correspond to the optimized objectives, naturally favoring KTGen. More comprehensive metrics such as C2ST, α-precision, or β-recall are not reported."
    Always report at least one held-out metric that is not in your training loss. If all your metrics are your objectives, reviewers will call it circular.

37. **Claiming to handle knowledge type X but only implementing Y = overclaimed scope.** *(real ICLR 2026)*
    KTGen categorized external knowledge as "unstructured textual and statistical" but the actual method only handled statistical knowledge. Reviewer: "No mechanism is provided for textual or semantic knowledge, making the claimed scope broader than what the method achieves."
    If your intro or framework diagram promises a capability, the method section must deliver it. Unimplemented claims are treated as scope inflation.

38. **Missing inference time and compute cost — called out by 3 out of 4 reviewers independently.** *(real ICLR 2026)*
    SRT (time series super-resolution) had this raised by every reviewer except the confidence-2 outlier: "computational complexity and inference speed are relatively high... please analyze and compare"; "does not discuss overall training or inference cost"; "is the computational complexity during inference reasonable?"
    For any generative model or multi-stage pipeline: always include inference time table vs. baselines. This is now a near-universal reviewer expectation.

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
- Watch for explicit signals: "I am willing to raise the score for further explanations" — these reviewers are reachable. Address their exact question directly and concisely.
- *(confirmed ICLR 2026)* "I am inclined to give it a score of 7–8. However, since the current scoring system cancels a 7, I am provisionally assigning a 6. If the authors can address a substantial portion of my concerns, I would be happy to raise my score to 8 or higher." — FSF few-shot paper scored 4,6,8,8 (avg 6.5, likely accepted). The 6 was explicitly provisional; the reviewer named the exact missing ablation (OP without FSF) and missing baselines (GDA-CLIP, TIMO). This is the clearest rebuttal upgrade signal: reviewer names the score they want to give, the system prevents it, and they tell you exactly what to add.

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
- *(confirmed ICLR 2026)* Incorrect convergence proof — IDEA scored 2,2,2,2 and no rebuttal could fix Theorem 1 being provably wrong (linear regret bound).
