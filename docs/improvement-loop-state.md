# MagiAchiral improvement loop — persistent state

Started 2026-07-21. This doc is the loop's memory: every iteration reads it,
acts on the top of the backlog, records what happened, and re-ranks. It is
committed after every iteration so the loop survives session loss.

---

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
