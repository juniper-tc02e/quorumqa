"""Typed loaders for QuorumQA's figure set -- the provenance firewall.

WHY THIS EXISTS (see benchmark/results/figure_claims_ledger.md for the full
contract): our validated, published numbers are PAIRED common-item deltas
that otherwise live only as prose in `*_findings.md` files. Meanwhile
`benchmark/results/f2_compute_frontier.csv` holds POOLED-MARGINAL accuracies
(each config scored over whatever items it happened to run) which are NOT
the same numbers as our published record -- three confirmed traps are
documented in the ledger .md (MMLU-Pro flagship_panel +1.2 pooled vs the
paired +0.0; GPQA shipped_engine 79.78%/n=183 pooled vs the published
78.9%/n=90 frozen build; SuperGPQA flagship_panel raw pooled 82.7% vs the
validated +4.1 mean on common-item intersections).

This module makes conflating those two kinds of number a TYPE ERROR, not a
discipline problem: `load_ledger()` returns a `PairedFrame`, `load_frontier()`
returns a `PooledFrame`, and the two classes are not interchangeable, do not
share a common data-bearing base class, and carry a `.provenance_tag` a
figure script can stamp directly onto a plot. Anything that isn't a clean
paired comparison (small-n paired CSVs, local-only gitignored JSONLs) gets
its own frozen wrapper too, so every figure script's imports make its own
evidence tier legible at a glance.

Usage:
    python -m benchmark.figure_data --check     # runs verify_ledger()
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "benchmark" / "results"

LEDGER_CSV = RESULTS_DIR / "figure_claims_ledger.csv"
LEDGER_MD = RESULTS_DIR / "figure_claims_ledger.md"
FRONTIER_CSV = RESULTS_DIR / "f2_compute_frontier.csv"
F5_DIFFICULTY_CSV = RESULTS_DIR / "f5_difficulty_map.csv"
MOO_CALIBRATION_CSV = RESULTS_DIR / "moo_calibration_table.csv"
FAMILY_FLOOR_JSON = RESULTS_DIR / "family_floor_analysis_data.json"
AGENT_COST_CSV = RESULTS_DIR / "agent_cost_calibration.csv"

# ---------------------------------------------------------------------------
# Shared visual conventions -- module constants so figure scripts can't drift
# ---------------------------------------------------------------------------

#: Below this magnitude, a single-run delta is indistinguishable from the
#: measured zero-change-rerun noise floor (2.5pp, see lever_findings.md
#: "The noise floor (measured, not assumed)"). Figure scripts should shade
#: or hatch bars smaller than this rather than plotting them as flat fact.
NOISE_FLOOR_PP = 2.5

#: The minimum net-discordant-item count that clears one-sided exact
#: McNemar p < 0.05 with zero losses (docs/negative-results.md Sec.4,
#: docs/experiment-spec-book.md Sec.1.1: +3 -> p=0.125, +4 -> p=0.0625,
#: +5 -> p=0.03125). Bars below this should not be presented as
#: statistically established without the pooled 2-of-3-seed exception.
MCNEMAR_MIN_NET = 5

#: config -> footnote text for every ledger row whose `contaminated` column
#: is TRUE. Keyed on the ledger's `config` value so a figure script can look
#: up the right asterisk text for whatever bar it is currently drawing.
CONTAMINATION_FOOTNOTES: dict[str, str] = {
    "qwen38_judge": (
        "n=76/90 surviving; 14 drops were 300s ReadTimeouts on the Token "
        "Plan endpoint, 13/14 in Organic Chemistry -- a survivorship "
        "pattern, not a clean paired comparison at n=90."
    ),
    "qwen3.8_solo": (
        "POINT ESTIMATE RETIRED 2026-07-30 by D0's own pre-registered kill "
        "clause. Three paced retries recovered only 2 of 12 missing items "
        "(78->80/90); the residual failures are server-side 504s, not client "
        "timeouts, so they are structural. The honest figure is the "
        "imputation INTERVAL [83.3%, 94.4%], not 93.6% -- which was the "
        "survivor-only rate. Any figure plotting 93.6% as a point, and "
        "especially as a Pareto-frontier point, is showing a number this "
        "repo has retracted. See "
        "benchmark/results/qwen38_bar_repair_preregistration.md."
    ),
    "qwen38_panel": (
        "30% timeout drop rate (27/90), concentrated in the hardest "
        "Science/Engineering subjects. The 58-item common-item comparison "
        "set is the easier survivorship tail; paired verdict is negative "
        "(ties baseline, trails flagship_panel on the same items)."
    ),
}

#: Benchmarks whose result files are explicitly excluded from the ledger.
#: AIME's cheap-tier pilot #1 was invalidated by survivorship bias (32/60
#: panel + 12/60 baseline items dropped to ReadTimeout/429), and every
#: committed AIME result file is a survivor set of that run -- see
#: docs/negative-results.md Sec.4 ("The AIME cheap-tier pilot's first run
#: was invalidated..."). No AIME row may appear in the ledger until a
#: clean re-run lands with its own result file.
EXCLUDED_BENCHMARKS = frozenset({"AIME"})

#: Configs whose POINT ESTIMATE has been formally retired by a pre-registered
#: kill clause. These are not merely "contaminated" (which a footnote can
#: carry) -- the repo has withdrawn the number itself, so plotting it as a
#: point, and above all as a Pareto-frontier point, republishes a retraction.
#:
#: `qwen3.8_solo`: retired 2026-07-30. The 93.6% was the survivor-only rate
#: over 73/78; after three paced retries recovered 2 of 12 missing items the
#: honest figure is the imputation interval [83.3%, 94.4%]. It appeared in
#: `docs/figures/f04_accuracy_vs_tokens_frontier.svg` as the HIGHEST GPQA
#: point and was marked on_pareto_frontier=True -- i.e. the retracted number
#: was doing load-bearing work in a published figure. Found 2026-08-02 while
#: building the TB-1 paired frontier.
#:
#: A frontier is a claim about what is achievable. A retired estimate cannot
#: support one, so these configs must be excluded from any frontier
#: computation or drawn as an interval, never as a point.
RETIRED_POINT_ESTIMATES: dict[str, str] = {
    "qwen3.8_solo": "retired 2026-07-30 by D0's kill clause; honest figure is the interval [83.3%, 94.4%]",
}

_COST_PATTERN = re.compile(r"usd|cost|dollar", re.IGNORECASE)

# Ledger columns that carry an actual measured numeric CLAIM (as opposed to
# bookkeeping columns like n_common_items/seeds/source_doc) -- these are the
# columns verify_ledger() greps the cited source doc for.
_CLAIM_COLUMNS = (
    "per_seed_delta_pp",
    "mean_delta_pp",
    "absolute_accuracy_pct",
    "net_discordant_items",
    "mcnemar_p",
    "unanimous_wrong_rate_pct",
    "escalation_rate_pct",
    "mean_tokens_per_q",
)

# A bare numeric token: optional sign (ASCII hyphen, unicode minus, or plus),
# digits, optional decimal part. Deliberately excludes non-numeric tokens
# like "tie" (used verbatim in the ledger for a literal tied seed) so those
# are skipped rather than treated as an unverifiable claim.
_NUMERIC_TOKEN_RE = re.compile(r"^[+\-−]?\d+(\.\d+)?$")


# ---------------------------------------------------------------------------
# Frozen typed frames -- the type separation IS the trap-prevention
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PairedFrame:
    """A same-item paired comparison: every row's accuracy/delta was scored
    on the identical question set as its comparator (apples-to-apples,
    common-item intersection). This is the ONLY tier safe to plot as "our
    validated record" without a caveat footnote. Tier A."""

    data: pd.DataFrame
    tier: str
    source_paths: list[Path]
    caveat: str
    provenance_tag: str = "[PAIRED]"


