# Family floor analysis (F1, F2, F5) — offline log-mining

Implements exactly the three free rungs specified in `docs/same-provider-scaling-research.md`
§3 (F1, F2, F5) and answers the honesty questions in §4. Pure offline JSONL mining — zero API
calls, zero cost. Script: `benchmark/analyze_family_floor.py`. Reproduce with:

```
.venv/Scripts/python.exe benchmark/analyze_family_floor.py
```

Ran twice back to back and diffed stdout byte-for-byte — output is deterministic (no
randomness in the analysis itself; the underlying JSONLs are static). Writes:

- `benchmark/results/f1_family_floor_items.csv` — every floor item, per benchmark
- `benchmark/results/f1_gpqa_deficit_items.csv` — the GPQA 3.8-vs-society deficit set
- `benchmark/results/f2_compute_frontier.csv` — config × benchmark accuracy/tokens table, with a `on_pareto_frontier` flag
- `benchmark/results/f5_difficulty_map.csv` — moo-bucket profile-vs-single-call deltas
- `benchmark/results/family_floor_analysis_data.json` — everything above, unrounded, for re-checking any number quoted below

## 0. Inventory — what's usable and what isn't

All 74 committed `benchmark/results/*.jsonl` files were inspected. **73 were used, 1 excluded:**

- `lever_gate_replay.jsonl` — excluded. Different schema entirely
  (`was_unanimous_correct`/`gate_doubt`/`gate_cost_usd`/`escalated_after_gate`), an analysis
  artifact of gate decisions, not a config×item correctness observation. Not usable for F1/F2/F5.

The other 73 files fall into 6 row schemas (baseline-wrapped, engine-wrapped-with-lever,
combo baseline+engine[+self_consistency5], flat qwen3.8-solo, flat moo, flat math-open) — all
handled, 0 unrecognized rows. Total: 6,284 JSONL lines → 6,975 normalized (benchmark, config,
question_id, correct, escalated, tokens) records (combo files emit up to 3 records/line since a
row logs baseline+engine+self_consistency5 on the same item).

**Benchmark identity was established from, in priority order:** an explicit `dataset` field
(`gpqa`/`supergpqa`/`lexam`/`mmlu_pro`/`mmlu_pro_stem`) → filename markers for files with no
`dataset` field (pilots, `qwen38_baseline`, `aime_open_*`, `math_open_*`) → the `question_id`
shape itself (`rec*` = GPQA-Diamond's native Record ID; 32-char hex = SuperGPQA's native uuid).
Files carrying no `dataset` field and no benchmark-naming filename convention (`lever_baseline_seed123.jsonl`, `lever_control_seed7.jsonl`, `lever_flagship_panel_seed42.jsonl`, etc. — the pre-multi-benchmark-harness generation) were spot-checked by `question_id` prefix and confirmed to be 100% GPQA-Diamond (`rec*` ids).

**One non-obvious but load-bearing check:** `moo_m1_eval.jsonl`'s four buckets
(`gpqa_hard`/`supergpqa_hard`/`medqa`/`saturated_easy_mmlu`, prefixed onto each `question_id`
as `bucket:id`) are **not a separate item pool** — they draw on the *same* loaders
(`load_gpqa`, `load_supergpqa`, `load_medqa`, `load_mmlu_pro`) with native, seed-independent
IDs (GPQA's Record ID, SuperGPQA's uuid, MedQA's/MMLU-Pro's own row index). Verified by direct
ID-overlap: `moo`'s `medqa` bucket shares 30/30 sampled ids with `medqa_pilot_seed42.jsonl`;
`moo`'s `saturated_easy_mmlu` bucket shares 30/30 with `mmlu_pro_pilot_seed42.jsonl` (13/30 also
land in the separately-STEM-filtered `lever_baseline_mmlu_pro_stem` pool). This means moo's
per-item results were correctly merge-able into the same benchmark pools as the lever/pilot
files below, which materially deepens F1's config coverage on GPQA-Diamond, SuperGPQA-hard,
MedQA and MMLU-Pro.

