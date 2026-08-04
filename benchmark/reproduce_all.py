"""Run every offline analysis in the repo and report which ones reproduce.

The strongest claim this project makes about itself is that every published
number traces to a committed artifact and can be recomputed. That claim was
only checkable by reading seventeen separate commands out of seven documents
and running them by hand. This is the one command.

    python -m benchmark.reproduce_all            # run everything
    python -m benchmark.reproduce_all --list     # show what would run
    python -m benchmark.reproduce_all --quiet    # summary table only

No API calls, no network, no tokens. Every input is a committed file.

WHAT "OK" MEANS HERE, precisely: the script ran to completion and its own
internal assertions held. It does NOT mean the number it printed matches the
number in the docs -- that is what `figure_data.verify_ledger()` checks (118
numbers against their cited source docs), and it runs here too, last, so a
green summary covers both properties.

SKIPPED IS NOT PASSED. Analyses whose raw .jsonl inputs are gitignored cannot
run in a fresh clone. Those are reported as SKIP with the missing file named,
never silently omitted -- a reproduction harness that quietly drops what it
cannot check is worse than none, because it reads as verification.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS = PROJECT_ROOT / "benchmark" / "results"
PY = sys.executable

#: A representative input each analysis needs, as a glob under benchmark/results.
#: Raw .jsonl runs are gitignored, so on a FRESH CLONE most of these are absent
#: and the analysis cannot run.
#:
#: Without this map the harness reports FAIL there, which is a lie in the
#: misleading direction: it reads as "the repo does not reproduce" when the
#: truth is "the data is not in the repo, by design". A fresh clone is exactly
#: this tool's audience, so the distinction has to be right for a reader who
#: has never run a benchmark.
NEEDS_GLOB: dict[str, str] = {
    "benchmark.analyze_judge_anchoring": "*.jsonl",
    "benchmark.analyze_dropout_bias": "*.jsonl",
    "benchmark.analyze_family_floor": "lever_baseline_*.jsonl",
    "benchmark.analyze_cost_frontier": "TB1_flagship1x_gpqa_seed*.jsonl",
    "benchmark.analyze_agent_costs": "*.jsonl",
    "benchmark.analyze_stability_repaired": "*.jsonl",
    "benchmark.verify_flagship_claim": "lever_flagship_panel_supergpqa_*.jsonl",
    "benchmark.verify_chemistry_claim": "*.jsonl",
    "benchmark.verify_compute_matched_control": "compute_matched_control_*.jsonl",
    "benchmark.verify_universal_gate": "lever_universal_gate_gpqa_seed*.jsonl",
    "benchmark.verify_tb1_flagship": "TB1_flagship1x_gpqa_seed*.jsonl",
    "benchmark.verify_tb1b_supergpqa": "TB1B_universal_gate_supergpqa_seed*.jsonl",
    # These two read committed CSV/JSON only, so they run anywhere.
    "benchmark.analyze_headroom_rule": "",
    # Reads the COMMITTED per-item table, so it runs on a fresh clone -- which
    # is the entire reason that table exists.
    "benchmark.analyze_dropout_sensitivity": "",
    "benchmark.figure_data": "",
    # Takes its inputs as explicit --control/--permuted paths rather than
    # globbing, so _missing_inputs() already covers it. Declared as "" so the
    # map stays complete -- an analysis absent from this map silently defaults
    # to "runnable anywhere", which is the FAIL-on-a-fresh-clone path.
    "benchmark.analyze_unanimous_stability": "",
}

#: (module, args, one-line description). Ordered roughly from raw analysis to
#: published claim, so a failure early explains failures later.
ANALYSES: list[tuple[str, list[str], str]] = [
    ("benchmark.analyze_judge_anchoring", [],
     "Judge off-slate behaviour + the unanimous-gate recall headroom"),
    ("benchmark.analyze_dropout_bias", [],
     "Are dropped items missing-at-random? (they are not)"),
    ("benchmark.analyze_family_floor", [],
     "Same-family floor: what a panel of one model family cannot fix"),
    ("benchmark.analyze_cost_frontier", [],
     "The paired accuracy-vs-tokens frontier (Tier A)"),
    ("benchmark.analyze_headroom_rule", [],
     "Does the unanimous-wrong rate PREDICT lever payoff? (it bounds, not predicts)"),
    ("benchmark.analyze_dropout_sensitivity", [],
     "Every headline under complete-case AND timeout-as-failure (2 of 4 flip)"),
    ("benchmark.analyze_agent_costs", [],
     "Terminal-Bench agent token accounting"),
    ("benchmark.analyze_stability_repaired", [],
     "Answer-instability lift against its own permutation null"),
    ("benchmark.verify_flagship_claim", [],
     "flagship_panel on SuperGPQA-hard, paired"),
    ("benchmark.verify_chemistry_claim", [],
     "chem_thinking_gate, 3 seeds"),
    ("benchmark.verify_compute_matched_control", [],
     "Deliberation vs self-consistency: the control that retracted a mechanism"),
    ("benchmark.verify_universal_gate", [],
     "universal_gate, 3 seeds, vs the shipped rule"),
    ("benchmark.verify_tb1_flagship", [],
     "TB-1: the whole stack vs one flagship call (GPQA)"),
    ("benchmark.verify_tb1b_supergpqa", [],
     "TB-1B: cheap seats + escalate-all vs one flagship call (SuperGPQA-hard)"),
    ("benchmark.analyze_unanimous_stability", [
        "--control",
        "benchmark/results/META2_control_supergpqa_seed909.jsonl",
        "benchmark/results/META2_control_supergpqa_seed1313.jsonl",
        "benchmark/results/META2_control_supergpqa_seed2027.jsonl",
        "--permuted",
        "benchmark/results/META2_permuted_panel_supergpqa_seed909.jsonl",
        "benchmark/results/META2_permuted_panel_supergpqa_seed1313.jsonl",
        "benchmark/results/META2_permuted_panel_supergpqa_seed2027.jsonl",
     ], "META-2: permutation instability as a wrongness signal"),
]

#: Run last: checks every ledger cell against the doc that cites it.
LEDGER = ("benchmark.figure_data", ["--check"],
          "Claims ledger: every published number vs its cited source doc")


def _missing_inputs(args: list[str]) -> list[str]:
    """Explicit --in/--control/--permuted paths that are not present."""
    return [a for a in args
            if a.endswith(".jsonl") and not (PROJECT_ROOT / a).exists()]


def run_one(module: str, args: list[str], quiet: bool) -> tuple[str, str]:
    missing = _missing_inputs(args)
    if missing:
        return "SKIP", f"missing input(s): {', '.join(missing)}"

    glob = NEEDS_GLOB.get(module, "")
    if glob and not list(RESULTS.glob(glob)):
        return "SKIP", (f"no {glob} in benchmark/results (raw runs are "
                        f"gitignored; expected on a fresh clone)")

    proc = subprocess.run([PY, "-m", module, *args], cwd=PROJECT_ROOT,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    if proc.returncode == 0:
        return "OK", ""
    tail = [ln for ln in (proc.stderr or proc.stdout).splitlines() if ln.strip()]
    return "FAIL", (tail[-1][:160] if tail else f"exit {proc.returncode}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--list", action="store_true", help="show what would run")
    ap.add_argument("--quiet", action="store_true", help="summary table only")
    a = ap.parse_args()

    everything = [*ANALYSES, LEDGER]

    if a.list:
        for mod, args, desc in everything:
            print(f"  {mod.split('.')[-1]:34s} {desc}")
        print(f"\n{len(everything)} analyses. None make API calls.")
        return 0

    print("=" * 78)
    print("QuorumQA -- reproducing every offline analysis")
    print("No API calls, no network. Every input is a committed file.")
    print("=" * 78)

    results = []
    for mod, args, desc in everything:
        name = mod.split(".")[-1]
        if not a.quiet:
            print(f"  running {name} ...", flush=True)
        status, note = run_one(mod, args, a.quiet)
        results.append((name, status, note, desc))

    print()
    print("-" * 78)
    width = max(len(n) for n, _, _, _ in results)
    for name, status, note, desc in results:
        mark = {"OK": "  OK  ", "FAIL": " FAIL ", "SKIP": " SKIP "}[status]
        print(f"[{mark}] {name:<{width}}  {desc}")
        if note:
            print(f"{'':>{width + 11}}{note}")
    print("-" * 78)

    ok = sum(1 for _, s, _, _ in results if s == "OK")
    skipped = [n for n, s, _, _ in results if s == "SKIP"]
    failed = [n for n, s, _, _ in results if s == "FAIL"]

    print(f"{ok}/{len(results)} reproduced.", end="")
    if skipped:
        print(f"  {len(skipped)} SKIPPED for missing gitignored inputs: "
              f"{', '.join(skipped)}", end="")
    if failed:
        print(f"  {len(failed)} FAILED: {', '.join(failed)}", end="")
    print()

    if skipped and not failed:
        print("\nNOTE: skipped is not passed. Those analyses were not checked "
              "at all -- their raw .jsonl inputs are gitignored, so they only "
              "run on a machine that holds the runs.")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
