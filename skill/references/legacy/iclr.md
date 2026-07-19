> **ARCHIVAL -- NOT LOADED AT RUNTIME.** This file predates the Phase 4A skill redesign and is hand-written, unvalidated prose -- it was never checked against the structured claim schema (`generation.py`) that every current `references/<family>.md` file now passes through. It contains claims this project no longer stands behind verbatim, including unqualified "actual distribution" and "area-chair-level experience" framing. Kept only for historical continuity per the project's no-delete policy -- see `skill/references/legacy/README.md`. The active skill (`skill/SKILL.md`) never loads anything from this directory.

---

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

11. **Dataset papers: breadth + automatic curation + cross-benchmark validation.** *(real ICLR 2024)*
    LRV-Instruction scored 6,8,8,8 (avg 7.5). The recipe: (a) 16 tasks and 400k samples — breadth signals the dataset generalizes, (b) GPT-4-based automatic curation makes the scale credible and reproducible, (c) improvements showed up on 3 independent benchmarks (MME, POPE, GQA) the authors didn't build. Reviewers praised both points explicitly: "they show how finetuning on this dataset reduces hallucination but also interestingly in three different independent tasks."
    Dataset contributions need all three — broad task coverage, scalable/automated construction, and cross-benchmark transfer. A dataset that only improves your own benchmark is suspect.

12. **Pareto efficiency — better accuracy at lower cost — is a strong explicit accept signal.** *(real ICLR 2026)*
    ASPEC scored 8,6,6,6 (avg 6.5). One reviewer explicitly called it "Pareto-efficient behavior is one of its key strengths" — higher accuracy than all baselines while costing less compute.
    If your method wins on two axes simultaneously (accuracy AND efficiency), say so explicitly in the abstract and intro. Don't bury it in a table. Reviewers who see "outperforms baselines on 5 benchmarks at a fraction of the cost" treat it as a compelling signal — it rules out the standard "sure but at what cost?" objection before it's raised.

13. **Decoupling previously coupled design choices = architectural flexibility contribution.** *(real ICLR 2026)*
    FSF scored 4,6,8,8 (avg 6.5). The core contribution was decoupling encoder choice from alignment — prior methods required jointly trained vision-language models (CLIP). Reviewer: "This is a significant advantage, as it allows ones to plug in state-of-the-art vision or text models that may be more powerful or better suited for a specific domain."
    When your method removes a constraint that forced users to make coupled decisions (must use X AND Y together), the flexibility argument is a genuine contribution even if your SOTA numbers are marginal. Name the constraint explicitly, name who it blocks, and show a concrete case where flexibility matters (e.g., medical domain with a specialist encoder).

14. **Closed-form solution + learned residual = principled architecture that reviewers trust.** *(real ICLR 2026)*
    FSF combined Orthogonal Procrustes (closed-form, geometry-preserving linear alignment) with a lightweight flow-matching prior (learned non-linear component). Reviewers praised this combination explicitly: "novel and effective." The structure signals the authors understood what each component does — the closed-form part handles what can be solved analytically, the learned part handles the residual.
    When your architecture has one component with analytical guarantees and one learned component that handles what the analytical solution can't, explain that division explicitly. It distinguishes deliberate design from "we tried things until it worked."

15. **"Train once, deploy everywhere" paradigm is explicitly praised when backed by diverse benchmarks.** *(real ICLR 2026)*
    NodePFN (graph foundation model) scored 8,6,4,4 (avg 5.5). The 8-reviewer explicitly praised: "The 'train once, deploy everywhere' paradigm offers practical benefits, removing the need for dataset-specific training while maintaining competitive performance." What made it credible: (a) 23 diverse benchmarks including both homophilic and heterophilic graphs, (b) no fine-tuning at test time, (c) still competitive with supervised GNNs trained per-dataset.
    For foundation model or zero-shot transfer papers: the credibility threshold is breadth × diversity. You need enough benchmarks to rule out cherry-picking, and enough variation (easy + hard, in-distribution + out-of-distribution) to show the paradigm generalizes. Also quantify the amortization: how much compute does "train once" save vs. training a separate model per dataset? Reviewers who are excited about the paradigm will still ask this.

---

## 3. Reject Signals *(accumulating from real data)*

### A. Baseline & Evaluation Fairness