**Config naming.** Each file family maps to a `config` label: `baseline_3.7max` (the
single-flagship-call baseline, `solve_single_agent`/`qwen3.7-max`, all `baseline`-wrapped rows
and `lever_baseline_*` files), `shipped_engine` (`quorumqa.engine.orchestrator.run_question`,
the `engine`-wrapped rows in the combo pilot files), `qwen3.8_solo` (the standalone
`qwen38_baseline.py` script), one label per `lever` field value in the `lever_*` engine files
(`control`, `thinking_gate`, `chem_thinking_gate`, `flagship_panel`, `rag_presolve`, etc.),
`moo:<profile>` for the 7 moo profiles, and `baseline_3.7max_open` / `panel_open_flagship` /
`panel_open_cheap` for the open-answer AIME/MATH-500 files.

**Gap disclosed up front, relevant to F2:** the task's config list for F2 asks for "single flash
(thinking on or off)" as a standalone comparator. No file in this repo logs a bare single flash
call as the *graded top-level answer* — every `baseline`-labeled row uses `qwen3.7-max`
(flagship), and flash only appears as embedded seats inside multi-agent panels (`role="solver"`/`"solver_thinking"` inside `calls`). `moo:single-call` — the closest thing to a cheap
single-call baseline — is confirmed (`quorumqa/engine/profiles.py`) to be the *same*
`solve_single_agent` flagship baseline under a different harness, not a flash call. So "single
flash accuracy" as its own frontier point is **not computable from these logs** — noted rather
than approximated.

---

## F1(a) — Family blind-spot intersection per benchmark

**Definition used** (matches the task spec exactly): for each benchmark, take every item
attempted by ≥2 distinct configs (a config is "distinct" by its label above, e.g. `control` vs
`thinking_gate` vs `moo:flagship_panel` are three distinct configs even where seeds overlap).
Where the same (config, item) pair was logged more than once (different seeds re-sampling the
same item under the same lever name), the config is credited correct if it was **ever** correct
across those repeats — the floor set is therefore the *strict, cross-history, cross-config*
intersection: an item only counts as "floor" if literally every config ever logged against it,
including strong ones like `qwen3.8_solo` and the best 3-seed `chem_thinking_gate`, got it wrong
every single time.

**This is a different, much stricter quantity than the "unanimous-wrong" rate quoted elsewhere
in the project's own docs** (~10/90 ≈ 11% on GPQA cheap-tier, ~20/86 ≈ 23% on SuperGPQA-hard).
That figure is a property of *one config's internal panel* (do this run's 3 cheap seats agree on
the wrong letter) — a single-run measurement. What's computed here is a property spanning *every
config this project has ever run* on that item, so it is necessarily smaller: an item has to
defeat baseline_3.7max AND qwen3.8_solo AND chem_thinking_gate AND flagship_panel AND every RAG
variant, not just one gate's three cheap seats. Both numbers matter for different questions —
the single-run figure says how often a shipped gate will notice trouble; the cross-config figure
here says what no amount of within-family diversity has ever cracked.

| Benchmark | n items (ever logged) | n attempted by ≥2 configs | n floor items | floor rate (of the ≥2-config set) | configs covering it |
|---|---:|---:|---:|---:|---:|
| GPQA-Diamond | 197 | 192 | **4** | 2.1% | 24 |
| SuperGPQA-hard | 524 | 522 | **84** | 16.1% | 15 |
| LEXam | 90 | 90 | **8** | 8.9% | 5 |
| MedQA | 50 | 50 | **2** | 4.0% | 9 |
| MMLU-Pro | 83 | 83 | **2** | 2.4% | 11 |
| MATH-500-open | 59 | 59 | **1** | 1.7% | 3 |
| MATH-500-MC (4-choice) | 49 | 49 | 0 | 0.0% | 2 |
| GSM8K | 50 | 50 | 0 | 0.0% | 2 |
| AIME | 50 | 26 | 0 | 0.0% | 2 |

**Honesty note on thin-coverage benchmarks:** GSM8K, MATH-500-MC and AIME show a 0% floor, but
only 2 configs (`baseline_3.7max`/`shipped_engine`, or `baseline_3.7max_open`/`panel_open_cheap`
for AIME) were ever logged against them — a 0% floor there is not evidence of "no ceiling," it's
evidence of "we never tried hard enough configs to find one." GPQA-Diamond, SuperGPQA-hard,
LEXam, MedQA and MMLU-Pro have real multi-config depth (5–24 distinct configs) and their floor
numbers should be trusted much more than the thin ones.

**Floor question_ids** (full lists in `f1_family_floor_items.csv`):

