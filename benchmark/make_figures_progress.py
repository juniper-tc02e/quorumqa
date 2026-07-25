"""CORE progression figures for QuorumQA (F01, F02, F03, F06) -- the paired-
delta build record, in gap space, not a cross-benchmark accuracy leaderboard.

WHY GAP SPACE: absolute accuracies do not travel across benchmarks (SuperGPQA
-hard and MMLU-Pro-STEM are 4-choice trims, MATH-500 is MC-ified), so every
comparison here is a paired delta vs. that benchmark's own single-flagship
call, never a raw-accuracy bar chart. And there is no build *sequence* per
benchmark -- one v1 (the shipped cheap panel) plus a fan of parallel lever
variants. A genuine v1->current pair exists on only 4 benchmarks (GPQA
-Diamond, SuperGPQA-hard, MMLU-Pro, LEXam); the other 5 (MMLU-Pro-STEM,
MedQA, MATH-500-open, MATH-500-MC, GSM8K) ran one build ever -- no
improvement arrow is drawn where there is no second build.

DELTA RESOLUTION POLICY (see resolve_ledger_configs()): for every ledger v1/v2
row, in priority order --
  1. `mean_delta_pp` if the source doc printed one verbatim  -> provenance
     'printed_mean'.
  2. else `per_seed_delta_pp` if present ('tie' -> 0.0)      -> provenance
     'printed_per_seed_centroid'; the plotted x is the centroid of the
     printed per-seed numbers, never itself printed as a fabricated mean.
  3. else compute (absolute_accuracy_pct - benchmark's flat flagship
     reference accuracy). If the row's `comparator` names a matched-seed
     baseline ("matched_flagship_baseline" etc.) that isn't separately
     recorded in the ledger, this is only an APPROXIMATION -- chem_thinking
     _gate's seed-314 matched delta is independently printed in
     lever_findings.md as +4.4pp, while this approximation reads +6.5pp
     (flat baseline 84.4 vs the seed-314 matched baseline's real 86.5) --
     so provenance 'computed_matched_approx' rows are visually capped at
     half-fill at most, regardless of magnitude or seed count, and the cap
     is documented inline. Non-matched comparators use provenance
     'computed_vs_flat_reference' with no cap.
  4. else 'unresolved' (excluded from delta figures, kept only in F03).

KNOWN LEDGER GAPS HANDLED HONESTLY, NOT PAPERED OVER:
  - chem_thinking_gate has per-seed *accuracy* in lever_findings.md
    (90.9/91.0/90.8 -- the ~0.2pt cluster) but the ledger's own
    `per_seed_delta_pp` cell is empty (only the aggregate absolute 90.9 was
    transcribed). Since this script may not edit the ledger, F06 (which
    sources strictly from `per_seed_delta_pp`) excludes it; it still appears
    in F02/F03 via the fallback above.
  - MMLU-Pro-STEM and MATH-500-open have v2 rows but no v1 (shipped_engine)
    row at all -- there is no "before" state to anchor an arrow, so F01
    renders them as unconnected single markers, not a dumbbell.

Usage:
    .venv/Scripts/python.exe -m benchmark.make_figures_progress
    .venv/Scripts/python.exe -m benchmark.make_figures_progress --only f01

Writes:
    docs/figures/f01_build_progress_gap_space.svg / .png
    docs/figures/f02_lever_deltas_by_benchmark.svg / .png
    docs/figures/f03_evidence_inventory_heatmap.svg / .png
    docs/figures/f06_per_seed_spread.svg / .png
    benchmark/results/figure_f01_build_progress_gap_space.csv
    benchmark/results/figure_f02_lever_deltas_by_benchmark.csv
    benchmark/results/figure_f03_evidence_inventory_heatmap.csv
    benchmark/results/figure_f06_per_seed_spread.csv

No network or paid API calls -- pure offline CSV/ledger mining via
benchmark.figure_data's typed loaders (load_ledger / load_frontier).
"""

from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "quorumqa-figures-progress-v1"
matplotlib.rcParams["font.size"] = 10

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import RegularPolygon, Circle

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmark.figure_data import (  # noqa: E402
    CONTAMINATION_FOOTNOTES,
    MCNEMAR_MIN_NET,
    NOISE_FLOOR_PP,
    load_frontier,
    load_ledger,
)

FIGURES_DIR = PROJECT_ROOT / "docs" / "figures"
RESULTS_DIR = PROJECT_ROOT / "benchmark" / "results"

# ---------------------------------------------------------------------------
# Shared visual conventions -- one place so figures cannot drift apart
# ---------------------------------------------------------------------------

# Diverging blue/red pair + neutral grey midpoint (validated diverging pair,
# see dataviz skill references/palette.md): win = blue, loss = red, tie/
# neutral = grey. Status "critical" red reserved for the contamination
# outline so it never doubles as a plain "loss" cue.
COLOR_WIN = "#2a78d6"
COLOR_LOSS = "#e34948"
COLOR_NEUTRAL = "#6b6a66"
COLOR_RIBBON = "#f0efec"
COLOR_RIBBON_EDGE = "#c9c8c2"
COLOR_MCNEMAR_LINE = "#52514e"
COLOR_ZERO_LINE = "#0b0b0b"
COLOR_CONTAM_EDGE = "#d03b3b"
COLOR_TEXT_PRIMARY = "#0b0b0b"
COLOR_TEXT_SECONDARY = "#52514e"

TAG_COLOR = {
    "[PAIRED]": "#0b0b0b",
    "[POOLED-MARGINAL]": "#9c6b00",
    "[PAIRED-SMALL-N]": "#9c6b00",
    "[LOCAL-ONLY]": "#52514e",
}

# Sequential blue ramp, light -> dark, for F03's seed-count heatmap cells.
SEQ_BLUE = ["#e8f0fc", "#b7d3f6", "#86b6ef", "#5598e7", "#2a78d6", "#184f95", "#0d366b"]

AIME_FOOTNOTE = (
    "AIME excluded: both files are survivor sets of an explicitly "
    "invalidated run."
)

