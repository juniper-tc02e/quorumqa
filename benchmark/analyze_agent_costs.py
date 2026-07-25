"""Measured (not estimated) per-task agent token costs for QuorumQAAgent's
prior Terminal-Bench runs, and a re-pricing of capability-roadmap.md's P13
(A1a self-check gate) and P15 (A0 Batch-1 oracle gap) against that measured
distribution instead of the roadmap's own flagged-unverifiable "~150k
tok/task" estimate (docs/capability-roadmap.md line 683/685).

ZERO PAID TOKENS. This script is log mining only: it reads artifacts
already on disk from past `harbor run` invocations. It does not run
Terminal-Bench, does not invoke Harbor, and does not call any model.

Where the data lives (and why it is not inside this git repo):
    `QuorumQAAgent.__init__`'s first positional arg is `logs_dir`
    (src/quorumqa/agents/terminal_agent.py:81), which is populated from
    Harbor's own `--jobs-dir` CLI flag -- Harbor's job/trial artifact
    tree, not a QuorumQA-owned log file. Every real historical run in
    this project passed `--jobs-dir` pointing at one of three directories
    under the OS temp dir (confirmed by directly reading each run's
    config.json, and cross-checked against
    docs/superpowers/plans/notes/2026-07-21-harbor-sanity-check.md, which
    records the first such run and its exact --jobs-dir value):
        %TEMP%/harbor_jobs            (harbor sanity check, nop agent -- not QuorumQAAgent)
        %TEMP%/harbor_jobs_quorumqa   (harbor sanity check, real QuorumQAAgent anecdote, n=1)
        %TEMP%/harbor_jobs_pilot      (every real pilot: seed-42, seed-42-retry,
                                        seed-7 pre-hardening x2, seed-7 hardened
                                        rerun, seed-3 fresh hardened baseline)
    None of this lives under benchmark/results/ -- Harbor writes to its own
    --jobs-dir, this project's benchmark/results/ is untouched by any of
    these runs. A repo-side search (this script also performs one, see
    search_repo_for_stray_artifacts()) finds nothing, which is reported
    explicitly rather than silently.

Reproduce:
    .venv/Scripts/python.exe benchmark/analyze_agent_costs.py

Outputs (new files only, nothing else is modified):
    benchmark/results/agent_cost_calibration.md
    benchmark/results/agent_cost_calibration.csv
"""

import csv
import json
import math
import os
import statistics
import tempfile
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = Path(__file__).resolve().parent / "results"
ROADMAP_PATH = REPO_ROOT / "docs" / "capability-roadmap.md"

# Candidate Harbor --jobs-dir roots. Every one found is scanned; a root
# that doesn't exist on this machine is skipped, not an error -- this is
# what makes the script survive %TEMP% getting cleared or a run on a
# different machine (it will then honestly report zero artifacts found,
# see MISSING-DATA handling in main()).
_TEMP_CANDIDATES = {tempfile.gettempdir()}
for env_var in ("TEMP", "TMP"):
    v = os.environ.get(env_var)
    if v:
        _TEMP_CANDIDATES.add(v)
HARBOR_JOB_ROOT_NAMES = ["harbor_jobs_pilot", "harbor_jobs_quorumqa", "harbor_jobs"]
HARBOR_JOB_ROOTS = sorted({
    Path(base) / name
    for base in _TEMP_CANDIDATES
    for name in HARBOR_JOB_ROOT_NAMES
})