1. **Missing recent baselines — reviewers will name the exact paper they expect.** *(real ICLR 2024 + 2026)*
   "The authors compare against methods from 2021 but omit [NeurIPS 2023 method] which directly addresses the same problem."
   "An important related work is missing. CoSCL is a recent ensemble-based method... an in-depth comparison is strongly encouraged." Missing it drops the score to 3.
   "Kumar 2023 is mentioned in Section 2.2 but no empirical comparison is provided."
   Reviewers cross-check your related work against your experiments. If you cite it, compare to it. If a reviewer expects it and you omit it, they name it explicitly — check the last 2 years of your target venue for methods on the same task. For domain-specific subfields (e.g., medical AI: LLaVA-Med, BiomedCLIP, SAM-Med, MedSAM), reviewers list expected names by name.

2. **Unfair baseline: data leakage from pretraining.** *(real ICLR 2024)*
   "All experiments use a pre-trained checkpoint on ImageNet that overlaps with downstream datasets such as CIFAR-100."
   Reviewers check pretraining data overlap explicitly — this is the most common subtle flaw.

3. **Missing canonical evaluation settings for your subfield.** *(real ICLR 2024)*
   "The experiment does not cover the commonly used Class-IL or Domain-IL setting."
   Every subfield has standard protocols. Missing them is treated as not knowing the field, not as a deliberate choice.

4. **Showing only your method's numbers without baseline numbers = incomplete evaluation.** *(real ICLR 2026)*
   SEAL showed accuracy results for its method across vision datasets but provided no accuracy numbers for the baseline defenses it compared against. "Where is the accuracy results for these baselines?"
   A comparison table with only one row is not a comparison. Every metric you report for your method must have corresponding numbers for every baseline.

5. **Baseline unfairness: your method uses a technique withheld from baselines.** *(real ICLR 2026)*
   SpecExtend (speculative decoding) used FlashAttention internally but did not apply it to baseline methods — giving the paper's approach a latency advantage not given to competitors. Reviewer caught this directly.
   If your method uses any component (efficient attention, mixed precision, quantization) that would also benefit baselines, apply it uniformly. Reviewers will attribute all gains to the component, not your contribution.

6. **If your comparison baseline evaluated on architecture X, you must also evaluate on X.** *(real ICLR 2026)*
   StoRM (mixup augmentation) compared against AdAutoMix and AutoMix, both of which evaluated on ViT-based architectures (DeiT-Small, Swin, ConvNeXt). StoRM only used CNNs. Reviewer: "The experiments lack generalization. The authors fail to demonstrate the performance of ViT-based methods."
   When you compare against a paper, you inherit their evaluation scope. If your baselines evaluated on architecture families, model sizes, or tasks that you omit, reviewers will ask why. Either include them or explicitly argue why the omitted setting is out of scope.

7. **Unfair supervision comparison: your method uses annotations that baselines explicitly avoid.** *(real ICLR 2026)*
   ODIS (object-level self-distillation) used ground-truth bounding boxes during training and compared against DINO/iBOT, which require no annotations at all. Confidence-5 reviewer: "the comparisons included in the paper are not fair at all." Adding any form of supervision — bounding boxes, class labels, pseudo-labels — creates an apples-to-oranges comparison with self-supervised baselines.
   If your method requires any additional annotations (bounding boxes, weak labels, object masks), compare against other weakly-supervised methods that also use annotations, not purely unsupervised ones. If you must compare to unsupervised baselines, acknowledge and quantify the annotation cost explicitly.

8. **Baseline re-implemented below its published performance = unfair comparison.** *(real ICLR 2026)*
   BayesShift included only one EDG baseline (MMD-LSAE) and reported its performance "suspiciously low compared to its original publication." Reviewer flagged this as undermining the fairness of the proposed method's advantage.
   When you re-implement a baseline, report numbers that match or exceed the original paper's reported results. If you can't reproduce the original numbers, explain why (different setup, compute budget) and use the original paper's numbers as the reference. Mysteriously low baseline results trigger reviewer suspicion that the comparison is tilted.

### B. Experimental Rigor

9. **Single, synthetic, or toy dataset is insufficient.** *(real ICLR 2024)*
   "The evaluation on CIFAR-10 alone is insufficient to support the broad claims in the abstract."
   "The comparison with baselines is carried out solely on a synthetic dataset, ColorMNIST."
   Synthetic datasets are worse than small real datasets — reviewers treat them as evidence the authors avoided harder settings. Every subfield has canonical benchmarks; missing them signals the authors don't know the field.
   - Fairness: CelebA, COMPAS, Adult + Demographic Parity / Equalized Odds metrics
   - GNN robustness: adaptive attacks, white-box + black-box, poison + evasion attacks

10. **No ablation or poorly designed ablation.**
    "It is impossible to tell which component drives the improvement — removing X and Y together proves nothing."