FLAGSHIP_BASELINE_PREFIX = "baseline_3.7max"

# 9 benchmarks with a genuine v1(shipped_engine) -> v2(lever fan) pair.
ARROW_BENCHMARKS = ("GPQA-Diamond", "SuperGPQA-hard", "MMLU-Pro", "LEXam")

_NUMERIC_RE = re.compile(r"^[+\-−]?\d+(\.\d+)?$")


def _to_float(token: str) -> float:
    return float(token.strip().replace("−", "-").lstrip("+"))


def get_git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


GIT_SHA = get_git_sha()
TODAY = date.today().isoformat()


def add_footer(fig, source_files: list[str], caveat: str, extra_lines: Optional[list[str]] = None) -> None:
    """The mandated 3-line auto-generated footer: source file(s) -> git SHA +
    generation date -> caveat text (pulled from the ledger/frontier caveat so
    it can never drift from the number it guards). extra_lines are appended
    (e.g. per-figure exclusion notes) below the 3 canonical lines. Every line
    is wrapped to the figure's own width so nothing runs off the right edge
    regardless of which figure (narrow F01/F06 vs. wide F03) is calling in."""
    fig_width_in = fig.get_size_inches()[0]
    char_width_in = 6.7 * 0.60 / 72.0  # monospace, fontsize 6.7pt
    wrap_width = max(80, int((fig_width_in * 0.96) / char_width_in))

    line1 = "Source: " + "; ".join(source_files)
    line2 = f"Commit {GIT_SHA} -- generated {TODAY}"
    raw_lines = [line1, line2, caveat, AIME_FOOTNOTE] + list(extra_lines or [])
    wrapped_lines = [textwrap.fill(line, width=wrap_width) for line in raw_lines]
    fig.text(
        0.01,
        0.01,
        "\n".join(wrapped_lines),
        fontsize=6.7,
        color=COLOR_TEXT_SECONDARY,
        va="bottom",
        ha="left",
        family="monospace",
    )


def assert_no_aime(df: pd.DataFrame, label_col: str) -> None:
    mask = df[label_col].astype(str).str.upper().str.contains("AIME")
    assert not mask.any(), f"AIME row(s) reached a plotted frame in column {label_col!r}: {df[mask]}"


def savefig(fig, stem: Path) -> tuple[Path, Path]:
    """Deterministic SVG + ~1600px-wide PNG so re-runs don't churn git."""
    svg_path = stem.with_suffix(".svg")
    png_path = stem.with_suffix(".png")
    fig.savefig(svg_path, format="svg", metadata={"Date": None})
    fig.savefig(png_path, format="png", dpi=200, metadata={"Software": None})
    return svg_path, png_path


# ---------------------------------------------------------------------------
# Ledger parsing helpers
# ---------------------------------------------------------------------------


def parse_seeds(cell: str) -> list[str]:
    if not cell:
        return []
    return [s.strip() for s in str(cell).split(";") if s.strip()]


def seed_count(seeds_cell: str) -> int:
    seeds = parse_seeds(seeds_cell)
    return len(seeds) if seeds else 1  # a logged row is at least one run


def parse_delta_tokens(cell: str) -> list[Optional[float]]:
    """Semicolon-separated per-seed delta cell -> list of floats, 'tie'
    mapped to the literal 0.0 it represents. Non-numeric/non-tie tokens
    become None (skipped by callers, never silently coerced)."""
    if not cell:
        return []
    out: list[Optional[float]] = []
    for raw in str(cell).split(";"):
        tok = raw.strip()
        if not tok:
            continue
        if tok.lower() == "tie":
            out.append(0.0)
        elif _NUMERIC_RE.match(tok):
            out.append(_to_float(tok))
        else:
            out.append(None)
    return out


def parse_numeric_list(cell: str) -> list[float]:
    if not cell:
        return []
    return [_to_float(t) for t in str(cell).split(";") if t.strip() and _NUMERIC_RE.match(t.strip())]


def is_true(cell) -> bool:
    return str(cell).strip().upper() == "TRUE"


# ---------------------------------------------------------------------------
# Core resolution: every ledger v1/v2 row -> one delta-vs-flagship record
# ---------------------------------------------------------------------------


@dataclass
class Resolved:
    benchmark: str
    config: str
    build_stage: str
    verdict: str
    comparator: str
    delta_pp: Optional[float]
    provenance: str
    per_seed_values: list = field(default_factory=list)
    seeds: int = 1
    n: Optional[str] = None
    contaminated: bool = False
    is_tie: bool = False
    fill: str = "hollow"
    shape: str = "unknown"


def flat_reference_accuracy(ledger_df: pd.DataFrame, benchmark: str) -> Optional[float]:
    """The benchmark's single canonical flagship-baseline accuracy. When the
    source doc only ever printed per-seed baseline values (no aggregate,
    e.g. SuperGPQA-hard's 79.5/79.3/76.5), the mean of those is used as an
    internal fallback anchor -- ONLY for configs that have no delta or
    per-seed data of their own to fall back on."""
    ref = ledger_df[
        (ledger_df["benchmark_label"] == benchmark)
        & (ledger_df["build_stage"] == "reference")
        & (ledger_df["config"].str.startswith(FLAGSHIP_BASELINE_PREFIX))
    ]
    if ref.empty:
        return None
    vals = parse_numeric_list(ref.iloc[0]["absolute_accuracy_pct"])
    if not vals:
        return None
    return sum(vals) / len(vals)


