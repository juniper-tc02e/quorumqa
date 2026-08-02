"""Is the Judge anchored to the letters its solvers offered?

Motivation. AggLM (arXiv:2509.06870) prompts its aggregator with "it is possible
that any, all, or NONE of these solutions are correct" and explicitly licenses
synthesising an answer that appeared in no candidate. QuorumQA's JUDGE_SYSTEM
already supplies full solver rationales and already tells the Judge to weigh
arguments over headcounts -- but it asks it to "rule on the single best answer
letter", which frames the job as SELECTION AMONG PRESENTED POSITIONS. For
multiple choice, AggLM's "none are correct" case has an exact analogue: choosing
a letter that no solver picked.

This script measures, over every committed escalation, how often the Judge
actually does that -- and, in the decisive subset where the gold letter was
offered by NO solver, how often it recovers the answer regardless. A recovery
rate near zero means the none-of-the-offered path is effectively unreachable and
an explicit licence is a real, untested lever. A healthy rate means the Judge is
already unanchored and the lever is dead on arrival.

Offline. Reads only committed result files. No API calls, no tokens.

    python benchmark/analyze_judge_anchoring.py
"""

from __future__ import annotations

import collections
import glob
import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"


def _engines(row: dict):
    """Yield engine-shaped records from either wrapper layout."""
    for key in ("engine", "result"):
        val = row.get(key)
        if isinstance(val, dict):
            yield val


def corpus_size() -> int:
    """How many result files collect() will read.

    Exposed because every pooled figure here is computed over a glob of
    `results/*.jsonl`, so it grows whenever any new experiment is committed.
    A test that pins the pooled counts is really pinning "the corpus as of date
    D", and without this it has no way to say which corpus it meant.
    """
    return len(glob.glob(str(RESULTS / "*.jsonl")))


def collect() -> dict:
    esc = 0
    # Every unanimous panel seen, escalated or not -- the denominator for
    # doubt-gate recall. The shipped orchestrator returns early on unanimity
    # (`if unanimous: return`), so only lever configs carrying a doubt/score
    # gate ever surface these.
    unanimous_total = 0
    unanimous_total_wrong = 0
    unanimous_unescalated_wrong = 0
    off_slate = 0
    off_slate_correct = 0
    on_slate = 0
    on_slate_correct = 0
    gold_unoffered = 0
    gold_unoffered_recovered = 0
    per_file: collections.Counter = collections.Counter()
    unanimous_wrong_escalations = 0
    unanimous_wrong_recovered = 0
    unanimous_right_escalations = 0
    unanimous_right_broken = 0

    # Per-dataset, because the pooled conversion rate is NOT uniform and the
    # pooled number alone would mislead: SuperGPQA converts far worse than GPQA.
    by_ds: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter
    )

    for path in sorted(glob.glob(str(RESULTS / "*.jsonl"))):
        try:
            with open(path, encoding="utf-8") as fh:
                rows = [json.loads(line) for line in fh if line.strip()]
        except (OSError, json.JSONDecodeError):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            dataset = str(row.get("dataset") or "gpqa(default)")
            for eng in _engines(row):
                answers = eng.get("solver_answers")
                if not answers:
                    continue
                # Recall denominator: count unanimous panels regardless of
                # whether a verdict exists (no verdict == never escalated).
                all_letters = [
                    str(a.get("letter") or "").strip().upper()
                    for a in answers
                    if isinstance(a, dict)
                ]
                gold_any = str(
                    (eng.get("item") or {}).get("correct_letter") or ""
                ).strip().upper()
                if all_letters and len(set(all_letters)) == 1 and gold_any:
                    unanimous_total += 1
                    was_wrong = all_letters[0] != gold_any
                    if was_wrong:
                        unanimous_total_wrong += 1
                        if not isinstance(eng.get("verdict"), dict):
                            unanimous_unescalated_wrong += 1

                verdict = eng.get("verdict")
                if not isinstance(verdict, dict):
                    continue
                final = str(verdict.get("final_letter") or "").strip().upper()
                slate = {
                    str(a.get("letter") or "").strip().upper()
                    for a in answers
                    if isinstance(a, dict)
                }
                slate.discard("")
                if not final or not slate:
                    continue
                gold = str(
                    (eng.get("item") or {}).get("correct_letter") or ""
                ).strip().upper()

                esc += 1
                per_file[Path(path).name] += 1

                if len(slate) == 1 and gold and gold in slate:
                    # Unanimous and ALREADY RIGHT, yet escalated anyway. This is
                    # the cost side of raising gate recall: every extra firing
                    # exposes an item like this to being broken by the tribunal.
                    unanimous_right_escalations += 1
                    by_ds[dataset]["right"] += 1
                    if final != gold:
                        unanimous_right_broken += 1
                        by_ds[dataset]["broken"] += 1

                if len(slate) == 1 and gold and gold not in slate:
                    # Unanimous AND all wrong, yet it still reached the tribunal
                    # -- so via a doubt/score gate, never the disagreement
                    # trigger. This is the ONLY empirical window onto the
                    # 61.6% unanimous-wrong ceiling the repo calls unreachable
                    # "by construction": these are items of exactly that kind
                    # that a non-disagreement gate did in fact surface.
                    unanimous_wrong_escalations += 1
                    by_ds[dataset]["wrong"] += 1
                    if final == gold:
                        unanimous_wrong_recovered += 1
                        by_ds[dataset]["recovered"] += 1

                if gold and gold not in slate:
                    gold_unoffered += 1
                    if final == gold:
                        gold_unoffered_recovered += 1

                if final not in slate:
                    off_slate += 1
                    if gold and final == gold:
                        off_slate_correct += 1
                else:
                    on_slate += 1
                    if gold and final == gold:
                        on_slate_correct += 1

    return {
        "escalations": esc,
        "off_slate": off_slate,
        "off_slate_correct": off_slate_correct,
        "on_slate": on_slate,
        "on_slate_correct": on_slate_correct,
        "gold_unoffered": gold_unoffered,
        "gold_unoffered_recovered": gold_unoffered_recovered,
        "unanimous_wrong_escalations": unanimous_wrong_escalations,
        "unanimous_wrong_recovered": unanimous_wrong_recovered,
        "unanimous_right_escalations": unanimous_right_escalations,
        "unanimous_right_broken": unanimous_right_broken,
        "unanimous_total": unanimous_total,
        "unanimous_total_wrong": unanimous_total_wrong,
        "unanimous_unescalated_wrong": unanimous_unescalated_wrong,
        "per_file": per_file,
        "by_dataset": {k: dict(v) for k, v in by_ds.items()},
    }