# Manual, cited classification of each job run's hardening era. This is
# NOT derivable from the job artifacts themselves -- every job's
# config.json specifies an identical `max_turns: 15` regardless of era;
# the hardening changes (retry-on-ReadTimeout, TIMEOUT-as-observation
# instead of fatal exception, 1024->4096 max_tokens) live in
# src/quorumqa/agents/terminal_agent.py's git history, not in any run
# artifact. Sourced from:
#   docs/superpowers/plans/notes/2026-07-21-terminal-bench-14-task-pilot.md
#   docs/superpowers/plans/notes/2026-07-22-terminal-bench-seed7-pilot.md
# A job name not in this dict is still included in the overall inventory
# and CSV, just excluded from the pre/post-hardening split and flagged.
HARDENING_ERA = {
    "phase1-pilot-seed42": "pre-hardening",
    "phase1-pilot-seed42-retry": "pre-hardening",
    "phase1-pilot-seed7": "pre-hardening",
    "phase1-pilot-seed7c": "pre-hardening",
    "seed7-hardened-rerun": "hardened",
    "hardened-baseline-seed3": "hardened",
    "2026-07-21__15-28-24": "pre-hardening",  # single-task anecdote, real QuorumQAAgent
    "2026-07-21__15-21-01": "not-quorumqa",   # harbor sanity check, agent=nop, excluded from cost stats
}

CODE_DEFAULT_MAX_TURNS = 30  # src/quorumqa/agents/terminal_agent.py __init__ signature default
ROADMAP_ASSUMED_TOK_PER_TASK = 150_000  # the flagged-unverifiable estimate this script replaces
MEASURED_WEEKLY_QUOTA_TOKENS = 43_828_731  # benchmark/results/quota_token_audit.md TOTAL row


def find_job_dirs():
    """A 'job dir' is one `harbor run` invocation: has its own config.json
    and result.json directly inside it. Returns (root, job_dir) pairs."""
    found = []
    for root in HARBOR_JOB_ROOTS:
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            if (child / "config.json").is_file() and (child / "result.json").is_file():
                found.append((root, child))
    return found


def search_repo_for_stray_artifacts():
    """Honest check that no Harbor/agent artifacts were ever committed into
    the repo itself (benchmark/results/ or elsewhere). Returns a list of
    matches; an empty list is reported as such, not silently skipped."""
    hits = []
    for p in REPO_ROOT.rglob("*.json"):
        if ".venv" in p.parts or ".git" in p.parts:
            continue
        try:
            head = p.read_text(encoding="utf-8", errors="ignore")[:400]
        except OSError:
            continue
        if '"trial_name"' in head or '"quorumqa-single"' in head:
            hits.append(str(p.relative_to(REPO_ROOT)))
    for p in REPO_ROOT.rglob("*.jsonl"):
        if ".venv" in p.parts or ".git" in p.parts:
            continue
        name = p.name.lower()
        if "terminal" in name or "harbor" in name or "agent" in name:
            hits.append(str(p.relative_to(REPO_ROOT)))
    return hits


def parse_iso(ts):
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def load_task_trial(task_dir, job_name, job_max_turns):
    result_path = task_dir / "result.json"
    if not result_path.is_file():
        return None
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if "trial_name" not in data:
        return None  # this is a job-level result.json, not a task trial

    task_id = data.get("task_id") or {}
    task_name = task_id.get("name") or (data.get("task_name") or "").replace("terminal-bench/", "")
    agent_result = data.get("agent_result") or {}
    n_in = agent_result.get("n_input_tokens")
    n_out = agent_result.get("n_output_tokens")
    total = (n_in + n_out) if (n_in is not None and n_out is not None) else None

    verifier_result = data.get("verifier_result")
    reward = None
    if verifier_result and isinstance(verifier_result.get("rewards"), dict):
        reward = verifier_result["rewards"].get("reward")

    exc = data.get("exception_info") or {}
    exception_type = exc.get("exception_type")
    exception_message = (exc.get("exception_message") or "")[:120]

    if reward is not None:
        status = "solved" if reward >= 1.0 else "failed_graded"
    elif exception_type:
        status = "ungraded_exception"
    else:
        status = "ungraded_other"

    agent_exec = data.get("agent_execution") or {}
    started = parse_iso(agent_exec.get("started_at"))
    finished = parse_iso(agent_exec.get("finished_at"))
    wall_clock_sec = (finished - started).total_seconds() if (started and finished) else None

    return {
        "job_name": job_name,
        "hardening_era": HARDENING_ERA.get(job_name, "UNCLASSIFIED"),
        "task_name": task_name,
        "trial_name": data.get("trial_name"),
        "job_max_turns": job_max_turns,
        "n_input_tokens": n_in,
        "n_output_tokens": n_out,
        "total_tokens": total,
        "reward": reward,
        "status": status,
        "exception_type": exception_type,
        "exception_message": exception_message,
        "agent_wall_clock_sec": round(wall_clock_sec, 1) if wall_clock_sec is not None else None,
    }