def fill_category(seeds: int, delta_pp: Optional[float], contaminated: bool, provenance: str) -> str:
    """Convention 2: solid = paired >=3 seeds clearing the +5 net-discordant
    bar (here, the +-5pp dashed line is used as the visual proxy for that
    bar, matching MCNEMAR_MIN_NET's own re-use across these figures). Half =
    2 seeds, or magnitude in [NOISE_FLOOR, MCNEMAR_MIN_NET). Hollow = single
    seed, OR inside the noise band -- nothing hollow is a claimed win.
    Contaminated rows and 'computed_matched_approx' (baseline-mismatch risk
    demonstrated on chem_thinking_gate, see module docstring) are capped
    below solid regardless of magnitude/seed count."""
    if delta_pp is None:
        return "hollow"
    magnitude = abs(delta_pp)
    if contaminated:
        return "hollow"
    if seeds <= 1 or magnitude < NOISE_FLOOR_PP:
        category = "hollow"
    elif seeds >= 3 and magnitude >= MCNEMAR_MIN_NET:
        category = "solid"
    else:
        category = "half"
    if provenance == "computed_matched_approx" and category == "solid":
        category = "half"
    return category


def marker_shape(delta_pp: Optional[float], is_tie: bool) -> str:
    if delta_pp is None:
        return "unknown"
    if is_tie or math.isclose(delta_pp, 0.0, abs_tol=1e-9):
        return "tie"
    return "win" if delta_pp > 0 else "loss"


def resolve_row(row: pd.Series, flat_ref: Optional[float]) -> Resolved:
    seeds = seed_count(row["seeds"])
    contaminated = is_true(row["contaminated"])
    per_seed = parse_delta_tokens(row["per_seed_delta_pp"])
    numeric_per_seed = [v for v in per_seed if v is not None]
    comparator = str(row["comparator"] or "")
    n_val = str(row["n_common_items"]).strip() or None

    mean_cell = str(row["mean_delta_pp"]).strip()
    if mean_cell:
        delta = _to_float(mean_cell)
        provenance = "printed_mean"
    elif numeric_per_seed:
        delta = sum(numeric_per_seed) / len(numeric_per_seed)
        provenance = "printed_per_seed_centroid"
    else:
        abs_vals = parse_numeric_list(row["absolute_accuracy_pct"])
        if abs_vals and flat_ref is not None:
            abs_mean = sum(abs_vals) / len(abs_vals)
            delta = abs_mean - flat_ref
            provenance = "computed_matched_approx" if "matched" in comparator.lower() else "computed_vs_flat_reference"
        else:
            delta = None
            provenance = "unresolved"

    is_tie = delta is not None and math.isclose(delta, 0.0, abs_tol=1e-9)
    fill = fill_category(seeds, delta, contaminated, provenance)
    shape = marker_shape(delta, is_tie)

    return Resolved(
        benchmark=row["benchmark_label"],
        config=row["config"],
        build_stage=row["build_stage"],
        verdict=row["verdict"],
        comparator=comparator,
        delta_pp=delta,
        provenance=provenance,
        per_seed_values=numeric_per_seed,
        seeds=seeds,
        n=n_val,
        contaminated=contaminated,
        is_tie=is_tie,
        fill=fill,
        shape=shape,
    )


def resolve_ledger_configs(ledger_df: pd.DataFrame) -> pd.DataFrame:
    """Resolves every build_stage in {v1, v2} ledger row to one delta-vs-
    flagship record. Reference rows (the baselines themselves, and the
    separate qwen3.8_solo 'family-best solo' comparator) are excluded here --
    they anchor deltas, they are not orchestrations being measured."""
    configs = ledger_df[ledger_df["build_stage"].isin(["v1", "v2"])].copy()
    flat_refs = {b: flat_reference_accuracy(ledger_df, b) for b in ledger_df["benchmark_label"].unique()}
    records = [resolve_row(row, flat_refs.get(row["benchmark_label"])) for _, row in configs.iterrows()]
    out = pd.DataFrame([r.__dict__ for r in records])
    return out


# ---------------------------------------------------------------------------
# Drawing primitives
# ---------------------------------------------------------------------------


def _color_for_shape(shape: str) -> str:
    return {"win": COLOR_WIN, "loss": COLOR_LOSS, "tie": COLOR_NEUTRAL, "unknown": COLOR_NEUTRAL}[shape]


def _marker_for_shape(shape: str) -> str:
    # Horizontal orientation throughout (x = delta): win points right,
    # loss points left, tie/neutral is a diamond (convention 6).
    return {"win": ">", "loss": "<", "tie": "D", "unknown": "x"}[shape]


def draw_point(ax, x: float, y: float, shape: str, fill: str, contaminated: bool, size: float = 11.0, zorder: int = 5):
    """One evidence-strength-encoded marker: solid/half/hollow fill via
    Line2D fillstyle for the plain case; a hatched, distinct-outline patch
    (never solid) for contaminated rows, per convention 3."""
    color = _color_for_shape(shape)
    if contaminated:
        patch = RegularPolygon(
            (x, y),
            numVertices=3 if shape in ("win", "loss") else 4,
            radius=0.30,
            orientation=(np.pi / 2 if shape == "win" else -np.pi / 2 if shape == "loss" else np.pi / 4),
            facecolor="none",
            edgecolor=COLOR_CONTAM_EDGE,
            hatch="///",
            linewidth=1.6,
            zorder=zorder,
        )
        ax.add_patch(patch)
        return
    fillstyle = {"solid": "full", "half": "left", "hollow": "none"}[fill]
    marker = _marker_for_shape(shape)
    ax.plot(
        [x],
        [y],
        marker=marker,
        fillstyle=fillstyle,
        markersize=size,
        markeredgewidth=1.6,
        markeredgecolor=color if fill != "hollow" else color,
        markerfacecolor=color,
        color=color,
        linestyle="none",
        zorder=zorder,
    )


def draw_v1_circle(ax, x: float, y: float, zorder: int = 5):
    ax.plot(
        [x],
        [y],
        marker="o",
        fillstyle="none",
        markersize=10,
        markeredgewidth=1.8,
        markeredgecolor=COLOR_TEXT_PRIMARY,
        zorder=zorder,
    )