- **GPQA-Diamond (4):** `rec7qmSnbud4FHSqL` (Physics general), `recAYkd96NNuNl1Ei` (Genetics),
  `recUOePh79cp4T2Bg` (Organic Chemistry), `recf6ayQmL1SxKbvW` (Molecular Biology) — none of
  these is even in the GPQA 3.8-deficit set below (see F1b), i.e. `qwen3.8_solo` also failed all
  4 wherever it attempted them, so these are genuine family-wide dead ends, not solo-model wins.
- **SuperGPQA-hard (84 of 522, 16.1%):** by far the largest and most concentrated floor — full
  list in the CSV; subjects skew "Science"/"Engineering" (SuperGPQA-hard's only two subject
  labels in this pool).
- **LEXam (8):** `102d2e11…`, `1aa2d158…`, `70d58c55…`, `72d45659…`, `7fe55c7a…`, `ed64e65a…`,
  `f1bdfe14…`, `fcdfb402…` (full uuids in the CSV) — 8.9% is high for only 5 configs covering it;
  worth flagging for the parked LEXam workstream.
- **MedQA (2):** `1142`, `202` — both `step2&3` (the harder clinical-management tier, not `step1`).
- **MMLU-Pro (2):** `1540` (law), `8955`.
- **MATH-500-open (1):** `test/precalculus/768.json`.

---

## F1(b) — GPQA qwen3.8-solo deficit decomposition

`qwen38_baseline_seed123.jsonl` (`qwen3.8-max-preview`, the family's best single model) attempted
**78/90** items (12 dropped to timeouts/429s per the commit history) and scored **73/78 = 93.6%**
— exact match to the number already recorded in the repo history.

"Best society" = the 3-seed `chem_thinking_gate` GPQA runs (seeds 217/314/471), pooled:
**240/264 = 90.9%** — exact match to the recorded 90.9% headline number. (Per-seed: 217→91.0%,
314→90.9%, 471→90.8% — a tight, low-variance 3-seed result, consistent with the project's own
"validated" bar.)

Because `qwen3.8_solo` (seed=123) and the `chem_thinking_gate` seeds (217/314/471) each sample a
*different* random 90-item subset from the ~198-item GPQA-Diamond pool (seed only controls
which indices get drawn, not a fixed split — see `benchmark/load_gpqa.py`), the two runs share
**68 items** in common, not 78 or 90. On those 68 shared items:

- `qwen3.8_solo` beat the (pooled, ever-correct) society on **2 items**:
  - `recVvpD8miVjmmyfe` (Molecular Biology) — society wrong under seeds 217 *and* 471, **escalated=True both times** (2 independent escalated-and-lost observations)
  - `recwW1A85nfyQpReG` (Astrophysics) — society wrong under seed 314, **escalated=True**

- **Split: 0 never-escalated (blind spot) / 2 escalated-and-lost (selection failure).**

**This is a small-n result (2 items) and should not be over-generalized, but the direction is
unambiguous and 100% one-sided**: on every item where the 3.8-solo bar beat the validated
90.9% society, the society's tribunal machinery *did* notice the disagreement (both items
escalated in every observation) but the judge/verifier chain still landed on the wrong answer.
Zero cases where the panel unanimously agreed on the wrong answer and never got a second look.
**This arbitrates cleanly toward selection-side levers (verifier-selected best-of-N, judge
quality, self-preference audit — P2/P4/P5 in the plan) over coverage-side levers (flaw-finder
recall, permutation) for closing the remaining GPQA gap** — at least on this small, honest
sample. A coverage lever (W1's flaw-finder, W2's permutation) has *no logged evidence* of a
target to fix here: there is no blind-spot item in this deficit set for it to catch. Note this
conclusion is about the 2-item *3.8-vs-society deficit*, not the 4-item cross-config *floor*
above — those are disjoint sets answering disjoint questions (the floor is unsolved by
everything ever logged, including 3.8; the deficit is solved by 3.8 but lost by the society).

---

## F2 — Compute-allocation frontier

For every (benchmark, config) pair: `accuracy` = correct/n pooled across every row logged under
that config (not a paired-same-items delta — see caveat below), `mean_tokens_per_q` = mean of
(sum of input+output tokens across all `calls` in that row), or moo's own `total_tokens` field
directly as instructed. Full table: `f2_compute_frontier.csv`. Below: the **Pareto frontier**
per benchmark (configs no cheaper *and* more accurate alternative dominates).