11. **Qualitative-only experiments.** *(real ICLR 2024)*
    "The empirical evaluation is solely qualitative, which makes it impossible to assess whether there is a benefit."
    "The results are entirely qualitative (meaning they can be easily cherrypicked)."
    Seen across both rejected (3) and borderline accepted (6) papers — always cited as a weakness. Always add quantitative comparisons.

12. **Results without statistical significance markers are treated as inconclusive.** *(real ICLR 2026)*
    "In almost all experiments, the shaded areas overlap meaning that the differences between the algorithms are not statistically significant."
    Overlapping confidence intervals with no p-values = reviewers assume null result. Report std devs, CIs, and p-values; if CIs overlap, address it directly.

13. **Evaluation metrics that match your training objectives = circular evaluation.** *(real ICLR 2026)*
    KTGen (tabular generation) used KL divergence, Wasserstein per column, and KS as fidelity metrics — the same quantities it was trained to minimize. "The main fidelity metrics directly correspond to the optimized objectives, naturally favoring KTGen."
    Always report at least one held-out metric not in your training loss. If all your metrics are your objectives, reviewers will call it circular.

14. **Methodology-experiment dimensional mismatch.** *(real ICLR 2026)*
    SI-SR (symbolic regression) defined its main formulation for a single spatial variable x, but ran experiments on 2D reaction-diffusion systems with both x and y. "This mismatch raises questions about how the framework extends to higher-dimensional inputs."
    Every dimension, variable type, or structural assumption in your method section must be consistent with your experiments. Reviewers will find the mismatch and interpret it as an unresolved limitation.

15. **Missing inference time and compute cost — near-universal reviewer expectation.** *(real ICLR 2026)*
    SRT (time series super-resolution) had inference time raised by 3 out of 4 reviewers independently: "computational complexity and inference speed are relatively high"; "does not discuss overall training or inference cost"; "is the computational complexity during inference reasonable?"
    For any generative model or multi-stage pipeline: always include an inference time table vs. baselines.

16. **Method being slower than baseline in any setting must be addressed head-on.** *(real ICLR 2024)*
    Graph coarsening paper showed the method was slower than training on the original graph in some configurations — reviewers penalized this without mercy.
    If speed comparisons are unflattering in any setting, either exclude that setting with justification, or address it directly in the limitations section.

17. **Experimental setup that exceeds realistic use-case budgets invalidates conclusions.** *(real ICLR 2026)*
    IDEA used 4000 warm-up queries to estimate noise — "that typically already exceeds the budgets we have in BO, raising concerns as to how realistic this problem setting really is."
    If your method requires more setup cost than a practitioner would have for the full task, reviewers will call it out as an unfair baseline.

18. **Fine-tuning that degrades the base model signals low data quality.** *(real ICLR 2026)*
    GUIrilla fine-tuned Qwen2.5-VL 3B and 7B on collected data; both models scored *lower* on ScreenSpot-Pro after fine-tuning (3B: 23.9% → 19.17%). Reviewer: "This suggests the training data may be of low quality and may have harmed the base models' performance."
    Always report base model performance alongside fine-tuned performance. If fine-tuning hurts, address it explicitly — reviewers will compare the numbers themselves.

19. **Modifying the test set makes results incomparable to all prior work.** *(real ICLR 2026)*
    SMMT (speech-guided MT) removed overlapping portions from the FLORES devtest set. Reviewer: "You should never modify a test set! This makes it impossible to compare results. Which version of Flores was used? Did you recalculate the scores for the other systems?"
    Test sets are fixed contracts. Removing samples — even for legitimate reasons (overlap with training data) — requires reporting on the original set too, or results cannot be compared to any prior work. This is treated as a critical experimental flaw.

20. **Key experimental conditions buried in appendix = hidden advantage.** *(real ICLR 2026)*
    FSCIL paper used pretrained ImageNet features on CUB-200 but disclosed this only in the appendix. Reviewer: "This should be clarified in the main paper. The paper should also compare against simpler works that use pre-trained ImageNet features."
    If a design choice meaningfully affects performance — pretrained features, additional data, auxiliary supervision — it belongs in the main paper. Hiding it in the appendix looks like concealment and triggers reviewer distrust.

