# MagiAchiral improvement loop — persistent state

Started 2026-07-21. This doc is the loop's memory: every iteration reads it,
acts on the top of the backlog, records what happened, and re-ranks. It is
committed after every iteration so the loop survives session loss.

## Hard stop: 2026-07-22 07:15 SGT

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
5. **Stack test: chem_flagship_gate + thinking_gate** — do the two validated
   levers compose? (After #1 lands.)
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
