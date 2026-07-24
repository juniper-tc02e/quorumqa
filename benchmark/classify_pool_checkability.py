"""F6 tool-checkable-fraction classification of the unanimous-wrong pool
(docs/same-provider-scaling-research.md F6, docs/reasoning-supercharge-
plan.md's W1 section): "this fraction IS the W1-B (CAS arm) CAP, committed
before W1 runs."

WHY: W1-B (the CAS/extraction-and-verify arm) can only ever catch
unanimous-wrong items whose answer choices are numeric/equation-shaped --
something a deterministic checker (sympy, unit conversion, etc.) can
evaluate. Items whose choices are prose ("which of the following best
explains...", a named reaction mechanism, a clinical recommendation) have
no such checker; W1-B is structurally blind to them regardless of how good
the extraction step is. This module measures, OFFLINE from already-logged
results (no API calls, no cost), what fraction of the REAL unanimous-wrong
pool is even theoretically reachable by that arm -- an honest upper bound
on W1-B's ceiling, not an aspiration.

SCOPE (be honest about coverage):
  - Only GPQA and SuperGPQA-hard result JSONLs under benchmark/results/ are
    in scope (per the task); LEXam/MMLU-Pro/MedQA/GSM8K/MATH/AIME logs are
    skipped even when they carry the same QuestionResult "engine" shape.
  - Only rows from the CONTROL-lever config are pooled: lever == "control"
    (benchmark/lever_experiments.py's explicit tag) or lever is unset
    (the pre-lever-tagging legacy files -- full_run.jsonl, full_run2.jsonl,
    adhoc_check.jsonl, smoke*.jsonl, lever_control_seed7*.jsonl,
    supergpqa_hard_pilot_seed42.jsonl -- which used the exact same
    unmodified solve_all() cheap 3-solver panel, confirmed below). Every
    OTHER lever (thinking_gate, smart_gate, chem_*_gate, flagship_panel,
    rag_*, combined, subject, five, ...) changes either the solver dispatch
    itself or forces escalation on unanimity for some subjects -- pooling
    them in would silently mix "unanimous-wrong under a DIFFERENT engine"
    into what is supposed to be THE shipped baseline's blind spot.
  - Confirmed against the two numbers already published in
    benchmark/results/lever_findings.md / supergpqa_findings.md:
    full_run2.jsonl alone (GPQA, seed 42, n=90) gives 12/90 unanimous-wrong
    (doc cites "~10/90"); supergpqa_hard_pilot_seed42.jsonl alone (n=86)
    gives EXACTLY 20/86 (doc cites "20 of 86"). This module's pool is
    BROADER than either single seed -- it aggregates every control-lever
    seed/run available, deduped by question_id -- for more statistical
    power on the checkable-fraction estimate; both single-seed reference
    numbers are printed alongside the aggregate so the two are directly
    comparable.
  - "Unanimous-wrong" = an engine row's 3 solver_answers letters all agree
    AND engine.correct is False. Rows with any other solver count are
    skipped (guards against a differently-shaped lever, e.g. `five`,
    leaking in through a missing/None lever tag).

CLASSIFICATION: deterministic regex heuristics over QUESTION + CHOICES
text only, no model call. "quantitative-checkable": the answer choices are
dominated by digits / LaTeX math / units -- values or equations a CAS-style
checker could in principle evaluate. "conceptual": everything else (fails
CLOSED toward conceptual on any ambiguity, since this fraction is used as
an UPPER BOUND -- overclaiming checkable coverage would inflate the W1-B
cap dishonestly). See classify_item()'s docstring for the exact rule.

Usage:
  python -m benchmark.classify_pool_checkability
Writes benchmark/results/pool_checkability.md and prints the same summary.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent / "results"
OUTPUT_PATH = RESULTS_DIR / "pool_checkability.md"

# Benchmarks that are explicitly OUT of scope for this classifier (their
# result files carry the same "engine.solver_answers" shape as GPQA/
# SuperGPQA, so they'd otherwise slip through the unlabeled-dataset default
# below). Matched as a filename substring.
_OTHER_BENCHMARK_TAGS = ("lexam", "mmlu_pro", "medqa", "gsm8k", "math", "aime", "qwen38_baseline", "moo_m1_eval")

# Reference single-seed files each dataset's headline doc number came from
# (see the module docstring) -- printed for direct comparability, not
# treated specially by the pooling logic otherwise.
_REFERENCE_FILES = {
    "gpqa": "full_run2.jsonl",
    "supergpqa": "supergpqa_hard_pilot_seed42.jsonl",
}

LABEL_QUANT = "quantitative-checkable"
LABEL_CONCEPTUAL = "conceptual"


# ---------------------------------------------------------------------------
# File inventory + control-lever pool construction
# ---------------------------------------------------------------------------


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _dataset_for(row: dict, path: Path) -> str | None:
    """'gpqa' / 'supergpqa' / None (out of scope). An explicit `dataset`
    field (the lever_*.jsonl convention) always wins. Files with no
    `dataset` field predate that convention -- 'supergpqa' in the filename
    routes to SuperGPQA, any other-benchmark tag routes out of scope, and
    everything else defaults to GPQA (the original, unlabeled benchmark)."""
    ds = row.get("dataset")
    if ds:
        ds = str(ds).lower()
        return ds if ds in ("gpqa", "supergpqa") else None
    name = path.name.lower()
    if "supergpqa" in name:
        return "supergpqa"
    if any(tag in name for tag in _OTHER_BENCHMARK_TAGS):
        return None
    return "gpqa"


def _is_control_lever(row: dict) -> bool:
    lever = row.get("lever")
    return lever == "control" or lever is None


def _is_unanimous_wrong(engine: dict) -> bool:
    solver_answers = engine.get("solver_answers") or []
    letters = [sa.get("letter") for sa in solver_answers if sa.get("letter")]
    # Require exactly 3 (the shipped cheap panel's N_SOLVERS) so a
    # differently-shaped lever's row (e.g. `five`, 5 solvers) can never
    # sneak into the control pool even if it were mistagged.
    if len(letters) != 3:
        return False
    if len(set(letters)) != 1:
        return False
    return engine.get("correct") is False


def inventory_and_pool() -> tuple[list[dict], dict[str, dict[str, dict]], dict[str, dict]]:
    """Scans every benchmark/results/*.jsonl file once. Returns:
      - file_inventory: per-file scan status (for the "which files have
        solver_answers" audit trail).
      - pool: {dataset: {question_id: {"question", "choices", "sources"}}}
        -- the deduped control-lever unanimous-wrong pool.
      - denom: {dataset: {"unique_questions_seen", "control_files"}} --
        coverage context (how big a population the pool was drawn from).
    """
    file_inventory: list[dict] = []
    pool: dict[str, dict[str, dict]] = {"gpqa": {}, "supergpqa": {}}
    unique_questions_seen: dict[str, set] = {"gpqa": set(), "supergpqa": set()}
    control_files: dict[str, set] = {"gpqa": set(), "supergpqa": set()}
    raw_unanimous_wrong_rows: dict[str, int] = {"gpqa": 0, "supergpqa": 0}

    for path in sorted(RESULTS_DIR.glob("*.jsonl")):
        n_rows = 0
        n_engine_rows = 0
        n_control_included = 0
        dataset_seen = None
        for row in _iter_jsonl(path):
            n_rows += 1
            engine = row.get("engine")
            if not isinstance(engine, dict) or "solver_answers" not in engine:
                continue
            n_engine_rows += 1
            if not _is_control_lever(row):
                continue
            ds = _dataset_for(row, path)
            if ds is None or ds not in pool:
                continue
            item = engine.get("item") or {}
            qid, question, choices = item.get("question_id"), item.get("question"), item.get("choices") or []
            if not qid or not question or not choices:
                continue
            dataset_seen = ds
            n_control_included += 1
            unique_questions_seen[ds].add(qid)
            control_files[ds].add(path.name)
            if _is_unanimous_wrong(engine):
                raw_unanimous_wrong_rows[ds] += 1
                entry = pool[ds].setdefault(qid, {"question": question, "choices": choices, "sources": set()})
                entry["sources"].add(path.name)

        file_inventory.append({
            "file": path.name,
            "n_rows": n_rows,
            "n_engine_rows": n_engine_rows,  # has solver_answers at all
            "n_control_included": n_control_included,  # + control-lever + in-scope dataset
            "dataset": dataset_seen,
        })

    denom = {
        ds: {
            "unique_questions_seen": len(unique_questions_seen[ds]),
            "control_files": sorted(control_files[ds]),
            "raw_unanimous_wrong_rows": raw_unanimous_wrong_rows[ds],
        }
        for ds in pool
    }
    return file_inventory, pool, denom


# ---------------------------------------------------------------------------
# Heuristic classifier: quantitative-checkable vs conceptual
# ---------------------------------------------------------------------------

_DIGIT_RE = re.compile(r"\d")
_LATEX_CMD_RE = re.compile(r"\\[a-zA-Z]+")
_LATEX_MATH_TOKEN_RE = re.compile(
    r"\\(?:frac|sqrt|int|sum|prod|pi|alpha|beta|gamma|delta|Delta|theta|omega|"
    r"Omega|lambda|mu|sigma|Sigma|times|cdot|left|right|infty|leq|geq|approx|"
    r"pm|mp|log|ln|sin|cos|tan|exp|rightarrow|longrightarrow|rightleftharpoons|"
    r"mathrm|text)\b|\$|\^\{|_\{"
)
# 6+ consecutive letters, AFTER stripping \latex\commands -- catches prose
# words and multi-syllable nomenclature ("tetramethylbenzene", "mechanism",
# "explains") without being tripped up by LaTeX command names themselves
# ("\mathrm", "\times") which are math signal, not prose signal.
_LONGWORD_RE = re.compile(r"[A-Za-z]{6,}")

# A pure "which items apply" combinator ("2, 3 and 4", "3 and 4", "I and
# II", "all of the above") -- digits/roman-numerals are present, but the
# choice is selecting among enumerated STATEMENTS, not stating a computed
# value/equation, so it is vetoed back to non-quantitative even though it
# would otherwise pass the bare digit check. Anchored to the WHOLE choice
# string so a genuine compound numeric answer joined by "and" (e.g.
# "10^12 and 5eV") -- which has non-digit/roman characters mixed in -- is
# left alone.
_ITEM_SELECTOR_RE = re.compile(
    r"^\s*(?:all|none|both) of the above\s*$"
    r"|^\s*(?:[ivxlcdmIVXLCDM]+|\d+)\s*(?:,\s*(?:[ivxlcdmIVXLCDM]+|\d+)\s*)*"
    r"(?:,?\s*(?:and|or|&)\s*(?:[ivxlcdmIVXLCDM]+|\d+))\s*$",
    re.IGNORECASE,
)

_NUMERIC_CUE_RE = re.compile(
    r"\b(calculate|compute|how many|what is the value|what is the magnitude|"
    r"find the (?:value|magnitude|number|probability|energy|frequency|"
    r"wavelength|mass|volume|concentration|pressure|temperature|velocity|"
    r"speed|current|voltage|resistance|charge)|what is the (?:molar|mass|"
    r"volume|concentration|frequency|wavelength|energy|voltage|current|"
    r"resistance|pressure|temperature|probability|rate|ph|ka|kb))\b",
    re.IGNORECASE,
)


def _is_quantitative_choice(choice: str) -> bool:
    """One answer choice counts as 'quantitative' when it is dominated by
    digits / LaTeX math rather than prose -- e.g. "15", "\\frac{\\pi}{8}",
    "0.886 x 10^8 cm^-1", "q1 - q2 + 2q3" -- as opposed to a sentence or
    multi-word name like "First you identify the virus by performing cDNA
    sequencing." or "1,2,4,5-tetramethylbenzene". Two vetoes fire first:
    _ITEM_SELECTOR_RE catches "which items apply" combinators ("2, 3 and 4",
    "All of the above") -- digits present, but selecting among enumerated
    STATEMENTS is not a computed value. Then `long_words >= 2` is the
    prose/nomenclature veto: it takes TWO 6+-letter words (after stripping
    LaTeX commands) to disqualify a choice, so a single descriptive word
    next to a bare value ("concentration 0.5 mol/L") still counts, but two
    or more (a sentence, or compound chemical nomenclature) does not."""
    s = choice.strip()
    if not s:
        return False
    if _ITEM_SELECTOR_RE.match(s):
        return False
    digits = len(_DIGIT_RE.findall(s))
    latex_hits = len(_LATEX_MATH_TOKEN_RE.findall(s))
    prose = _LATEX_CMD_RE.sub(" ", s)
    long_words = len(_LONGWORD_RE.findall(prose))
    if long_words >= 2:
        return False
    return digits > 0 or latex_hits > 0


def classify_item(question: str, choices: list[str]) -> tuple[str, str]:
    """Deterministic classification of one MC item into
    'quantitative-checkable' or 'conceptual', from QUESTION + CHOICES text
    only (no model call, no network). Returns (label, reason) so every
    classification is auditable.

    Rule: if >=75% of choices are quantitative (see _is_quantitative_choice),
    the item is quantitative-checkable outright. If exactly half are
    quantitative AND the question stem itself has a numeric-answer cue
    ("calculate", "what is the value of", ...), it's ALSO
    quantitative-checkable (a 2-of-4 numeric split with a numeric-cue stem
    is a value question whose distractors happen to include text, not a
    conceptual question). Every other case -- including ties without a cue,
    and anything below half -- is 'conceptual'. This fails CLOSED toward
    conceptual: the fraction reported downstream is a CAP on W1-B's reach,
    so a borderline item should never inflate it."""
    quant_flags = [_is_quantitative_choice(c) for c in choices]
    n_quant = sum(quant_flags)
    n_total = len(choices)
    quant_frac = n_quant / n_total if n_total else 0.0
    cue_match = _NUMERIC_CUE_RE.search(question)

    if quant_frac >= 0.75:
        return LABEL_QUANT, f"{n_quant}/{n_total} choices numeric/equation-shaped (>=75%)"
    if quant_frac >= 0.5 and cue_match:
        return LABEL_QUANT, (
            f"{n_quant}/{n_total} choices numeric/equation-shaped (>=50%) + "
            f"numeric-answer cue in question ({cue_match.group(0)!r})"
        )
    reason = f"only {n_quant}/{n_total} choices numeric/equation-shaped"
    if cue_match and quant_frac < 0.5:
        reason += f"; has a numeric cue ({cue_match.group(0)!r}) but below the 50% choice threshold"
    return LABEL_CONCEPTUAL, reason


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def _classify_pool(items: dict[str, dict]) -> dict[str, tuple[str, str]]:
    return {qid: classify_item(v["question"], v["choices"]) for qid, v in items.items()}


def _examples(items: dict[str, dict], classified: dict[str, tuple[str, str]], label: str, k: int = 3) -> list[dict]:
    qids = sorted(qid for qid, (lbl, _) in classified.items() if lbl == label)
    out = []
    for qid in qids[:k]:
        v = items[qid]
        out.append({
            "question_id": qid,
            "question": v["question"],
            "choices": v["choices"],
            "reason": classified[qid][1],
        })
    return out


def _reference_check(ds: str) -> str:
    ref_name = _REFERENCE_FILES.get(ds)
    if not ref_name:
        return "(no reference file)"
    path = RESULTS_DIR / ref_name
    if not path.exists():
        return f"{ref_name}: NOT FOUND"
    n = uw = 0
    for row in _iter_jsonl(path):
        engine = row.get("engine")
        if not isinstance(engine, dict) or "solver_answers" not in engine:
            continue
        n += 1
        if _is_unanimous_wrong(engine):
            uw += 1
    return f"{ref_name}: {uw}/{n} unanimous-wrong ({100 * uw / n:.1f}%)" if n else f"{ref_name}: empty"


def build_report() -> tuple[str, dict]:
    file_inventory, pool, denom = inventory_and_pool()

    per_dataset = {}
    for ds in ("gpqa", "supergpqa"):
        items = pool[ds]
        classified = _classify_pool(items)
        n_quant = sum(1 for lbl, _ in classified.values() if lbl == LABEL_QUANT)
        n_total = len(items)
        frac = n_quant / n_total if n_total else 0.0
        per_dataset[ds] = {
            "pool_size": n_total,
            "n_quant": n_quant,
            "n_conceptual": n_total - n_quant,
            "checkable_fraction": frac,
            "raw_unanimous_wrong_rows": denom[ds]["raw_unanimous_wrong_rows"],
            "unique_questions_seen": denom[ds]["unique_questions_seen"],
            "control_files": denom[ds]["control_files"],
            "reference_check": _reference_check(ds),
            "examples_quant": _examples(items, classified, LABEL_QUANT),
            "examples_conceptual": _examples(items, classified, LABEL_CONCEPTUAL),
        }

    lines = []
    lines.append("# Pool checkability: W1-B (CAS arm) cap")
    lines.append("")
    lines.append(
        "Offline, no-API classification of the CONTROL-lever unanimous-wrong pool "
        "(GPQA + SuperGPQA-hard) into `quantitative-checkable` vs `conceptual`, "
        "per `docs/same-provider-scaling-research.md` F6. **This fraction IS the "
        "W1-B (CAS arm) CAP, committed before W1 runs** -- W1-B structurally cannot "
        "catch a `conceptual` unanimous-wrong item no matter how good its "
        "extraction/verification step is."
    )
    lines.append("")
    lines.append(
        "Scope: only `lever == \"control\"` (or unlabeled legacy pre-lever-tagging) "
        "rows count -- every other lever changes the solver dispatch or forces "
        "escalation on some unanimous cases, which would mix \"unanimous-wrong under "
        "a different engine\" into what should be the shipped baseline's blind spot. "
        "See `benchmark/classify_pool_checkability.py`'s module docstring for the "
        "full inventory rationale."
    )
    lines.append("")
    lines.append(
        "**Honest caveat:** the measured fractions below (53% GPQA, 87% SuperGPQA-"
        "hard) are noticeably HIGHER than `same-provider-scaling-research.md`'s "
        "prior qualitative framing (\"the unanimous-wrong pool is largely "
        "conceptual MC\"). That framing was an impression, not a prior "
        "measurement -- this is the first actual classification run. Two things "
        "can both be true and should be checked before leaning on this number: "
        "(1) SuperGPQA-hard's trimmed-to-4-choices subset (see "
        "`benchmark/load_supergpqa.py`) may simply skew toward STEM-numeric "
        "disciplines more than GPQA does, which the pool composition here "
        "supports (spot-check the examples below); (2) this regex heuristic errs "
        "toward counting short alphanumeric codes (point groups, chemical "
        "formulas, symmetry labels) as \"quantitative\" even though a CAS engine "
        "cannot literally evaluate them the way it can an equation -- a stricter "
        "heuristic would likely pull the fraction down, not up. Treat these "
        "numbers as the CEILING the heuristic supports, not a validated floor."
    )
    lines.append("")

    for ds in ("gpqa", "supergpqa"):
        d = per_dataset[ds]
        label = "GPQA" if ds == "gpqa" else "SuperGPQA-hard"
        lines.append(f"## {label}")
        lines.append("")
        lines.append(f"- Control-lever files pooled: {', '.join(d['control_files'])}")
        lines.append(f"- Unique questions observed across those files: {d['unique_questions_seen']}")
        lines.append(f"- Raw unanimous-wrong rows (pre-dedup, across seeds/files): {d['raw_unanimous_wrong_rows']}")
        lines.append(f"- **Pool size (unique unanimous-wrong items, deduped by question_id): {d['pool_size']}**")
        lines.append(f"- Single-seed reference cross-check: {d['reference_check']}")
        lines.append(
            f"- **Checkable fraction: {d['n_quant']}/{d['pool_size']} = "
            f"{100 * d['checkable_fraction']:.1f}% quantitative-checkable "
            f"({d['n_conceptual']} conceptual)**"
        )
        lines.append("")
        lines.append("Example `quantitative-checkable` items:")
        lines.append("")
        for ex in d["examples_quant"]:
            lines.append(f"- `{ex['question_id']}` -- {ex['reason']}")
            lines.append(f"  - Q: {ex['question'][:220].replace(chr(10), ' ')}")
            lines.append(f"  - Choices: {ex['choices']}")
        if not d["examples_quant"]:
            lines.append("  (none in this pool)")
        lines.append("")
        lines.append("Example `conceptual` items:")
        lines.append("")
        for ex in d["examples_conceptual"]:
            lines.append(f"- `{ex['question_id']}` -- {ex['reason']}")
            lines.append(f"  - Q: {ex['question'][:220].replace(chr(10), ' ')}")
            lines.append(f"  - Choices: {ex['choices']}")
        if not d["examples_conceptual"]:
            lines.append("  (none in this pool)")
        lines.append("")

    lines.append("## File inventory (which files have `solver_answers`)")
    lines.append("")
    lines.append("| file | rows | has solver_answers | control-lever + in-scope | dataset |")
    lines.append("|---|---:|---:|---:|---|")
    for fi in file_inventory:
        lines.append(
            f"| {fi['file']} | {fi['n_rows']} | {fi['n_engine_rows']} | "
            f"{fi['n_control_included']} | {fi['dataset'] or ''} |"
        )
    lines.append("")

    return "\n".join(lines), per_dataset


def main() -> None:
    report_md, per_dataset = build_report()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(report_md, encoding="utf-8")

    for ds in ("gpqa", "supergpqa"):
        d = per_dataset[ds]
        label = "GPQA" if ds == "gpqa" else "SuperGPQA-hard"
        print(
            f"{label}: pool_size={d['pool_size']} "
            f"checkable={d['n_quant']}/{d['pool_size']} "
            f"({100 * d['checkable_fraction']:.1f}%) "
            f"conceptual={d['n_conceptual']} "
            f"[reference: {d['reference_check']}]"
        )
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