21. **Results table with systematic blank entries = selective reporting.** *(real ICLR 2026)*
    Membership Decoding paper scored 6,4,4,2. Table 2 had "most positions blank." Reviewer: "these missing results seriously puts into question the validity of the results of this study." Also: a HARD setting mentioned in the paper had no results anywhere.
    Blank entries in a results table signal either the method failed in those conditions or the experiments weren't run — both trigger reviewer distrust. Either fill them in, explain in the caption why entries are absent (e.g., "method not applicable in this setting"), or remove the conditions from the table. A results table with unexplained gaps is treated as evidence of cherry-picking.

22. **Greedy decoding only (temperature=0) with no sampling variance.** *(real ICLR 2026)*
    PROBE evaluated all models at temperature=0 with no sampling variance reported. For any stochastic model, greedy-only gives a single point estimate with no uncertainty — particularly problematic when margins between models are small.
    Always run at least 3 seeds or sampling runs and report variance. Greedy-only is acceptable only if you argue it is standard for your specific task.

### C. Novelty & Positioning

23. **Overclaiming: scope in abstract, unimplemented capabilities, or claim vs. evidence mismatch.** *(real ICLR 2024 + 2026)*
    "The abstract claims state-of-the-art on language understanding but the experiments cover only two GLUE tasks."
    "No mechanism is provided for textual or semantic knowledge, making the claimed scope broader than what the method achieves."
    If your intro or framework diagram promises a capability, the method section must deliver it. Unimplemented claims and abstract-level scope inflation are treated as the same flaw.

24. **"Essentially the same as prior work" = novelty rejection.** *(real ICLR 2024)*
    "The FAREContrast objective function is essentially the same as the one described at [prior work]."
    Reviewers will find the closest prior work and do a line-by-line comparison. Differences must be explicit.

25. **Extension and framework papers: the generalization itself must be hard and novel.** *(real ICLR 2024)*
    "It's not a surprise that Eq 4 can generalize these, and this is not new."
    "The work does not introduce a new concept and is a formulation of existing concepts into an existing framework."
    "Data dependent coupling was already introduced in Flow-Matching, which is an essentially equivalent framework."
    Reviewers will find the closest equivalent framework and ask: what does this add? If the unification is obvious in hindsight, it's not a contribution. Answer this explicitly in the paper.

26. **Assembly of existing components without a unifying conceptual advance = engineering, not research.** *(real ICLR 2026)*
    "The paper assembles several established components — soft contrastive learning, dual-path attention, and nonlinear gating — without offering a cohesive conceptual advance or deeper theoretical insight."
    Combining three things that individually work is not a contribution unless you explain what only the combination enables.

27. **Trendy component (KAN, Mamba, etc.) added without domain-specific justification gets penalized.** *(real ICLR 2026)*
    "The motivation for using KAN is not convincing. The paper does not explain why a spline-based gating function is needed or what specific limitation of existing nonlinearities it solves."
    "Table 3 even shows pure KAN encoder performs worse than hybrid, contradicting claims about superior nonlinear modeling."
    Adding a trending architecture block without proving it addresses a specific limitation will be called out. If you use KAN/Mamba/etc., show what breaks without it.

28. **Conceptual framework that renames existing concepts without enabling new analysis will be called out.** *(real ICLR 2026)*
    Probing Memes introduced "memes," "phemotypes," and a "perception matrix" — three reviewers independently said "the core contributions would not be affected if the metaphor were removed." The relabeling added terminology without enabling analysis that wasn't already possible.
    If your paper introduces a theoretical framework or metaphor, it must enable at least one analysis, decomposition, or insight that could not be expressed without it. Naming the same concept differently is not a contribution. Ask yourself: what can I prove, measure, or argue using this framework that I couldn't before?

29. **Empirical study findings must distinguish novel from already-established results.** *(real ICLR 2026)*
    Multilingual pretraining study scored 6,8,4,4. A 4-reviewer explicitly flagged: "The finding that the curse of multilinguality relates to model capacity has already been stated in the original XLM-R paper." The paper presented this as a finding without positioning it against prior consensus.
    For empirical studies with multiple findings: each finding must be labeled as (a) contradicting prior work, (b) confirming under new conditions (larger scale, new setting), or (c) genuinely new. Don't present confirmation of established results as novel discoveries — reviewers will flag it. If your contribution is confirmation at a larger scale or in a new domain, say that explicitly and argue why it matters.

30. **Method name collision with prior work = novelty flag.** *(real ICLR 2026)*
    DRO paper (4,2,2,2): Richemond et al. (2024) already published a method also named "Direct Reward Optimization (DRO)" based on the same RLHF derivation — not cited and not compared to. Confidence-5 reviewer raised this as the primary novelty concern: without clearly differentiating from the identically-named prior work, it is impossible to assess what is new.
    Before submitting, search for existing methods with the same name or acronym. If one exists using the same formulation, it must be cited, compared to, and the delta explicitly explained. Submitting without this looks like an oversight or a priority claim issue.

