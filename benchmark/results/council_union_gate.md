# Council union gate (D2) — de-inflated cross-config union, GPQA-Diamond

Implements `docs/capability-roadmap.md` §2.4 lever **D2** ("De-inflated cross-config union
(the free half of the council lever)"), the free rung that must clear before the paid **D4**
council-of-configs screen (~5.0M tokens, §2.4 Rung 2) is allowed to run. Pure offline JSONL
log-mining. Zero API calls, zero cost. Script: `benchmark/council_union_gate.py`. Reproduce with:

```
.venv/Scripts/python.exe benchmark/council_union_gate.py
```

Run twice back to back and diffed stdout byte-for-byte — output is deterministic (no randomness
anywhere in this analysis; the underlying JSONLs are static). Writes:

- `benchmark/results/council_union_gate_items.csv` — every GPQA item covered by ≥3 configs, full per-item detail
- `benchmark/results/council_union_gate_pairs.csv` — every config pair's discordance rate
- `benchmark/results/council_union_gate_configs.csv` — per-config accuracy, full pool vs D2 subset
- `benchmark/results/council_union_gate_data.json` — everything above, unrounded, for re-checking any number quoted below

## 0. Why this script exists

§2.3 of the roadmap reports F1(a): on GPQA, only 4 of 192 multi-config items (2.1%) are wrong
under *every* logged config, against 90.9% for the best single config (`chem_thinking_gate`) —
roughly **7pt of answers the model family already produces and then discards**. That number is
the entire evidence base for **D4**, the proposed council lever (show a judge the candidate
answers from several different configs, ~5.0M tokens for a single-seed screen). But §2.3 also
states the number is **inflated**, for a specific, named reason: a config was credited correct if
it was **ever** correct across seed repeats of that same config, so part of the 7pt is resampling
luck, not genuine cross-config complementarity that a council could exploit. This script
de-inflates it and applies a pre-registered decision rule to decide whether D4 is worth funding.

## 1. Inventory — what's usable and what isn't

All 74 committed `benchmark/results/*.jsonl` files were inspected (full per-file table in stdout /
the JSON `inventory` key). **36 files contribute ≥1 GPQA-Diamond record, 37 were inspected and
carry zero GPQA rows (other benchmarks — SuperGPQA-hard, LEXam, MMLU-Pro, MedQA, GSM8K, MATH-500,
AIME), and 1 was excluded outright:**

- `lever_gate_replay.jsonl` — excluded. Different schema (`was_unanimous_correct` /
  `gate_doubt` / `gate_cost_usd` / `escalated_after_gate`), a gate-decision analysis artifact, not
  a config × item correctness observation, and carries no `item`/`choices` to key on. Same
  exclusion `analyze_family_floor.py` (F1/F2/F5) already applied to this file.

3,303 GPQA-Diamond records were normalized across 6 row schemas (baseline-wrapped, engine-wrapped
lever files, combo baseline+engine[+self_consistency5], flat `qwen38_baseline`, flat `moo` with a
`gpqa_hard`-bucket filter, and the excluded gate-replay schema). Two schema-specific coverage
gaps, disclosed rather than papered over:

- **`qwen38_baseline_seed123.jsonl` (78 rows) carries no `choices` list.** Correctness is fully
  resolvable (`answer_letter` and `correct_letter` are both present on every row), but the chosen
  **text** is not recoverable for this config, so it cannot participate in the text-keyed
  plurality vote or pairwise-discordance tables below — it still counts fully toward the union,
  floor, and contingency numbers, which only need correct/incorrect.
- **`moo_m1_eval.jsonl` (827 rows total) is 4 blended-workload buckets; only the 205 rows in its
  `gpqa_hard` bucket are GPQA-Diamond** (native Record IDs, same `load_gpqa` pool — already
  verified by direct ID-overlap in `family_floor_analysis.md`). The other 622 rows
  (`supergpqa_hard`/`medqa`/`saturated_easy_mmlu`) are different benchmarks and skipped.

## 2. Pre-registered rules (stated before any result below)

**2.1 — Correctness and text-join methodology (roadmap §1.5, item 2 — the load-bearing
requirement for this whole analysis).** `load_gpqa._shuffle_choices` reshuffles the four options
per seed, so the letter "C" in one run is not the same answer as "C" in another run. Enforced
everywhere below:

- Per-row correctness is resolved as `chosen_letter == that row's own correct_letter` — never
  trusted from a different row, never compared as a bare letter across rows. **QA check, not an
  assumption:** recomputing this from raw fields matched the logged `correct` boolean on all 3,303
  rows carrying both a chosen letter and a logged flag (0 mismatches) — see stdout section "QA —
  letter-based correctness recompute."
- Per-row "which answer did this config pick" is resolved by mapping the chosen letter to its
  choice **text** via that row's own `choices` list (whitespace-stripped — see 2.1a below).
- Union/floor/contingency crediting needs only the per-row correct/incorrect boolean above, which
  is already letter-shuffle-safe by construction — no additional text join is needed there.
  Cross-config **agreement** questions (the plurality vote, pairwise discordance) DO require the
  text join, because they compare *what different configs actually answered*, and that
  comparison is done on text, never letter, exactly per §1.5.
- **QA check:** the canonical correct-answer TEXT for a given `question_id` should be identical
  across every row that ever logged it (same physical correct answer, different letter position
  per shuffle). Checked on all 197 GPQA question_ids ever logged in this repo: **0 conflicts**
  after the whitespace fix below.

**2.1a — one real bug found and fixed during QA, disclosed rather than silently patched.** The
first version of the text-join compared raw `choices[idx]` strings without stripping whitespace.
12 of the 197 GPQA question_ids then showed a spurious "correct-text conflict" — inspection showed
every one differed only by trailing whitespace/newlines in the source JSONL (e.g. `"...field."` vs
`"...field.  "`), never in content. Fixed by stripping the extracted text before any comparison
(`letter_to_text` in the script). This mattered for real: the naive plurality-vote accuracy moved
from 82.2% to 88.9% and mean pairwise discordance from 18.8% to 16.9% once whitespace-only
"disagreements" stopped being miscounted as real ones. All numbers in this report are **post-fix**.

**2.2 — Repeat-selection rule for de-inflation (the de-inflation itself, stated before computing
it).** When the same (config, question_id) pair has more than one logged observation (a seed
repeat), the OLD rule credited the config correct if it was **ever** correct across those repeats.
The DE-INFLATED rule used everywhere below instead takes **the lowest seed's observation only** —
a single fixed sample, no "ever correct" crediting. Concretely: rows with an explicit numeric
`seed` field sort first (ascending, lowest wins); rows with no explicit `seed` field (six
pre-seed-tagging legacy files — `adhoc_check`, `full_run`, `full_run2`, `smoke`, `smoke2`,
`smoke3` — plus `moo_m1_eval.jsonl`, which never carried one) fall back to a seed parsed from
their **own filename** via `seed(\d+)` if present (this recovers seed=123 for
`qwen38_baseline_seed123.jsonl`, which has the number in its filename but not in its rows), else
are treated as truly unknown and sorted **after** every numbered seed, tie-broken by filename.
This means a numbered-seed observation is always preferred over an unnumbered one for the same
(config, item); it is disclosed, deterministic, and reproducible, not a second "ever correct" in
disguise.

**2.3 — Item-coverage threshold.** Per the D2 spec verbatim: items covered by **≥3 distinct
configs** ("distinct" by label — `control` vs `thinking_gate` vs `moo:flagship_panel` count as 3
even where their seeds overlap). 180 of 197 GPQA question_ids ever logged (91.4%) clear this bar
— see §5.

**2.4 — Decision rule (fund D4 or not), fixed before any number below was computed.** The
council lever (D4) is worth funding only if, after de-inflation:

- **(a)** the rate of items solved-by-**some**-but-not-**all** configs is **≥ 5 per 90** D2-subset
  items, AND
- **(b)** mean pairwise discordance across qualifying config pairs (≥10 shared, text-comparable
  items) is **≥ 10%** — reusing the roadmap's own kill threshold for this exact lever family
  (D4's stated kill: "disagreement < 10% — the configs have homogenized"), applied here as the
  **pass** bar for condition (b), not the kill bar.

If either condition fails, the verdict is **do not fund** — the union has collapsed toward the
best single config and that is a valid, valuable free kill (it saves the ~5.0M-token D4 run).

## 3. Headline: inflated vs de-inflated union, side by side

On the **180** GPQA items covered by ≥3 distinct configs:

| | INFLATED (ever-correct across repeats — the old number) | DE-INFLATED (lowest-seed-only, the de-inflated number) |
|---|---:|---:|
| Union correct | 176/180 = **97.8%** | 176/180 = **97.8%** |
| Floor (wrong under every config) | 4/180 = **2.2%** | 4/180 = **2.2%** |

**The de-inflation produces zero movement in the item-level union or floor number.** This was
checked, not assumed: of the 2,225 distinct (config, question_id) groups, 831 have more than one
logged observation (a seed repeat); of *those*, de-inflation flips the credited correctness
(inflated "ever correct" → de-inflated lowest-seed "wrong") on **43 groups (5.2% of repeat
groups)** — real, measurable resampling luck at the config level. But **41 of those 43 flips land
on items covered by 13–22 other configs**, so the item retains another, unaffected correct
observation and the item-level union survives unchanged; the remaining 2 flips land on items with
fewer than 3 covering configs (outside the D2 subset entirely). Mechanically: **union correctness
requires only one surviving correct config per item, and GPQA's logged coverage is deep enough
(median ~11–12 distinct configs per D2 item) that losing one config's lucky credit essentially
never removes an item's only correct observation.** This is the honest finding, not a rounding
artifact — see `council_union_gate_items.csv` for every one of the 43 flip groups traced to its
item's full covering-config list.

**Reading this correctly:** the roadmap's "inflation" concern predicted the *union number itself*
would shrink under de-inflation. On this dataset, at this coverage depth, it doesn't. The
resampling-luck effect is real (5.2% of repeat groups) but structurally too small and too diffuse
across configs to move the headline 97.8%/2.2% figures. **The original "~7pt union headroom" claim
survives the de-inflation test as measured, but for a different reason than assumed** — not
because resampling luck was absent, but because item-level coverage redundancy absorbs it. This
reframes, but does not kill, F1(a)'s headline number.

Ceiling (right under every config): 102/180 = 56.7%. **Partial — solved by SOME but not ALL
configs (de-inflated): 74/180 = 41.1%** — this is the pool the council lever would actually have
something to work with; the 56.7% ceiling items and 2.2% floor items are structurally irrelevant
to it (nothing to adjudicate when everyone agrees).

**Free bonus, no paid call:** a naive plurality-of-configs (majority text-vote among the
de-inflated single-seed picks of every config that covers an item, no judge) scores **160/180 =
88.9%** — *below* the union's 97.8% and only marginally above `baseline_3.7max`'s own 87.8% on
this exact item set. This is diagnostic, not discouraging: the naive vote equal-weights **every**
config ever logged, including weak ones (`self_consistency_5x` scores 59.6% on this same pool —
see §5), which dilutes the vote. This is **not** a preview of D4's mechanism — D4 specifies a
curated K=5 candidate set of comparable, genuinely-different-conditioning configs, not "every
config in the repo's history." The 88.9% naive number is a useful floor/strawman, not a forecast
of D4's outcome, and D4's own value proposition is precisely that a judge (or a curated vote) can
do better than an undiscriminating plurality — this result is a data point in favor of curation
mattering, consistent with Self-MoA's own finding that mixing in weak members hurts.

## 4. Contingency structure

Item count by (number of covering configs, number of those configs correct), de-inflated. Full
table in stdout / `contingency_table` in the JSON; example rows:

| n_covering | n_items | k-of-N breakdown |
|---:|---:|---|
| 3 | 17 | k=0:1, k=1:1, k=2:1, k=3:14 |
| 9 | 13 | k=1:1, k=4:1, k=7:1, k=8:1, k=9:9 |
| 12 | 23 | k=0:1, k=5:1, k=7:1, k=9:1, k=10:2, k=11:2, k=12:15 |
| 15 | 17 | k=1:1, k=5:1, k=6:2, k=7:1, k=12:1, k=13:2, k=15:9 |
| 22 | 13 | k=12:1, k=13:1, k=15:1, k=18:2, k=20:1, k=21:2, k=22:5 |

Coverage is ragged (3 to 23 distinct configs per item, see the coverage histogram in §5), so this
is reported in full in the CSV rather than forced into a single N; the floor/ceiling/partial
three-way split in §3 is the scale-invariant summary of the same data.

**Per-config accuracy on the D2 subset** (de-inflated, full table in
`council_union_gate_configs.csv`; "eligible" = ≥30 D2-subset items):

| Config | D2-subset n | D2-subset acc | Eligible for "best single"? |
|---|---:|---:|---|
| `qwen3.8_solo` | 78 | 93.6% | yes — **but D0-flagged survivorship-contaminated (78/90, 12 drops)** |
| `moo:thinking_gate` | 30 | 93.3% | yes |
| `chem_thinking_gate` | 152 | 92.1% | yes — the roadmap's own **validated**, uncontaminated best lever |
| `chem_flagship_gate` | 147 | 89.1% | yes |
| `flagship_panel` | 141 | 87.9% | yes |
| `baseline_3.7max` | 180 | 87.8% | yes |
| … | … | … | (17 more configs, `self_consistency_5x` lowest at 59.6%) |

**Union vs. every eligible single config, paired on that config's own D2-subset coverage**
(McNemar-style gain/loss; full table in the JSON `union_vs_each_eligible_config`):

| vs. config | own acc | n | union correct | config correct | net |
|---|---:|---:|---:|---:|---:|
| `qwen3.8_solo` | 93.6% | 78 | 77 | 73 | **+4** *(below the roadmap's own +5 D2 bar)* |
| `moo:thinking_gate` | 93.3% | 30 | 30 | 28 | +2 |
| `chem_thinking_gate` | 92.1% | 152 | 149 | 140 | **+9** *(clears the roadmap's +5 D2 bar)* |
| `chem_flagship_gate` | 89.1% | 147 | 144 | 131 | +13 |
| `baseline_3.7max` | 87.8% | 180 | 176 | 158 | +18 |
| `self_consistency_5x` | 59.6% | 94 | 92 | 56 | +36 |

**Methodological caveat that must be stated plainly:** the "loss" column is **0 for every
single config, by construction** — since the union is defined as "any covering config correct,"
a config being correct on an item logically guarantees the union is credited correct on that item
too. So `net = union_correct − config_correct` always, and this whole table is a **one-sided
ceiling**, not a genuine two-arm paired test: it is the maximum a hypothetically **perfect**
judge could gain over that config by always picking the right teammate when they disagree. It
says nothing about whether a *real* judge captures any of that ceiling without introducing new
losses of its own (second-guessing a config that happened to be right). That is precisely what
the paid D4 screen exists to measure — this script prices the ceiling, not the achievable gain.

**Auto-selected "best single config" is `qwen3.8_solo` (93.6%), and it is the exact config the
roadmap's own D0 flags as survivorship-contaminated** (78/90 attempted, 12 timeout/429 drops,
disproportionately biasing toward easier survivors — the identical contamination pattern F2 used
to disqualify `qwen38_panel`'s 87.3%). Against it, the union's ceiling is **+4, one item short of
the roadmap's own +5 D2 bar**. Against the next-best **validated, uncontaminated** lever,
`chem_thinking_gate` (92.1%, n=152, no drop contamination), the ceiling is **+9**, comfortably
clearing +5. Read together: **the roadmap's own D2 bar is sensitive to which "best single config"
you compare against, and the config that currently wins that comparison is the one already
flagged elsewhere in this roadmap as unreliable.** Against every clean, validated comparator the
ceiling clears the bar; against the contaminated one it narrowly doesn't.

## 5. Selection-bias control

**Coverage framing (the informative check for this dataset):** 180 of the 197 distinct GPQA
question_ids ever logged in this repo (**91.4%**) clear the ≥3-config D2 threshold; only 17 items
(8.6%) are excluded for thin coverage. **The D2 subset is nearly the whole logged GPQA corpus, not
a cherry-picked easy or hard slice** — there is very little room for the coverage criterion itself
to have selected for difficulty in either direction.

**`baseline_3.7max` accuracy, full pool vs D2 subset:** n=180 / 87.8% both ways, delta = **+0.0pp
— degenerate by construction**, not evidence of "no bias." `baseline_3.7max` is logged in nearly
every experiment file in this repo (it is the standard comparator), so its own 180-item footprint
turns out to be a **perfect subset** of the D2 pool — every item it was ever run on also reaches
≥3 total configs. This specific comparison has no statistical power to detect a selection effect
here; the coverage framing above is what actually answers the question. Cross-check against a
previously-published, independently-computed number: `family_floor_analysis.md`'s F2 table reports
`baseline_3.7max`: 86.7% pooled marginal accuracy at n=451 (that number counts every row
including un-deduplicated seed repeats, a different denominator by design). This script's 87.8% at
n=180 (de-duplicated, one observation per item) is 1.1pp higher and derived independently — close
enough to be a mild reassurance, not a formal equivalence test.

## 6. Pairwise discordance — the cross-config complementarity a council would exploit

Computed over each pair's full joint coverage (de-inflated single pick per config per item, not
restricted to the D2 subset — more statistical power; full 253-pair table in
`council_union_gate_pairs.csv`, pairs with <10 shared text-comparable items excluded from this
headline). **Mean discordance across 253 qualifying pairs: 16.9%.**

Top of the table is dominated by `self_consistency_5x` (the weakest config, 59.6% accuracy) — it
disagrees with everything else at 27–45%, which is expected for a config that's simply worse, not
necessarily "complementary" in a useful sense. **Robustness check: excluding every pair involving
`self_consistency_5x` leaves 231 qualifying pairs, mean discordance 15.1% (median 14.3%, range
0–38.5%)** — the signal is not a one-config artifact; it survives with the weakest, most obviously
different config removed.

## 7. Verdict

Applying the pre-registered rule from §2.4:

- **(a) Partial-solved rate:** 74/180 = **37.0 per 90** D2-subset items, vs the ≥5/90 bar →
  **PASS** (7.4× the bar).
- **(b) Mean pairwise discordance:** **16.9%** (qualifying pairs), vs the ≥10% bar → **PASS**
  (robust to dropping the weakest config: 15.1%, still passes).

**VERDICT: FUND the D4 council screen.**

Both conditions clear with real margin, not narrowly. This is a genuine pass, not a coin flip —
even applying the roadmap's own, stricter D2 bar (net ≥ +5 discordant vs. the best single config)
passes against every validated, uncontaminated comparator (`chem_thinking_gate`: +9;
`baseline_3.7max`: +18), and only narrowly misses (+4) against the one comparator (`qwen3.8_solo`)
this roadmap itself has separately flagged as unreliable.

## 8. Decision consequences

**What the de-inflated number means for the roadmap's "7pt of discarded answers" claim.** The
inflation concern predicted the item-level union number would shrink once "ever correct across
repeats" credit was replaced with a single, pre-registered lowest-seed observation. It does not
shrink — 97.8% union / 2.2% floor is identical before and after de-inflation on this dataset,
because GPQA's logged coverage is deep enough (91.4% of all logged items reach ≥3 configs, median
coverage ~11-12 configs/item) that any one config's resampling luck is absorbed by redundant
coverage from other configs. **The "~7pt union headroom" is not seed luck on this measurement —
it survives a direct, adversarial de-inflation test.** That is a stronger result for D4 than the
roadmap's own §2.3 anticipated, not a weaker one.

**What does NOT survive unscathed: the specific "+5 vs best single config" framing.** The
auto-selected best single config (`qwen3.8_solo`, 93.6%) is the same config D0 already flags as
survivorship-contaminated. Against it the ceiling gain is +4, one item short of the roadmap's
literal D2 bar. Funding D4 without first landing D0's repair (already funded, Rung 1, ~0.05M
tokens, "already-built") risks measuring D4's actual screen against a moving, currently-inflated
target. **Recommendation: run D0 before or alongside D4's screen**, not instead of it — D0 is
already funded and cheap, and it directly disambiguates which of the two "best single config"
numbers (+4 contaminated vs +9 validated) D4 should be judged against.

**What this buys, concretely.** D4's own pre-registered bar (§2.4, Rung 2) is: net ≥ +5 discordant
vs. a **compute-matched control**, AND hidden-vote judge beats shown-vote judge, AND judge
diverges from raw hidden majority on ≥10% of items with those overrides net-positive, AND
cross-config disagreement ≥10% (this script's own §6 finding, 16.9%/15.1%, already clears that
specific sub-bar for free). This script prices the **selection-side ceiling** (§4's one-sided
+4-to-+36 table) and the **complementarity precondition** (§6's discordance) that D4's full paid
run needs in order to have anything to select between. It does not, and cannot, measure whether a
real judge — anchored, de-anchored, hidden-vote, or shown-vote — actually captures any of that
ceiling without also introducing new losses; that is exactly what the ~5.0M-token single-seed
screen is for. The verdict here is: **the free precondition is satisfied with margin, proceed to
the paid screen** — this is not a claim that D4 will pass its own harder, judge-quality bar.