**Caveat, stated up front:** these are pooled marginal accuracies across whatever items each
config happened to be run on (different seeds sample different item subsets), *not* the
paired-same-items 3-seed deltas the project's own validated numbers use. They're the right tool
for a frontier/dominance question (which configs are Pareto-inefficient) but shouldn't be read
as precise point estimates of a lever's effect size — e.g. `chem_thinking_gate`'s 90.9% here
matches the validated paired number closely because that config *is* the validated 3-seed run,
but `thinking_gate`'s 86.6% here vs. baseline's 86.7% is a marginal-pool comparison, not the
paired "+1.1pp" already recorded elsewhere.

| Benchmark | Pareto frontier (config: acc @ mean tok/q, n) |
|---|---|
| GPQA-Diamond | `baseline_3.7max`: 86.7% @ 3,282tok (n=451) → `qwen3.8_solo`: 93.6% @ 4,229tok (n=78) |
| SuperGPQA-hard | `baseline_3.7max`: 77.3% @ 3,151tok (n=260) → `moo:single-call`: 79.3% @ 4,106tok (n=29) → `qwen38_panel`: 87.3% @ 7,584tok (n=63) |
| MMLU-Pro | `moo:single-call`: 96.7% @ 919tok (n=30) — **alone**, dominates everything else logged |
| MedQA | `baseline_3.7max`: 94.0% @ 1,065tok (n=50) → `moo:single-call`: 96.7% @ 1,072tok (n=30) |
| LEXam | `baseline_3.7max`: 86.0% @ 1,285tok (n=50) — **alone** |
| GSM8K | `baseline_3.7max`: 100% @ 656tok (n=50) — **alone** |
| MATH-500-MC | `baseline_3.7max`: 100% @ 1,640tok (n=49) — **alone** |
| MATH-500-open | `baseline_3.7max_open`: 96.6% @ 2,703tok (n=59) — **alone** |
| AIME | `baseline_3.7max_open`: 100% @ 5,327tok (n=48) — **alone** |

**The headline finding, stated plainly because it's uncomfortable but the numbers are what they
are:** on 6 of 9 benchmarks, a single bare flagship call (`baseline_3.7max`) is the ENTIRE Pareto
frontier — every multi-agent lever logged against that benchmark (`shipped_engine`, `control`,
`thinking_gate`, `flagship_panel`, `rag_*`, `combined`, `five`, `smart_gate`, `subject`,
`thinking_all`) is strictly dominated: more tokens for equal or worse accuracy. This is not new —
it's the same story the repo's own commit history already tells for the shipped engine ("shipped
78.9% @ −11% cost vs flagship-solo 84.4%" — a *cost-down* trade, not an accuracy-up one) — but F2
makes it precise and near-universal across the whole logged portfolio, not just the one shipped
config. The two places a multi-agent/higher-tier config *does* clear the frontier are exactly the
two the project's own validated record already flags as real wins: **GPQA** (`qwen3.8_solo`, a
higher-tier *model* swap, not a lever) and **SuperGPQA-hard** (`qwen38_panel`, ditto, and only
after `moo:single-call` first beats plain baseline by 2pt at slightly more tokens). No *lever*
(gate/panel/RAG built purely from flagship+flash seats) makes the frontier on any of the 9
benchmarks in this analysis. **MMLU-Pro and GSM8K/MATH-500-MC/AIME/LEXam/MATH-500-open are
flagged as saturated or near-saturated single-call domains where any additional-compute lever is
pure waste** — consistent with §4.6 of the plan.

`shipped_engine` is dominated everywhere it appears (GPQA 79.8%@8,620tok vs baseline 86.7%@3,282tok; SuperGPQA-hard 67.4%@10,343tok vs baseline 77.3%@3,151tok; GSM8K 96.0%@1,746tok vs 100%@656tok; LEXam 72.0%@3,480tok vs 86.0%@1,285tok; MATH-500-MC 93.9%@5,655tok vs 100%@1,640tok; MMLU-Pro 82.0%@4,154tok vs baseline 95.5%@1,202tok) — the single largest, most consistent dominance pattern in the whole table.

---

## F5 — Difficulty-conditional non-monotonicity map

Primary vehicle: `moo_m1_eval.jsonl`'s 4 blended-workload buckets, which are themselves
difficulty/gap tiers by construction (`run_moo_eval.py`'s own docstring: `gpqa_hard` = moderate
gap ~11% unanimous-wrong, `supergpqa_hard` = large gap ~23%, `medqa` = tiny gap ~4%,
`saturated_easy_mmlu` = saturated/easy). For each bucket, restricted to the item set common to
**all 7 profiles** (paired comparison), delta = profile accuracy − `single-call` accuracy.