@dataclass(frozen=True)
class PooledFrame:
    """A pooled-marginal accuracy: each config's accuracy is computed over
    whatever items it happened to run across however many logged files got
    concatenated (drops, resumes, adhoc/smoke runs and all). NOT comparable
    to a PairedFrame row for the same (benchmark, config) pair -- see the
    three confirmed traps in figure_claims_ledger.md. Tier B."""

    data: pd.DataFrame
    tier: str
    source_paths: list[Path]
    caveat: str
    provenance_tag: str = "[POOLED-MARGINAL]"


@dataclass(frozen=True)
class SmallNPairedFrame:
    """A paired comparison, but at a small enough per-cell n (typically
    n<30, often n=4-14) that per-row noise is comparable to or larger than
    the effect being read off it. Paired in design, not yet paired in
    statistical power. Tier C."""

    data: pd.DataFrame
    tier: str
    source_paths: list[Path]
    caveat: str
    provenance_tag: str = "[PAIRED-SMALL-N]"


@dataclass(frozen=True)
class LocalFrame:
    """Data that only exists as local, gitignored JSONL/log files -- never
    committed, never reproducible from a fresh clone. Tier D. Provided for
    interface completeness; no committed loader instantiates this today
    (every committed figure-relevant number has a Tier A/B/C home). A
    project-local script MAY construct one directly from its own JSONLs."""

    data: pd.DataFrame
    tier: str
    source_paths: list[Path]
    caveat: str
    provenance_tag: str = "[LOCAL-ONLY]"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_ledger() -> PairedFrame:
    """Loads benchmark/results/figure_claims_ledger.csv -- the hand-
    transcribed, quote-checked, paired common-item record. This is the
    ONLY function that should back a "validated wins" or "shipped vs
    baseline" figure. Every numeric cell is checkable against its cited
    source_doc via verify_ledger()."""
    if not LEDGER_CSV.exists():
        raise FileNotFoundError(f"Ledger CSV not found: {LEDGER_CSV}")
    df = pd.read_csv(LEDGER_CSV, dtype=str, keep_default_na=False)
    return PairedFrame(
        data=df,
        tier="A",
        source_paths=[LEDGER_CSV],
        caveat=(
            "Hand-transcribed from *_findings.md prose; the only tier safe "
            "to cite as this project's published record. Run "
            "verify_ledger() before trusting a fresh checkout -- it greps "
            "every non-empty numeric cell against its cited source_doc."
        ),
    )


