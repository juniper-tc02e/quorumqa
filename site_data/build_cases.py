"""Extract a curated, web-ready case set from the frozen n=90 benchmark run.

Output feeds the MagiAchiral public site: the hero deliberation replay, the
scoreboard, and the case gallery. Everything here is already public -- GPQA
questions, their public answer key, and our own model outputs. No credentials,
no infrastructure identifiers.
"""

import json
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUN = ROOT / "benchmark" / "results" / "full_run2.jsonl"
OUT = pathlib.Path(__file__).resolve().parent / "cases.json"

# The hero replay: panel voted D, Judge overruled to C, C is correct.
HERO_ID = "recIj8lR4tuDgrHou"


def cost_of(calls):
    return round(sum(c.get("cost_usd", 0.0) for c in calls), 6)


def tokens_of(calls):
    """Total input+output tokens.

    Tokens, not dollars, because the Token Plan bills tokens and the two point
    in OPPOSITE directions here: the engine is ~11% cheaper in dollars and
    ~2.6x more expensive in tokens.
    """
    return sum(c.get("input_tokens", 0) + c.get("output_tokens", 0) for c in calls)


def role_costs(calls):
    by_role = {}
    for c in calls:
        by_role[c["role"]] = round(by_role.get(c["role"], 0.0) + c.get("cost_usd", 0.0), 6)
    return by_role


def shape_case(rec):
    eng = rec["engine"]
    base = rec["baseline"]
    sc5 = rec["self_consistency5"]
    item = eng["item"]

    overturned = bool(eng.get("escalated")) and eng.get("final_letter") != eng.get("plurality_letter")

    if not eng.get("escalated"):
        verdict_kind = "unanimous"
    elif overturned:
        verdict_kind = "overruled"
    else:
        verdict_kind = "confirmed"

    return {
        "id": item["question_id"],
        "subject": item["subject"],
        "question": item["question"],
        "choices": item["choices"],
        "correct_letter": item["correct_letter"],
        "solvers": [
            {
                "letter": s["letter"],
                "confidence": s["confidence"],
                "reasoning": s["reasoning"],
                "lens": s["lens"],
            }
            for s in eng["solver_answers"]
        ],
        "plurality_letter": eng.get("plurality_letter"),
        "escalated": bool(eng.get("escalated")),
        "overturned": overturned,
        "verdict_kind": verdict_kind,
        "skeptic": eng.get("skeptic_rebuttal"),
        "verifier": eng.get("verifier_findings") or [],
        "verdict": eng.get("verdict"),
        "final_letter": eng.get("final_letter"),
        "correct": bool(eng.get("correct")),
        "false_escalation": bool(eng.get("false_escalation")),
        "cost_usd": cost_of(eng["calls"]),
        "cost_by_role": role_costs(eng["calls"]),
        "latency_s": round(eng.get("latency_s", 0.0), 2),
        "baseline": {
            "letter": base.get("answer_letter"),
            "correct": bool(base.get("correct")),
            "cost_usd": cost_of(base["calls"]),
            "latency_s": round(base.get("latency_s", 0.0), 2),
        },
        "self_consistency5": {
            "letter": sc5.get("answer_letter"),
            "correct": bool(sc5.get("correct")),
            "cost_usd": cost_of(sc5["calls"]),
        },
    }