def draw_thresholds_x(ax, xmin: float, xmax: float):
    """Convention 4: a grey +-2.5pp noise-floor ribbon (labelled inside the
    band) and dashed +-5pp minimum-net-discordant lines, on the x (delta)
    axis. Caller supplies xmin/xmax so the ribbon/lines only draw within the
    plotted axis extent."""
    ax.axvspan(-NOISE_FLOOR_PP, NOISE_FLOOR_PP, facecolor=COLOR_RIBBON, zorder=0, edgecolor=COLOR_RIBBON_EDGE, linewidth=0.5)
    ax.axvline(0.0, color=COLOR_ZERO_LINE, linewidth=1.1, zorder=1)
    for x in (-MCNEMAR_MIN_NET, MCNEMAR_MIN_NET):
        if xmin <= x <= xmax:
            ax.axvline(x, color=COLOR_MCNEMAR_LINE, linewidth=0.9, linestyle="--", zorder=1)


def n_seed_label(config: str, n, seeds: int) -> str:
    is_missing = n is None or (isinstance(n, float) and math.isnan(n)) or str(n).strip().lower() in ("", "nan", "none")
    n_disp = "NR" if is_missing else n
    seed_word = "seed" if seeds == 1 else "seeds"
    return f"{config} (n={n_disp}, {seeds} {seed_word})"


def provenance_title(tag: str, title: str) -> str:
    return f"{tag} {title}"


def add_title_block(fig, tag: str, title_text: str, subtitle_text: str, title_y: float = 0.975, subtitle_y: float = 0.935) -> None:
    """Title + subtitle as figure-level text (never axes-relative), so the
    two never collide regardless of axes size -- convention 1's provenance
    tag lives in the title itself, so a cropped screenshot can't lose it."""
    fig.text(0.01, title_y, provenance_title(tag, title_text), fontsize=13.5, color=TAG_COLOR[tag], ha="left", va="top", fontweight="bold")
    fig.text(0.01, subtitle_y, subtitle_text, fontsize=8.3, color=COLOR_TEXT_SECONDARY, ha="left", va="top")


# ---------------------------------------------------------------------------
# F03 -- evidence inventory heatmap (renders first; frames everything else)
# ---------------------------------------------------------------------------


def build_f03_frame() -> pd.DataFrame:
    frontier = load_frontier()
    df = frontier.data.copy()
    df = df[df["benchmark"].astype(str).str.upper() != "AIME"].copy()
    assert_no_aime(df, "benchmark")
    df["seed_count"] = df["seeds"].apply(seed_count)
    df["contaminated"] = df["config"].isin(CONTAMINATION_FOOTNOTES.keys())
    return df, frontier.caveat, [str(p.relative_to(PROJECT_ROOT)) for p in frontier.source_paths]


def make_f03(only_check: bool = False) -> Path:
    df, caveat, source_files = build_f03_frame()

    bench_order = df.groupby("benchmark").size().sort_values(ascending=False).index.tolist()
    config_freq = df.groupby("config")["benchmark"].nunique().sort_values(ascending=False)
    config_order = config_freq.index.tolist()

    n_rows, n_cols = len(bench_order), len(config_order)
    row_idx = {b: i for i, b in enumerate(bench_order)}
    col_idx = {c: j for j, c in enumerate(config_order)}

    max_seeds = int(df["seed_count"].max())
    ramp = SEQ_BLUE

    def color_for_seeds(k: int) -> str:
        if max_seeds <= 1:
            return ramp[3]
        frac = (k - 1) / max(1, max_seeds - 1)
        idx = min(len(ramp) - 1, int(round(frac * (len(ramp) - 1))))
        return ramp[idx]

    fig_w = max(14.0, 0.42 * n_cols + 3)
    fig_h = max(6.5, 0.42 * n_rows + 3)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    for _, row in df.iterrows():
        i, j = row_idx[row["benchmark"]], col_idx[row["config"]]
        k = int(row["seed_count"])
        n = int(row["n"])
        contaminated = bool(row["contaminated"])
        color = color_for_seeds(k)
        rect = plt.Rectangle((j, i), 1, 1, facecolor=color, edgecolor="white", linewidth=0.8)
        ax.add_patch(rect)
        if contaminated:
            hatch_rect = plt.Rectangle(
                (j, i), 1, 1, facecolor="none", edgecolor=COLOR_CONTAM_EDGE, hatch="///", linewidth=1.4
            )
            ax.add_patch(hatch_rect)
        text_color = "white" if k >= (max_seeds / 2) else COLOR_TEXT_PRIMARY
        label = f"n={n}"
        if contaminated:
            label += "*"
        ax.text(j + 0.5, i + 0.5, label, ha="center", va="center", fontsize=6.2, color=text_color)

    ax.set_xlim(0, n_cols)
    ax.set_ylim(0, n_rows)
    ax.invert_yaxis()
    ax.set_xticks([j + 0.5 for j in range(n_cols)])
    ax.set_xticklabels(config_order, rotation=75, ha="right", fontsize=7)
    bench_labels = [f"{b} ({config_freq.index.isin(df[df['benchmark'] == b]['config']).sum() if False else int((df['benchmark'] == b).sum())} configs)" for b in bench_order]
    ax.set_yticks([i + 0.5 for i in range(n_rows)])
    ax.set_yticklabels(bench_labels, fontsize=8)
    ax.set_xlabel("config", fontsize=9)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    # legend: sequential ramp swatch
    legend_handles = [
        Line2D([0], [0], marker="s", color="none", markerfacecolor=color_for_seeds(k), markersize=12, label=f"{k} seed{'s' if k != 1 else ''}")
        for k in sorted(df["seed_count"].unique())
    ]
    legend_handles.append(
        Line2D([0], [0], marker="s", color="none", markerfacecolor="none", markeredgecolor=COLOR_CONTAM_EDGE, markersize=12, label="contaminated (hatched)")
    )
    ax.legend(handles=legend_handles, loc="upper left", bbox_to_anchor=(1.005, 1.0), fontsize=7.5, frameon=False, title="seed count")

    fig.subplots_adjust(left=0.16, right=0.86, top=0.84, bottom=0.22)
    add_title_block(
        fig,
        "[POOLED-MARGINAL]",
        "F03 -- Evidence inventory: seed coverage per (benchmark, config)",
        "Cell shade = seed count (darker = more seeds). Blank = never run. Hatch = survivorship-contaminated config.",
        title_y=0.975,
        subtitle_y=0.925,
    )
    add_footer(
        fig,
        source_files,
        caveat,
        extra_lines=[
            "GPQA-Diamond ran 24 logged configs; GSM8K ran 2 -- coverage, not accuracy, is what this figure plots.",
            "Tier B (pooled-marginal) is legitimate here: F03 plots coverage, never a validated accuracy claim.",
        ],
    )

    out_frame = df[["benchmark", "config", "n", "seed_count", "seeds", "accuracy", "contaminated", "on_pareto_frontier"]].copy()
    out_frame = out_frame.sort_values(["benchmark", "config"])
    csv_path = RESULTS_DIR / "figure_f03_evidence_inventory_heatmap.csv"
    out_frame.to_csv(csv_path, index=False)

    stem = FIGURES_DIR / "f03_evidence_inventory_heatmap"
    svg_path, png_path = savefig(fig, stem)
    plt.close(fig)
    print(f"F03 written: {svg_path}, {png_path}, {csv_path}")
    return csv_path