### D. Theory & Mathematical Correctness

31. **Novel contribution must be written as equations — prose description alone is insufficient.** *(real ICLR 2026)*
    "The paper only provides two known formulas in the preliminaries section and offers no expressions for its own methodology, especially for the loss function. A mere textual description is insufficient."
    If your method has a loss function, an objective, or a core operation — write the equation. Reviewers treat missing math as a signal the method is underspecified.

32. **Proof gaps or unverified assumptions.**
    "Lemma 3 assumes bounded gradient norm but this is never verified empirically or justified theoretically."

33. **Core argument not convincingly justified — reviewer can't trace theory to claim.** *(real ICLR 2024)*
    "I cannot tell how the high variance is connected to the generalization of diffusion models."
    "The mathematical derivation looks like heuristics instead of rigorous proof."
    For theory papers: if the causal chain from result → claim is unclear, the score lands at 3–5 regardless of technical correctness.

34. **Proof errors early in paper cause reviewers to stop reading entirely.** *(real ICLR 2024)*
    "I ceased my examination of the subsequent proofs due to the glaring inadequacies in the mathematical statements presented thus far."
    One bad theorem early kills the entire technical credibility of the paper.

35. **Proof error = score 2 regardless of other merits — and multiple reviewers will independently find it.** *(real ICLR 2026)*
    IDEA (Bayesian optimization) scored 2,2,2,2. Theorem 1's convergence proof was wrong: the regret bound reduced to O(N) (linear), meaning the algorithm doesn't converge. Three separate reviewers caught this independently.
    "Making the bound linear and thus trivial. An algorithm with linear regret does no better than just a naive strategy of constantly selecting the same point."
    Verify every proof step produces the correct asymptotic before submission.

36. **Inconsistent notation throughout a paper = reviewer distrust, not just minor polish.** *(real ICLR 2026)*
    IDEA switched between f(x,ξ), y(x), and f(x) for the same function; used N and n interchangeably; used k and k₀ for the same kernel. Reviewers flagged this as a sign the paper was not carefully prepared.
    Notation inconsistency signals the paper hasn't been read end-to-end. Do a full symbol audit before submission.

37. **Security papers without formal guarantees are treated as empirical-only and penalized.** *(real ICLR 2026)*
    SEAL (split learning privacy) scored 2,2,2,2 partly because: "There is no formal security guarantee provided in the paper."
    For security/privacy papers: empirical defense results alone are not sufficient at ICLR. Reviewers expect either a formal privacy guarantee (differential privacy, information-theoretic bound, etc.) or an explicit argument for why one cannot be provided. Without it, the contribution is treated as an engineering solution, not a research one.

38. **Self-contradiction in the threat model or problem setup is caught immediately.** *(real ICLR 2026)*
    SEAL claimed passive adversaries in §2.2 but described an active adversary in §3. Reviewer: "This is a self-contradiction."
    Reviewers read the threat model and problem setup carefully and check it against every subsequent section. Any inconsistency signals the paper wasn't read end-to-end before submission.

### E. Presentation & Completeness

39. **Presentation failures — undefined symbols, illegible figures, inaccessible prose.** *(real ICLR 2024)*
    "I really do not understand the statement of Theorem 1; there are undefined symbols like T(i)."
    "Figures and tables are almost illegible."
    "In its current form, it is inaccessible even to experts, leave alone non-experts."
    "The results are important enough that the paper ought to be substantially rewritten and resubmitted."
    Presentation failures are scored harshly at ICLR more than at other venues — reviewers treat them as disrespect for their time. A technically correct paper with illegible figures or unreadable notation will score 3 regardless of results.

40. **Informal language in formal writing.** *(real ICLR 2024)*
    "The usage of contractions like 'don't' and 'won't' is not suitable for formal writing."
    Cited explicitly as a weakness — signals the paper was rushed.

41. **Missing punctuation after equations cited as unprofessional.** *(real ICLR 2024)*
    "A glaring oversight is the absence of punctuation marks following ALL equations throughout the document."
    Seen in multiple papers — equations must end with period or comma like prose.

42. **Background section bloat at the expense of methodology = flagged explicitly.** *(real ICLR 2026)*
    "The paper dedicates an excessive amount of space (Section 3) to preliminary discussions of well-known concepts... In contrast, the core methodology (Section 4) is rushed and lacks crucial technical details."
    Space is zero-sum. If preliminaries run long and methodology is thin, reviewers notice and interpret it as the contribution being weak.

