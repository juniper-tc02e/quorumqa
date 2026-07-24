# Pool checkability: W1-B (CAS arm) cap

Offline, no-API classification of the CONTROL-lever unanimous-wrong pool (GPQA + SuperGPQA-hard) into `quantitative-checkable` vs `conceptual`, per `docs/same-provider-scaling-research.md` F6. **This fraction IS the W1-B (CAS arm) CAP, committed before W1 runs** -- W1-B structurally cannot catch a `conceptual` unanimous-wrong item no matter how good its extraction/verification step is.

Scope: only `lever == "control"` (or unlabeled legacy pre-lever-tagging) rows count -- every other lever changes the solver dispatch or forces escalation on some unanimous cases, which would mix "unanimous-wrong under a different engine" into what should be the shipped baseline's blind spot. See `benchmark/classify_pool_checkability.py`'s module docstring for the full inventory rationale.

**Honest caveat:** the measured fractions below (53% GPQA, 87% SuperGPQA-hard) are noticeably HIGHER than `same-provider-scaling-research.md`'s prior qualitative framing ("the unanimous-wrong pool is largely conceptual MC"). That framing was an impression, not a prior measurement -- this is the first actual classification run. Two things can both be true and should be checked before leaning on this number: (1) SuperGPQA-hard's trimmed-to-4-choices subset (see `benchmark/load_supergpqa.py`) may simply skew toward STEM-numeric disciplines more than GPQA does, which the pool composition here supports (spot-check the examples below); (2) this regex heuristic errs toward counting short alphanumeric codes (point groups, chemical formulas, symmetry labels) as "quantitative" even though a CAS engine cannot literally evaluate them the way it can an equation -- a stricter heuristic would likely pull the fraction down, not up. Treat these numbers as the CEILING the heuristic supports, not a validated floor.

## GPQA

- Control-lever files pooled: adhoc_check.jsonl, full_run.jsonl, full_run2.jsonl, lever_control_seed7.jsonl, lever_control_seed7_replicate.jsonl, smoke.jsonl, smoke2.jsonl, smoke3.jsonl
- Unique questions observed across those files: 144
- Raw unanimous-wrong rows (pre-dedup, across seeds/files): 53
- **Pool size (unique unanimous-wrong items, deduped by question_id): 34**
- Single-seed reference cross-check: full_run2.jsonl: 12/90 unanimous-wrong (13.3%)
- **Checkable fraction: 18/34 = 52.9% quantitative-checkable (16 conceptual)**

Example `quantitative-checkable` items:

- `rec0Arme2jcXQZnAW` -- 4/4 choices numeric/equation-shaped (>=75%)
  - Q: trans-cinnamaldehyde was treated with methylmagnesium bromide, forming product 1.  1 was treated with pyridinium chlorochromate, forming product 2.  3 was treated with (dimethyl(oxo)-l6-sulfaneylidene)methane in DMSO at 
  - Choices: ['11', '10', '12', '14']
- `recDj2Y2BbtV02Wv5` -- 3/4 choices numeric/equation-shaped (>=75%)
  - Q: toluene is treated with nitric acid and sulfuric acid, forming product 1.  1 is treated with MnO2 and H2SO4, forming product 2.  2 is treated with acetone and aqueous sodium hydroxide, forming product 3.  what is the mol
  - Choices: ['c3', 'c2h', 'd2h', 'cs']
- `recGee5m84dg5FZkc` -- 4/4 choices numeric/equation-shaped (>=75%)
  - Q: Substances 1-6 undergo an electrophilic substitution reaction with an excess of bromine (it is assumed that only one monobromo derivative is formed): 1) С6H5-CH3 2) C6H5-COOC2H5 3) C6H5-Cl 4) C6H5-NO2 5) C6H5-C2H5 6) C6H
  - Choices: ['3<5<1<6<2<4', '4<2<6<3<1<5', '4<6<2<1<5<3', '6<2<4<5<1<3']

Example `conceptual` items:

- `rec0yTRmO1o1xCA6H` -- only 0/4 choices numeric/equation-shaped
  - Q: In a parallel universe where a magnet can have an isolated North or South pole, Maxwell’s equations look different. But, specifically, which of those equations are different?
  - Choices: ['The ones related to the divergence and the curl of the magnetic field.', 'The one related to the circulation of the magnetic field and the flux of the electric field.', 'The ones related to the circulation of the electric field and the divergence of the magnetic field.', 'The one related to the divergence of the magnetic field.']