# ---------------------------------------------------------------------------
# F01 -- build progress in gap space (the core ask)
# ---------------------------------------------------------------------------


def make_f01() -> Path:
    ledger = load_ledger()
    ledger_df = ledger.data.copy()
    assert_no_aime(ledger_df, "benchmark_label")
    resolved = resolve_ledger_configs(ledger_df)

    rows_for_plot = []  # each: dict with benchmark, kind('arrow'/'single'), points list

    all_benchmarks = ledger_df["benchmark_label"].unique().tolist()
    for benchmark in all_benchmarks:
        bench_resolved = resolved[resolved["benchmark"] == benchmark]
        has_v1 = (bench_resolved["build_stage"] == "v1").any()
        has_v2 = (bench_resolved["build_stage"] == "v2").any()

        if benchmark in ARROW_BENCHMARKS and has_v1 and has_v2:
            v1_row = bench_resolved[bench_resolved["build_stage"] == "v1"].iloc[0]
            v2_candidates = bench_resolved[(bench_resolved["build_stage"] == "v2") & (~bench_resolved["contaminated"])]
            v2_candidates = v2_candidates[v2_candidates["delta_pp"].notna()]
            best_row = v2_candidates.loc[v2_candidates["delta_pp"].idxmax()]
            rows_for_plot.append(
                {
                    "benchmark": benchmark,
                    "kind": "arrow",
                    "v1": v1_row,
                    "best": best_row,
                }
            )
        else:
            # "one build ever": every non-reference row for this benchmark,
            # plotted as unconnected single markers (never an arrow).
            singles = bench_resolved[bench_resolved["delta_pp"].notna()]
            rows_for_plot.append({"benchmark": benchmark, "kind": "single", "points": singles})

    def sort_key(entry):
        if entry["kind"] == "arrow":
            return (0, -abs(entry["best"]["delta_pp"]))
        pts = entry["points"]
        best_mag = pts["delta_pp"].abs().max() if len(pts) else 0
        return (1, -best_mag)

    rows_for_plot.sort(key=sort_key)

    n_rows = len(rows_for_plot)
    fig, ax = plt.subplots(figsize=(14.5, max(6.5, 0.72 * n_rows + 2)))

    all_deltas = [ledger_v for entry in rows_for_plot for ledger_v in (
        [entry["v1"]["delta_pp"], entry["best"]["delta_pp"]] if entry["kind"] == "arrow"
        else entry["points"]["delta_pp"].tolist()
    )]
    xmin = min(all_deltas + [-MCNEMAR_MIN_NET]) - 2.5
    xmax = max(all_deltas + [MCNEMAR_MIN_NET]) + 4.5

    ytick_labels = []
    plotted_rows = []
    contam_letters: dict[str, str] = {}

    for i, entry in enumerate(rows_for_plot):
        y = n_rows - 1 - i
        benchmark = entry["benchmark"]
        if entry["kind"] == "arrow":
            v1, best = entry["v1"], entry["best"]
            draw_v1_circle(ax, v1["delta_pp"], y)
            ax.annotate(
                "",
                xy=(best["delta_pp"], y),
                xytext=(v1["delta_pp"], y),
                arrowprops=dict(arrowstyle="-|>", color=COLOR_TEXT_SECONDARY, lw=1.3, shrinkA=8, shrinkB=8),
                zorder=3,
            )
            draw_point(ax, best["delta_pp"], y, best["shape"], best["fill"], best["contaminated"])
            approx_flag = "*" if best["provenance"] == "computed_matched_approx" else ""
            going_right = best["delta_pp"] >= v1["delta_pp"]
            ax.text(
                best["delta_pp"] + (0.4 if going_right else -0.4),
                y + 0.28,
                f"{best['config']}{approx_flag}",
                fontsize=7.3,
                color=COLOR_TEXT_PRIMARY,
                ha="left" if going_right else "right",
            )
            ytick_labels.append(f"{benchmark}\n{n_seed_label(best['config'], best['n'], best['seeds'])}")
            plotted_rows.append(
                dict(benchmark=benchmark, role="v1", config=v1["config"], delta_pp=v1["delta_pp"], provenance=v1["provenance"], seeds=v1["seeds"], n=v1["n"], contaminated=v1["contaminated"], fill=v1["fill"], shape=v1["shape"])
            )
            plotted_rows.append(
                dict(benchmark=benchmark, role="current_best", config=best["config"], delta_pp=best["delta_pp"], provenance=best["provenance"], seeds=best["seeds"], n=best["n"], contaminated=best["contaminated"], fill=best["fill"], shape=best["shape"])
            )
            if best["contaminated"]:
                contam_letters.setdefault(best["config"], chr(ord("a") + len(contam_letters)))
        else:
            pts = entry["points"]
            configs_seen = []
            for _, p in pts.iterrows():
                draw_point(ax, p["delta_pp"], y, p["shape"], p["fill"], p["contaminated"])
                configs_seen.append(p["config"])
                plotted_rows.append(
                    dict(benchmark=benchmark, role="single_build", config=p["config"], delta_pp=p["delta_pp"], provenance=p["provenance"], seeds=p["seeds"], n=p["n"], contaminated=p["contaminated"], fill=p["fill"], shape=p["shape"])
                )
                if p["contaminated"]:
                    contam_letters.setdefault(p["config"], chr(ord("a") + len(contam_letters)))
            has_v1_single = (pts["build_stage"] == "v1").any()
            note = "v1 only -- no second build run" if has_v1_single else "v2 only -- no v1 shipped"
            x_note = pts["delta_pp"].max() + 0.8
            ax.text(x_note, y + 0.28, note, fontsize=7.0, color=COLOR_TEXT_SECONDARY, va="center", style="italic")
            n_configs = len(pts)
            config_lines = "\n".join(n_seed_label(c, n, s) for c, n, s in zip(pts["config"], pts["n"], pts["seeds"]))
            ytick_labels.append(f"{benchmark}\n{config_lines}")

    draw_thresholds_x(ax, xmin, xmax)
    ax.text(NOISE_FLOOR_PP + 0.1, n_rows - 0.55, f"+{NOISE_FLOOR_PP}pp", fontsize=6.8, color=COLOR_TEXT_SECONDARY)
    ax.text(-NOISE_FLOOR_PP - 0.1, n_rows - 0.55, f"-{NOISE_FLOOR_PP}pp noise floor", fontsize=6.8, color=COLOR_TEXT_SECONDARY, ha="right")

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(-0.7, n_rows - 0.15)
    ax.set_yticks(range(n_rows - 1, -1, -1))
    ax.set_yticklabels(ytick_labels, fontsize=7.6)
    ax.set_xlabel("paired delta vs. the single flagship call (pp) -- x=0 is flagship parity", fontsize=9)

    legend_handles = [
        Line2D([0], [0], marker="o", fillstyle="none", color=COLOR_TEXT_PRIMARY, linestyle="none", markersize=9, label="v1 (shipped engine)"),
        Line2D([0], [0], marker=">", fillstyle="full", color=COLOR_WIN, linestyle="none", markersize=9, label="win, solid=strong"),
        Line2D([0], [0], marker=">", fillstyle="left", color=COLOR_WIN, linestyle="none", markersize=9, label="win, half=moderate"),
        Line2D([0], [0], marker=">", fillstyle="none", color=COLOR_WIN, linestyle="none", markersize=9, label="win, hollow=1-seed/inside noise floor"),
        Line2D([0], [0], marker="<", fillstyle="none", color=COLOR_LOSS, linestyle="none", markersize=9, label="loss"),
        Line2D([0], [0], marker="D", fillstyle="none", color=COLOR_NEUTRAL, linestyle="none", markersize=8, label="tie (0.0pp)"),
    ]
    if contam_letters:
        legend_handles.append(
            Line2D([0], [0], marker="s", color="none", markeredgecolor=COLOR_CONTAM_EDGE, markerfacecolor="none", markersize=9, label="hatched = contaminated (see footer)")
        )

    fig.subplots_adjust(left=0.26, right=0.90, top=0.85, bottom=0.30)
    fig.legend(handles=legend_handles, loc="lower center", bbox_to_anchor=(0.60, 0.135), fontsize=7, frameon=False, ncol=4)

    # Only emit the '*' footnote if a plotted row actually carries that
    # provenance. A footnote with no referent on the chart reads as sloppiness
    # and quietly devalues the contamination footnotes beside it, which DO have
    # referents. (chem_thinking_gate stopped needing it once its printed
    # matched-seed delta, +4.4pp, was transcribed into the ledger; chem_flagship_gate
    # still needs it in F02, because its seeds 555/777/888 genuinely have no
    # matched-baseline row anywhere in the findings docs.)
    extra = []
    if any(row.get("provenance") == "computed_matched_approx" for row in plotted_rows):
        extra.append(
            "* = delta approximated against the flat single-seed flagship reference, because the ledger records a "
            "matched-seed comparator for this config without a separate matched-baseline row to subtract. Such rows are "
            "capped at half-fill or below, never solid."
        )
    if contam_letters:
        for cfg, letter in contam_letters.items():
            note = CONTAMINATION_FOOTNOTES.get(cfg, "")
            extra.append(f"({letter}) {cfg}: {note}")
    add_footer(fig, [str(p.relative_to(PROJECT_ROOT)) for p in ledger.source_paths], ledger.caveat, extra_lines=extra)
    add_title_block(
        fig,
        "[PAIRED]",
        "F01 -- Build progress in gap space: v1 -> current best, per benchmark",
        "Open circle = v1 (shipped engine). Filled/hollow triangle = current best v2 lever (fill = evidence strength). Arrow only where a genuine v1->v2 pair exists.",
        title_y=0.975,
        subtitle_y=0.930,
    )

    out_df = pd.DataFrame(plotted_rows)
    csv_path = RESULTS_DIR / "figure_f01_build_progress_gap_space.csv"
    out_df.to_csv(csv_path, index=False)

    stem = FIGURES_DIR / "f01_build_progress_gap_space"
    svg_path, png_path = savefig(fig, stem)
    plt.close(fig)
    print(f"F01 written: {svg_path}, {png_path}, {csv_path}")
    return csv_path