43. **Submitting an incomplete manuscript = automatic rejection.** *(real ICLR 2026)*
    Dyna-ViT had literal placeholder text "fill" and "fill if measured" in its experimental tables. Two reviewers with confidence 5 both responded: "I suggest the authors to complete this manuscript first and then submit."
    Placeholder text, missing numbers, or clearly unfinished sections are noticed immediately. There is no partial credit — reviewers treat it as disrespect for the review process and decline to evaluate the work.

44. **Title mismatch between PDF and submission system.** *(real ICLR 2026)*
    Physics-informed MeshGraphNet: the PDF title differed from the OpenReview submission title. Seen in two papers in the same batch — reviewers notice and it reduces confidence in overall care and rigor.
    Verify your PDF title, abstract, and author list exactly match what was submitted to the venue system before the deadline.

45. **Under page limit is penalized — use the full page allocation.** *(real ICLR 2026)*
    FINEdits image editing paper was under the ICLR page limit. Reviewer explicitly: "fill all 9 pages for ICLR."
    ICLR has a page limit, not a page target — but consistently short papers signal incomplete work. Use the full allocation.

46. **Human subjects studies require an IRB/ethics statement.** *(real ICLR 2026)*
    BayesBench involved human psychophysics participants. Reviewer: "Human subject studies require an ethics statement. Was this work approved by an Institutional Review Board? I may have missed something but I did not find any ethics statement in the current manuscript."
    Any paper involving human participants — including online studies, crowdsourced annotation, user evaluations, psychophysics — must include an ethics/IRB statement. Its absence is a reviewable defect. Add it to the paper, not just the appendix.

### F. Scope, Generalization & Application

47. **Method complexity must match the stated goal — contradiction is fatal.** *(real ICLR 2024)*
    Graph coarsening paper claimed to scale to large graphs but had O(n²k) complexity and was only tested on small graphs.
    "The proposed method is tested only on small graphs, which contradicts the motivation for graph coarsening."
    If your paper's motivation is scalability, your method's complexity and your benchmark graphs must both reflect that.

48. **Small gain relative to added complexity must be justified.** *(real ICLR 2026)*
    "The reported performance improvements are modest (~1–2% Dice) compared with the additional complexity introduced by multi-stage training and multiple attention and gating modules. The computational cost–benefit trade-off is not justified."
    If your improvement is single-digit percentage, you need either an efficiency argument or a theoretical explanation for why even small gains matter for the application.

49. **Medical AI papers: narrow domain scope (e.g., single pathology) blocks acceptance.** *(real ICLR 2026)*
    "The experimental scope is narrow... both tasks are limited to binary lesion segmentation. This setup is not representative of real clinical scenarios."
    Reviewers expect evaluation across multiple organs, modalities, and anatomies. COVID-only or single-disease papers must explicitly argue why generalization claims hold.

50. **Paper scope must match the venue — reviewers will question fit explicitly.** *(real ICLR 2026)*
    PS-QNN (quantum neural network) paper: all experiments were combinatorial optimization problems with no ML component. Reviewer: "I would therefore ask the authors to provide clarification on the nomenclature and why they think that the paper even fits the scope of this conference."
    If your paper is primarily from another field (quantum computing, operations research, control theory), make the ML connection explicit in the introduction. Reviewers will raise venue fit as a formal concern.

51. **LLMs evaluated on tasks where classical ML clearly dominates = wrong research framing.** *(real ICLR 2026)*
    HealthSLM-Bench evaluated SLMs on classification and regression tasks over wearable sensor data. Reviewer: "Normal ML prediction models can work much better, efficient, and accurate. There is no need to involve LLMs."
    If your task is a standard supervised prediction problem (classification, regression) with tabular or time-series input, you must compare against classical ML baselines (XGBoost, LSTM, etc.) and explain why LLMs are the right tool. Skipping this comparison signals the authors didn't ask the right question.

52. **Method that requires manual domain decomposition must address automatic alternatives.** *(real ICLR 2026)*
    LEICA (MARL) scored 4,6,4,2. The method's core requires hand-crafting an endogenous/exogenous state partition using domain knowledge of SMAX's data structure. Two reviewers independently flagged: "it is unclear whether it is suitable for other environments." The robustness claims were undermined because the foundation of the method can't be instantiated without knowing the environment.
    If your method has a component that requires manual domain-specific specification (state decomposition, graph partition, feature grouping), reviewers expect either: (a) an automatic or learned alternative, or (b) an explicit argument for why manual specification is practical and how a practitioner would do it in a new domain. Ignoring this question reads as the authors haven't thought about generalization.

