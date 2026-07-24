# MagiAchiral improvement loop — persistent state

Started 2026-07-21. This doc is the loop's memory: every iteration reads it,
acts on the top of the backlog, records what happened, and re-ranks. It is
committed after every iteration so the loop survives session loss.

---

## LOOP RESTARTED — 2026-07-22 evening, NO stop time (supersedes the wrap-up below)

Jun Kai restarted the loop with no scheduled stop. Objective: beat
benchmarks in all aspects with EMPHASIS ON REASONING — topping top
models. Two standing workstreams:
1. **Levers** (reasoning emphasis): seed-123 SuperGPQA flagship_panel
   pair RUNNING (completes the 3-seed bar for the top validated-queue
   item). Next reasoning levers queued: qwen3.8-tier solver panel on
   hard STEM (its solo GPQA read was 93.6% vs 3.7-max's 85.6 — a panel
   of them is the strongest untested reasoning lever), deliberation-depth
   variants, panel-diversity variants.
2. **Recursive RAG** (docs/recursive-rag-plan.md): plan COMPLETE with
   verified Appendix A (hybrid+rerank v1 confirmed by evidence; Discovery
   shape verified genuinely novel vs DRAG/ACL-2025; no contamination
   standard exists — our firewall is a contribution). **G0 BUILT**
   (907d4f9): rag package, FTS5+dense+RRF, search_corpus MCP tool, 83
   tests green, ~200ms/query. Full 200k-article index building in
   background (resumable: benchmark/build_rag_index.py --max-articles
   200000 --db-path benchmark/data/rag_index.sqlite3; log
   benchmark/results/rag_full_build.log). Next: G1 = wire search_corpus
   into the Verifier tool rack behind a flag + R1 pre-solve pilot on
   SuperGPQA-hard (Bet 1 threshold: ≥+4 vs cheap-panel 67.9 on same
   items).

## WIND-DOWN WRAP-UP — 2026-07-22 window (read this first)

Two unsupervised windows (overnight + a daytime extension) ran the loop
autonomously. What it produced, ranked by what Jun Kai should act on.

### Validated wins (met the 3-seed bar)
1. **chem_thinking_gate — 90.9% mean (seeds 314/217/471, 0.2pt spread),
   +4.4 over the matched flagship baseline.** The best configuration this
   project has produced; stacks the two prior validated levers
   (thinking_gate + chem_flagship). Strictly dominates both parents. This
   is the config the post-judging engine upgrade should adopt if any is.
   [benchmark/results/lever_findings.md]
2. **Agent hardening — graded coverage 36%→86%** on the same Terminal-Bench
   sample (timeouts-as-observations, one API retry, bigger token budget).
   Two former infrastructure casualties now solve outright.

### The central intellectual result: WHEN deliberation helps
Five non-GPQA benchmarks pinned down the predictor. It is NOT baseline
height — it is the **cheap-tier-to-flagship gap, measured by the
unanimous-wrong rate**:

| Benchmark | Domain | Flagship base | Unan-wrong | Engine vs base | Right MoO route |
|---|---|---|---|---|---|
| GPQA-Diamond | phys/chem | 84-86% | ~11% | −5.5 (closes most) | thinking_gate / stem-max |
| MedQA | medicine | 94% | **4%** | +2 (**tie**) | single-call / standard |
| LEXam | law | 86% | elevated | −14 | single-call |
| MMLU-Pro | broad | 94% | ~14% | −12 | single-call |
| SuperGPQA-hard | hard STEM | 79% | **23%** | −11.6 → **+3.8** w/ flagship panel | flagship_panel |
| MATH-500 / GSM8K | math | 100% | ~6% | −4 to −6 (saturated) | single-call |

Low unanimous-wrong (cheap tier competent, e.g. medicine) → deliberation
ties the flagship cheaply. High unanimous-wrong (out of depth, e.g. hard
STEM) → route the panel to the flagship tier, which **flips −11.6 into
+3.8** (flagship_panel generalizes chem_flagship_gate from one subject to
a whole benchmark — the general-use proof the MoO thesis needed).

### Design delivered
- **docs/mixture-of-orchestrations-plan.md** — full MoO architecture
  (router + declarative profile registry + 3-memory system + benchmark-
  mode memory firewall), every choice cited to a measured finding, with
  an adversarially-verified OSS memory/attention appendix (3 adopt-now
  hosted-API moves; self-hosting bucket honestly marked unresearched).
- **docs/agentic-rebuild-scoping.md** — what Terminal-Bench/SWE-Bench
  would take.
- Benchmark infra now spans 8 datasets (GPQA, LEXam, MMLU-Pro, SuperGPQA,
  MedQA, GSM8K, MATH-500, Terminal-Bench), every lever runnable on each.

### Top recommended next actions (ranked, for Jun Kai)
1. **flagship_panel on SuperGPQA-hard: now 2-seed replicated (+3.8, +2.4,
   mean +3.1) — run ONE more fresh seed to complete the 3-seed bar** and
   promote it to a validated MoO domain profile. Strong, replicated
   positive already; one run away from the full bar.
2. **Build the MoO M0 refactor** — levers → declarative profiles + the
   benchmark-mode memory firewall assertion. Unblocks everything else.
3. **Open-answer math grading path** (SymPy numeric-equivalence) — the
   real `math-verified` prerequisite; distractor-MC saturated and can't
   test math deliberation.
4. **Additive site Build Log entries** for the validated results (queued,
   additive-only, safe before Aug 11 judging).
5. Terminal-Bench Phase 2 (best-of-N filtered by the task verifier),
   sized against the established 37.5% hardened baseline.

### Nothing shipped to the submission
Every result above is research in the repo. The frozen n=90 submission,
its numbers, and the live site are untouched, per the additive-only
constraint through Aug 11 judging.

---

## Objective (broadened by Jun Kai, 2026-07-22 14:53)