# ---------------------------------------------------------------------------
# F02 -- every orchestration's delta vs baseline, with the noise band
# ---------------------------------------------------------------------------


def make_f02() -> Path:
    ledger = load_ledger()
    ledger_df = ledger.data.copy()
    assert_no_aime(ledger_df, "benchmark_label")
    resolved = resolve_ledger_configs(ledger_df)
    resolved = resolved[resolved["delta_pp"].notna()].copy()

    benchmarks = sorted(resolved["benchmark"].unique(), key=lambda b: -len(resolved[resolved["benchmark"] == b]))
    max_configs = max(len(resolved[resolved["benchmark"] == b]) for b in benchmarks)

    xmin = min(-MCNEMAR_MIN_NET - 2, resolved["delta_pp"].min() - 2)
    xmax = max(MCNEMAR_MIN_NET + 2, resolved["delta_pp"].max() + 2)

    n_bench = len(benchmarks)
    n_cols = 3
    n_plot_rows = math.ceil(n_bench / n_cols)
    fig, axes = plt.subplots(n_plot_rows, n_cols, figsize=(15, 3.1 * n_plot_rows), squeeze=False)

    for idx, benchmark in enumerate(benchmarks):
        r, c = divmod(idx, n_cols)
        ax = axes[r][c]
        sub = resolved[resolved["benchmark"] == benchmark].sort_values("delta_pp")
        draw_thresholds_x(ax, xmin, xmax)
        y_positions = range(len(sub))
        for y, (_, row) in zip(y_positions, sub.iterrows()):
            ax.plot([0, row["delta_pp"]], [y, y], color=COLOR_TEXT_SECONDARY, linewidth=1.0, zorder=2)
            draw_point(ax, row["delta_pp"], y, row["shape"], row["fill"], row["contaminated"], size=9)
        ax.set_yticks(list(y_positions))
        ax.set_yticklabels(
            [
                # '*' marks a delta measured against the flat reference rather than
                # a matched-seed baseline -- see the footer note. Without this the
                # footnote would have no visible referent on the chart.
                n_seed_label(row["config"], row["n"], row["seeds"])
                + ("*" if row["provenance"] == "computed_matched_approx" else "")
                for _, row in sub.iterrows()
            ],
            fontsize=6.6,
        )
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(-0.7, max(len(sub) - 0.3, 0.5))
        ax.set_title(f"{benchmark} ({len(sub)} configs)", fontsize=9.5, loc="left")
        ax.tick_params(axis="x", labelsize=7)
        if len(sub) < 3:
            ax.text(
                0.5,
                0.5,
                f"{len(sub)} of {max_configs} configs run here",
                transform=ax.transAxes,
                fontsize=9,
                color=COLOR_RIBBON_EDGE,
                ha="center",
                va="center",
                alpha=0.9,
                rotation=20,
            )

    for idx in range(n_bench, n_plot_rows * n_cols):
        r, c = divmod(idx, n_cols)
        axes[r][c].axis("off")

    legend_handles = [
        Line2D([0], [0], marker=">", fillstyle="full", color=COLOR_WIN, linestyle="none", markersize=8, label="win, solid"),
        Line2D([0], [0], marker=">", fillstyle="left", color=COLOR_WIN, linestyle="none", markersize=8, label="win, half"),
        Line2D([0], [0], marker=">", fillstyle="none", color=COLOR_WIN, linestyle="none", markersize=8, label="win, hollow"),
        Line2D([0], [0], marker="<", fillstyle="none", color=COLOR_LOSS, linestyle="none", markersize=8, label="loss"),
        Line2D([0], [0], marker="D", fillstyle="none", color=COLOR_NEUTRAL, linestyle="none", markersize=7, label="tie"),
        Line2D([0], [0], marker="s", color="none", markeredgecolor=COLOR_CONTAM_EDGE, markerfacecolor="none", markersize=8, label="contaminated"),
    ]
    fig.legend(handles=legend_handles, loc="upper right", fontsize=7.3, frameon=False, ncol=3, bbox_to_anchor=(0.985, 0.965))

    fig.subplots_adjust(left=0.14, right=0.985, top=0.84, bottom=0.14, hspace=0.55, wspace=0.35)

    contaminated_configs = resolved[resolved["contaminated"]]["config"].unique().tolist()
    extra = [f"({chr(ord('a') + i)}) {cfg}: {CONTAMINATION_FOOTNOTES.get(cfg, '')}" for i, cfg in enumerate(contaminated_configs)]

    # Disclose the baseline-mismatch approximation HERE too. F01 marked such
    # configs with '*' and footnoted them, but this panel grid did neither --
    # so chem_flagship_gate's delta (its seeds 555/777/888 have no matched
    # baseline row anywhere in the findings docs, so it is measured against the
    # flat single-seed reference) was being drawn with no disclosure at all.
    # An undisclosed approximation is a worse failure than a redundant footnote.
    approx_configs = sorted(resolved[resolved["provenance"] == "computed_matched_approx"]["config"].unique().tolist())
    if approx_configs:
        extra.append(
            f"* {', '.join(approx_configs)}: delta measured against the flat single-seed flagship reference -- the ledger "
            "records a matched-seed comparator for these configs but no matched-baseline row exists to subtract. Capped at "
            "half-fill or below, never solid."
        )

    unresolved_n = len(load_ledger().data[load_ledger().data["build_stage"].isin(["v1", "v2"])]) - len(resolved)
    if unresolved_n:
        extra.append(f"{unresolved_n} v1/v2 ledger row(s) had no usable delta (no mean/per-seed/absolute+reference) -- excluded here, still in F03.")
    add_footer(fig, [str(p.relative_to(PROJECT_ROOT)) for p in ledger.source_paths], ledger.caveat, extra_lines=extra)
    add_title_block(
        fig,
        "[PAIRED]",
        "F02 -- Every orchestration's delta vs. baseline, per benchmark",
        "Sorted by delta. Same x-axis extent in every panel (convention 8) -- sparse panels are watermarked, never rescaled.",
        title_y=0.975,
        subtitle_y=0.895,
    )

    csv_path = RESULTS_DIR / "figure_f02_lever_deltas_by_benchmark.csv"
    resolved.drop(columns=["per_seed_values"]).to_csv(csv_path, index=False)

    stem = FIGURES_DIR / "f02_lever_deltas_by_benchmark"
    svg_path, png_path = savefig(fig, stem)
    plt.close(fig)
    print(f"F02 written: {svg_path}, {png_path}, {csv_path}")
    return csv_path