def load_frontier() -> PooledFrame:
    """Loads benchmark/results/f2_compute_frontier.csv -- POOLED-MARGINAL
    accuracies (each config's accuracy pooled across every logged run file
    for that (benchmark, config) pair, drops and all). Legitimate use: a
    compute-frontier / Pareto scatter across the whole logged record, or an
    investment-allocation argument ("how many benchmarks does a bare
    flagship call dominate"). ILLEGITIMATE use: citing a single cell as
    this project's validated number for that (benchmark, config) -- three
    confirmed traps are documented in figure_claims_ledger.md. Always
    render with the [POOLED-MARGINAL] tag visible on the figure."""
    if not FRONTIER_CSV.exists():
        raise FileNotFoundError(f"Frontier CSV not found: {FRONTIER_CSV}")
    df = pd.read_csv(FRONTIER_CSV)
    return PooledFrame(
        data=df,
        tier="B",
        source_paths=[FRONTIER_CSV],
        caveat=(
            "Pooled-marginal: each (benchmark, config) accuracy is computed "
            "over whatever items that config happened to run, concatenated "
            "across every logged result file (full runs, resumes, adhoc, "
            "smoke). NOT a same-item paired comparison. Three confirmed "
            "traps vs the published paired record are documented in "
            "figure_claims_ledger.md Sec.'Three confirmed CSV traps'. Never "
            "plot a single cell from this frame as a validated claim "
            "without cross-checking figure_claims_ledger.csv first."
        ),
    )


def load_moo_small_n() -> SmallNPairedFrame:
    """Loads f5_difficulty_map.csv (per-bucket profile deltas vs
    single-call, n_common_items in the 25-30 range) and
    moo_calibration_table.csv (per-(profile, router-bucket) calibration,
    n as low as 4-5 for gpqa_hard_stem -- explicitly flagged in
    moo_m1_corrected_findings.md as "thin, not independently trusted").
    Both are paired-by-construction (same router bucket / same item pool)
    but small-n enough that per-row noise can swamp the effect; concatenated
    with a `source_file` column so a consumer can filter by provenance."""
    paths = [F5_DIFFICULTY_CSV, MOO_CALIBRATION_CSV]
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing small-n source file(s): {missing}")

    f5 = pd.read_csv(F5_DIFFICULTY_CSV)
    f5["source_file"] = F5_DIFFICULTY_CSV.name
    moo = pd.read_csv(MOO_CALIBRATION_CSV)
    moo["source_file"] = MOO_CALIBRATION_CSV.name

    combined = pd.concat([f5, moo], ignore_index=True, sort=False)
    return SmallNPairedFrame(
        data=combined,
        tier="C",
        source_paths=paths,
        caveat=(
            "Paired by construction (same router bucket / item pool per "
            "row) but small n per cell -- as low as n=4-5 for "
            "gpqa_hard_stem in moo_calibration_table.csv, explicitly "
            "flagged 'thin, not independently trusted' in "
            "moo_m1_corrected_findings.md. Treat single-cell reads as "
            "directional, not as a validated claim; prefer the Tier A "
            "ledger wherever a row overlaps."
        ),
    )