**Honesty note on a difficulty proxy that does NOT work here:** the task asks to use "MATH-500's
level field." Both `math500_hard_pilot_seed42.jsonl` and the `math_open_*` files are generated by
`load_math.py`/`load_math_open.py` filtered to `level=5` only (MATH-500's own hardest label) —
level is **constant across every row in these files**, so it cannot be used as an in-file binning
variable. This is stated in the loaders' own docstrings ("needs real headroom... defaults to
level=5"). No level-conditional non-monotonicity map is computable from these particular logs.

| Bucket (n common) | single-call acc | Profiles that clear the noise floor (≥2/n items, i.e. ≳8pp at this n) |
|---|---:|---|
| gpqa_hard (n=27) | 88.9% | `thinking_gate` **+11.1pp** (+3 items) — the only clean positive |
| supergpqa_hard (n=25) | 84.0% | `standard-tribunal` **−20.0pp** (−5), `rag_presolve` **−12.0pp** (−3), `thinking_gate` **−8.0pp** (−2, borderline) |
| medqa (n=30) | 96.7% | none — every profile tied at 0.0pp |
| saturated_easy_mmlu (n=29) | 96.6% | none clears 2 items; `standard-tribunal` −3.4pp (−1) is noise-level |

(Noise threshold: the project's own house rule treats ~1 item as noise at n=90; scaled to these
n≈25–30 paired sets, 1 item ≈ 3.3–4.0pp, so only ≥2-item deltas — ≈7–8pp — are treated as signal
here; 1-item deltas are listed in the CSV but not called out as findings.)

**This refines, rather than cleanly confirms, the task's stated "known result."** The
saturated/easy and tiny-gap buckets behave as expected — no config clears noise in either
direction, i.e. deliberation is inert (not harmful) there on this sample, milder than the
"−4 to −6" prior. The moderate-gap bucket (`gpqa_hard`) shows exactly one config (`thinking_gate`)
with a real, clean positive — consistent with "helps on hard-gap bins." **But the large-gap
bucket (`supergpqa_hard`) — the regime the prior would predict the strongest help — instead shows
3 of 6 non-baseline profiles actively HURTING relative to single-call**, including
`standard-tribunal`'s −20pp, the single largest effect in the whole table. `flagship_panel` (the
one profile validated at 3-seed, 90-item scale as +4.1) is merely flat here (0.0pp), not
negative, so this is not a contradiction of that validated result — this is a *different*,
smaller (n=25), single-seed, blended-workload sample, not the same items/seed as the validated
run. The honest reading: **deliberation's payoff on the hardest bucket is highly
technique-dependent, not a blanket "more calls help here"** — `standard-tribunal` and
`rag_presolve` are actively counterproductive on `supergpqa_hard` in this sample while
`flagship_panel` merely breaks even and only `qwen38_panel`/`moo:single-call` (per F2, not part
of this paired table) show clear gains. This is worth a dedicated, larger-n follow-up before
locking any routing rule that assumes "hard bucket → route to any deliberation profile."

**Secondary, lower-confidence proxy — per-subject `shipped_engine` vs `baseline_3.7max` within
the combo pilot files** (paired on the same item, same row; full table in stdout / the JSON):
most subject bins are too small (n=1–8) to trust, but two bins clear real N and show a
consistent, large negative: **GPQA-Diamond Organic Chemistry (n=86): 86%→72%, −14.0pp (−12
items)** and **SuperGPQA-hard Science (n=58): 76%→64%, −12.1pp (−7 items)**. LEXam
Interdisciplinary (n=42): 86%→69%, −16.7pp (−7 items) is also large-N. All three point the same
direction as F2's headline finding: `shipped_engine` is a net accuracy cost relative to a bare
flagship call on the specific high-volume subject bins it's actually tested on, not a targeted
win.

---

## Decision consequences