General-use excellence, NOT just GPQA: coding, auditing, research, data
analytics, chemistry, math, biology. Keep testing all relevant benchmarks
and developing levers per docs/mixture-of-orchestrations-plan.md. Each
domain needs (a) a reachable benchmark with a pilot, (b) a diagnosis of
where the flat engine loses, (c) a domain orchestration profile that
closes it, validated at 3 seeds. The MoO plan is the frame; per-domain
levers are the work.

### Domain-coverage backlog (the broadened objective, ranked by reachability)
1. **Math** — GSM8K + MATH-500 loaders+runners BUILT and committed
   (c6ae818). Both use distractor-synthesis into A-D (documented
   non-comparable to published open-answer scores). CAVEAT to weight when
   reading pilot numbers: domain-agnostic numeric distractors can be
   trivially eliminable (a mod-11 remainder can't be 90), so
   distractor-MC math may read EASIER than the real open-answer task —
   these pilots test the ENGINE's relative behavior, not absolute math
   ability. MATH-500 excludes 27% of answers (non-numeric) as unsafe to
   synthesize. Pilots queued behind SuperGPQA. `math-verified` profile
   (add SymPy verifier tool) is the lever if the flat engine loses here.
2. **Science (broad)** — SuperGPQA hard (pilot RUNNING), MMLU-Pro STEM slice.
3. **Chemistry** — DONE: chem_thinking_gate validated 90.9%. The template
   for every other domain profile.
4. **Coding** — Terminal-Bench (baseline 37.5% established) → best-of-N
   Phase 2; MBPP/HumanEval as single-turn checkable-code pilots.
5. **Biology/Medicine** — MedQA (clean 4-option): loader+runner BUILT and
   committed (85c01b5), verified live (native 4-option, zero-warning full
   split). Pilot queued behind SuperGPQA per Token-Plan serialization.
6. **Data analytics** — needs a benchmark scout (DS-1000? tabular-QA?).
7. **Auditing/security** — SEC-bench/ExploitBench are agentic (scoping
   doc covers the rebuild); a text-only security-MCQ pilot is the
   reachable near-term proxy.
8. **Research/reasoning-general** — the blended-workload router eval (MoO M1).

## Hard stop: 2026-07-22 17:30 SGT (reset from 07:15; broadened-objective window)

Original overnight window (07:15) was extended live. Now 17:30 SGT.
Wind-down: no new long runs after ~17:00; final wrap-up at the top of this
doc by 17:30.

## Hard stop (superseded — kept for audit): 2026-07-22 07:15 SGT

Set by Jun Kai at 01:16 SGT. Wind-down protocol: no new long-running
launches after ~06:30; final iteration writes a wrap-up section at the top
of this doc (what was validated, what's still running/queued, recommended
next actions) by 07:15, commits and pushes it, then stops the wakeup loop.

**Autonomy grant for the window:** anything that would normally pause for
approval → review the options, take the most-recommended approach, and log
the decision + reasoning in the iteration log below. Exception: genuinely
novel external actions (PRs to third-party repos, leaderboard submissions,
anything published beyond this repo and additive magiachiral.com sections)
are prepared and queued here for post-window review, not executed.

## Standing constraints (set by Jun Kai, 2026-07-21)

- **Budget:** no fixed cap; scale each experiment to its question; flag any
  single run projected over ~$30 before launching it.
- **Ship rights:** research + *additive* site updates only (new Build Log
  entries, new research sections). The shipped engine defaults, the frozen
  n=90 numbers, and existing site claims stay untouched until Devpost
  judging ends (Aug 11, 2026).
- **Worker routing:** Fable orchestrates/judges/synthesizes; Sonnet workers
  execute (code, runs, analysis drafts); Opus only for judgment-heavy
  verdicts or security-adjacent work. Per fable-sonnet-orchestrator.
- **Honesty bar (non-negotiable, learned this session):** every run gets a
  drop-bias check before its number is reported; single-seed results are
  "promising", not "settled" — the bar is 3 independent seeds; negative
  results get written up and committed with the same care as wins.

## Benchmark reality (verified 2026-07-21, deep-research with adversarial verification)

**Reachable now (single-turn QA):** GPQA-Diamond (primary), LEXam, MMLU-Pro,
SuperGPQA, MedQA (needs load smoke-test), Minority-Sentinel six-pack.
**Reachable via QuorumQAAgent (agent loop, built this session):**
Terminal-Bench 2.1 (89 tasks, Harbor). Next: SWE-Bench Pro (public, ~23% SOTA).
**Real but blocked:** FrontierCode (Cognition won't release tasks), GDPval-AA
(AA-hosted), OSWorld-Verified (needs GUI control — different again from
terminal), HealthBench Professional (rubric-graded, needs different judging),
HLE (compatibility disputed 0-3 in verification — re-check queued below).
**Not verifiable as real (re-check occasionally, don't chase):** GDP.pdf,
Blueprint-Bench2, AutomationBench*, Legal Agent Benchmark*, BioMysteryBench,
Agents' Last Exam, "Multi-Agent" variants of BrowseComp/SEC-Bench/T-Bench.
(*likely = Zapier AutomationBench / Harvey LAB, both agentic; re-verify if
targeted.)

## Key empirical findings the backlog builds on

1. **chem_flagship_gate: 89.8% overall / 90.0% chemistry at seed 555** — best
   single-seed GPQA result. Subject-routed flagship panel fixes the
   qwen3.6-flash chemistry blind spot that more thinking time couldn't.
   1 seed; needs 2 more.
2. **qwen3.8-max-preview scores 93.6% solo** (n=78/90, 12 API-timeout drops
   disclosed) — far above qwen3.7-max's 85.6% at the same seed. It is NOT
   usable as a solver panel (Token Plan endpoint, quota-limited, slow) but
   as the *Judge only* (called on ~40% of questions, 1 call each) it's
   plausibly the single biggest untested lever.
3. **Escalation value needs flagship headroom.** LEXam (-14pts) and MMLU-Pro
   (-12pts) both show: when the flagship baseline is near-ceiling (86-94%),
   unanimous-wrong dominates and the engine loses. QuorumQA's niche is
   question sets hard enough that the flagship itself errs (GPQA: 84-86%).
   Pilot-first, and prefer hardest-subset sampling on any new benchmark.
4. **Terminal-Bench single-agent baseline: 6/11 solved (54.5%)** of tasks
   that complete; 3/14 blocked on two distinct timeout classes (slow builds
   >300s; model-API ReadTimeout on hard reasoning turns). 1 seed, n=15/89.
5. **Verifier tools are science-specific.** On LEXam, 7/9 escalations had
   zero verifier findings — the tribunal degrades to Skeptic+Judge outside
   STEM. Domain-appropriate verifier tools are an untested lever class.

## Backlog (ranked; loop takes from the top)

1. **[DONE iter-1] chem_flagship_gate seed-777 replication** — overall
   88.6% (n=88/90), replicating seed-555's 89.8%; both seeds clearly beat
   thinking_gate's 86.7%. Chemistry softer: 82.1%, honest drop-bias band
   76.7-83.3% (both drops were chem) vs seed-555's 90.0% — real effect,
   smaller per-subject size than one seed suggested. **Third seed (888)
   queued — deliberately NOT launched concurrently with the qwen38_judge
   pilot: both now draw on the same Token Plan 5-hour sliding quota (the
   client migrated wholesale to the Token Plan endpoint; cost_usd=0.0 by
   design there, tokens are the signal), and racing them risks quota
   exhaustion mid-run corrupting both via mass drops.** Decision logged
   per autonomy grant.
2. **[DONE iter-1: NEGATIVE, mechanistically informative] qwen38-judge
   lever** — no measurable gain (paired vs frozen run: fixed 1, broke 3,
   inside the ±2.5pt noise floor; headline 80.3% biased up by 14 chem-heavy
   ReadTimeout drops; even a perfect drop-retry caps at 83.3%, below
   baseline). The judge itself went 9/9 on overturns — proving judge
   quality was never the binding constraint; unanimous-wrong never reaches
   any judge. Confirms from a third angle: escalation COVERAGE is the
   ceiling, not tribunal quality. Full write-up in lever_findings.md.
   Decision (autonomy grant): deprioritized; drop-retry skipped as
   conclusion-robust; quota window given to chem_flagship_gate seed-888
   instead (now RUNNING, iter-2).
3. ~~HLE re-verification~~ **[DONE iter-1: BLOCKED, deprioritized]** — the
   0-3 refutation holds on stronger grounds: no choices column exists at all
   (MC options are free text inside the question, 5+ of them), official
   grading is LLM-judge semantic equivalence even for MC, and the dataset is
   gated with our HF account not granted. Decision (autonomy grant): drop
   HLE from the active backlog entirely rather than queue an access request
   — even with access, the structural findings mean it needs a semantic-
   grading path, a bigger change than any reachable benchmark requires.
   Queued for Jun Kai (informational, not blocking): accepting the HF terms
   on cais/hle would allow measuring the text-only∩MC joint count, the only
   thing that could reopen this. See benchmark/results/hle_feasibility.md.
4. **Terminal-Bench seed-2 sample (14 fresh tasks)** — validate the 54.5%
   baseline before Phase 2. Prerequisite DONE (iter-2): model-requestable
   per-command timeout_sec, clamped [10,1200], default 300 unchanged;
   TDD 29→35 tests, commit f1d8385, diff spot-checked by orchestrator.
   Ready to launch when the Token Plan quota window is clear of the chem
   seed-888 run (both share it).
5. **[BUILT iter-3, pilot queued] Stack test: chem_thinking_gate** — worker
   delivered clean (RED→GREEN, 35→41 tests, live smoke exercised all three
   routing paths: chem+gate pass, chem+gate→tribunal, non-chem split→
   tribunal). Commit ce048b4, pushed. Pilot at fresh seed 314 (999 lightly
   exposed by the smoke; 42/7/123/555/777/888 burned) queued behind the
   running T-Bench seed-7c job per the Token-Plan serialization rule —
   launches on its completion notification.
6. **Terminal-Bench Phase 2: best-of-N filtered by task verifier** — per
   agentic-rebuild-scoping.md Option A. Size N against measured pilot costs.
7. **SuperGPQA pilot (hardest-subset sample per finding #3)** — next
   text-QA benchmark, structurally GPQA's sibling.
8. **Legal verifier tool for LEXam retry** — statute-lookup MCP tool; tests
   whether tribunal value returns with domain-appropriate grounding.
9. **SWE-Bench Pro feasibility spike** — after Terminal-Bench Phase 2 shows
   the loop works.
10. **MedQA load smoke-test + pilot** — medical second-opinion story fits
    the site's pitch; pilot-first per finding #3.

## Validated results so far (the loop's scoreboard)

- **chem_thinking_gate (stack): 90.9% (seed 314) and 91.0% (seed 217)** —
  two fresh seeds, near-identical replication, both the best overall
  numbers of the whole project. Matched seed-314 flagship baseline: 86.5%
  (+4.4 margin). Chemistry 91.2%/90.0%, escalation 34-37%. Third fresh
  seed (471) running — completes the validation bar.
- **Agent hardening: VALIDATED by same-sample rerun** — graded coverage
  36%→86% on seed-7, exceptions 9→2, two former infrastructure casualties
  now solve outright.
- **REFINED THESIS (SuperGPQA-hard):** flagship headroom is necessary but
  NOT sufficient — the engine lost −11.6 even with 79% flagship headroom,
  because the cheap-tier-to-flagship GAP was too big (23% unanimous-wrong).
  The MoO router must estimate that gap, not just difficulty.
- **flagship_panel on SuperGPQA-hard: VALIDATED (3 seeds, +3.8/+2.4/+6.2, mean +4.1, never negative)** — third fully-validated lever, first beyond GPQA. Supersedes the 1-seed line below.
- **qwen38_panel (strongest solver tier) on hard STEM: NEGATIVE** — ties the single baseline, TRAILS flagship_panel (3.7), 30% timeout drops, 0% escalation (a too-strong homogeneous panel never disagrees → expensive self-consistency, tribunal idle). Top-tier confirmation of the panel-diversity principle: the lever is productive disagreement, not raw per-seat strength. flagship_panel (3.7) stays the hard-STEM profile.
- **flagship_panel domain-routing GENERALIZES (SuperGPQA-hard, 1 seed):**
  on 78 identical items, cheap-panel 67.9% → flagship-panel 83.3% (+3.8
  over the single flagship baseline, +15.4 over cheap). chem_flagship_gate's
  one-subject routing works across a whole broad-STEM benchmark. Needs
  3-seed bar to become a validated MoO profile.

- **chem_flagship_gate: VALIDATED at 3 seeds** (89.8/88.6/87.4, mean 88.6%)
  — beats the flagship baseline (~85.5%) and every prior configuration at
  every seed tested. The strongest configuration this project has produced.
- **qwen38_judge: validated NEGATIVE** — judge quality is not the binding
  constraint (9/9 overturns, zero net gain); escalation coverage is.
- **HLE: confirmed unreachable** without a semantic-grading rebuild.

## Iteration log

### Iteration 1 — 2026-07-21/22 overnight
- chem seed-777: done, replicates (88.6%). HLE: closed (blocked).
  qwen38_judge: built clean, pilot ran, negative result recorded.
### Iteration 2 — 2026-07-22 ~02:00-02:30
- chem seed-888: done, 87.4% — **3-seed validation bar met**, promoted to
  validated in lever_findings.md.
- Adaptive per-command timeout: built+committed (f1d8385), spot-checked.
- Terminal-Bench seed-7 sample (14 fresh tasks, verified zero overlap with
  the 15 already run): first launch failed instantly — Docker Desktop was
  not running (stopped since the earlier pilot). Restarted Docker Desktop,
  relaunched with an engine-readiness wait guard. Running.
- Next when quota/pilot allow: stack test (chem_flagship_gate +
  thinking_gate), SuperGPQA hardest-subset pilot.

### Iteration 3 (continued) — agent hardening landed
- All three T-Bench robustness fixes delivered TDD'd (41→47 tests, commit
  7bcdc7d, pushed): command timeouts are now observations the model reacts
  to (with a separate ERROR branch so non-timeout failures aren't
  mislabeled), model-API ReadTimeout/ConnectionError get one retry in the
  agent loop only (QA engine untouched), agent max_tokens 1024→4096.
  Worker read Harbor's own source to pin the real exception mechanism
  (asyncio.TimeoutError → RuntimeError in docker.py; backend-dependent,
  hence justified broad catch).
- **Queued behind the seed-314 stack pilot (quota rule): rerun the full
  seed-7 T-Bench sample with the hardened agent** — same 14 tasks, direct
  before/after on the exception rate (9 blocked pre-fix). No unbiased
  solve-rate claim from that rerun alone; a fresh seed follows if the
  hardening holds.

### Iteration 3 — 2026-07-22 ~09:06 (window extended by Jun Kai, live)
- **5 hours lost overnight, disclosed:** the seed-7 T-Bench launch died
  silently — Docker Desktop never finished starting, and the readiness
  guard's `docker info` polls HUNG instead of failing fast (each poll
  blocking on the half-started daemon), so the shell sat inside the wait
  loop producing zero output until the session itself died. Lesson
  applied: readiness checks now use `timeout 10 docker info`, and the
  relaunch only happened after Docker was verified up. The 07:15 hard
  stop passed during the outage; Jun Kai extended the window live at
  ~09:06 with "Continue the loop."
- Relaunched seed-7 T-Bench pilot (job dir confirmed created this time —
  the previous failure mode is checked for, not assumed away).
- Dispatched: chem_thinking_gate stack lever build (Sonnet worker, TDD).
  Fresh-seeds-only note included — all six prior seeds are burned for it.
- **Two more launch stumbles on the seed-7 pilot, both caught by verifying
  the job dir instead of trusting exit codes:** (1) `--task` is a
  run-ONE-task flag (last one wins) — only sam-cell-seg ran (reward 0.0,
  clean, counts as a valid seed-7 outcome); (2) `-i` include filters need
  the `terminal-bench/` org prefix. Third launch (phase1-pilot-seed7c,
  13 remaining tasks) verified live with 4 concurrent task dirs.

## RAG index throughput constraint + decision (2026-07-22 ~19:50)

The from-scratch G0 build embeds on CPU at ~1.6 articles/s (~800 kept
after 26 min) — 200k articles would take ~100h, impractical. **DECISION
(autonomy grant):** G0.5 switches to a PRE-EMBEDDED English-Wikipedia
corpus from HuggingFace (embeddings already computed — skips the CPU
bottleneck, gives full coverage) instead of grinding the from-scratch
build. The current build keeps running as a small-index fallback for
early G1 smoke, but the R1 accuracy pilot should WAIT for the
pre-embedded corpus, because a small index that misses relevant passages
would make RAG look worse than it is and confound the pre-registered
Bet-1 test. G0.5 task (Sonnet worker): evaluate a current pre-embedded
EN-Wikipedia HF dataset (license-checked, e.g. a Cohere/Wikipedia-
embeddings-class set), load into the same RagIndex/RRF store, verify
search_corpus returns sensible STEM hits. Then G1 (verifier wiring) → R1
pilot.

## G0.5 COMPLETE + verified (2026-07-22 ~23:00)

Pre-embedded corpus fix landed and works. Index at 115k+ passages
(building toward the source's 518k), license-clean (CC-BY-SA-3.0,
mxbai-embed-large-v1 1024-dim, Apache-2.0 local encoder). Retrieval
verified against 5 STEM probes — all return on-topic hits with the
correctly-matched query encoder (activation energy→Activation
energy/Arrhenius; CRISPR→CRISPR/Cas9; thermodynamics→Thermodynamics/
Temperature; etc.). search_corpus is production-usable.

**NEXT (G1 → R1, dispatch to Sonnet worker):**
- G1: wire search_corpus into the Verifier tool rack behind a `--rag`
  flag (verifier.py EXTRACT_SYSTEM allowlist gains search_corpus; a new
  R1-style pre-solve retrieval option feeds top-k passages to solvers as
  context). TDD, no full pilot.
- R1 pilot: cheap-panel + pre-solve RAG on SuperGPQA-hard seed 42,
  apples-to-apples vs the cheap-panel baseline (67.9 on same items).
  Pre-registered Bet-1 threshold: ≥ +4 to keep building. GPQA null
  control (expect ~0, contamination tripwire). Benchmark-mode: index is
  general Wikipedia, not benchmark-derived — firewall satisfied, but
  label results RAG-ON and cite the snapshot ID.

## R1 BET-1 MET (2026-07-23 ~00:30) — retrieval is the third fix, domain-gated

cheap-panel + pre-solve RAG on SuperGPQA-hard: **+4.7 (s42) / +6.9 (s7)**, 2-seed replicated, over the
cheap panel (72.1 vs 67.4), clears the pre-registered +4, ZERO drops, and
cut the unanimous-wrong floor 20→14 (the designed mechanism). GPQA
tripwire PASSED: −4.7 (negative = no contamination) and proves retrieval
must be router-gated (hurts on search-proof GPQA). RAG = a domain-gated
lever like flagship_panel: help where the gap is retrievable knowledge,
skip where search-proof. Cheaper than tier-swap.

**RAG results:** R1 `rag_presolve` = **validated-with-variance** (4 seeds:
+4.7/+6.9/+8.0/−5.6, mean +3.5; the negative seed's mechanism is
diagnostic — retrieved passages misled the panel into false consensus on
10 questions). Stack finding (seed 271): thinking seat + gate RESIST
evidence-misled consensus (floor 22→9, strongest cut measured) but
tribunal broke even. Evidence-relevance gating TESTED (offline, 350 questions): score-gating
CANNOT fix it — regression/helped/neutral top-scores are statistically
identical (0.0288/0.0290/0.0286), because the RRF score is retrieval
CONFIDENCE not correctness-for-this-question; the failure is
high-scoring-but-wrong passages. rag_gated_presolve kept as documented-
ineffective. **rag_thinking_gate VALIDATED (3 seeds: +0.0/+4.6/+4.5 vs control, never
negative, floor cut to 5-9 every time) as the ROBUST retrieval profile —
fixes raw rag_presolve's -5.6 tail by reasoning about evidence. 5th
validated profile. ~1.5x escalation cost. Router prefers it over raw R1
where budget allows.** R2 disputed-step recursion (G2) = Bet-2
NOT met: −1.2 vs R1, no gain, because R2 fires only on escalation and so
structurally cannot touch the unanimous-wrong floor where the accuracy
lives (see rag_r2_findings.md). Reinforces: binding constraint is upstream
solver knowledge, not the tribunal. **NEXT:** G3 LEXam retry (running) —
the DIFFERENT test where R2 revives a dead verifier rather than augmenting
a strong one; then R1 third seed (123) to complete the rag_presolve bar.
Reasoning track continues (flagship_panel on MMLU-Pro STEM; deliberation
variants).

## Process-inspection correction (2026-07-23 ~12:30, important for loop ops)

Two python.exe processes with IDENTICAL command lines and IDENTICAL
creation times are a PARENT-CHILD LAUNCHER CHAIN (system python spawning
the .venv python), i.e. ONE run — NOT duplicate runs racing on the same
output. The earlier "duplicate rag_recursive pilot" diagnosis was wrong
on this point (killing the "duplicate" parent cascaded and terminated the
single legitimate pilot; harmless then since it had produced no output
and was re-run, but the lesson stands). Rule for future iterations:
before killing an apparent duplicate, check creation times — same-second
creation + identical cmdline = one process tree; only genuinely
different creation times indicate a real second launch.

## MoO M0 DONE (2026-07-23 ~21:00) — router unblocked

profiles.py: OrchestrationProfile registry (7 validated profiles:
standard-tribunal, thinking_gate, stem-max, flagship_panel, rag_presolve,
rag_thinking_gate, single-call), one run_profile() engine path, benchmark-
mode memory firewall assertion (unconditional, tested to fire before the
not-built stub). Equivalence proven offline: each profile's run_profile
dispatch produces an identical MULTISET of full call fingerprints
(role/model/thinking/temp/system/user) vs its source lever — byte-identical
behavior, no paid pilot needed. 213 tests. Commit 4fa3b27.
Follow-ups the worker flagged (non-blocking): profiles.py imports helpers
from benchmark/lever_experiments.py (backwards dep, future cleanup);
single-call uses a synthetic SolverAnswer placeholder; tribunal on/off +
gate-model-swap declared-but-unwired (no validated profile needs them).

## NEXT: MoO M1 — the router (where the thesis is tested)
Dispatch: build the R1 router (heuristic/classifier: domain + gap
estimate + checkability -> profile) over the registry, plus the blended-
workload eval (GPQA-hard + SuperGPQA-hard + a saturated-easy slice)
reporting flat-best / routed / oracle. MoO earns its existence here: if
routed >> flat-best toward oracle, the mixture is worth its complexity; if
not, say so. Also queued: flagship_panel on MMLU-Pro STEM (generalization);
additive site Build Log entries for the validated RAG results.

## MoO M1 ROUTER EVAL — honest verdict (2026-07-24 ~00:30)

The make-or-break test. R1 heuristic router (balanced) on a 120-q blend:
flat-best (flagship_panel) 92.8% vs ROUTED 90.1% vs oracle 96.4% — **the
router as shipped LOSES (−2.7pts AND costlier), does not justify its
complexity.** Reported straight. BUT the per-bucket breakdown is diagnostic
and fixable:
- Easy/competent (medqa, saturated): router TIES flagship accuracy at
  1/4-1/2 cost — routing works where tiers separate.
- Hard STEM: router routed to rag_thinking_gate/stem-max which were WORSE
  AND COSTLIER than flagship_panel. Wrong assumption killed by the eval:
  flagship_panel rarely escalates (~8-12%) so it's CHEAPER than the
  escalation-heavy (55-69%) retrieval/thinking stacks; cost is dominated by
  escalation rate not solver tier -> must be MEASURED per-profile-per-domain
  (calibration memory §5.1), not assumed.
- Corrected router (flagship for hard STEM, cheap for easy) ties flat-best
  accuracy at lower cost -> the defensible MoO claim is a COST win at equal
  accuracy, NOT an accuracy win.

## NEXT (ranked)
1. **Corrected router + measured cost model**: fix the hard-STEM rule to
   flagship_panel, drive routing off measured per-profile-per-domain
   escalation/cost, re-run the blend, report cost-at-equal-accuracy (the
   metric MoO wins on). Dispatch to a Sonnet worker.
2. Calibration memory (§5.1) — the per-domain outcome+cost store the
   corrected router needs; also the substrate for the R2 per-question
   router that could capture the 3.6pt oracle gap.
3. Additive site Build Log entries for the validated results (RAG,
   rag_thinking_gate, the honest M1 verdict) — additive-only, pre-Aug-11.

## MoO M1 CORRECTED router (2026-07-24 ~01:00) — the honest MoO verdict

Corrected router (flagship for hard STEM, cost-aware tie-break from a
measured calibration table built offline from moo_m1_eval.jsonl — zero new
paid calls). Independently re-verified (91.0% @ 6208 tok/q, n=111):

| | Accuracy | Cost tok/q |
|---|---|---|
| flat-best (flagship_panel) | 92.8% | 6625 |
| OLD R1 router | 90.1% | 7826 |
| CORRECTED router | 91.0% | 6208 |
| oracle | 96.4% | — |

**Honest verdict: the corrected router clearly beats the naive router
(+0.9pt AND 21% cheaper) but does NOT beat flat-best flagship_panel —
1.8pt less accurate at ~6% lower cost.** On this balanced blend, MoO
routing does not deliver a clean win over simply running the strongest
single profile. The 1.8pt shortfall is in two noisy small-sample buckets
(gpqa_organic_chem n=14, unknown n=9-11); on the robust-sample bucket
(supergpqa_hard_stem) the fix works exactly as diagnosed (ties bucket
flat-best at flagship cost). 328 tests.

**The strategic truth, stated straight:** flagship_panel is a strong,
surprisingly cheap generalist (rare escalation -> low cost, strong solvers
-> high accuracy), which sets a bar domain-routing struggles to beat on a
balanced 50/50 hard/easy blend. The individual profiles ARE validated
niche wins (chem_thinking_gate, flagship_panel, rag_thinking_gate each beat
their relevant baselines); ORCHESTRATING across them is marginal HERE. MoO's
value would grow on an easy-skewed workload (routing to single-call saves
more) or a latency/cost-constrained regime — testable offline by
re-weighting the existing eval data. No accuracy-win over-claim.

## MoO WIN on realistic traffic (2026-07-24 ~02:00) — re-weighting, FREE

Re-weighted the existing moo_m1_eval buckets (zero new paid calls) across
easy:hard traffic mixes. The balanced 50/50 blend is an adversarial
worst-case for routing (half the questions are hardest-STEM where
flagship_panel is BOTH cheap and strong, leaving little to save). Real QA
traffic isn't 50% GPQA-Diamond-hard.

| easy% of traffic | routed acc − flagship | routed cost vs flagship |
|---|---|---|
| 50% (balanced blend) | −1.9 pt | 5% cheaper |
| 70% | −1.1 pt | 18% cheaper |
| 80% | −0.7 pt | 28% cheaper |
| 90% | −0.4 pt | 41% cheaper |
| 95% | −0.2 pt | **50% cheaper** |

**The honest, defensible MoO result: on realistic easy-heavy traffic the
router matches flagship-everywhere accuracy to within noise (−0.2 to
−0.7pt at 80-95% easy) while cutting cost 28-50%.** MoO is a cost-efficiency
play — it avoids paying flagship-tier compute for questions a single cheap
call answers identically, and the saving scales directly with workload
answerability. Marginal (5%) on the adversarial balanced blend; large on
anything resembling real usage. Stated as a cost win at statistically-equal
accuracy — no accuracy-win over-claim. This closes the MoO M1 arc honestly
AND positively (on the right metric). Findings in
benchmark/results/moo_m1_corrected_findings.md; commit e08f668.

## flagship_panel / MMLU-Pro STEM (2026-07-24 ~01:40) — clean NULL, thesis CONFIRMED

Third hard-STEM generalization pilot. `mmlu_pro_stem` = MMLU-Pro's six
hard-STEM categories, 4-choice-trimmed, n=60 seed 42, apples-to-apples vs
single flagship.

| MMLU-Pro STEM seed 42 (n=60) | Acc |
|---|---|
| single flagship baseline | 96.7% |
| flagship_panel engine | 96.7% |
| **delta** | **+0.0** |
| escalation | 3.3% (2/60) |
| unanimous-wrong | 1.7% (1/60) |

**Not a negative for flagship_panel — a PREDICTIVE confirmation of the
unanimous-wrong-rate rule.** The flagship already scores 96.7%, so the gap
is ~0 (unanimous-wrong 1.7% vs ~15-23% where flagship_panel wins) → the rule
FORECASTS +0.0, and +0.0 is what came back. 4-choice-trimmed MMLU-Pro STEM
is saturated for the flagship (same caveat as MATH-500/GSM8K distractor-MC):
too easy to test hard-STEM deliberation. Two takeaways: (1) flagship_panel
does ZERO harm on a saturated set (better than cheap deliberation's −4.0/−6.1
saturated cost) → safe general-STEM default; (2) a real 3rd-benchmark
generalization needs a harder slice — MMLU-Pro full 10-way (engine change to
A–J) or a benchmark with real flagship headroom. SuperGPQA-hard (3-seed,
mean +4.1) stays THE validated hard-STEM generalization.
Findings: benchmark/results/flagship_panel_mmlu_pro_stem_findings.md.

Also DONE this window: 5 additive Build Log entries deployed-pending on the
MagiAchiral site (commit 80de3f1 in magiachiral-site) documenting the whole
arc — all numbers verified against primary result files, typecheck clean.

## Open-answer math GRADER built (2026-07-24 ~02:30) — prerequisite DONE

`benchmark/math_grade.py` + 26 tests (all green; suite 354). LaTeX→sympy
equivalence grader so hard math can be graded open-answer (0.5 == \frac12,
\sqrt20 == 2\sqrt5, 2π+18 == 18+2π), breaking the distractor-MC saturation
that pinned the flagship at 100% on MATH-500/GSM8K. Key discovery:
**HuggingFace math_verify is UNUSABLE on Windows** — its parse/verify path
uses a multiprocessing timeout that spawn-storms (WinError 87) and returns
[] for every input. Built instead on latex2sympy2-extended (works
standalone) + sympy. Validated on real MATH-500: 95% parse coverage
(477/500), ~0 false-positives (1/3000 distinct pairs, and that one is
30°==30 by design), FAILS CLOSED. Commit 11a264a, pushed.

## Open-answer math ENGINE path BUILT + smoke-validated (2026-07-24 ~02:00)

Sonnet worker built 4 files (commit 96a12dd, pushed), NOT touching the
shipped A–D engine: load_math_open.py (MATH-500 L5, keeps open gold),
math_open_engine.py (3 flagship solvers → union-find cluster by math_grade
equivalence → plurality wins, 3-way split escalates to a judge that
re-derives + emits a boxed answer; single-flagship baseline), run_math_open.py
(both arms extract+grade IDENTICALLY → fair delta), 15 offline tests. Suite
369 green. Orchestrator reviewed the engine+runner (no correctness bug found;
comparison is fair) and ran a 3-question LIVE smoke: baseline 3/3 & panel 3/3
on real MATH-500 L5, LaTeX-fraction answer -\dfrac{35}{9} graded correct,
clustering found agreement (0 escalation) — real-API behavior confirmed.

## Hard-math pilot DONE (2026-07-24 ~02:30) — no win, honest reason why

n=60 L5 seed 42 (n=59 common, 1 drop/arm). **Corrected**: baseline 96.6%
(57/59), panel 98.3% (58/59), **delta +1.7pp (one question)**, **escalation
0.0%**. Findings: benchmark/results/math_open_pilot_findings.md.

TWO honest findings:
1. **Deliberation is INERT on hard math** (the real result): 0% escalation —
   57/59 all-3-agree, 2/59 two-agree, ZERO 3-way splits, so the judge never
   fired. The +1.7 (1 item) is self-consistency@3 within noise, not
   deliberation. Three strong homogeneous solvers converge → nothing triggers
   the tribunal. SAME mechanism as the qwen38_panel negative; and the failure
   it can't fix (all-3-agree-wrong) IS the central unanimous-wrong mode.
2. **MATH-500 L5 is near-saturated for the flagship even open-answer** (96.6%,
   not the 89.8% first reported). Open-answer did NOT expose big headroom.
   Testing math deliberation needs a sub-90% surface (AIME/Olympiad) AND a
   weaker/more-diverse solver pool that actually disagrees.

METHODOLOGICAL CATCH (ultracode verification paid off): the FIRST grader
reported 89.8% — but 4 of 6 "errors" were grader false-negatives on
interval/±/set answers. Upgraded the grader (commit 40372fb; 0/4000
false-positives, L5 96→97%), RE-GRADED the stored answers for free → 96.6/98.3.
A naive grader undercounts hard-math by ~7pt and fabricates headroom. Caught
before it became a recorded "finding."

REUSABLE ASSETS delivered: open-answer math engine + false-positive-free
equivalence grader, both offline-tested, that make hard open-answer math
evaluable at all (nothing else in this repo could grade `\frac12`==`0.5`).

## MATH-500 cheap-tier DECISIVE + AIME pilot LAUNCHED (2026-07-24 ~03:00)

Cheap-tier MATH-500 L5 (shipped-engine design: flash solvers + flagship
judge): **flash 96.6% = flagship 96.6%, 0% escalation, 55/59 unanimous.**
qwen3.6-flash+thinking is AS GOOD as the flagship on MATH-500 L5 → benchmark
saturated at BOTH tiers → no cheap→flagship gap → deliberation can't help
(and didn't). Two pilots close MATH-500 for good. Findings updated in
math_open_pilot_findings.md, commit 109822a.

Built AIME loader (2024+2025, 60 integer-answer problems, commit) + --dataset
flag. **AIME cheap-tier pilot LAUNCHED** (task bh2nmup1m): flagship baseline
vs cheap-panel(flash solvers + flagship judge). AIME is the regime where flash
is genuinely weak (~10-40%) and the flagship better — a LARGE cheap→flagship
gap where, per the thesis, escalation should FIRE and the flagship judge
recover. THE experiment that could produce a math-deliberation win. Result
pending.

## AIME cheap-tier run #1 = INVALID (survivorship bias, 2026-07-24 ~03:45)

First AIME run is NOT a finding — 32/60 panel + 12/60 baseline items DROPPED
(ReadTimeout ×56, 429 rate-limit ×30). AIME thinking traces exceed the 300s
timeout AND concurrency-6 × (3 solvers+judge) tripped the rate limit; the
HARDEST problems (longest traces, most likely wrong/disagreeing) dropped, so
the n=26 survivors are a biased EASY subset → flash "100%", 0 escalation. Same
survivorship trap as the early chem_flagship_gate run; caught, not reported.
Root causes: (a) client retries only JSON-parse failures, transport errors
(ReadTimeout/429) propagate → item drops; (b) concurrency too high.
FIX: retry-with-backoff on transient errors in the runner + concurrency 2.

## ⛔ TOKEN-PLAN QUOTA EXHAUSTED — all paid runs blocked until 2026-07-28 03:32 UTC

Diagnosed 2026-07-24 ~03:52: every call now returns
`429 Throttling.AllocationQuota — "Your token-plan 1-week quota has been
exhausted. The quota will reset at 07-28 03:32:00 UTC."` The QwenClient routes
through the Token Plan endpoint (token-plan.ap-southeast-1.maas.aliyuncs.com/
apps/anthropic), whose **1-WEEK sliding quota** this session's pilots consumed
(MATH-500 flagship + cheap + AIME run #1). **No paid benchmark work is
possible until 2026-07-28 03:32 UTC (~4 days).**

KEY LESSON (record for pacing): Token Plan bills against an opaque weekly
quota with NO per-token USD meter (cost_usd is logged as 0.0), so the
"flag >$30" rule can't be applied by watching dollars — the only signal is
the quota-exhausted 429. Pace paid runs against the weekly quota, not USD.

The AIME cheap-tier fixes (thinking=False flash, retry-with-backoff, max_tokens
2048) are BUILT, committed, and offline-tested (suite 380) — ready to run the
instant the quota resets. AIME run #1 stays INVALID (survivorship bias).

## Same-provider scaling research LANDED (2026-07-24) — Track B redefined

Jun Kai redirected Track B: cross-vendor parked as CONSIDERED; active
question = scale with **Qwen-family agents only**. 5-angle research fan-out +
synthesis produced `docs/same-provider-scaling-research.md`: 28-technique
map (validated / planned / NEW / do-not-spend), a NEW test ladder (F1-F6
free rungs, P1-P11 paid riders ranked by info-per-quota-token), the honest
ceiling section (correlated-error floor, verifier gap, self-preference
bias, tool-checkable cap), and Track B restated as a measurable claim:
**beat qwen3.8-max-preview solo on shared items/seeds, net ≥ +3/90
discordant, 3-seed bar, diversity accounting mandatory.** Key status: GPQA
society (90.9%) is −2.7pt UNDER the 3.8-solo bar (93.6%); SuperGPQA-hard
bar unmeasured → P1 (3.8-solo paired baselines) is the first new paid spend.

## FREE SPRINT COMPLETE (2026-07-24, orchestrator + 4 Sonnet workers)

All free rungs executed, reviewed, committed, pushed. Suite: **443 passed.**

| Rung | Verdict / deliverable |
|---|---|
| #0 Token-audit | Weekly quota ≈ **43.8M logged tokens** (lower bound) — corrects the "~3 pilots/week" fear; week-1 schedule ≈ 8-11% of quota. Rule: ≤25% before mid-week re-check. |
| F1 floor + deficit | Family floor MUCH smaller than single-run unanimous-wrong (GPQA 2.1% vs 11%; SuperGPQA 16.1% vs 23%) → addressable pool bigger than feared. GPQA 3.8-deficit: **0 blind-spot / 2 escalated-and-lost** (small-n, one-sided) → GPQA effort goes to SELECTION levers (P2/P4/P5), not coverage. |
| F2 frontier | On 6/9 benchmarks a bare flagship call Pareto-dominates every logged lever; levers pay only on large-gap surfaces. 2 survivorship-contaminated rows annotated before commit (qwen38_panel 87.3% survivors-only; AIME invalidated 100%). |
| F5 map | moo-bucket flags: never route large-gap items to standard-tribunal/rag_presolve (small-n paired; respect in routing, not a contradiction of 3-seed records). |
| W5+F3 predictor | **BAND (median LOBO AUC 0.625)** — W7 cost-router input ONLY. F3 distribution features NEGATIVE (ΔAUC −0.026). P(wrong\|unanimous) unmeasured pending instability features (W2-arm0/P6 produce them). Secondary 0.751 annotated for unanimity-leakage. |
| W1+W2 builds | verified_gate_flaw / verified_gate_cas (+ sympy_check/substitute_check MCP tools) / permuted_panel / method_panel — 37 tests, pre-gate votes logged with byte-identical shipped prompts (W2's control provenance secured). |
| W3+F6 builds | solve_selfconsistency_math (grade-clustering, margin dial, F4 early-stop verified exact) + --mode sc; qwen_client seed/thinking_budget (byte-identical defaults, captured-request tested); **W1-B cap committed pre-run**: GPQA 53% checkable, SuperGPQA-hard 87% (heuristic ceiling, honestly flagged). |

Remaining optional free items: W4/W6 shelf-builds (conditional levers — build
only if W1/W2 screen positive, per plan demotion). NOT built yet by design.

## NEXT — everything is READY-TO-FIRE at quota reset (2026-07-28 03:32 UTC)
1. AIME pilot ① (queued, fixed, paired design) — always first.
2. W1 verified_gate screen (flaw-finder arm) on SuperGPQA-hard, 1 fresh seed
   — logs the pre-gate control W2 needs. Note F1's arbitration: GPQA gap is
   selection-side, so W1's screen runs on SuperGPQA (bigger coverage pool,
   16.1% floor) where coverage levers still have targets.
3. W2 arm-0 permuted_panel at the same seeds (rides W1's control; produces
   the instability features W5's conditional predictor needs).
4. P1 qwen3.8-solo paired baselines (SuperGPQA n=86 + AIME n=60) — sets the
   Track-B family bar. Riders: P7 if headroom.
Total ≈ 4-5M tokens ≈ 10% of measured quota.
2. Consolidate the whole reasoning arc into an additive site Build Log entry
   (when does deliberation help: validated hard-STEM wins; inert on saturated
   math; the AIME result). Additive-only, within grant.
3. Calibration memory (§5.1) + R2 per-question router for the MoO oracle gap.