def load_subject_deltas() -> SmallNPairedFrame:
    """Loads family_floor_analysis_data.json's `f5_subject_breakdown` list
    (per-GPQA-subject baseline vs shipped-engine accuracy, n as low as 4-14
    questions per subject -- e.g. n=5 for Electromagnetism and Photonics).
    Paired (same subject's items scored under both configs) but at
    per-subject n far below any statistical bar."""
    if not FAMILY_FLOOR_JSON.exists():
        raise FileNotFoundError(f"Family floor JSON not found: {FAMILY_FLOOR_JSON}")
    with FAMILY_FLOOR_JSON.open(encoding="utf-8") as f:
        raw = json.load(f)
    breakdown = raw.get("f5_subject_breakdown")
    if breakdown is None:
        raise KeyError(
            f"'f5_subject_breakdown' key not found in {FAMILY_FLOOR_JSON}; "
            f"available keys: {list(raw.keys())}"
        )
    df = pd.DataFrame(breakdown)
    return SmallNPairedFrame(
        data=df,
        tier="C",
        source_paths=[FAMILY_FLOOR_JSON],
        caveat=(
            "Per-subject paired deltas (baseline vs shipped engine, same "
            "items) at per-subject n typically well under 30 -- some "
            "subjects (e.g. Electromagnetism and Photonics) at n=5. "
            "Individual subject rows are directional evidence for the "
            "diagnosis narrative (e.g. Organic Chemistry's blind spot), "
            "not standalone validated claims."
        ),
    )


def load_agent_eras() -> PairedFrame:
    """Loads benchmark/results/agent_cost_calibration.csv -- the
    QuorumQAAgent Harbor/Terminal-Bench coding-agent hardening record. Has a
    real `hardening_era` column (e.g. hardened-baseline vs earlier eras) so
    the same task_name can be paired era-over-era, unlike the QA-benchmark
    frames above which pair by question id. Tier A: genuinely paired by
    (task_name, trial), not pooled-marginal."""
    if not AGENT_COST_CSV.exists():
        raise FileNotFoundError(f"Agent cost calibration CSV not found: {AGENT_COST_CSV}")
    df = pd.read_csv(AGENT_COST_CSV)
    return PairedFrame(
        data=df,
        tier="A",
        source_paths=[AGENT_COST_CSV],
        caveat=(
            "Paired by (task_name, hardening_era): the same Terminal-Bench "
            "2.1 task attempted under different agent-hardening eras. Cost "
            "columns are token counts (n_input_tokens/n_output_tokens/"
            "total_tokens), not USD -- consistent with the project's "
            "post-Token-Plan-migration 'tokens, not dollars' convention."
        ),
    )


# ---------------------------------------------------------------------------
# verify_ledger() -- the transcription-typo safety net
# ---------------------------------------------------------------------------


class LedgerVerificationError(AssertionError):
    """Raised by verify_ledger() when a ledger claim fails verification."""


def _read_text_cached(path: Path, cache: dict[Path, str]) -> str:
    if path not in cache:
        cache[path] = path.read_text(encoding="utf-8")
    return cache[path]


def _numeric_tokens(cell: str) -> list[str]:
    """Splits a ledger cell on ';' (the per-seed-list convention) and
    returns only the tokens that look like a bare signed/unsigned number.
    Non-numeric tokens (e.g. the literal 'tie' used for a zero-delta seed)
    are skipped -- they carry no independently-checkable digit string."""
    tokens = []
    for raw in str(cell).split(";"):
        tok = raw.strip()
        if tok and _NUMERIC_TOKEN_RE.match(tok):
            tokens.append(tok)
    return tokens


def _token_variants(token: str) -> list[str]:
    """A negative number may be printed in source docs with either an ASCII
    hyphen-minus or a proper unicode minus sign (U+2212); the ledger CSV
    stores ASCII throughout. Returns every literal string worth searching
    for, per the task's own example ("-11.6" AND its unicode variant)."""
    variants = [token]
    if token.startswith("-"):
        variants.append("−" + token[1:])
    return variants