# ---------------------------------------------------------------------------
# F06 -- per-seed spread for multi-seed configs
# ---------------------------------------------------------------------------


def make_f06() -> Path:
    ledger = load_ledger()
    ledger_df = ledger.data.copy()
    assert_no_aime(ledger_df, "benchmark_label")

    configs = ledger_df[ledger_df["build_stage"].isin(["v1", "v2"])].copy()
    all_v1v2_n = len(configs)

    multi_rows = []
    single_seat_excluded = 0
    no_perseed_data_excluded = []
    for _, row in configs.iterrows():
        seeds_list = parse_seeds(row["seeds"])
        n_seeds_logged = len(seeds_list) if seeds_list else 1
        tokens = parse_delta_tokens(row["per_seed_delta_pp"])
        numeric_tokens = [t for t in tokens if t is not None]
        if n_seeds_logged <= 1:
            single_seat_excluded += 1
            continue
        if len(numeric_tokens) < 2:
            no_perseed_data_excluded.append(row["config"])
            continue
        seeds_for_tokens = seeds_list[: len(tokens)]
        for seed_label, tok in zip(seeds_for_tokens, tokens):
            if tok is None:
                continue
            multi_rows.append(
                dict(
                    benchmark=row["benchmark_label"],
                    config=row["config"],
                    seed=seed_label,
                    delta_pp=tok,
                    is_tie=math.isclose(tok, 0.0, abs_tol=1e-9),
                )
            )

    spread_df = pd.DataFrame(multi_rows)
    pair_order = (
        spread_df.groupby(["benchmark", "config"])["delta_pp"]
        .mean()
        .sort_values()
        .index.tolist()
    )
    pair_idx = {p: i for i, p in enumerate(pair_order)}
    n_pairs = len(pair_order)

    fig, ax = plt.subplots(figsize=(11, max(3.2, 0.75 * n_pairs + 1.6)))
    xmin = min(-MCNEMAR_MIN_NET - 2, spread_df["delta_pp"].min() - 2)
    xmax = max(MCNEMAR_MIN_NET + 2, spread_df["delta_pp"].max() + 2)
    draw_thresholds_x(ax, xmin, xmax)

    for (benchmark, config), y in pair_idx.items():
        sub = spread_df[(spread_df["benchmark"] == benchmark) & (spread_df["config"] == config)]
        for _, p in sub.iterrows():
            if p["is_tie"]:
                color, marker = COLOR_NEUTRAL, "D"
            else:
                color, marker = (COLOR_WIN if p["delta_pp"] > 0 else COLOR_LOSS), "o"
            ax.plot([p["delta_pp"]], [y], marker=marker, markersize=9, color=color, markeredgecolor=color, alpha=0.9, zorder=4)
        mean_val = sub["delta_pp"].mean()
        ax.plot([mean_val, mean_val], [y - 0.22, y + 0.22], color=COLOR_TEXT_PRIMARY, linewidth=2.2, zorder=5)

    ax.set_yticks(list(pair_idx.values()))
    ax.set_yticklabels(
        [f"{b} / {c} ({len(spread_df[(spread_df.benchmark==b)&(spread_df.config==c)])} seeds)" for b, c in pair_order],
        fontsize=8.5,
    )
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(-0.7, n_pairs - 0.3)
    ax.set_xlabel("per-seed delta vs. baseline (pp)", fontsize=9)

    legend_handles = [
        Line2D([0], [0], marker="o", color=COLOR_WIN, linestyle="none", markersize=8, label="seed, positive delta"),
        Line2D([0], [0], marker="o", color=COLOR_LOSS, linestyle="none", markersize=8, label="seed, negative delta"),
        Line2D([0], [0], marker="D", color=COLOR_NEUTRAL, linestyle="none", markersize=7, label="seed, tie (0.0pp)"),
        Line2D([0], [0], color=COLOR_TEXT_PRIMARY, linewidth=2.2, label="mean of seeds shown"),
    ]
    ax.legend(handles=legend_handles, loc="lower right", fontsize=7.5, frameon=False)

    fig.subplots_adjust(left=0.30, right=0.97, top=0.78, bottom=0.32)

    extra = [
        f"{single_seat_excluded} configs at 1 seed -- variance unmeasured (excluded: a lone dot reads as zero variance).",
    ]
    if no_perseed_data_excluded:
        extra.append(
            f"{len(no_perseed_data_excluded)} additional configs have >=2 seeds but no per-seed delta breakdown in the ledger "
            f"({', '.join(no_perseed_data_excluded)}) -- e.g. chem_thinking_gate's per-seed accuracy (90.9/91.0/90.8, "
            "lever_findings.md) exists in prose but the ledger's per_seed_delta_pp cell is empty; excluded here rather than fabricated."
        )
    add_footer(fig, [str(p.relative_to(PROJECT_ROOT)) for p in ledger.source_paths], ledger.caveat, extra_lines=extra)
    add_title_block(
        fig,
        "[PAIRED]",
        "F06 -- Per-seed spread for multi-seed configs",
        "One dot per seed, mean tick in black. Diamond = a literal 'tie' seed (0.0pp). Only configs with a per-seed delta breakdown in the ledger appear.",
        title_y=0.975,
        subtitle_y=0.895,
    )

    csv_path = RESULTS_DIR / "figure_f06_per_seed_spread.csv"
    spread_df.to_csv(csv_path, index=False)

    stem = FIGURES_DIR / "f06_per_seed_spread"
    svg_path, png_path = savefig(fig, stem)
    plt.close(fig)
    print(f"F06 written: {svg_path}, {png_path}, {csv_path}")
    print(f"  ({all_v1v2_n} total v1/v2 ledger rows: {single_seat_excluded} single-seed, {len(no_perseed_data_excluded)} multi-seed-no-breakdown, {n_pairs} plotted)")
    return csv_path


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", choices=["f01", "f02", "f03", "f06"], default=None, help="Build only this figure (default: all four, F03 first).")
    args = parser.parse_args()

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    builders = {"f03": make_f03, "f01": make_f01, "f02": make_f02, "f06": make_f06}
    order = ["f03", "f01", "f02", "f06"]

    if args.only:
        builders[args.only]()
    else:
        for key in order:
            builders[key]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