**For W1/W2's addressable pools.** The plan quotes bars as "~+3/90 against ADDRESSABLE items"
(pool minus floor). Using the strict cross-config floor measured here: on **GPQA**, the floor is
only 4/197 (2.1%) — subtracting it from a fresh 90-item run costs ≈1.9 items, so a "+3/90" bar is
barely affected; W1/W2 should still budget against ~88 addressable items, not a materially
smaller number. On **SuperGPQA-hard**, the floor is 84/522 (16.1%) — subtracting it from a fresh
90-item run costs ≈14.5 items, shrinking the addressable base to ~75–76; a "+3" bar there is
effectively **+3/~76 (≈4.0% relative)**, not +3/90 (≈3.3%) — a real, if modest, upward
recalibration of what "clearing the bar" means on that surface specifically. Separately, F1(b)'s
2-item GPQA deficit set is 100% escalated-and-lost, 0% never-escalated — it hands W1 (a
coverage/blind-spot lever) zero logged targets on this small sample, while handing selection-side
work (P2 verifier-selection, P4 self-preference audit, P5 plus-as-flaw-finder) a concrete, if
small, existence proof that the gap is real and selection-shaped on GPQA.

**For W7's reframing.** F2's answer to the plan's own pre-registered decision rule ("crossovers
exist → reframe as compute-allocator; no crossovers → record dominant config per surface") is
unambiguous: crossovers exist, and they are severe. On 6 of 9 benchmarks a bare flagship call is
the *entire* frontier — nothing built from panels/gates/RAG on top of it is worth its tokens. W7
should be scoped even more narrowly than "route hard items to a panel": the router's job on most
surfaces is to **recognize saturation and default to `baseline_3.7max`**, escalating to a
different *tier* (3.8) rather than a different *lever* only on GPQA/SuperGPQA-hard, and even
there only after confirming (as `qwen38_panel`/`qwen3.8_solo` already do) that the escalation
target is a stronger model, not more calls to the same tier.

**For F5's routing rules.** Lock in: saturated/easy and tiny-gap items → single call, no
exceptions (confirmed, though the effect size here is milder than the −4/−6 prior — call it
"inert, not clearly harmful" pending a larger sample). Moderate-gap (GPQA-hard-tier) →
`thinking_gate` specifically clears noise positively; other profiles don't, so "route to
deliberation" should mean "route to thinking_gate," not "route to any panel." **Do NOT lock a
rule that routes large-gap (SuperGPQA-hard-tier) items to `standard-tribunal` or `rag_presolve`**
— both showed real, noise-clearing harm on this sample; only `flagship_panel`-class configs (and,
per F2, tier escalation) have any logged evidence of net benefit there. This is a genuine
refinement of the plan's working assumption and should gate P9 (heterogeneous flagship panel)
planning: the hard bucket is not "deliberation helps here," it's "*specifically* flagship-tier
deliberation helps, cheap-tier tribunal/RAG-gate machinery hurts."

---

## Orchestrator review annotations (2026-07-24, before commit)

Two F2 frontier rows are SURVIVORSHIP-CONTAMINATED and must not be read as
frontier points:

1. **`qwen38_panel` 87.3% @ 7,584 tok (n=63) on SuperGPQA-hard** — this is
   pooled marginal accuracy over the 63 SURVIVORS of a run with ~30% timeout
   drops (the dropped items skew hard/long). The recorded PAIRED verdict for
   this config is NEGATIVE ("ties the single baseline, TRAILS
   flagship_panel, 0% escalation" — improvement-loop-state.md). The paired
   verdict stands; the pooled 87.3% is an artifact of who survived.
2. **AIME `baseline_3.7max_open` 100% (n=48)** — survivors of the
   INVALIDATED run #1 (12/60 baseline drops, biased-easy). AIME has no valid
   measured numbers yet; the queued fixed pilot is the measurement.

With those rows discounted, F2's headline is unchanged and slightly
STRONGER: the only clean frontier-clearing config beyond a bare flagship
call is `qwen3.8_solo` on GPQA — a tier swap. The core reading stands: on 6
of 9 benchmarks a single flagship call dominates every logged lever; levers
only pay on the large-gap surfaces (GPQA/SuperGPQA-hard), and there they pay
as ACCURACY-up at cost-up (validated paired records), not as frontier
domination in pooled tokens.

Also noted: F5's supergpqa_hard bucket findings (standard-tribunal −20pp,
rag_presolve −12pp) come from moo_m1_eval's ~25-30-item buckets — paired but
small-n; treat as flags to respect in routing (do NOT route large-gap items
to standard-tribunal), not as contradictions of the 3-seed validated
rag_presolve record (+4.7/+6.9/+8.0/−5.6 on n=86-90 runs).