def main():
    records = [json.loads(line) for line in RUN.open(encoding="utf-8")]
    cases = [shape_case(r) for r in records]
    n = len(cases)

    engine_correct = sum(c["correct"] for c in cases)
    base_correct = sum(c["baseline"]["correct"] for c in cases)
    sc5_correct = sum(c["self_consistency5"]["correct"] for c in cases)
    escalated = [c for c in cases if c["escalated"]]
    overturns = [c for c in cases if c["overturned"]]
    good_overturns = [c for c in overturns if c["correct"]]
    unanimous = [c for c in cases if not c["escalated"]]

    # Per-path token cost, computed from THIS run's own call logs. `records`
    # rather than `cases` because shape_case drops the raw call list.
    eng_toks = [tokens_of(r["engine"]["calls"]) for r in records]
    base_toks = [tokens_of(r["baseline"]["calls"]) for r in records]
    un_toks = [t for r, t in zip(records, eng_toks) if not r["engine"].get("escalated")]
    esc_toks = [t for r, t in zip(records, eng_toks) if r["engine"].get("escalated")]
    tok_engine = round(sum(eng_toks) / len(eng_toks))
    tok_base = round(sum(base_toks) / len(base_toks))
    tok_unanimous = round(sum(un_toks) / len(un_toks)) if un_toks else 0
    tok_escalated = round(sum(esc_toks) / len(esc_toks)) if esc_toks else 0

    # Cases where the engine was right and a single flagship call was wrong.
    #
    # NOT "the cheap society beat the expensive model": measured 2026-08-03,
    # 2 of these 5 ESCALATED and therefore consumed a `qwen3.7-max` judge call
    # -- the same model as the baseline they beat -- so for those two the
    # engine did not out-perform the flagship, it *routed to* it. Only 3 were
    # answered by the cheap panel alone. The breakdown is emitted below so the
    # distinction is available to any consumer rather than lost in one count.
    #
    # The aggregate claim is weaker still: on identical items across 3 fresh
    # seeds the full stack is net +1, p=0.50 against one flagship call
    # (docs/FINDINGS-2026-08.md).
    beats_flagship = [c for c in cases if c["correct"] and not c["baseline"]["correct"]]
    bf_panel_only = [c for c in beats_flagship if not c["escalated"]]
    bf_escalated = [c for c in beats_flagship if c["escalated"]]

    stats = {
        "n": n,
        "accuracy": {
            "engine": round(100 * engine_correct / n, 1),
            "baseline": round(100 * base_correct / n, 1),
            "self_consistency5": round(100 * sc5_correct / n, 1),
        },
        "cost_per_question": {
            "engine": round(sum(c["cost_usd"] for c in cases) / n, 5),
            "baseline": round(sum(c["baseline"]["cost_usd"] for c in cases) / n, 5),
            "self_consistency5": round(sum(c["self_consistency5"]["cost_usd"] for c in cases) / n, 5),
        },
        "unanimous_cost_per_question": round(
            sum(c["cost_usd"] for c in unanimous) / max(len(unanimous), 1), 5
        ),
        "escalated_cost_per_question": round(
            sum(c["cost_usd"] for c in escalated) / max(len(escalated), 1), 5
        ),
        "escalation_rate": round(100 * len(escalated) / n, 1),
        "unanimous_rate": round(100 * len(unanimous) / n, 1),
        "false_escalation_rate": round(
            100 * sum(c["false_escalation"] for c in escalated) / max(len(escalated), 1), 1
        ),
        "overturns": len(overturns),
        "overturns_correct": len(good_overturns),
        "overturn_precision": round(100 * len(good_overturns) / max(len(overturns), 1), 1),
        "beats_flagship": len(beats_flagship),
        # See the comment at the definition: this count is NOT "cheap beat
        # expensive" -- the escalated ones used a flagship judge.
        "flagship_miss_engine_hit": {
            "total": len(beats_flagship),
            "panel_only": len(bf_panel_only),
            "judge_escalated": len(bf_escalated),
        },
        "cost_unit": (
            f"USD, pre-Token-Plan pricing (superseded 2026-08; see "
            f"docs/FINDINGS-2026-08.md). In tokens, the unit that now bills, "
            f"this run's engine costs {tok_engine:,} vs the baseline's "
            f"{tok_base:,} per item -- {tok_engine / tok_base:.2f}x MORE."
        ),
        # COMPUTED from this run, never hardcoded. Until 2026-08-03 this field
        # held a literal 8,690 / 2,792 -- correct numbers, wrong run. That pair
        # is the TB-1 paired item set (seeds 1001/2311/3407, n=265); everything
        # else in this stats block describes the frozen n=90 seed-42 run, whose
        # own figures are 9,013 / 3,415. A stats block about one run must quote
        # that run's cost, and computing it makes the mismatch impossible.
        "tokens_per_question": {
            "engine": tok_engine,
            "baseline": tok_base,
            "unanimous_path": tok_unanimous,
            "escalated_path": tok_escalated,
            "multiple_vs_baseline": round(tok_engine / tok_base, 2),
            "measured_on": (
                "THIS run: the frozen n=90 seed-42 submission run, the same run "
                "every other number in this stats block describes. Source: "
                "benchmark/results/submission_token_economics.json."
            ),
            "do_not_confuse_with": (
                "8,690 / 2,792 (3.1x), quoted in README.md, docs/architecture.md "
                "and docs/FINDINGS-2026-08.md. That pair is the TB-1 paired item "
                "set -- seeds 1001/2311/3407, n=265 shared items -- a DIFFERENT "
                "run, not a competing estimate of the same quantity."
            ),
        },
        "median_latency_s": round(
            sorted(c["latency_s"] for c in cases)[n // 2], 2
        ),
        "subjects": dict(Counter(c["subject"] for c in cases).most_common()),
    }

    # Gallery: every overturn (including the three the Judge got wrong -- the
    # honest ones stay in), the flagship-beating cases, plus a representative
    # spread of confirmed escalations and cheap unanimous answers.
    picked, seen = [], set()

    def take(pool, limit=None):
        count = 0
        for c in pool:
            if c["id"] in seen:
                continue
            if limit is not None and count >= limit:
                break
            seen.add(c["id"])
            picked.append(c)
            count += 1

    take([c for c in cases if c["id"] == HERO_ID])
    take(overturns)
    take(sorted(beats_flagship, key=lambda c: -c["cost_usd"]), limit=6)
    take([c for c in escalated if not c["overturned"]], limit=6)
    take(sorted(unanimous, key=lambda c: c["cost_usd"]), limit=8)

    payload = {
        "generated_from": RUN.name,
        "stats": stats,
        "hero_case_id": HERO_ID,
        "cases": picked,
    }

    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")

    size_kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT.name}: {len(picked)} cases, {size_kb:.0f} KB")
    print(json.dumps(stats, indent=1))
    print("\nhero case present:", any(c["id"] == HERO_ID for c in picked))
    print("verdict kinds:", Counter(c["verdict_kind"] for c in picked).most_common())


if __name__ == "__main__":
    main()