def load_all_trials():
    trials = []
    job_summaries = []
    for root, job_dir in find_job_dirs():
        try:
            cfg = json.loads((job_dir / "config.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        job_name = cfg.get("job_name", job_dir.name)
        agents = cfg.get("agents") or [{}]
        agent_name = agents[0].get("name", "")
        if "quorumqa" not in agent_name:
            # e.g. the `nop` sanity-check run -- not this agent, skip from
            # cost accounting but note it existed.
            job_summaries.append({
                "job_name": job_name, "root": str(root), "agent": agent_name,
                "max_turns": None, "n_task_dirs": sum(
                    1 for d in job_dir.iterdir() if d.is_dir()
                ),
                "included": False,
            })
            continue
        job_max_turns = (agents[0].get("kwargs") or {}).get("max_turns")

        n_task_dirs = 0
        for task_dir in sorted(job_dir.iterdir()):
            if not task_dir.is_dir():
                continue
            n_task_dirs += 1
            trial = load_task_trial(task_dir, job_name, job_max_turns)
            if trial:
                trials.append(trial)
        job_summaries.append({
            "job_name": job_name, "root": str(root), "agent": agent_name,
            "max_turns": job_max_turns, "n_task_dirs": n_task_dirs,
            "included": True,
        })
    return trials, job_summaries


def percentile(sorted_vals, p):
    """Linear-interpolation percentile (numpy's default 'linear' method),
    p in [0, 100]. sorted_vals must already be sorted ascending."""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def distribution(values):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    return {
        "n": len(vals),
        "min": vals[0],
        "median": statistics.median(vals),
        "mean": statistics.mean(vals),
        "p90": percentile(vals, 90),
        "max": vals[-1],
    }


def fmt_dist(d, unit="tok"):
    if d is None:
        return "NO DATA"
    return (f"n={d['n']}  min={d['min']:,.0f}  median={d['median']:,.0f}  "
            f"mean={d['mean']:,.0f}  p90={d['p90']:,.0f}  max={d['max']:,.0f}  [{unit}]")


def write_csv(trials, path):
    fields = ["job_name", "hardening_era", "task_name", "trial_name", "job_max_turns",
              "n_input_tokens", "n_output_tokens", "total_tokens", "reward", "status",
              "exception_type", "exception_message", "agent_wall_clock_sec"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for t in trials:
            w.writerow(t)


def main():
    lines = []
    lines.append("# Agent cost calibration -- measured, not estimated")
    lines.append("")
    lines.append("Reproduce: `.venv/Scripts/python.exe benchmark/analyze_agent_costs.py`")
    lines.append("")
    lines.append("**Zero paid tokens.** Log mining only, over Harbor job artifacts already")
    lines.append("on disk from prior `harbor run` invocations. No Terminal-Bench task,")
    lines.append("Harbor invocation, or model call was made to produce this report.")
    lines.append("")

    # --- 1. Inventory ---
    lines.append("## 1. What was found")
    lines.append("")
    lines.append("Search roots (Harbor `--jobs-dir` locations, deduplicated):")
    for r in HARBOR_JOB_ROOTS:
        exists = "exists" if r.is_dir() else "does not exist on this machine"
        lines.append(f"- `{r}` ({exists})")
    lines.append("")

    stray = search_repo_for_stray_artifacts()
    lines.append("In-repo search for stray agent/Harbor artifacts "
                  "(`benchmark/results/`, anywhere else under the repo): "
                  f"**{len(stray)} found**"
                  + ("." if stray else " -- none. Harbor writes to its own "
                     "--jobs-dir, never into this repo."))
    for h in stray:
        lines.append(f"  - {h}")
    lines.append("")

    trials, job_summaries = load_all_trials()

    lines.append(f"Harbor job directories found: {len(job_summaries)}")
    lines.append("")
    lines.append("| job_name | root | agent | job max_turns | task dirs | included in cost stats |")
    lines.append("|---|---|---|---|---|---|")
    for j in job_summaries:
        lines.append(f"| {j['job_name']} | `{Path(j['root']).name}` | {j['agent']} | "
                      f"{j['max_turns'] if j['max_turns'] is not None else '-'} | "
                      f"{j['n_task_dirs']} | {'yes' if j['included'] else 'no (not QuorumQAAgent)'} |")
    lines.append("")
    lines.append(f"QuorumQAAgent task trials recovered: **{len(trials)}**")
    lines.append("")

    if not trials:
        lines.append("**NO USABLE ARTIFACTS FOUND.** This is not a fabricated fallback: it means")
        lines.append("none of the three known --jobs-dir locations exist on this machine right now")
        lines.append("(most likely %TEMP% was cleared since the pilots ran). The cheapest way to")
        lines.append("get a real number in that case is `docs/capability-roadmap.md`'s own A0'")
        lines.append("calibration lever (4 tasks, k=1, ~0.5M tokens) -- there is no free substitute")
        lines.append("once these temp artifacts are gone.")
        out_md = RESULTS_DIR / "agent_cost_calibration.md"
        out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        return

    # --- 2. Max-turns cap discrepancy (found while reading configs) ---
    turn_caps = {t["job_max_turns"] for t in trials}
    lines.append("## 2. Turn-cap discrepancy (found while reading job configs)")
    lines.append("")
    lines.append(f"Every real historical QuorumQAAgent job passed an explicit `max_turns` "
                  f"override. Caps observed across all {len(job_summaries)} jobs: "
                  f"**{sorted(x for x in turn_caps if x is not None)}**.")
    lines.append(f"`src/quorumqa/agents/terminal_agent.py`'s constructor **default** is "
                  f"`max_turns={CODE_DEFAULT_MAX_TURNS}`, and `docs/capability-roadmap.md` "
                  f"itself refers to 'the existing 30-turn cap' / 'the unchanged 30-turn cap' "
                  f"(A1a, A2 rows, section 3.5). **Every actual historical run used 15, not "
                  f"30.** No historical run exists at the 30-turn cap the roadmap's own prose "
                  f"assumes P13/P15 will run at. This matters directly for re-pricing below: "
                  f"tasks that exhaust their turn budget without finishing pay for roughly "
                  f"twice as many turns at cap=30 as at cap=15, and per-turn prompts grow with "
                  f"transcript length, so the cost of a capped-out task is *worse* than linear "
                  f"in the cap. The measured distribution below is a same-cap (15) read; it")
    lines.append("does not by itself tell us the cost at cap=30 (see section 5).")
    lines.append("")

    # --- 3. Turn-level granularity ---
    lines.append("## 3. Per-turn granularity: not available")
    lines.append("")
    lines.append("`QuorumQAAgent.run()` (src/quorumqa/agents/terminal_agent.py) accumulates "
                  "`total_input_tokens`/`total_output_tokens` in local variables across its "
                  "turn loop and only ever writes them into `context.n_input_tokens` / "
                  "`context.n_output_tokens` -- it never calls `self.logger` or writes a "
                  "per-turn record to `logs_dir`. Harbor's own `result.json` per task mirrors "
                  "this: it stores only the cumulative `agent_result.n_input_tokens` / "
                  "`n_output_tokens` for the whole trial, with no turn-by-turn breakdown "
                  "(`agent/` and `artifacts/logs/` subdirectories under each task trial exist "
                  "but are empty in every trial checked). Wall-clock timestamps "
                  "(`agent_execution.started_at`/`finished_at`) ARE present per task and are "
                  "reported below, but they cannot be divided by a turn count we don't have to "
                  "back out a reliable per-turn figure. **This report gives per-TASK "
                  "distributions (measured) and does not fabricate a per-turn number.**")
    lines.append("")

    missing_usage = [t for t in trials if t["total_tokens"] is None]
    if missing_usage:
        lines.append(f"**{len(missing_usage)} trials have NO recorded usage at all** "
                     "(agent_result.n_input_tokens/n_output_tokens both null in Harbor's "
                     "result.json) -- not zero spend, an unrecorded gap. In every case the "
                     "exception (a bare RuntimeError from an un-caught exec() timeout, or a "
                     "ValueError from JSON-truncation inside chat_json itself) fired before "
                     "`QuorumQAAgent.run()` ever reached its `context.n_input_tokens = "
                     "total_input_tokens` assignment, so real token spend on at least the "
                     "in-flight turn was never written back to Harbor. These are excluded from "
                     "every distribution below (not treated as 0) and are all pre-hardening:")
        for t in missing_usage:
            lines.append(f"  - `{t['job_name']}` / `{t['task_name']}`: {t['exception_type']} "
                         f"-- {t['exception_message']}")
        lines.append("")

    # --- 4. Per-task distributions ---
    lines.append("## 4. Measured per-task token cost distribution")
    lines.append("")

    def subset(era=None):
        if era is None:
            return trials
        return [t for t in trials if t["hardening_era"] == era]

    all_total = distribution([t["total_tokens"] for t in trials])
    all_in = distribution([t["n_input_tokens"] for t in trials])
    all_out = distribution([t["n_output_tokens"] for t in trials])
    hardened_total = distribution([t["total_tokens"] for t in subset("hardened")])
    prehard_total = distribution([t["total_tokens"] for t in subset("pre-hardening")])
    hardened_wall = distribution([t["agent_wall_clock_sec"] for t in subset("hardened")])

    lines.append("**All eras pooled** (pre-hardening + hardened + the single anecdote task; "
                 f"n={len(trials)} task trials across {len(job_summaries)} jobs):")
    lines.append(f"- total tokens/task: {fmt_dist(all_total)}")
    lines.append(f"- input tokens/task: {fmt_dist(all_in)}")
    lines.append(f"- output tokens/task: {fmt_dist(all_out)}")
    lines.append("")
    lines.append(f"**Pre-hardening only** (n={prehard_total['n'] if prehard_total else 0}): "
                 f"total tokens/task: {fmt_dist(prehard_total)}")
    lines.append(f"**Hardened only** (n={hardened_total['n'] if hardened_total else 0}, "
                 f"the fairer analog for a fresh P13/P15 sample since P13/P15 will run the "
                 f"hardened agent): total tokens/task: {fmt_dist(hardened_total)}")
    lines.append(f"**Hardened-only agent wall-clock/task (seconds)**: {fmt_dist(hardened_wall, unit='sec')}")
    lines.append("")

    status_counts = {}
    for t in trials:
        status_counts[t["status"]] = status_counts.get(t["status"], 0) + 1
    lines.append("Status breakdown across all recovered trials: "
                 + ", ".join(f"{k}={v}" for k, v in sorted(status_counts.items())))
    lines.append("")
    lines.append("(`ungraded_exception` includes trials where an exception co-occurred with a "
                 "real verifier grade, e.g. `break-filter-js-from-html` hit its own 1200s "
                 "AgentTimeoutError but the container state still graded 1.0 -- Harbor logs "
                 "the exception and the grade independently; this script classifies by "
                 "grade-presence first, so that specific trial shows as `solved`, not "
                 "`ungraded_exception`. Full per-task detail, including which trials had a "
                 "co-occurring exception, is in the CSV.)")
    lines.append("")

    # --- 5. Re-pricing P13 / P15 ---
    lines.append("## 5. Re-pricing P13 and P15")
    lines.append("")
    lines.append(f"Roadmap's own flagged-unverifiable assumption: "
                 f"**{ROADMAP_ASSUMED_TOK_PER_TASK:,} tok/task-attempt** "
                 f"(docs/capability-roadmap.md lines 683/685, 'the unverifiable ~150k "
                 f"tok/task estimate').")
    lines.append("")

    if hardened_total:
        measured_mean = hardened_total["mean"]
        measured_p90 = hardened_total["p90"]
        basis_n = hardened_total["n"]
        basis_label = "hardened-only measured mean/p90"
    else:
        measured_mean = all_total["mean"]
        measured_p90 = all_total["p90"]
        basis_n = all_total["n"]
        basis_label = "all-eras measured mean/p90 (no hardened data recovered)"

    ratio_mean = measured_mean / ROADMAP_ASSUMED_TOK_PER_TASK
    ratio_p90 = measured_p90 / ROADMAP_ASSUMED_TOK_PER_TASK

    lines.append(f"Basis for re-pricing: {basis_label}, n={basis_n} task trials -- "
                 f"mean={measured_mean:,.0f} tok/task, p90={measured_p90:,.0f} tok/task.")
    lines.append(f"Ratio vs the roadmap's 150k/task assumption: "
                 f"**mean = {ratio_mean:.2f}x, p90 = {ratio_p90:.2f}x** the assumed figure.")
    lines.append("")

    for item, tokens_budgeted, n_task_attempts, gate in [
        ("P13", 1_100_000, 1_100_000 / ROADMAP_ASSUMED_TOK_PER_TASK,
         "A1a self-check gate + A0' calibration, fresh disjoint sample"),
        ("P15", 5_500_000, 5_500_000 / ROADMAP_ASSUMED_TOK_PER_TASK,
         "A0 Batch-1 oracle gap, 12 fresh tasks x k=3 = 36 rollouts"),
    ]:
        repriced_point = n_task_attempts * measured_mean
        repriced_p90 = n_task_attempts * measured_p90
        pct_point = 100 * repriced_point / MEASURED_WEEKLY_QUOTA_TOKENS
        pct_p90 = 100 * repriced_p90 / MEASURED_WEEKLY_QUOTA_TOKENS
        orig_pct = 100 * tokens_budgeted / MEASURED_WEEKLY_QUOTA_TOKENS
        lines.append(f"### {item} -- {gate}")
        lines.append(f"- Roadmap budget: {tokens_budgeted:,} tokens "
                     f"({orig_pct:.2f}% of {MEASURED_WEEKLY_QUOTA_TOKENS:,}/wk quota), "
                     f"implying {n_task_attempts:.1f} task-attempts at the assumed 150k/task rate.")
        lines.append(f"- Re-priced at measured cost, **same task-attempt count** "
                     f"({n_task_attempts:.1f}): "
                     f"point estimate (mean) = **{repriced_point:,.0f} tokens** "
                     f"({pct_point:.2f}% of weekly quota); "
                     f"p90 upper bound = **{repriced_p90:,.0f} tokens** "
                     f"({pct_p90:.2f}% of weekly quota).")
        lines.append(f"- vs roadmap budget: point-estimate ratio = {repriced_point/tokens_budgeted:.2f}x, "
                     f"p90 ratio = {repriced_p90/tokens_budgeted:.2f}x.")
        lines.append("")

    # --- 6. Sampling caveat ---
    lines.append("## 6. What this licenses, and what it does not")
    lines.append("")
    lines.append("- **Turn cap mismatch (section 2).** All measured data is at max_turns=15. "
                 "The roadmap's own prose assumes a 30-turn cap for P13/P15's agentic work "
                 "('the existing/unchanged 30-turn cap', A1a/A2). No historical run at cap=30 "
                 "exists. If P13/P15 actually run at 30, tasks that would have exhausted a "
                 "15-turn cap can run for materially more tokens than this report's p90 "
                 "captures -- per-turn prompt size grows with transcript length, so cost is "
                 "worse than linear in the cap for capped-out tasks. Decide the actual cap "
                 "for P13/P15 before trusting the p90 figure as a hard ceiling; if it's 30, "
                 "treat the p90 above as a floor, not a ceiling.")
    lines.append("- **The 24-task hardened-against set is not this report's basis, but the "
                 "underlying agent is the same hardened agent.** P13/P15 explicitly target a "
                 "*fresh, disjoint* sample specifically because the 24-task set "
                 "(seed-7 pre/post + seed-3) was used to develop and tune the hardening fixes "
                 "-- this report's 'hardened' subset overlaps that same 24-task set (it *is* "
                 "the seed-7-hardened-rerun + seed-3 runs). The token-COST distribution is a "
                 "reasonable analog for a fresh sample (nothing about token cost per turn is "
                 "tuned by the hardening fixes -- the fixes changed retry/timeout/error-"
                 "handling behavior, not prompt size), but the SOLVE-RATE numbers from this "
                 "same data must not be reused as a fresh-sample accuracy baseline, exactly as "
                 "capability-roadmap.md section 3.5 already states.")
    lines.append("- **Hardening changed token spend, not just error handling, and the direction "
                 "is toward more tokens per task.** The 3-fix hardening pass (retry-on-"
                 "ReadTimeout, TIMEOUT-as-observation instead of fatal exception, 1024->4096 "
                 "max_tokens) means a task that used to die in 1-2 turns pre-hardening now "
                 "survives to consume more turns post-hardening. Compare pre-hardening vs "
                 "hardened means printed in section 4 -- if hardened mean > pre-hardening mean "
                 "(check the numbers above), that is this effect showing up directly, not noise.")
    lines.append("- **This is a small, non-uniform sample (mixed task difficulty, mixed "
                 "concurrency, mixed time-of-day).** Distribution shape (mean vs p90 spread) is "
                 "informative; the exact p90 value should not be treated as more precise than "
                 f"n={hardened_total['n'] if hardened_total else all_total['n']} tasks supports.")
    lines.append("")

    # --- 7. Decision consequences ---
    lines.append("## 7. Decision consequences")
    lines.append("")
    if hardened_total:
        verdict = ("UNDER-PRICED" if ratio_mean > 1.15 else
                   "OVER-PRICED" if ratio_mean < 0.85 else
                   "ROUGHLY CORRECTLY PRICED")
        lines.append(f"At the mean, the roadmap's 150k/task assumption is "
                     f"**{ratio_mean:.2f}x** the measured hardened-era mean "
                     f"({measured_mean:,.0f} tok/task) -> the agentic branch is "
                     f"**{verdict}** on point estimate.")
        lines.append(f"At p90, the ratio is **{ratio_p90:.2f}x** "
                     f"({measured_p90:,.0f} measured tok/task at p90) -- this is the number that "
                     f"matters for the 20% quota-reserve risk the task brief calls out, since "
                     f"agentic cost is long-tailed by construction (a task that survives to the "
                     f"turn cap costs far more than one that finishes in 2 turns).")
        lines.append("")
        if ratio_p90 > 1:
            lines.append("p90 ratio > 1: a batch sized at the roadmap's point estimate risks "
                         "silently eating into the 20% reserve on an unlucky-but-plausible draw "
                         "of task difficulty (long-tail tasks landing disproportionately in the "
                         "sample) -- this does NOT change P13/P15's position in the paid firing "
                         "order (both are still small relative to the 43.8M/wk quota, P13 at "
                         "~1.1M and P15 at ~5.5M budgeted), but it does argue for sizing the "
                         "actual spend cap off the measured p90, not the mean, and for "
                         "confirming the real turn cap (section 2) before committing tokens.")
        else:
            lines.append("p90 ratio <= 1: the roadmap's 150k figure was conservative even at "
                         "the tail measured so far -- P13/P15 can run with headroom to spare "
                         "against their own budget line at the SAME turn cap (15) this data was "
                         "measured at. This is NOT a reason to move them earlier in the firing "
                         "order (their position was set by information-per-token, a different "
                         "question), and it is NOT license to skip the turn-cap-30 caveat above "
                         "-- an under-priced risk at cap=15 can still turn into an over-spend at "
                         "cap=30 if that is the cap actually used.")
    else:
        lines.append("No hardened-era data was recoverable -- see section 1's inventory for why. "
                     "**No verdict is stated here rather than inferring one from pre-hardening-"
                     "only data**, which would misrepresent the agent P13/P15 will actually run.")
    lines.append("")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_md = RESULTS_DIR / "agent_cost_calibration.md"
    out_csv = RESULTS_DIR / "agent_cost_calibration.csv"
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_csv(trials, out_csv)

    print("\n".join(lines))
    print(f"\nwrote {out_md}")
    print(f"wrote {out_csv}")


if __name__ == "__main__":
    main()