def verify_ledger() -> None:
    """Implements `--check`: for every figure_claims_ledger.csv row with a
    non-empty numeric claim, greps the row's cited source_doc for the
    literal formatted number (trying both the ASCII-hyphen and unicode-minus
    sign variants). Fails loudly, listing every unverifiable number, rather
    than passing silently on a transcription typo.

    Also asserts:
      - zero AIME rows (both AIME result files are survivor sets of an
        invalidated run; no AIME claim may enter the ledger -- see
        EXCLUDED_BENCHMARKS docstring above),
      - no column name matching usd|cost|dollar in any loaded frame (USD is
        $0.00 everywhere post-Token-Plan migration; tokens are the only
        honest cost signal),
      - every declared source path (ledger source_doc column, and every
        loader's source_paths) actually exists on disk.

    Raises LedgerVerificationError on any failure; prints a per-row report
    and returns normally on success.
    """
    ledger = load_ledger()
    df = ledger.data
    failures: list[str] = []
    doc_cache: dict[Path, str] = {}
    checked_numbers = 0
    checked_rows = 0

    # --- 1. zero excluded-benchmark rows (AIME, per EXCLUDED_BENCHMARKS) ---
    excluded_mask = df["benchmark_label"].apply(
        lambda label: any(ex in str(label).upper() for ex in EXCLUDED_BENCHMARKS)
    )
    excluded_rows = df[excluded_mask]
    if not excluded_rows.empty:
        failures.append(
            f"{len(excluded_rows)} row(s) found for an EXCLUDED_BENCHMARKS "
            f"label ({sorted(EXCLUDED_BENCHMARKS)}) -- both AIME result "
            "files are survivor sets of an explicitly invalidated run "
            "(docs/negative-results.md Sec.4); no row for an excluded "
            f"benchmark is permitted. Offending rows: "
            f"{excluded_rows[['benchmark_label', 'config']].to_dict('records')}"
        )

    # --- 2. every declared source_doc exists --------------------------------
    for doc_rel in sorted(set(df["source_doc"]) - {""}):
        doc_path = PROJECT_ROOT / doc_rel
        if not doc_path.exists():
            failures.append(f"source_doc does not exist on disk: {doc_rel}")

    # --- 3. per-row numeric claim verification -----------------------------
    for row in df.itertuples(index=False):
        row_d = row._asdict()
        doc_rel = row_d.get("source_doc", "")
        if not doc_rel:
            continue
        doc_path = PROJECT_ROOT / doc_rel
        if not doc_path.exists():
            continue  # already reported above
        try:
            doc_text = _read_text_cached(doc_path, doc_cache)
        except OSError as exc:
            failures.append(f"could not read {doc_rel}: {exc}")
            continue

        row_label = f"{row_d.get('benchmark_label')}/{row_d.get('config')}/{row_d.get('build_stage')}"
        row_had_number = False
        for col in _CLAIM_COLUMNS:
            cell = row_d.get(col, "")
            if not cell:
                continue
            for token in _numeric_tokens(cell):
                checked_numbers += 1
                row_had_number = True
                variants = _token_variants(token)
                if not any(v in doc_text for v in variants):
                    failures.append(
                        f"[{row_label}] column '{col}' claims '{token}' "
                        f"(checked variants {variants}) but it does not "
                        f"appear verbatim in {doc_rel}"
                    )
        if row_had_number:
            checked_rows += 1

    # --- 4. no usd|cost|dollar column in any loaded frame -------------------
    frame_loaders = [
        ("load_ledger", load_ledger),
        ("load_frontier", load_frontier),
        ("load_moo_small_n", load_moo_small_n),
        ("load_subject_deltas", load_subject_deltas),
        ("load_agent_eras", load_agent_eras),
    ]
    for name, loader in frame_loaders:
        frame = loader()
        bad_cols = [c for c in frame.data.columns if _COST_PATTERN.search(str(c))]
        if bad_cols:
            failures.append(
                f"{name}() frame has USD-shaped column(s) {bad_cols} -- USD "
                "is $0.00 everywhere post-Token-Plan migration; tokens only."
            )
        for p in frame.source_paths:
            if not p.exists():
                failures.append(f"{name}() declares a source_path that does not exist: {p}")

    if failures:
        report = "\n  - ".join(failures)
        raise LedgerVerificationError(
            f"verify_ledger() found {len(failures)} problem(s):\n  - {report}"
        )

    print(
        f"verify_ledger: OK -- {len(df)} ledger rows, {checked_rows} row(s) "
        f"with numeric claims, {checked_numbers} individual number(s) "
        f"verified against their cited source_doc. Zero AIME rows. "
        f"No usd/cost/dollar columns in any of {len(frame_loaders)} loaded frames."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Run verify_ledger() and exit 0/1.")
    args = parser.parse_args()

    if args.check or True:  # this module's only CLI behavior is the check
        try:
            verify_ledger()
        except LedgerVerificationError as exc:
            print(f"verify_ledger: FAILED\n{exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