- `recAYkd96NNuNl1Ei` -- only 0/4 choices numeric/equation-shaped
  - Q: Which of the following issues are the most common sources of difficult-to-spot erroneous results generated in genomics data analysis:  - Mutually incompatible data formats - The "chr" / "no chr" confusion - Reference ass
  - Choices: ['2, 3 and 4', '3 and 4', '2 and 3', 'All of the above']
- `recBhnXrUyTJ6WHIR` -- only 0/4 choices numeric/equation-shaped
  - Q: You are studying a nuclear decay which converts two heavy nucleons of flavor A to another flavor B, while simultaneously emitting two much lighter particles E and V. In short, 2A -> 2B + 2E + 2V. It is known that the tot
  - Choices: ['The spectrum becomes discrete, and the endpoint decreases.', 'The spectrum remains continuous with an adjusted shape, and the endpoint decreases.', 'The spectrum becomes discrete, and the endpoint increases.', 'The spectrum remains continuous with an adjusted shape, and the endpoint increases.']

## SuperGPQA-hard

- Control-lever files pooled: lever_control_supergpqa_seed123.jsonl, lever_control_supergpqa_seed271.jsonl, lever_control_supergpqa_seed606.jsonl, lever_control_supergpqa_seed7.jsonl, lever_control_supergpqa_seed838.jsonl, supergpqa_hard_pilot_seed42.jsonl
- Unique questions observed across those files: 518
- Raw unanimous-wrong rows (pre-dedup, across seeds/files): 112
- **Pool size (unique unanimous-wrong items, deduped by question_id): 110**
- Single-seed reference cross-check: supergpqa_hard_pilot_seed42.jsonl: 20/86 unanimous-wrong (23.3%)
- **Checkable fraction: 96/110 = 87.3% quantitative-checkable (14 conceptual)**

Example `quantitative-checkable` items:

- `01ac3e46a5f04c48b3ad3d21e7a8eacd` -- 4/4 choices numeric/equation-shaped (>=75%)
  - Q: There are two concurrent programs, $\mathbf{P}_{1}$ and $\mathbf{P}_{2}$, with the same priority level, and their execution processes are as follows. Assume that the current semaphores are $\mathrm{s1} = 0$, $\mathrm{s2}
  - Choices: ['$$\n5, 1 2, 9\n$$', '$$\n4, 1 2, 9\n$$', '$$\n4, 1 1, 8\n$$', '$$\n5, 1 1, 8\n$$']
- `05ff75c957d445298164337f6fb16dce` -- 4/4 choices numeric/equation-shaped (>=75%)
  - Q: The torque machine can generate a large amount of torque on the $O$ axis. The active component is the gear on the $C$ axis, which drives a screw with a pitch of $3mm$. When the screw rotates, it causes the internally thr
  - Choices: ['$$\n0. 8 9 \\times1 0^{-6} \\mathbf{r} \\mathrm{a d} / \\mathbf{s}^{2}\n$$', '$$\n1. 4 8 \\times1 0^{-2} \\mathbf{r} \\mathrm{a d} / \\mathbf{s}^{2}\n$$', '$$\n3. 3 1 \\times1 0^{-4} \\mathbf{r} \\mathrm{a d} / \\mathbf{s}^{2}\n$$', '$$\n- 3. 5 9 \\times1 0^{-4} \\mathbf{r} \\mathrm{a d} / \\mathbf{s}^{2}\n$$']
- `095ff35b087e416f9a2797a86611b4c2` -- 4/4 choices numeric/equation-shaped (>=75%)
  - Q: Find the heat capacity for a non-atomic gas undergoing the following process
  - Choices: ['$$PV^{-1}=Const$$', '$$ \\dfrac{P}{T^2} =Const$$', 'PV^{-5}=Const', 'PV^{-2}=Const']

Example `conceptual` items:

- `10306739cc6f4b94afa3336c48376be7` -- only 2/4 choices numeric/equation-shaped
  - Q: Let `xi _1, xi _2, xi _3, xi _4` be a fundamental solution set of `Ax=0`. Then another fundamental solution set of the equation can be ( )
  - Choices: ['a vector group `alpha _1, alpha _2, alpha _3, alpha _4` equivalent to `xi _1, xi _2, xi _3, xi _4`', 'a vector group `alpha _1, alpha _2, alpha _3, alpha _4` of the same nullity as `xi _1, xi _2, xi _3, xi _4`', 'a vector group `alpha _1, alpha _2, alpha _3, alpha _4` of the same rank as `xi _1, xi _2, xi _3, xi _4`', 'a vector group `alpha _1, alpha _2, alpha _3, alpha _4` of the same span as `xi _1, xi _2, xi _3, xi _4`']
- `48de38a79dd148da89ca4bf92c8bddd1` -- only 0/4 choices numeric/equation-shaped
  - Q: A 23-year-old female experiences nausea and vomiting after consuming dried fish fillets and beer. A few hours later, she complains of numbness in the lips, weakness in the limbs, followed by difficulty breathing and coma
  - Choices: ['Botulism', 'Anaphylactic shock', 'Scombroid fish intoxication', 'Pufferfish (fugu) poisoning']
- `4da6b094f021432e9f07bcff16c36b4e` -- only 0/4 choices numeric/equation-shaped
  - Q: A patient with acute leukemia had 100% positive MPO, NAS-DCE, NAS-DAE, and PAS staining, with strong positivity for the first three, 0% for NAS-DAE plus NaF inhibitor, and diffuse positivity for PAS: 0%, and diffuse posi
  - Choices: ['Acute promyelocytic leukemia', 'Chronic neutrophilic leukemia', 'Chronic myelomonocytic leukemia', 'Acute myelomonocytic leukemia']

## File inventory (which files have `solver_answers`)