53. **Observed pattern consistent with your mechanism ≠ evidence for your mechanism.** *(real ICLR 2026)*
    BayesBench (4,4,4,2) argued LLMs show "Bayesian computation" based on a regression-toward-mean effect. Three reviewers independently pointed out: simple heuristics like anchoring to the session mean produce identical patterns. The paper never tested or ruled out non-Bayesian alternatives.
    For any mechanistic or interpretability claim — "this model uses Bayesian inference," "this component performs attention routing," "this representation encodes X" — you must: (a) identify simpler alternative mechanisms that produce the same observable pattern, and (b) design experiments that distinguish between your mechanism and those alternatives. Showing a pattern is consistent with your hypothesis is not the same as demonstrating your hypothesis.

54. **Applied paper must report domain-standard metrics, not just ML accuracy metrics.** *(real ICLR 2026)*
    Quantum-inspired finance paper (4,4,2) reported classification accuracy and "win rate." Reviewer: "without portfolio backtest metrics (IC, Rank IC, Sharpe ratio), it is unclear whether the accuracy uplift converts into practical use."
    When applying ML to a domain with established evaluation conventions — finance (IC, Sharpe), clinical AI (AUC-ROC, sensitivity/specificity), drug discovery (binding affinity, synthesizability), robotics (task success rate, contact force) — you must report those domain metrics alongside ML metrics. Showing ML accuracy in isolation signals the authors don't know what practitioners actually measure.

55. **Core user-facing capability must be demonstrated directly, not just via downstream metrics.** *(real ICLR 2026)*
    IPE (natural language preference steering) claimed its key contribution was steering model behavior via natural language. But the paper showed no examples of natural language specifications anywhere, no user study, and evaluated exclusively on standard long-tail accuracy metrics that don't test the steering capability at all. Reviewer: "there are no examples of the natural language specifications in the paper, making it very hard to understand what the method is actually trying to achieve."
    When the central contribution is an interactive, user-facing, or controllable capability — natural language control, dialogue agents, explanation systems, preference interfaces — you must demonstrate that capability directly: examples, user study, or interactive evaluation. Downstream accuracy metrics alone cannot validate "users can control this with language." Without demonstration, reviewers assume the capability works only in the conditions you already tested.

56. **High filtering rate contradicts scalability or coverage claims.** *(real ICLR 2026)*
    GUIrilla deployed its crawler on 12,298 apps but the final dataset covered only 23 app genres — roughly 99% filtered out. Reviewer: "why nearly 99% of the applications are dropped? I am worried that such a high filtering rate will limit the scaling potential."
    If your pipeline discards most of its input, you must justify the filtering criteria and address whether the remaining data is representative. A large-scale collection claim with a 1% yield is a contradiction.

### G. Benchmark & Metric Design

57. **Benchmark metric with no normative grounding = "is this actually a benchmark?"** *(real ICLR 2026)*
    SWF Benchmark (LLM allocators) scored 4,2,4,4: "There isn't a clear normative argument that higher scores on this benchmark are preferable." The metric (Gini × ROI) had a theoretical maximum determined by the model population, not by any principled human value.
    For benchmark papers: you must argue explicitly why higher scores are better. A metric that optimizes an arbitrary combination without grounding it in human preferences or theory will be challenged as not being a benchmark at all.

58. **Random baseline outperforming most models = task design flaw.** *(real ICLR 2026)*
    "The random strategy performs better in SWF than most models, potentially indicating that this task isn't well suited to LMs."
    If random or trivial baselines beat most of your evaluated models, reviewers conclude the task is miscalibrated — either too hard for current models, or structured in a way that rewards random behavior. Always include a random baseline and address it explicitly if it performs unexpectedly well.

59. **Benchmark that doesn't require its claimed modality = fundamental validity problem.** *(real ICLR 2026)*
    MA-EgoQA claimed to test multi-agent visual reasoning, but text+video EgoMAS scored only 0.4% higher than text-only — because QA pairs were generated from captions and transcripts. Reviewer: "The paper claims multi-agent reasoning but the task is effectively text retrieval."
    For any multimodal or multi-agent benchmark: add a modality ablation (text-only, vision-only, etc.) and report it prominently. If removing the key modality doesn't hurt performance, the benchmark isn't testing what it claims.