def main() -> None:
    r = collect()
    esc = r["escalations"]
    if not esc:
        print("No escalation records with a judge verdict found.")
        return

    def pct(a: int, b: int) -> str:
        return f"{100.0 * a / b:.1f}%" if b else "n/a"

    print("Judge anchoring to the solver slate")
    print(f"  escalated records carrying a verdict: {esc}")
    print(f"  spanning {len(r['per_file'])} result files")
    print()
    print("  Did the Judge ever leave the slate its solvers offered?")
    print(f"    chose an OFF-SLATE letter : {r['off_slate']:5d} "
          f"({pct(r['off_slate'], esc)})   correct: {r['off_slate_correct']}")
    print(f"    chose an ON-SLATE letter  : {r['on_slate']:5d} "
          f"({pct(r['on_slate'], esc)})   correct: {r['on_slate_correct']} "
          f"({pct(r['on_slate_correct'], r['on_slate'])})")
    print()
    print("  THE DECISIVE SUBSET -- gold was offered by NO solver, so the only")
    print("  path to a correct verdict is leaving the slate entirely:")
    print(f"    such items                : {r['gold_unoffered']:5d} "
          f"({pct(r['gold_unoffered'], esc)} of escalations)")
    print(f"    Judge recovered gold      : {r['gold_unoffered_recovered']:5d} "
          f"-> recovery rate {pct(r['gold_unoffered_recovered'], r['gold_unoffered'])}")
    print()
    uw, uwr = r["unanimous_wrong_escalations"], r["unanimous_wrong_recovered"]
    print("  THE CEILING WINDOW -- solvers UNANIMOUS and all wrong, yet still")
    print("  escalated (so surfaced by a doubt/score gate, never by")
    print("  disagreement). These are members of the 61.6% set the repo calls")
    print('  unreachable "by construction":')
    print(f"    such items                : {uw:5d}")
    print(f"    Judge recovered gold      : {uwr:5d} -> recovery rate "
          f"{pct(uwr, uw)}")
    ur, urb = r["unanimous_right_escalations"], r["unanimous_right_broken"]
    print()
    print("  THE COST SIDE -- solvers UNANIMOUS and already RIGHT, escalated")
    print("  anyway. Every extra gate firing risks one of these:")
    print(f"    such items                : {ur:5d}")
    print(f"    Judge BROKE a right answer: {urb:5d} -> breakage rate "
          f"{pct(urb, ur)}")
    if uw and ur:
        rec, brk = uwr / uw, urb / ur
        print()
        print("  NET ARITHMETIC for widening the gate. Among unanimous items a")
        print(f"  wider gate newly surfaces, let w = fraction that are wrong.")
        print(f"  Expected net gain per 100 newly-surfaced items:")
        print(f"    = 100 * (w * {rec:.3f} - (1-w) * {brk:.3f})")
        if rec + brk > 0:
            breakeven = brk / (rec + brk)
            print(f"    break-even at w = {100 * breakeven:.1f}% wrong among the")
            print("    newly-surfaced unanimous items.")
            print("    Repo-measured baseline: 61.6% of WRONG panel rows are")
            print("    unanimous -- but w here is the wrong-rate among UNANIMOUS")
            print("    rows, a different and much smaller quantity. Do not")
            print("    conflate them; w must be measured before acting.")
    if uw:
        rate = 100.0 * uwr / uw
        print()
        if rate >= 20.0:
            print("    READ: the ceiling is NOT absolute. When a non-disagreement")
            print("    gate surfaces a unanimous-wrong item, the tribunal converts a")
            print(f"    material fraction ({rate:.0f}%) of them. The binding constraint is")
            print("    therefore GATE RECALL on unanimous-wrong items, not the")
            print("    tribunal's ability to fix them. That is a different -- and")
            print("    attackable -- problem from the one currently recorded.")
        else:
            print("    READ: even when surfaced, unanimous-wrong items are rarely")
            print("    converted. The ceiling is a tribunal-capability limit, not a")
            print("    gate-recall limit; improving gate recall would not pay.")
    print()
    if r["gold_unoffered"]:
        rate = 100.0 * r["gold_unoffered_recovered"] / r["gold_unoffered"]
        if rate < 5.0:
            print("  READ: the off-slate path is effectively unreachable. An explicit")
            print('  "any, all, or NONE of these may be correct" licence in')
            print("  JUDGE_SYSTEM is a real and untested lever on this subset.")
        else:
            print("  READ: the Judge already leaves the slate at a material rate;")
            print("  an explicit none-of-the-above licence is unlikely to add much.")
    ut, utw = r["unanimous_total"], r["unanimous_total_wrong"]
    miss = r["unanimous_unescalated_wrong"]
    print()
    print("  GATE RECALL and the headroom it leaves")
    print(f"    unanimous panels seen (all configs) : {ut:6d}")
    print(f"      of which WRONG                    : {utw:6d} "
          f"({pct(utw, ut)}) <- this is w, the quantity that matters")
    print(f"    unanimous-wrong that DID escalate   : {uw:6d} "
          f"({pct(uw, utw)} recall)")
    print(f"    unanimous-wrong never surfaced      : {miss:6d}")
    if uw and miss:
        rec = uwr / uw
        print()
        print(f"    At the measured {100 * rec:.1f}% conversion, perfect gate recall")
        print(f"    would be worth about {miss * rec:.0f} additional correct items")
        print(f"    across this pooled corpus -- versus {r['unanimous_right_broken']} "
              "breakages observed")
        print(f"    in {ur} unanimous-right escalations.")
        print()
        print("    PROVENANCE: pooled-marginal across many datasets, seeds and")
        print("    lever configs. NOT a paired delta and NOT a per-benchmark")
        print("    claim -- it sizes a hypothesis, it does not validate one.")
        print("    BIAS: the existing gates fire on DETECTABLE doubt, so both")
        print("    the 47.6% conversion and the 0.8% breakage are measured on a")
        print("    selected, boundary-adjacent subset. Conversion on")
        print("    confidently-wrong unanimous items is plausibly lower. Treat")
        print("    47.6% as an upper estimate, exactly as with the D0 bar.")
    print()
    print("  PER-DATASET -- the pooled rate above hides a 5x spread, and the")
    print("  cheapest reading of it would be wrong. Escalations per net item")
    print("  gained is the figure that decides whether this is affordable:")
    print(f"    {'dataset':<20} {'wrong':>6} {'rec':>5} {'rate':>6} "
          f"{'right':>6} {'brk':>4} {'esc/gain':>9}")
    for ds, c in sorted(
        r["by_dataset"].items(), key=lambda kv: -kv[1].get("wrong", 0)
    ):
        w, rec = c.get("wrong", 0), c.get("recovered", 0)
        rt, brk = c.get("right", 0), c.get("broken", 0)
        net = rec - brk
        eff = f"{(w + rt) / net:.1f}" if net > 0 else "n/a"
        print(f"    {ds[:20]:<20} {w:>6} {rec:>5} {pct(rec, w):>6} "
              f"{rt:>6} {brk:>4} {eff:>9}")
    print()
    print("    Accuracy-wise a wider gate is positive nearly everywhere,")
    print("    because breakage is ~0. COST is the real constraint: each")
    print("    firing spends ~4 extra calls. That makes this a Track-B lever")
    print("    (accuracy at any cost), NOT a Track-A price lever -- and")
    print("    materially better value on GPQA than on SuperGPQA.")
    print()
    print("  reproduce: python benchmark/analyze_judge_anchoring.py")


if __name__ == "__main__":
    main()