| file | rows | has solver_answers | control-lever + in-scope | dataset |
|---|---:|---:|---:|---|
| adhoc_check.jsonl | 9 | 9 | 9 | gpqa |
| aime_open_baseline_seed42.jsonl | 48 | 0 | 0 |  |
| aime_open_panel_cheap_seed42.jsonl | 28 | 0 | 0 |  |
| full_run.jsonl | 74 | 74 | 74 | gpqa |
| full_run2.jsonl | 90 | 90 | 90 | gpqa |
| gsm8k_pilot_seed42.jsonl | 50 | 50 | 0 |  |
| lever_baseline_gpqa_seed314.jsonl | 89 | 0 | 0 |  |
| lever_baseline_mmlu_pro_stem_seed42.jsonl | 60 | 0 | 0 |  |
| lever_baseline_seed123.jsonl | 90 | 0 | 0 |  |
| lever_baseline_seed7.jsonl | 89 | 0 | 0 |  |
| lever_baseline_supergpqa_seed123.jsonl | 86 | 0 | 0 |  |
| lever_baseline_supergpqa_seed7.jsonl | 88 | 0 | 0 |  |
| lever_chem_flagship_gate_gpqa_seed777.jsonl | 88 | 88 | 0 |  |
| lever_chem_flagship_gate_gpqa_seed888.jsonl | 87 | 87 | 0 |  |
| lever_chem_flagship_gate_seed555.jsonl | 88 | 88 | 0 |  |
| lever_chem_thinking_gate_gpqa_seed217.jsonl | 89 | 89 | 0 |  |
| lever_chem_thinking_gate_gpqa_seed314.jsonl | 88 | 88 | 0 |  |
| lever_chem_thinking_gate_gpqa_seed471.jsonl | 87 | 87 | 0 |  |
| lever_combined_seed42.jsonl | 90 | 90 | 0 |  |
| lever_combined_seed7.jsonl | 88 | 88 | 0 |  |
| lever_control_lexam_seed42.jsonl | 90 | 90 | 0 |  |
| lever_control_seed7.jsonl | 90 | 90 | 90 | gpqa |
| lever_control_seed7_replicate.jsonl | 89 | 89 | 89 | gpqa |
| lever_control_supergpqa_seed123.jsonl | 88 | 88 | 88 | supergpqa |
| lever_control_supergpqa_seed271.jsonl | 90 | 90 | 90 | supergpqa |
| lever_control_supergpqa_seed606.jsonl | 89 | 89 | 89 | supergpqa |
| lever_control_supergpqa_seed7.jsonl | 90 | 90 | 90 | supergpqa |
| lever_control_supergpqa_seed838.jsonl | 90 | 90 | 90 | supergpqa |
| lever_five_seed42.jsonl | 90 | 90 | 0 |  |
| lever_flagship_panel_mmlu_pro_stem_seed42.jsonl | 60 | 60 | 0 |  |
| lever_flagship_panel_seed42.jsonl | 90 | 90 | 0 |  |
| lever_flagship_panel_seed42_replicate.jsonl | 90 | 90 | 0 |  |
| lever_flagship_panel_seed7.jsonl | 90 | 90 | 0 |  |
| lever_flagship_panel_supergpqa_seed123.jsonl | 81 | 81 | 0 |  |
| lever_flagship_panel_supergpqa_seed42.jsonl | 79 | 79 | 0 |  |
| lever_flagship_panel_supergpqa_seed7.jsonl | 83 | 83 | 0 |  |
| lever_gate_replay.jsonl | 56 | 0 | 0 |  |
| lever_qwen38_judge_gpqa_seed42.jsonl | 76 | 76 | 0 |  |
| lever_qwen38_panel_supergpqa_seed42.jsonl | 63 | 63 | 0 |  |
| lever_rag_presolve_gpqa_seed42.jsonl | 86 | 86 | 0 |  |
| lever_rag_presolve_supergpqa_seed123.jsonl | 89 | 89 | 0 |  |
| lever_rag_presolve_supergpqa_seed271.jsonl | 90 | 90 | 0 |  |
| lever_rag_presolve_supergpqa_seed42.jsonl | 90 | 90 | 0 |  |
| lever_rag_presolve_supergpqa_seed606.jsonl | 90 | 90 | 0 |  |
| lever_rag_presolve_supergpqa_seed7.jsonl | 87 | 87 | 0 |  |
| lever_rag_recursive_lexam_seed42.jsonl | 90 | 90 | 0 |  |
| lever_rag_recursive_supergpqa_seed42.jsonl | 89 | 89 | 0 |  |
| lever_rag_thinking_gate_supergpqa_seed271.jsonl | 89 | 89 | 0 |  |
| lever_rag_thinking_gate_supergpqa_seed606.jsonl | 87 | 87 | 0 |  |
| lever_rag_thinking_gate_supergpqa_seed838.jsonl | 89 | 89 | 0 |  |
| lever_smart_gate_seed123.jsonl | 89 | 89 | 0 |  |
| lever_subject_seed7.jsonl | 89 | 89 | 0 |  |
| lever_thinking_all_seed42.jsonl | 90 | 90 | 0 |  |
| lever_thinking_all_seed7.jsonl | 90 | 90 | 0 |  |
| lever_thinking_gate_lexam_seed42.jsonl | 50 | 50 | 0 |  |
| lever_thinking_gate_mmlu_pro_seed42.jsonl | 50 | 50 | 0 |  |
| lever_thinking_gate_seed123.jsonl | 90 | 90 | 0 |  |
| lever_thinking_gate_seed42.jsonl | 90 | 90 | 0 |  |
| lever_thinking_gate_seed7.jsonl | 89 | 89 | 0 |  |
| lever_thinking_seed42.jsonl | 90 | 90 | 0 |  |
| lever_thinking_seed7.jsonl | 90 | 90 | 0 |  |
| lexam_pilot_seed42.jsonl | 50 | 50 | 0 |  |
| math500_hard_pilot_seed42.jsonl | 49 | 49 | 0 |  |
| math_open_baseline_seed42.jsonl | 59 | 0 | 0 |  |
| math_open_panel_cheap_seed42.jsonl | 59 | 0 | 0 |  |
| math_open_panel_seed42.jsonl | 59 | 0 | 0 |  |
| medqa_pilot_seed42.jsonl | 50 | 50 | 0 |  |
| mmlu_pro_pilot_seed42.jsonl | 50 | 50 | 0 |  |
| moo_m1_eval.jsonl | 827 | 0 | 0 |  |
| qwen38_baseline_seed123.jsonl | 78 | 0 | 0 |  |
| smoke.jsonl | 2 | 2 | 2 | gpqa |
| smoke2.jsonl | 2 | 2 | 2 | gpqa |
| smoke3.jsonl | 6 | 6 | 6 | gpqa |
| supergpqa_hard_pilot_seed42.jsonl | 86 | 86 | 86 | supergpqa |