60. **Benchmark with too few evaluation items cannot support reliability claims.** *(real ICLR 2026)*
    PROBE benchmark had only 216 questions total. Reviewers: statistically insufficient to draw reliable conclusions about model capabilities across dimensions.
    Single-digit hundreds of items for the whole benchmark is insufficient. As a rough guide, hundreds of items per capability dimension is the minimum — and include a saturation analysis if top models already score high.

61. **Benchmark oracle/ground truth construction must be fully documented.** *(real ICLR 2026)*
    MODEL-BENCH scored 2,2,2,2. The ground truth TLA+ specs relied on GPT-4o plus manual fixes — but the paper gave no details on how many annotators, how long it took, or whether multiple people reviewed each spec. Reviewer: "Without these important details, it is very difficult to judge the quality of the benchmark set."
    For any benchmark paper with a manual annotation or verification step: document the number of annotators, time cost, inter-annotator agreement, and whether any systematic quality check was run. Reviewers treat undocumented ground truth as untrustworthy ground truth.

62. **New benchmark must argue novelty against the closest existing benchmarks by name.** *(real ICLR 2026)*
    ITD (TTA benchmark) scored 2,4,2,4. Reviewers listed RoTTA, ImageNet-Vid, NOTE, TRIBE by name and asked: "How does ITD differ from these?" The paper didn't make this argument. MODEL-BENCH had the same problem — reviewers pointed out that existing model checker datasets (SPIN, TLA, UPPAAL) already had verified programs the authors could have used.
    Before submitting a benchmark paper, identify the 3–5 closest existing benchmarks and write a paragraph per one arguing what evaluation your benchmark enables that they cannot. If you can't answer that question, the benchmark contribution is weak.

63. **New evaluation metric or framework must show cases where it disagrees with the simple baseline.** *(real ICLR 2026)*
    Probing Memes scored 2,6,6,2. The phemotypes tracked accuracy almost perfectly in Figure 7. Reviewer: "If the proposed phemotypes largely parallel accuracy, what additional insight do they provide? This contradicts the motivation that current approaches obscure fine-grained differences."
    For any paper proposing a new evaluation metric, framework, or paradigm: show concrete examples where your metric gives different rankings or conclusions than accuracy/the existing baseline. If you can't find cases of disagreement, the metric is redundant. This is the primary empirical burden for evaluation framework papers.

### H. Structural & Logical Failures

64. **Taxonomy or framework paper must show what the framework enables, not just define it.** *(real ICLR 2026)*
    RL memory taxonomy paper scored 4,4,4,6: "This paper seems to have achieved only the first part." Reviewers expected either (a) a new benchmark built on the taxonomy or (b) a comparative analysis of existing methods classified under it. The definitions alone scored 4.
    If your contribution is a unifying taxonomy or formal framework, the second half of the paper must demonstrate what new analysis, insight, or evaluation it makes possible. Definitions without downstream payoff = incomplete contribution.

65. **Evaluation confound: labeling which response is "better" in the judge prompt biases the judge.** *(real ICLR 2026)*
    JUSSA (steering for LLM judges) explicitly labeled the steered output as "more honest alternative" in the judge prompt. Reviewer: "This framing undermines the central claim that JUSSA's improvements arise from genuine model-level contrast rather than prompt wording."
    For papers that use LLM judges: the judge prompt must be neutral. If you tell the judge which response is supposed to be better, the AUROC gain is measuring label bias, not method effectiveness.

66. **Tautological claims — results that hold by construction are not findings.** *(real ICLR 2026)*
    SWF Benchmark claimed "top models balance efficiency and fairness." Reviewer: "This is circular, since not doing so would mean they were not top models" — the multiplicative score selects for balance by definition.
    Before reporting a result, ask: does this follow necessarily from how I defined the metric or task? If yes, it is not a finding. Reviewers will catch it and use it to question whether the benchmark measures anything real.

67. **Extreme reviewer score variance (e.g., 2,2,2,8) is a rejection signal in 2026.** *(real ICLR 2026)*
    TopoGuide received three 2s from confidence-4/5 reviewers and one 8 from a confidence-3 reviewer. The outlier 8 did not rescue the paper.
    Per the 2025→2026 drift: AC meta-review now weights reviewer confidence when scores diverge. A single outlier high score from a low-confidence reviewer carries little weight against consensus from high-confidence reviewers.

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
- *(confirmed ICLR 2026)* Soundness theorem bug — ABS constrained generation paper had a fatal error in the proof of its main soundness guarantee. Confidence-5 reviewer: "Since that bug seems fatal, I won't bother to study the experiments unless urged to by the AC." When the main theorem is wrong, experiments become irrelevant to reviewers.
