"""KI-0R -- CAS-gate replay on the known-wrong (and matched known-right) pools.

docs/spec-sci1-and-knowledge-injection.md section 3.1, verbatim. Fires BEFORE
any live knowledge-injection arm because it measures the single unmeasured
parameter that KI-1 Arm A (2.30M) and KI-2 (2.76M) both depend on, for ~2.5%
of their combined cost.

THE QUESTION. `verified_gate_cas` escalates a unanimous panel only when
`cas_gate_check` emits a parseable relation AND the local `sympy_check`
returns "fail". Its projected value assumed p_check x y_detect = 0.437, built
as 0.873 x 0.50 -- where 0.873 is a number benchmark/results/pool_checkability.md
itself calls "the CEILING the heuristic supports, not a validated floor", and
0.50 was invented. This script measures the real product.

WHY IT MIGHT BE SMALL (the structural argument, stated before the data exists
so a low number cannot be retro-spun): CAS_EXTRACT_SYSTEM asks the model to
write "LHS = RHS with the chosen answer's numeric value already substituted
in" -- FROM ITS OWN TRANSCRIPT. A model reconstructing its own wrong chain
writes a SELF-CONSISTENT equation, sympy_check returns "pass", and nothing
escalates. CAS can therefore only catch ARITHMETIC SLIPS -- and three seats at
T=0.3/0.6/0.9 agreeing unanimously actively selects AGAINST stochastic slips
and FOR correlated conceptual/setup error. Unanimity filters out precisely the
error class CAS can see. Expected outcome: FAIL the 0.311 gate.

WHY THE unanimous-RIGHT ARMS EXIST. Sensitivity alone gives you `b` but not
`c`. Without a false-positive rate you cannot compute a net, and you cannot run
the cost-per-recovery non-inferiority test the review requires in place of an
accuracy McNemar. The matched right-pool sample is drawn with a fixed seed so
the specificity estimate is reproducible.

CONTAMINATION FIREWALL. Item selection reads THIS REPO'S OWN LOGGED `correct`
FIELD from committed run files -- our own past grading, not an answer-key
lookup. No key is retrieved or inspected. The gold letter is never passed to
the extractor; `cas_gate_check` sees only question/choices/transcript/plurality
letter, exactly as it would live.

SCOPE. Deliberately identical to benchmark/classify_pool_checkability.py's:
control-lever rows only (lever == "control" or the untagged legacy files that
ran the same unmodified 3-seat panel), GPQA + SuperGPQA-hard only, deduped by
question_id. Pooling other levers would mix "unanimous under a DIFFERENT
engine" into what is supposed to be the shipped panel's blind spot.

PAID. One MECHANICAL_MODEL (qwen3.6-flash, thinking=False) call per item.
sympy_check is offline and free.

    python -m benchmark.replay_cas_gate_on_wrong_pool \
        --datasets gpqa,supergpqa \
        --match-right-sample-seed 8419 \
        --out benchmark/results/KI0R_cas_gate_replay.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
from pathlib import Path

from quorumqa.qwen_client import QwenClient
from quorumqa.schemas import SolverAnswer
from quorumqa.tools.mcp_server import sympy_check

from benchmark.classify_pool_checkability import (
    RESULTS_DIR,
    _dataset_for,
    _is_control_lever,
    _iter_jsonl,
)
from benchmark.lever_experiments import cas_gate_check

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# The pre-registered gate. Gains >= 5 net at n=180 requires
# p_check x y_detect >= 5 / (33.8 x 0.476) = 0.311.
GATE_THRESHOLD = 0.311

_MAX_ATTEMPTS = 3
_BACKOFF_BASE_SECONDS = 5


def _unanimous(engine: dict) -> bool:
    """3 solver letters all agree. Mirrors classify_pool_checkability's
    _is_unanimous_wrong minus the correctness half, so the two scripts pool
    the same rows."""
    answers = engine.get("solver_answers") or []
    if len(answers) != 3:
        return False
    letters = {str(a.get("letter", "")).strip().upper() for a in answers}
    return len(letters) == 1 and "" not in letters


def inventory_both_pools(datasets) -> dict:
    """{dataset: {"wrong": {qid: rec}, "right": {qid: rec}}}, deduped and
    DISJOINT.

    Unlike classify_pool_checkability.inventory_and_pool (which keeps only
    question/choices, since a regex is all it needs), this retains
    solver_answers and plurality_letter -- cas_gate_check requires the full
    transcript.

    THE DISJOINTNESS RULE, and why it is not cosmetic. The same question_id can
    be unanimous-WRONG at one seed and unanimous-RIGHT at another: the seats are
    stochastic (T=0.3/0.6/0.9) and every control seed re-runs them. A naive
    two-bucket pass therefore puts ~dozens of items in BOTH pools, which would
    (a) let items from the sensitivity target leak into the specificity sample,
    biasing the false-positive rate toward the very items CAS is supposed to
    catch, and (b) double-count them in the cost arithmetic.

    Resolution, chosen to match what each number is FOR:
      - `wrong` = every item observed unanimous-wrong in ANY control run. This
        is exactly the pool KI-1 Arm A must convert, and it matches
        classify_pool_checkability's own across-seeds pooling semantics.
      - `right` = items NEVER observed unanimous-wrong in any control run. A
        clean specificity pool: firing on one of these is unambiguously a false
        positive, with no "well, it was wrong at another seed" ambiguity.
    Each retained transcript comes from a run whose outcome MATCHES its bucket,
    so the replay always sees the transcript the label refers to.
    """
    wrong = {ds: {} for ds in datasets}
    right_candidates = {ds: {} for ds in datasets}

    for path in sorted(RESULTS_DIR.glob("*.jsonl")):
        for row in _iter_jsonl(path):
            engine = row.get("engine")
            if not isinstance(engine, dict) or "solver_answers" not in engine:
                continue
            if not _is_control_lever(row):
                continue
            ds = _dataset_for(row, path)
            if ds is None or ds not in wrong:
                continue
            if not _unanimous(engine):
                continue
            item = engine.get("item") or {}
            qid = item.get("question_id")
            question = item.get("question")
            choices = item.get("choices") or []
            if not qid or not question or not choices:
                continue
            rec = {
                "question_id": qid,
                "question": question,
                "choices": choices,
                "solver_answers": engine["solver_answers"],
                "plurality_letter": engine.get("plurality_letter"),
                "source": path.name,
            }
            target = right_candidates[ds] if engine.get("correct") else wrong[ds]
            target.setdefault(qid, rec)

    # Any item ever seen unanimous-wrong belongs to the sensitivity pool only.
    return {
        ds: {
            "wrong": wrong[ds],
            "right": {q: r for q, r in right_candidates[ds].items() if q not in wrong[ds]},
        }
        for ds in datasets
    }


def _to_solver_answers(raw: list[dict]) -> list[SolverAnswer]:
    """cas_gate_check reads a.lens and a.reasoning off objects; the logs hold
    dicts. Rebuild the real schema object rather than a duck-typed shim so any
    field drift fails loudly here instead of silently producing an empty
    transcript."""
    return [SolverAnswer(**a) for a in raw]


async def _replay_one(client, rec: dict, semaphore, sleep_fn=asyncio.sleep) -> dict | None:
    """One extraction call + the local sympy check. Returns None only if every
    attempt failed (a dropped item is reported, never silently skipped)."""
    for attempt in range(_MAX_ATTEMPTS):
        try:
            async with semaphore:
                checkable, relation, candidate, usage = await asyncio.to_thread(
                    cas_gate_check,
                    client,
                    rec["question"],
                    rec["choices"],
                    _to_solver_answers(rec["solver_answers"]),
                    rec["plurality_letter"],
                )
            break
        except Exception as exc:
            if attempt == _MAX_ATTEMPTS - 1:
                log.error("%s: DROPPED after %d attempts (%s: %s)",
                          rec["question_id"], _MAX_ATTEMPTS, type(exc).__name__, str(exc)[:120])
                return None
            backoff = _BACKOFF_BASE_SECONDS * (2 ** attempt)
            log.warning("%s: attempt %d/%d failed (%s), retrying in %ds",
                        rec["question_id"], attempt + 1, _MAX_ATTEMPTS, type(exc).__name__, backoff)
            await sleep_fn(backoff)

    status, detail = "not_checkable", ""
    if checkable and relation:
        check = sympy_check(relation, candidate)
        status, detail = check["status"], check.get("detail", "")

    return {
        "question_id": rec["question_id"],
        "checkable": checkable,
        "relation": relation,
        "candidate": candidate,
        "status": status,          # not_checkable | pass | fail | unparseable
        "detail": detail,
        "gate_would_fire": status == "fail",   # exactly lever_experiments' rule
        "tokens": usage.input_tokens + usage.output_tokens,
    }


def summarize(rows: list[dict], n_attempted: int) -> dict:
    """p_check = emitted a checkable, parseable relation; y_detect = of those,
    sympy said 'fail'. The product is what the gate tests."""
    n = len(rows)
    checkable = [r for r in rows if r["checkable"]]
    parseable = [r for r in checkable if r["status"] in ("pass", "fail")]
    failed = [r for r in parseable if r["status"] == "fail"]
    unparseable = [r for r in checkable if r["status"] == "unparseable"]
    return {
        "n_attempted": n_attempted,
        "n_completed": n,
        "n_dropped": n_attempted - n,
        "n_checkable": len(checkable),
        "n_parseable": len(parseable),
        "n_unparseable": len(unparseable),
        "n_gate_fires": len(failed),
        "p_check": (len(parseable) / n) if n else None,
        "y_detect": (len(failed) / len(parseable)) if parseable else None,
        "product": (len(failed) / n) if n else None,
        "tokens": sum(r["tokens"] for r in rows),
    }


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval -- correct at the small n and near-zero rates this
    replay is expected to produce, where a normal approximation is not."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


async def main(datasets, sample_seed: int, out_path: Path, concurrency: int, limit: int | None) -> None:
    pools = inventory_both_pools(datasets)
    rng = random.Random(sample_seed)

    plan = []
    for ds in datasets:
        wrong = sorted(pools[ds]["wrong"].values(), key=lambda r: r["question_id"])
        right_all = sorted(pools[ds]["right"].values(), key=lambda r: r["question_id"])
        # Matched sample: same size as the wrong pool, so specificity is
        # estimated at comparable precision to sensitivity.
        k = min(len(wrong), len(right_all))
        right = rng.sample(right_all, k) if k else []
        if limit:
            wrong, right = wrong[:limit], right[:limit]
        plan.append((ds, "wrong", wrong))
        plan.append((ds, "right", right))
        log.info("%s: %d unanimous-wrong, %d unanimous-right available, sampling %d",
                 ds, len(wrong), len(right_all), len(right))

    client = QwenClient()
    semaphore = asyncio.Semaphore(concurrency)
    results = {}
    for ds, bucket, recs in plan:
        if not recs:
            results[(ds, bucket)] = ([], 0)
            continue
        log.info("replaying %s/%s: %d items", ds, bucket, len(recs))
        out = await asyncio.gather(*[
            asyncio.ensure_future(_replay_one(client, rec, semaphore)) for rec in recs
        ])
        results[(ds, bucket)] = ([r for r in out if r is not None], len(recs))

    report = _render(results, datasets, sample_seed)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    raw_path = out_path.with_suffix(".json")
    raw_path.write_text(json.dumps(
        {f"{ds}/{bucket}": {"summary": summarize(rows, n), "rows": rows}
         for (ds, bucket), (rows, n) in results.items()},
        indent=2, default=str,
    ), encoding="utf-8")

    print(report)
    log.info("Wrote %s and %s", out_path, raw_path)


def _render(results, datasets, sample_seed: int) -> str:
    L = ["# KI-0R -- CAS-gate replay on the known-wrong and matched known-right pools", ""]
    L.append("**docs/spec-sci1-and-knowledge-injection.md section 3.1.** Measures "
             "`p_check x y_detect` -- the fraction of items on which `cas_gate_check` emits a "
             "parseable relation AND local `sympy_check` returns `fail`, i.e. the fraction where "
             "`verified_gate_cas` would actually escalate.")
    L.append("")
    L.append(f"**Pre-registered gate: product >= {GATE_THRESHOLD} on SuperGPQA-hard.** Below that, "
             "KI-1 Arm A (`verified_gate_cas`, 2.30M) and KI-2 (2.76M) are both dead -- the "
             "mechanical-verification branch of knowledge injection is closed for MC-science.")
    L.append("")
    L.append(f"Matched unanimous-right sample seed: `analysis:{sample_seed}`. Item selection reads "
             "this repo's own logged `correct` field; **no answer key was retrieved**.")
    L.append("")

    total_tokens = 0
    for ds in datasets:
        L.append(f"## {ds}")
        L.append("")
        L.append("| pool | n | checkable | parseable | unparseable | gate fires | p_check | y_detect | product |")
        L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for bucket in ("wrong", "right"):
            rows, n_att = results.get((ds, bucket), ([], 0))
            s = summarize(rows, n_att)
            total_tokens += s["tokens"]
            pc = f"{s['p_check']*100:.1f}%" if s["p_check"] is not None else "n/a"
            yd = f"{s['y_detect']*100:.1f}%" if s["y_detect"] is not None else "n/a"
            pr = f"{s['product']*100:.1f}%" if s["product"] is not None else "n/a"
            L.append(f"| unanimous-**{bucket}** | {s['n_completed']} | {s['n_checkable']} | "
                     f"{s['n_parseable']} | {s['n_unparseable']} | {s['n_gate_fires']} | {pc} | {yd} | {pr} |")
        L.append("")

        rows, n_att = results.get((ds, "wrong"), ([], 0))
        s = summarize(rows, n_att)
        if s["n_completed"]:
            lo, hi = _wilson(s["n_gate_fires"], s["n_completed"])
            L.append(f"**{ds} sensitivity product = {s['product']*100:.1f}%** "
                     f"(Wilson 95% CI [{lo*100:.1f}%, {hi*100:.1f}%], "
                     f"{s['n_gate_fires']}/{s['n_completed']}).")
            verdict = "CLEARS" if (s["product"] or 0) >= GATE_THRESHOLD else "FAILS"
            L.append("")
            L.append(f"- Against the {GATE_THRESHOLD} gate: **{verdict}**.")
            if hi < GATE_THRESHOLD:
                L.append(f"- The entire 95% CI lies below the gate, so this is not a power problem.")
        rrows, rn = results.get((ds, "right"), ([], 0))
        rs = summarize(rrows, rn)
        if rs["n_completed"]:
            L.append(f"- False-positive rate on unanimous-**right**: "
                     f"**{rs['product']*100:.1f}%** ({rs['n_gate_fires']}/{rs['n_completed']}) -- "
                     f"these are items the gate would escalate that were already correct.")
        L.append("")

    L.append("## Cost")
    L.append("")
    L.append(f"**{total_tokens:,} tokens** (one `qwen3.6-flash` extraction call per item; "
             "`sympy_check` is offline and free).")
    L.append("")
    L.append("Reproduce: `python -m benchmark.replay_cas_gate_on_wrong_pool "
             f"--datasets {','.join(datasets)} --match-right-sample-seed {sample_seed}`")
    return "\n".join(L)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--datasets", type=str, default="gpqa,supergpqa")
    parser.add_argument("--match-right-sample-seed", type=int, required=True,
                        help="fixed seed for the matched unanimous-right specificity sample (analysis: namespace)")
    parser.add_argument("--out", type=str, default="benchmark/results/KI0R_cas_gate_replay.md")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--limit", type=int, default=None, help="cap items per pool (smoke tests only)")
    args = parser.parse_args()
    asyncio.run(main(
        [d.strip() for d in args.datasets.split(",") if d.strip()],
        args.match_right_sample_seed, Path(args.out), args.concurrency, args.limit,
    ))
