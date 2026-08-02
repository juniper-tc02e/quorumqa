"""F04 / F05 / F07 / F08 / F09 -- QuorumQA's "analysis" figure set (the
uncomfortable-findings half of the figure deck; the counterpart
`make_figures_progress.py` -- owned by a different worker, not touched here
-- covers the shipped-wins half).

Every number plotted here comes from `benchmark/figure_data.py`'s typed
loaders (`load_ledger`, `load_frontier`, `load_moo_small_n`,
`load_subject_deltas`, `load_agent_eras`) -- never a hand-copied constant --
so a fresh checkout reproduces byte-identical figures. See
`benchmark/results/figure_claims_ledger.md` for the provenance-tier contract
these loaders enforce (Tier A paired / Tier B pooled-marginal / Tier C
paired-small-n) and why conflating tiers is a documented, repeated trap in
this project's own history (three confirmed cases in that doc).

  F04  Accuracy-vs-tokens compute frontier, one small-multiple panel per
       benchmark (load_frontier, Tier B/POOLED-MARGINAL). Makes visible the
       uncomfortable F2 finding: a bare single flagship call Pareto-
       dominates every deliberation lever on 6 of the 9 logged benchmarks
       (docs/negative-results.md Sec.3.6 F1). AIME is excluded from the
       plotted panels (survivorship-invalidated pilot, EXCLUDED_BENCHMARKS)
       but stays in the "9" denominator to match the published claim
       verbatim -- the footer states this explicitly.
  F05  The central law: cheap-tier unanimous-wrong rate vs best validated
       paired lever delta, one point per benchmark (load_ledger,
       Tier A/PAIRED). Only 5 of the ledger's 9 benchmark_labels carry a
       ledger-sourced unanimous_wrong_rate_pct cell -- GPQA-Diamond does
       NOT (its only public unanimous-wrong number, 9.5%, lives in
       wrongness_predictor_findings.md and is a POOLED-across-all-configs
       quantity, explicitly excluded per the task brief's hard constraint).
       5 points are plotted, not the round number of 7 sometimes quoted
       informally; see this module's own header comment above build_f05().
  F07  Twin heatmap: MoO per-bucket delta-vs-single-call (left) and
       escalation rate (right), same 7 profiles x 4 buckets axes
       (load_moo_small_n, Tier C/PAIRED-SMALL-N). Escalation-rate cells are
       synthesized from moo_calibration_table.csv's finer router-bucket
       grain via an n-weighted rename/merge onto f5_difficulty_map.csv's 4
       buckets (mapping documented in F07_BUCKET_MAP below) so the two
       panels share one honest axis.
  F08  Subject-level paired deltas, all 43 records (load_subject_deltas,
       Tier C/PAIRED-SMALL-N) -- the diagnosis (GPQA Organic Chemistry,
       n=86, -14.0pp/-12 items) that motivated chem_flagship_gate and
       chem_thinking_gate.
  F09  Agent hardening, matched seed-7 Terminal-Bench sample (load_agent_eras,
       Tier A/PAIRED). Reproduces the published 5/14 (36%) -> 12/14 (86%)
       graded-coverage claim and the 2/14 -> 4/14 solved count from
       docs/superpowers/plans/notes/2026-07-22-terminal-bench-seed7-pilot.md,
       using ONLY the (job_name in {phase1-pilot-seed7c, phase1-pilot-seed7})
       vs (job_name == seed7-hardened-rerun) matched-task_name subset --
       the only true same-task pairing in the CSV (hardened-baseline-seed3
       has no pre-hardening counterpart and is excluded from this figure).

Usage:
    .venv/Scripts/python.exe benchmark/make_figures_analysis.py
    .venv/Scripts/python.exe benchmark/make_figures_analysis.py --only f04

Writes:
    docs/figures/f04_accuracy_vs_tokens_frontier.{svg,png}
    docs/figures/f05_unanimous_wrong_vs_lever_delta.{svg,png}
    docs/figures/f07_moo_delta_escalation_heatmap.{svg,png}
    docs/figures/f08_subject_paired_deltas.{svg,png}
    docs/figures/f09_agent_hardening.{svg,png}
    benchmark/results/figure_f04_accuracy_vs_tokens_frontier.csv
    benchmark/results/figure_f05_unanimous_wrong_vs_lever_delta.csv
    benchmark/results/figure_f07_moo_delta_escalation_heatmap.csv
    benchmark/results/figure_f08_subject_paired_deltas.csv
    benchmark/results/figure_f09_agent_hardening.csv

Zero API calls -- pure offline CSV/JSON plotting via matplotlib (Agg).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import textwrap
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyArrowPatch, Rectangle  # noqa: E402

try:
    from benchmark.figure_data import (
        CONTAMINATION_FOOTNOTES,
        EXCLUDED_BENCHMARKS,
        MCNEMAR_MIN_NET,
        NOISE_FLOOR_PP,
        PROJECT_ROOT,
        load_agent_eras,
        load_frontier,
        load_ledger,
        load_moo_small_n,
        load_subject_deltas,
    )
except ImportError:  # running as `python benchmark/make_figures_analysis.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from figure_data import (  # type: ignore
        CONTAMINATION_FOOTNOTES,
        EXCLUDED_BENCHMARKS,
        MCNEMAR_MIN_NET,
        NOISE_FLOOR_PP,
        PROJECT_ROOT,
        load_agent_eras,
        load_frontier,
        load_ledger,
        load_moo_small_n,
        load_subject_deltas,
    )

FIGURES_DIR = PROJECT_ROOT / "docs" / "figures"
RESULTS_DIR = PROJECT_ROOT / "benchmark" / "results"

# ---------------------------------------------------------------------------
# Shared visual conventions -- one module-level style helper, identical in
# spirit to the sibling make_figures_progress.py's (that file is owned by a
# different worker and not read/imported here; the conventions themselves
# come straight from the shared figure brief, not from that file).
# ---------------------------------------------------------------------------

matplotlib.rcParams["svg.hashsalt"] = "quorumqa-figures-fixed-salt"
matplotlib.rcParams["font.size"] = 9.5
matplotlib.rcParams["axes.titlesize"] = 10.5
matplotlib.rcParams["figure.facecolor"] = "white"
matplotlib.rcParams["savefig.facecolor"] = "white"

_SAVEFIG_METADATA = {"Date": None}

# Provenance-tag colors (convention #1): [PAIRED] near-black, [POOLED-
# MARGINAL]/[PAIRED-SMALL-N] amber, [LOCAL-ONLY] grey italic.
PROVENANCE_STYLE = {
    "[PAIRED]": dict(color="#151515", style="normal", bg="#eeeeee"),
    "[POOLED-MARGINAL]": dict(color="#9a5b00", style="normal", bg="#fff2dc"),
    "[PAIRED-SMALL-N]": dict(color="#9a5b00", style="normal", bg="#fff2dc"),
    "[LOCAL-ONLY]": dict(color="#7a7a7a", style="italic", bg="#f2f2f2"),
}

WIN_GREEN = "#1a7a3c"
LOSS_RED = "#b3211e"
NEUTRAL_GREY = "#8a8a8a"
FLAGSHIP_GOLD = "#c99a1f"
BASELINE_STAR_EDGE = "#3a2b00"
CONTAM_EDGE = "#7d1f7a"
RIBBON_GREY = "#d9d9d9"

_COST_RE = re.compile(r"usd|cost|dollar", re.IGNORECASE)


def _guard_no_cost_columns(df: pd.DataFrame, label: str) -> None:
    """Convention/hard-guard: raise on any column matching usd|cost|dollar.
    USD is $0.00 for everything after the Token-Plan migration; every figure
    in this module plots tokens, never dollars."""
    bad = [c for c in df.columns if _COST_RE.search(str(c))]
    if bad:
        raise ValueError(
            f"{label}: frame has USD-shaped column(s) {bad} -- tokens only, "
            "never dollars (see NOISE_FLOOR_PP module docstring / hard guard)."
        )


def _assert_no_aime(df: pd.DataFrame, col: str = "benchmark") -> None:
    """Convention #9: assert programmatically that no AIME row reaches a
    plotted frame (AIME's only committed result files are survivor sets of
    an invalidated run -- figure_claims_ledger.md Sec.3)."""
    if col not in df.columns:
        return
    bad = df[df[col].astype(str).str.upper().isin({b.upper() for b in EXCLUDED_BENCHMARKS})]
    assert bad.empty, f"AIME (or another EXCLUDED_BENCHMARKS row) reached a plotted frame:\n{bad}"


def _git_short_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


_GIT_SHA = _git_short_sha()
_TODAY = date.today().isoformat()


def draw_title(fig, tag: str, headline: str, subtitle: str = "", y: float = 0.975) -> None:
    """Convention #1: provenance tag rendered as part of the title block (a
    colored badge immediately left of the headline) so a cropped screenshot
    cannot lose it."""
    style = PROVENANCE_STYLE[tag]
    fig.text(
        0.01,
        y,
        f" {tag} ",
        fontsize=11,
        fontweight="bold",
        color=style["color"],
        fontstyle=style["style"],
        ha="left",
        va="top",
        bbox=dict(boxstyle="round,pad=0.3", fc=style["bg"], ec=style["color"], lw=1.1),
    )
    fig.text(0.98, y, headline, fontsize=13, fontweight="bold", color="#141414", ha="right", va="top")
    if subtitle:
        fig.text(0.98, y - 0.032, subtitle, fontsize=8.7, color="#3d3d3d", ha="right", va="top", style="italic", wrap=True)


def draw_footer(fig, sources: str, caveat: str, wrap: int = 175, y: float = 0.012, fontsize: float = 6.6) -> None:
    """Convention #7: auto 3-line in-image footer -- sources, git short SHA
    + date, caveat text from the data's own `.caveat` field (extended, where
    a figure has mandatory extra caveats, per that figure's build_fNN())."""
    line1 = f"Sources: {sources}"
    line2 = f"Commit {_GIT_SHA}  |  rendered {_TODAY}"
    line3 = "Caveat: " + caveat
    text = "\n".join(textwrap.fill(ln, wrap) for ln in (line1, line2, line3))
    fig.text(0.01, y, text, fontsize=fontsize, color="#4a4a4a", ha="left", va="bottom", family="monospace")


def evidence_fill(verdict: str | None, n_seeds: int) -> str:
    """Convention #2: solid = paired >=3 seeds clearing +5 net-discordant
    (approximated by ledger verdict=='validated', which is only assigned to
    rows meeting that bar); half = 2 seeds or net +3/+4 (verdict=='screen');
    hollow = single seed or inside the noise band (verdict in {'negative',
    'inert'}, or fewer than 2 seeds logged). Nothing hollow is a win."""
    v = (verdict or "").strip().lower()
    if v == "validated" or n_seeds >= 3:
        return "full"
    if v == "screen" or n_seeds == 2:
        return "half"
    return "none"


def _fillstyle_kwargs(fill: str, color: str) -> dict:
    if fill == "full":
        return dict(markerfacecolor=color, markeredgecolor=color, fillstyle="full")
    if fill == "half":
        return dict(markerfacecolor=color, markeredgecolor=color, fillstyle="left")
    return dict(markerfacecolor="none", markeredgecolor=color, fillstyle="none")


def direction_marker(delta: float, floor: float = NOISE_FLOOR_PP) -> str:
    """Convention #6: direction by shape as well as colour."""
    if delta > floor:
        return "^"
    if delta < -floor:
        return "v"
    return "o"


def draw_noise_ribbon_h(ax, floor: float = NOISE_FLOOR_PP, mcnemar_hint: float = 5.0) -> None:
    """Convention #4 (horizontal orientation, for a delta-on-the-y-axis
    figure): grey +/-2.5pp ribbon labelled INSIDE the band, dashed +/-5
    lines."""
    ax.axhspan(-floor, floor, color=RIBBON_GREY, alpha=0.55, zorder=0)
    xlim = ax.get_xlim()
    ax.text(
        xlim[1] - 0.02 * (xlim[1] - xlim[0]),
        0,
        f"noise floor ±{floor:g}pp",
        fontsize=7,
        color="#555555",
        ha="right",
        va="center",
        zorder=1,
    )
    ax.axhline(mcnemar_hint, color="#666666", lw=1.0, ls="--", zorder=1)
    ax.axhline(-mcnemar_hint, color="#666666", lw=1.0, ls="--", zorder=1)


def draw_noise_ribbon_v(ax, floor: float = NOISE_FLOOR_PP, mcnemar_hint: float = 5.0) -> None:
    """Convention #4 (vertical orientation, for a delta-on-the-x-axis
    figure)."""
    ax.axvspan(-floor, floor, color=RIBBON_GREY, alpha=0.55, zorder=0)
    ylim = ax.get_ylim()
    ax.text(
        0,
        ylim[1] - 0.03 * (ylim[1] - ylim[0]),
        f"noise floor ±{floor:g}pp",
        fontsize=7,
        color="#555555",
        ha="center",
        va="top",
        zorder=1,
    )
    ax.axvline(mcnemar_hint, color="#666666", lw=1.0, ls="--", zorder=1)
    ax.axvline(-mcnemar_hint, color="#666666", lw=1.0, ls="--", zorder=1)


def save_figure(fig, stem: str, plotted_df: pd.DataFrame) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    svg_path = FIGURES_DIR / f"{stem}.svg"
    png_path = FIGURES_DIR / f"{stem}.png"
    fig.savefig(svg_path, format="svg", metadata=_SAVEFIG_METADATA)
    fig.savefig(png_path, format="png", dpi=fig.dpi, metadata=_SAVEFIG_METADATA)
    csv_path = RESULTS_DIR / f"figure_{stem}.csv"
    plotted_df.to_csv(csv_path, index=False)
    plt.close(fig)
    print(f"  wrote {svg_path.relative_to(PROJECT_ROOT)} "
          f"({svg_path.stat().st_size:,}B), {png_path.relative_to(PROJECT_ROOT)} "
          f"({png_path.stat().st_size:,}B), {csv_path.relative_to(PROJECT_ROOT)} "
          f"({csv_path.stat().st_size:,}B)")


# ---------------------------------------------------------------------------
# F04 -- Accuracy vs tokens frontier (the uncomfortable finding)
# ---------------------------------------------------------------------------

# Classification per docs/negative-results.md Sec.3.6 (F1) and
# benchmark/results/family_floor_analysis.md's own F2 table: on 6 of the 9
# benchmarks ever logged, a bare baseline_3.7max[_open] single call is the
# ENTIRE Pareto frontier -- no multi-agent lever clears it. AIME would be a
# 7th "alone"-dominated row by the identical rule (baseline_3.7max_open is
# its sole frontier point) but is excluded from the plotted panels (and from
# this classification) because its only committed result file is a
# survivorship-invalidated pilot -- it still counts toward the published
# "9" denominator, per the source doc's own accounting.
# Configs that ARE a single flagship call, however they were logged.
# `moo:single-call` is the MoO router's own single-call route
# (docs/mixture-of-orchestrations-plan.md: "easy/saturated queries, or caller
# wants cheap") -- the flagship answering alone, recorded through a different
# harness at n=30. It must count as "the flagship", or a benchmark whose
# frontier is entirely single calls would be mislabelled as one where a
# deliberation lever won.
F04_SINGLE_CALL_CONFIGS = {"baseline_3.7max", "baseline_3.7max_open", "moo:single-call"}


def f04_flagship_dominates(bench_frame) -> bool:
    """A benchmark is flagship-dominated iff EVERY point on its (recomputed)
    Pareto frontier is a single flagship call.

    Derived rather than hardcoded. The previous hardcoded set went stale the
    moment `load_frontier` began excluding retired point estimates and
    recomputing the frontier: dropping `qwen3.8_solo`'s retracted 93.6% put
    five GPQA configs back on the frontier, and revealed that on MMLU-Pro the
    frontier point is `moo:single-call` rather than `baseline_3.7max` -- still
    a single flagship call, so still 'dominated', but the hardcoded set had no
    way to say so.
    """
    frontier = bench_frame[bench_frame["on_pareto_frontier"]]
    if frontier.empty:
        return False
    return bool(frontier["config"].isin(F04_SINGLE_CALL_CONFIGS).all())


#: Retained ONLY for the published "6 of 9" denominator sentence, which is
#: quoted verbatim from docs/negative-results.md Sec.3.6. Never used to decide
#: a panel's colour -- f04_flagship_dominates() does that from the data.
F04_DOMINATED = {"MMLU-Pro", "MedQA", "LEXam", "GSM8K", "MATH-500-MC", "MATH-500-open"}
F04_NOT_DOMINATED = {"GPQA-Diamond", "SuperGPQA-hard"}
F04_PANEL_ORDER = [
    "MMLU-Pro", "MedQA", "LEXam", "GSM8K", "MATH-500-MC", "MATH-500-open",
    "GPQA-Diamond", "SuperGPQA-hard",
]
F04_BASELINE_CONFIGS = {"baseline_3.7max", "baseline_3.7max_open"}


def _n_seeds(seeds_str: str) -> int:
    s = str(seeds_str or "").strip()
    if not s:
        return 0
    return len([t for t in s.split(";") if t.strip()])


def build_f04():
    frontier = load_frontier()
    _guard_no_cost_columns(frontier.data, "load_frontier()")
    df = frontier.data.copy()
    df = df[~df["benchmark"].isin(EXCLUDED_BENCHMARKS)].reset_index(drop=True)
    _assert_no_aime(df)

    df["accuracy_pct"] = df["accuracy"] * 100.0
    df["n_seeds"] = df["seeds"].apply(_n_seeds)
    df["is_baseline"] = df["config"].isin(F04_BASELINE_CONFIGS)
    df["is_contaminated"] = df["config"].isin(CONTAMINATION_FOOTNOTES.keys())

    footnote_letters = {name: chr(ord("a") + i) for i, name in enumerate(sorted(CONTAMINATION_FOOTNOTES.keys()))}
    df["footnote"] = df["config"].map(footnote_letters).fillna("")

    total_configs_logged = df["config"].nunique()

    fig, axes = plt.subplots(2, 4, figsize=(16.0, 10.4), dpi=100)
    axes = axes.ravel()

    for ax, bench in zip(axes, F04_PANEL_ORDER):
        g = df[df["benchmark"] == bench].sort_values("mean_tokens_per_q")
        dominated = f04_flagship_dominates(g)
        panel_bg = "#fff2ef" if dominated else "#eefaf0"
        ax.set_facecolor(panel_bg)

        baseline_rows = g[g["is_baseline"]]
        bx = float(baseline_rows["mean_tokens_per_q"].iloc[0]) if len(baseline_rows) else None
        by = float(baseline_rows["accuracy_pct"].iloc[0]) if len(baseline_rows) else None

        xlim_lo = max(g["mean_tokens_per_q"].min() * 0.6, 1)
        xlim_hi = g["mean_tokens_per_q"].max() * 1.6
        ylim_lo = max(0, g["accuracy_pct"].min() - 8)
        ylim_hi = min(101, g["accuracy_pct"].max() + 6)

        # Shaded region up-and-left of the baseline star: the zone a lever
        # would have to land in to Pareto-DOMINATE the flagship (fewer
        # tokens, higher accuracy). Its emptiness on 6/9 benchmarks is the
        # figure's point.
        if bx is not None:
            ax.add_patch(
                Rectangle(
                    (xlim_lo, by),
                    bx - xlim_lo,
                    ylim_hi - by,
                    facecolor="#2ca02c",
                    alpha=0.10,
                    zorder=0,
                    linewidth=0,
                )
            )

        # Non-baseline, non-contaminated points.
        rest = g[~g["is_baseline"] & ~g["is_contaminated"]]
        for _, row in rest.iterrows():
            fill = evidence_fill(None, row["n_seeds"])  # pooled data: no verdict, seed-count only
            color = "#1f6f3e" if row["on_pareto_frontier"] else NEUTRAL_GREY
            marker = "o"
            size = 68 if row["on_pareto_frontier"] else 34
            kw = _fillstyle_kwargs(fill, color)
            ax.plot(
                row["mean_tokens_per_q"], row["accuracy_pct"], marker=marker,
                markersize=np.sqrt(size), linestyle="none",
                markeredgewidth=1.2, alpha=0.9 if row["on_pareto_frontier"] else 0.55,
                zorder=3, **kw,
            )

        # Contaminated configs: hatched + hollow + footnote letter, always.
        contam = g[g["is_contaminated"]]
        if len(contam):
            ax.scatter(
                contam["mean_tokens_per_q"], contam["accuracy_pct"],
                s=110, facecolor="none", edgecolor=CONTAM_EDGE, hatch="////",
                linewidth=1.4, zorder=4, marker="D",
            )
            for _, row in contam.iterrows():
                ax.annotate(
                    row["footnote"], (row["mean_tokens_per_q"], row["accuracy_pct"]),
                    textcoords="offset points", xytext=(7, 6), fontsize=8,
                    fontweight="bold", color=CONTAM_EDGE,
                )

        # Pareto frontier connector: line for >=3 points, dominance arrow
        # for exactly 2, nothing for a lone point.
        frontier_pts = g[g["on_pareto_frontier"]].sort_values("mean_tokens_per_q")
        if len(frontier_pts) >= 3:
            ax.plot(
                frontier_pts["mean_tokens_per_q"], frontier_pts["accuracy_pct"],
                "-", color="#1f6f3e", lw=1.4, zorder=2, alpha=0.8,
            )
        elif len(frontier_pts) == 2:
            p0, p1 = frontier_pts.iloc[0], frontier_pts.iloc[1]
            ax.add_patch(
                FancyArrowPatch(
                    (p0["mean_tokens_per_q"], p0["accuracy_pct"]),
                    (p1["mean_tokens_per_q"], p1["accuracy_pct"]),
                    arrowstyle="-|>", mutation_scale=12, color="#1f6f3e",
                    lw=1.3, alpha=0.85, zorder=2, shrinkA=6, shrinkB=6,
                )
            )

        # Baseline star, drawn last so it's always on top.
        if bx is not None:
            ax.plot(
                bx, by, marker="*", markersize=20, markerfacecolor=FLAGSHIP_GOLD,
                markeredgecolor=BASELINE_STAR_EDGE, markeredgewidth=1.1, zorder=5,
            )

        ax.set_xscale("log")
        ax.set_xlim(xlim_lo, xlim_hi)
        ax.set_ylim(ylim_lo, ylim_hi)
        n_here = g["config"].nunique()
        tag_txt = "FLAGSHIP DOMINATES" if dominated else "lever clears frontier"
        tag_color = LOSS_RED if dominated else WIN_GREEN
        ax.set_title(f"{bench}", fontsize=9.5, fontweight="bold", loc="left")
        ax.text(
            0.98, 0.03, tag_txt, transform=ax.transAxes, fontsize=6.6,
            fontweight="bold", color=tag_color, ha="right", va="bottom",
        )
        ax.text(
            0.02, 0.03, f"configs: {n_here}/{total_configs_logged}", transform=ax.transAxes,
            fontsize=6.2, color="#666666", ha="left", va="bottom",
        )
        ax.set_xlabel("mean tokens/question (log)", fontsize=7.2)
        ax.set_ylabel("accuracy %", fontsize=7.2)
        ax.tick_params(labelsize=7)
        ax.xaxis.set_minor_formatter(plt.NullFormatter())
        ax.xaxis.set_major_locator(matplotlib.ticker.LogLocator(base=10.0, numticks=6))
        ax.grid(True, which="major", axis="both", alpha=0.25, lw=0.5)

    # Shared legend.
    from matplotlib.lines import Line2D

    legend_handles = [
        Line2D([0], [0], marker="*", color="none", markerfacecolor=FLAGSHIP_GOLD,
               markeredgecolor=BASELINE_STAR_EDGE, markersize=15, label="flagship baseline (single call)"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#1f6f3e",
               markeredgecolor="#1f6f3e", markersize=8, label="on Pareto frontier"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="none",
               markeredgecolor=NEUTRAL_GREY, markersize=8, label="dominated (off frontier)"),
        Line2D([0], [0], marker="D", color="none", markerfacecolor="none",
               markeredgecolor=CONTAM_EDGE, markersize=9, label="contaminated (see footnote letter)"),
        Rectangle((0, 0), 1, 1, facecolor="#2ca02c", alpha=0.15,
                  label="would Pareto-dominate flagship (fewer tok, higher acc)"),
    ]
    fig.legend(handles=legend_handles, loc="lower center", ncol=5, fontsize=7.6,
               bbox_to_anchor=(0.5, 0.155), frameon=False)

    draw_title(
        fig, "[POOLED-MARGINAL]",
        "F04 -- Accuracy vs tokens: the compute frontier",
        "each config plotted over whatever items it happened to run -- read the SHAPE, not the gaps; "
        "for validated deltas see F02. On 6 of 9 logged benchmarks a bare single flagship call is the "
        "ENTIRE Pareto frontier (AIME excluded from panels, see footer).",
        y=0.978,
    )
    footnote_text = "  ".join(f"({letter}) {name}: {CONTAMINATION_FOOTNOTES[name]}" for name, letter in footnote_letters.items())
    fig.text(
        0.01, 0.145, textwrap.fill("Contamination footnotes -- " + footnote_text, 205),
        fontsize=6.0, color="#5a1a58", ha="left", va="top", linespacing=1.35,
    )
    draw_footer(
        fig,
        sources="benchmark/results/f2_compute_frontier.csv (via load_frontier())",
        caveat=(
            frontier.caveat + " AIME excluded from all 8 plotted panels (survivorship-invalidated "
            "pilot, EXCLUDED_BENCHMARKS in figure_data.py) but is retained in the published '9' "
            "denominator per docs/negative-results.md Sec.3.6 (its baseline would be a 7th 'alone' "
            "dominator by the same rule)."
        ),
        y=0.010, fontsize=6.0, wrap=205,
    )
    fig.tight_layout(rect=(0, 0.235, 1, 0.925))

    out = df[[
        "benchmark", "config", "n", "accuracy_pct", "mean_tokens_per_q", "seeds", "n_seeds",
        "on_pareto_frontier", "is_baseline", "is_contaminated", "footnote",
    ]].copy()
    out["dominated_benchmark"] = out["benchmark"].map(
        lambda b: f04_flagship_dominates(df[df["benchmark"] == b])
    )
    return fig, out


# ---------------------------------------------------------------------------
# F05 -- The central law: unanimous-wrong rate vs best paired lever delta
# ---------------------------------------------------------------------------

# For each benchmark that carries a ledger-sourced unanimous_wrong_rate_pct
# cell, the "best paired lever delta" is the largest mean_delta_pp among
# that benchmark's v2 rows (falling back to the absolute-accuracy-pct
# difference against the reference baseline row when mean_delta_pp is
# blank -- every ledger cell used here is one verify_ledger() can already
# check verbatim against its source_doc, since absolute_accuracy_pct is
# itself a ledger column, not a derived invention). Where a benchmark has no
# v2 row at all (MedQA), the v1 shipped_engine row is used as the only
# paired comparison on record for that benchmark.
def _mean_numeric(cell: str) -> float | None:
    """A ledger cell may hold a single number or a ';'-joined per-seed list
    (e.g. SuperGPQA baseline's '79.5;79.3;76.5'); returns the mean of
    whichever numeric tokens it has, or None if it has none."""
    toks = [t for t in str(cell or "").split(";") if t.strip()]
    nums = [float(t) for t in toks if re.match(r"^[+-]?\d+(\.\d+)?$", t.strip())]
    return (sum(nums) / len(nums)) if nums else None


def _best_lever_delta(ledger_df: pd.DataFrame, benchmark: str) -> tuple[float, str, str, int]:
    g = ledger_df[ledger_df["benchmark_label"] == benchmark]
    ref = g[g["build_stage"] == "reference"]
    ref_acc = _mean_numeric(ref["absolute_accuracy_pct"].iloc[0]) if len(ref) else None

    # Contaminated rows (survivorship-biased, per CONTAMINATION_FOOTNOTES)
    # are excluded from "best lever" selection -- picking the highest
    # numeric delta among ALL rows would reproduce exactly the qwen38_panel
    # trap this ledger's own contamination flag exists to prevent (its
    # pooled 87.9%-on-58-survivors reads as a fake +9.5pp "best", when its
    # own honest paired verdict is negative -- ties baseline, trails the
    # real validated flagship_panel +4.1).
    candidates = g[g["build_stage"].isin(["v2", "v1"]) & (g["contaminated"].astype(str).str.upper() != "TRUE")].copy()
    best_delta, best_config, best_verdict, best_seeds = None, None, None, 0
    for _, row in candidates.iterrows():
        delta = None
        if row["mean_delta_pp"]:
            delta = float(row["mean_delta_pp"])
        elif row["absolute_accuracy_pct"] and ref_acc is not None:
            row_acc = _mean_numeric(row["absolute_accuracy_pct"])
            if row_acc is not None:
                delta = row_acc - ref_acc
        if delta is None:
            continue
        if best_delta is None or delta > best_delta:
            best_delta, best_config, best_verdict = delta, row["config"], row["verdict"]
            best_seeds = _n_seeds(row["seeds"])
    return best_delta, best_config, best_verdict, best_seeds


def build_f05():
    ledger = load_ledger()
    _guard_no_cost_columns(ledger.data, "load_ledger()")
    df = ledger.data.copy()
    _assert_no_aime(df, col="benchmark_label")

    uw = df[df["unanimous_wrong_rate_pct"].astype(str).str.strip() != ""].copy()
    benchmarks = sorted(uw["benchmark_label"].unique())

    points = []
    for bench in benchmarks:
        row = uw[uw["benchmark_label"] == bench].iloc[0]
        x = float(row["unanimous_wrong_rate_pct"])
        n_x = int(row["n_common_items"]) if str(row["n_common_items"]).strip() else None
        best_delta, best_config, best_verdict, best_seeds = _best_lever_delta(df, bench)
        if best_delta is None:
            continue
        points.append(dict(
            benchmark=bench, unanimous_wrong_rate_pct=x, n_unanimous_sample=n_x,
            best_lever_config=best_config, best_lever_delta_pp=best_delta,
            best_lever_verdict=best_verdict, best_lever_seeds=best_seeds,
        ))
    pts = pd.DataFrame(points)

    fig, ax = plt.subplots(figsize=(10.2, 7.0), dpi=157)
    ax.set_facecolor("white")

    x_max = max(pts["unanimous_wrong_rate_pct"].max() * 1.25, 30)
    y_abs = max(pts["best_lever_delta_pp"].abs().max() * 1.35, 10)
    ax.set_xlim(0, x_max)
    ax.set_ylim(-y_abs, y_abs)

    # Quadrant shading: "no gap -> nothing to win" (low x) vs "large gap ->
    # deliberation pays" (high x, y>0) vs the honest third case this
    # project's own record actually contains -- large gap, lever still lost.
    gap_split = 10.0  # pp; below this, ledger rows here cluster near-zero delta
    ax.axvspan(0, gap_split, color="#e8e8e8", alpha=0.6, zorder=0)
    ax.axhspan(0, y_abs, xmin=gap_split / x_max, xmax=1, color="#e6f5ea", alpha=0.7, zorder=0)
    ax.axhspan(-y_abs, 0, xmin=gap_split / x_max, xmax=1, color="#fbe9e7", alpha=0.55, zorder=0)
    ax.text(gap_split / 2, y_abs * 0.92, "no gap →\nnothing to win", ha="center", va="top",
            fontsize=8.5, color="#555555", style="italic")
    ax.text((x_max + gap_split) / 2, y_abs * 0.92, "large gap →\ndeliberation pays", ha="center",
            va="top", fontsize=8.5, color="#1a7a3c", style="italic")
    ax.text((x_max + gap_split) / 2, -y_abs * 0.92, "large gap, lever\nstill lost", ha="center", va="bottom",
            fontsize=8.5, color="#b3211e", style="italic")

    draw_noise_ribbon_h(ax, NOISE_FLOOR_PP, mcnemar_hint=5.0)
    ax.axvline(gap_split, color="#999999", lw=0.8, ls=":", zorder=1)

    for _, row in pts.iterrows():
        fill = evidence_fill(row["best_lever_verdict"], row["best_lever_seeds"])
        shape = direction_marker(row["best_lever_delta_pp"])
        color = WIN_GREEN if row["best_lever_delta_pp"] > NOISE_FLOOR_PP else (
            LOSS_RED if row["best_lever_delta_pp"] < -NOISE_FLOOR_PP else NEUTRAL_GREY)
        kw = _fillstyle_kwargs(fill, color)
        ax.plot(row["unanimous_wrong_rate_pct"], row["best_lever_delta_pp"], marker=shape,
                markersize=15, linestyle="none", markeredgewidth=1.6, zorder=4, **kw)
        n_lbl = f"n={row['n_unanimous_sample']}" if row["n_unanimous_sample"] else "n=?"
        seeds_lbl = f", {row['best_lever_seeds']}-seed" if row["best_lever_seeds"] else ""
        ax.annotate(
            f"{row['benchmark']}\n({row['best_lever_config']}, {n_lbl}{seeds_lbl})",
            (row["unanimous_wrong_rate_pct"], row["best_lever_delta_pp"]),
            textcoords="offset points", xytext=(9, 9), fontsize=7.6, color="#222222",
        )

    ax.set_xlabel("cheap-tier unanimous-wrong rate (%)  [ledger-sourced only -- see caveat]")
    ax.set_ylabel("best paired lever delta (pp, vs matched-seed flagship baseline)")
    ax.axhline(0, color="#333333", lw=0.8)
    ax.grid(True, alpha=0.2)

    draw_title(
        fig, "[PAIRED]",
        "F05 -- The central law: gap size vs deliberation payoff",
        "no fit line, no r² -- 5 heterogeneous ledger-sourced points at different n (see caveat "
        "for why not 7); n printed per point instead of a regression.",
    )
    draw_footer(
        fig,
        sources="benchmark/results/figure_claims_ledger.csv (via load_ledger())",
        caveat=(
            ledger.caveat + " Only 5 of the ledger's benchmark_labels carry a ledger-sourced "
            "unanimous_wrong_rate_pct cell (SuperGPQA-hard, MMLU-Pro, MMLU-Pro-STEM, LEXam, MedQA); "
            "GPQA-Diamond has none in the ledger and is DELIBERATELY omitted rather than backfilled "
            "from wrongness_predictor_findings.md's 9.5%/17.8% figures, which pool every config "
            "(including flagship panels) and are a different quantity than the cheap-tier rate this "
            "law is stated over -- mixing them would silently change the law's x-axis, per the task's "
            "own hard constraint. AIME excluded (EXCLUDED_BENCHMARKS)."
        ),
        y=0.012, fontsize=6.1, wrap=195,
    )
    fig.tight_layout(rect=(0, 0.145, 1, 0.895))

    pts_out = pts.copy()
    pts_out["evidence_fill"] = pts_out.apply(lambda r: evidence_fill(r["best_lever_verdict"], r["best_lever_seeds"]), axis=1)
    return fig, pts_out


# ---------------------------------------------------------------------------
# F07 -- Twin heatmap: MoO delta and escalation rate
# ---------------------------------------------------------------------------

F07_PROFILES = [
    "single-call", "standard-tribunal", "thinking_gate", "flagship_panel",
    "stem-max", "rag_presolve", "rag_thinking_gate",
]
F07_BUCKETS = ["saturated_easy_mmlu", "medqa", "gpqa_hard", "supergpqa_hard"]
# f5_difficulty_map.csv bucket -> moo_calibration_table.csv sub-bucket(s),
# n-weighted average when >1 (documented in the module docstring's F07 entry).
F07_BUCKET_MAP = {
    "gpqa_hard": ["gpqa_hard_stem", "gpqa_organic_chem"],
    "supergpqa_hard": ["supergpqa_hard_stem"],
    "medqa": ["medicine"],
    "saturated_easy_mmlu": ["saturated_easy"],
}


def build_f07():
    moo = load_moo_small_n()
    _guard_no_cost_columns(moo.data, "load_moo_small_n()")
    data = moo.data
    f5 = data[data["source_file"] == "f5_difficulty_map.csv"]
    calib = data[data["source_file"] == "moo_calibration_table.csv"]
    _assert_no_aime(f5, col="bucket")  # AIME never appears in this frame; belt-and-suspenders

    delta_grid = np.full((len(F07_PROFILES), len(F07_BUCKETS)), np.nan)
    items_grid = np.full((len(F07_PROFILES), len(F07_BUCKETS)), np.nan)
    n_grid = np.full((len(F07_PROFILES), len(F07_BUCKETS)), np.nan)
    esc_grid = np.full((len(F07_PROFILES), len(F07_BUCKETS)), np.nan)
    esc_n_grid = np.full((len(F07_PROFILES), len(F07_BUCKETS)), np.nan)
    hatch_mask = np.zeros((len(F07_PROFILES), len(F07_BUCKETS)), dtype=bool)

    rows_out = []
    for bi, bucket in enumerate(F07_BUCKETS):
        sub5 = f5[f5["bucket"] == bucket]
        sub_calib_buckets = F07_BUCKET_MAP[bucket]
        for pi, profile in enumerate(F07_PROFILES):
            r5 = sub5[sub5["profile"] == profile]
            if len(r5):
                delta = float(r5["delta_vs_single_call_pp"].iloc[0])
                items = float(r5["delta_vs_single_call_items"].iloc[0])
                n_common = float(r5["n_common_items"].iloc[0])
                delta_grid[pi, bi] = delta
                items_grid[pi, bi] = items
                n_grid[pi, bi] = n_common
                hatch_mask[pi, bi] = abs(items) < MCNEMAR_MIN_NET

            calib_rows = calib[(calib["profile"] == profile) & (calib["bucket"].isin(sub_calib_buckets))]
            if len(calib_rows):
                w = calib_rows["n"].astype(float)
                esc = (calib_rows["escalation_rate"].astype(float) * 100.0 * w).sum() / w.sum()
                esc_grid[pi, bi] = esc
                esc_n_grid[pi, bi] = w.sum()

            rows_out.append(dict(
                bucket=bucket, profile=profile,
                delta_vs_single_call_pp=delta_grid[pi, bi], delta_items=items_grid[pi, bi],
                n_common_items=n_grid[pi, bi], escalation_rate_pct=esc_grid[pi, bi],
                escalation_rate_n=esc_n_grid[pi, bi], below_mcnemar_floor=bool(hatch_mask[pi, bi]),
                calib_sub_buckets=";".join(sub_calib_buckets),
            ))

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(16.0, 8.2), dpi=100)

    vmax = max(np.nanmax(np.abs(delta_grid)), 1)
    imL = axL.imshow(delta_grid, cmap="RdYlGn", vmin=-vmax, vmax=vmax, aspect="auto")
    imR = axR.imshow(esc_grid, cmap="YlOrRd", vmin=0, vmax=100, aspect="auto")

    for ax, im, title in ((axL, imL, "delta vs single-call (pp)"), (axR, imR, "escalation rate (%)")):
        ax.set_xticks(range(len(F07_BUCKETS)))
        ax.set_xticklabels([f"{b}\n(n={int(n_grid[0, i]) if not np.isnan(n_grid[0,i]) else '?'})" for i, b in enumerate(F07_BUCKETS)],
                            fontsize=7.6)
        ax.set_yticks(range(len(F07_PROFILES)))
        ax.set_yticklabels(F07_PROFILES, fontsize=8.2)
        ax.set_title(title, fontsize=10, fontweight="bold")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    for pi in range(len(F07_PROFILES)):
        for bi in range(len(F07_BUCKETS)):
            d, it, n = delta_grid[pi, bi], items_grid[pi, bi], n_grid[pi, bi]
            if not np.isnan(d):
                txt = f"{d:+.1f}pp\n({it:+.0f}/{int(n)})"
                axL.text(bi, pi, txt, ha="center", va="center", fontsize=6.6, color="#111111")
            e, en = esc_grid[pi, bi], esc_n_grid[pi, bi]
            if not np.isnan(e):
                txt = f"{e:.1f}%\n(n={int(en)})"
                axR.text(bi, pi, txt, ha="center", va="center", fontsize=6.6, color="#111111")
            if hatch_mask[pi, bi]:
                for ax in (axL, axR):
                    ax.add_patch(Rectangle((bi - 0.5, pi - 0.5), 1, 1, fill=False, hatch="///",
                                            edgecolor="#555555", lw=0))

    fig.text(0.5, 0.155,
              f"Hatched cells (╱╱╱): |delta items| < {MCNEMAR_MIN_NET} (the McNemar-floor bar) -- "
              f"{int(hatch_mask.sum())}/{hatch_mask.size} cells here, i.e. nearly the whole grid. "
              "Same hatch mask on both panels by construction, so the visual correlation IS the mechanism:\n"
              "where the left panel goes flat/hatched, the right panel's escalation rate has typically collapsed too.",
              ha="center", va="top", fontsize=7.8, color="#444444", style="italic", linespacing=1.5)

    draw_title(
        fig, "[PAIRED-SMALL-N]",
        "F07 -- MoO delta and escalation rate, twin heatmap",
        "7 profiles x 4 buckets, identical axes on both panels. Right panel synthesized via n-weighted "
        "merge of moo_calibration_table.csv's finer router buckets onto f5_difficulty_map.csv's 4.",
    )
    draw_footer(
        fig,
        sources="benchmark/results/f5_difficulty_map.csv + moo_calibration_table.csv (via load_moo_small_n())",
        caveat=moo.caveat + f" Escalation-rate cells are an n-weighted average over: "
                             f"{'; '.join(f'{k}<-{v}' for k, v in F07_BUCKET_MAP.items())}.",
        y=0.010, fontsize=6.2, wrap=195,
    )
    fig.tight_layout(rect=(0, 0.225, 1, 0.90))

    return fig, pd.DataFrame(rows_out)


# ---------------------------------------------------------------------------
# F08 -- Subject-level paired deltas
# ---------------------------------------------------------------------------


def build_f08():
    subj = load_subject_deltas()
    _guard_no_cost_columns(subj.data, "load_subject_deltas()")
    df = subj.data.copy()
    _assert_no_aime(df, col="benchmark")
    df = df.sort_values("delta_pp", ascending=True).reset_index(drop=True)
    df["label"] = df["subject"] + "  (" + df["benchmark"] + ")"
    df["hatched"] = df["delta_items"].abs() < MCNEMAR_MIN_NET

    fig, ax = plt.subplots(figsize=(10.6, 15.2), dpi=150)
    y = np.arange(len(df))
    colors = [WIN_GREEN if d > NOISE_FLOOR_PP else (LOSS_RED if d < -NOISE_FLOOR_PP else NEUTRAL_GREY) for d in df["delta_pp"]]

    bars = ax.barh(y, df["delta_pp"], color=colors, edgecolor="#333333", linewidth=0.5, height=0.72, zorder=3)
    for bar, hatched in zip(bars, df["hatched"]):
        if hatched:
            bar.set_hatch("////")
            bar.set_alpha(0.55)

    for yi, row in df.iterrows():
        x = row["delta_pp"]
        offset = 1.6 if x >= 0 else -1.6
        ha = "left" if x >= 0 else "right"
        ax.text(x + offset, yi, f"n={row['n']}, {row['delta_items']:+d} items", va="center", ha=ha, fontsize=6.3, color="#333333")

    ax.set_yticks(y)
    ax.set_yticklabels(df["label"], fontsize=6.6)
    ax.set_xlabel("delta_pp: shipped engine vs baseline (paired, same items)")
    ax.axvline(0, color="#222222", lw=0.9)
    draw_noise_ribbon_v(ax, NOISE_FLOOR_PP, mcnemar_hint=float(MCNEMAR_MIN_NET))
    ax.set_xlim(df["delta_pp"].min() - 14, df["delta_pp"].max() + 14)
    ax.grid(True, axis="x", alpha=0.2)

    oc_idx = df.index[(df["subject"] == "Organic Chemistry") & (df["benchmark"] == "GPQA-Diamond")]
    if len(oc_idx):
        yi = oc_idx[0]
        row = df.loc[yi]
        ax.annotate(
            "the organic-chemistry hole:\nmotivated chem_flagship_gate\n& chem_thinking_gate",
            xy=(row["delta_pp"], yi), xycoords="data",
            xytext=(0.14, 0.50), textcoords="axes fraction",
            fontsize=8.5, fontweight="bold", color="#7a1f1f", ha="left", va="center",
            arrowprops=dict(arrowstyle="->", color="#7a1f1f", lw=1.3),
            bbox=dict(boxstyle="round,pad=0.35", fc="#ffe9e9", ec="#7a1f1f", lw=0.8),
        )

    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    legend_handles = [
        Patch(facecolor=WIN_GREEN, label=f"delta > +{NOISE_FLOOR_PP:g}pp"),
        Patch(facecolor=NEUTRAL_GREY, label="inside noise band"),
        Patch(facecolor=LOSS_RED, label=f"delta < -{NOISE_FLOOR_PP:g}pp"),
        Patch(facecolor="white", edgecolor="#333333", hatch="////", label=f"|delta items| < {MCNEMAR_MIN_NET} (below McNemar floor)"),
    ]
    ax.legend(handles=legend_handles, loc="lower right", fontsize=7.4, framealpha=0.9)

    n_hatched = int(df["hatched"].sum())
    draw_title(
        fig, "[PAIRED-SMALL-N]",
        "F08 -- Subject-level paired deltas (43 records)",
        f"sorted by delta_pp; {n_hatched}/{len(df)} bars hatched (|delta items| < {MCNEMAR_MIN_NET}) -- "
        "most per-subject bins are too small to trust individually; read the pattern, not any one bar.",
    )
    draw_footer(
        fig,
        sources="benchmark/results/family_floor_analysis_data.json:f5_subject_breakdown (via load_subject_deltas())",
        caveat=subj.caveat,
        y=0.012, fontsize=7.2, wrap=175,
    )
    fig.tight_layout(rect=(0, 0.055, 1, 0.925))

    return fig, df[["benchmark", "subject", "n", "baseline_acc", "engine_acc", "delta_pp", "delta_items", "hatched"]]


# ---------------------------------------------------------------------------
# F09 -- Agent hardening: initial vs current build on Terminal-Bench
# ---------------------------------------------------------------------------

F09_PRE_JOBS = {"phase1-pilot-seed7c", "phase1-pilot-seed7"}
F09_POST_JOB = "seed7-hardened-rerun"
F09_STATUS_ORDER = ["solved", "failed_graded", "ungraded_exception"]
F09_STATUS_COLOR = {"solved": WIN_GREEN, "failed_graded": "#c96f1a", "ungraded_exception": NEUTRAL_GREY}


def build_f09():
    agents = load_agent_eras()
    _guard_no_cost_columns(agents.data, "load_agent_eras()")
    df = agents.data.copy()

    pre = df[df["job_name"].isin(F09_PRE_JOBS)]
    post = df[df["job_name"] == F09_POST_JOB]

    assert len(pre) == 14, f"expected 14 pre-hardening seed-7 tasks, got {len(pre)}"
    assert len(post) == 14, f"expected 14 hardened seed-7-rerun tasks, got {len(post)}"
    assert set(pre["task_name"]) == set(post["task_name"]), "pre/post task_name sets are not the matched seed-7 pair"
    assert set(pre["hardening_era"].unique()) == {"pre-hardening"}
    assert set(post["hardening_era"].unique()) == {"hardened"}

    def counts(sub):
        vc = sub["status"].value_counts()
        return {s: int(vc.get(s, 0)) for s in F09_STATUS_ORDER}

    pre_counts, post_counts = counts(pre), counts(post)
    pre_graded = pre_counts["solved"] + pre_counts["failed_graded"]
    post_graded = post_counts["solved"] + post_counts["failed_graded"]

    # Reproduce the published claim exactly (docs/superpowers/plans/notes/
    # 2026-07-22-terminal-bench-seed7-pilot.md): 5/14 (36%) -> 12/14 (86%)
    # graded; solved 2/14 -> 4/14.
    assert pre_graded == 5 and post_graded == 12, (pre_graded, post_graded)
    assert pre_counts["solved"] == 2 and post_counts["solved"] == 4, (pre_counts, post_counts)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.6, 7.8), dpi=127, gridspec_kw=dict(width_ratios=[1.4, 1]))

    eras = ["pre-hardening\n(5/14 graded)", "hardened\n(12/14 graded)"]
    bottoms = [0, 0]
    for status in F09_STATUS_ORDER:
        vals = [pre_counts[status], post_counts[status]]
        ax1.bar(eras, vals, bottom=bottoms, color=F09_STATUS_COLOR[status], edgecolor="white",
                linewidth=0.8, label=status, width=0.55)
        for i, v in enumerate(vals):
            if v:
                ax1.text(i, bottoms[i] + v / 2, f"{status}\n{v}", ha="center", va="center", fontsize=7.6, color="white", fontweight="bold")
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    ax1.set_ylabel("task trials (n=14 matched seed-7 tasks per era)")
    ax1.set_title("Graded outcome mix, per era (stacked)", fontsize=9.5)
    ax1.axhline(14, color="#333333", lw=0.7, ls=":")
    ax1.text(1.35, 14, "n=14", fontsize=7, va="center", color="#333333")
    for i, g in enumerate([pre_graded, post_graded]):
        pct = 100 * g / 14
        ax1.text(i, 14.4, f"graded coverage {g}/14 = {pct:.0f}%", ha="center", fontsize=7.8, fontweight="bold")
    ax1.set_ylim(0, 16.5)

    solved_rate = [100 * pre_counts["solved"] / 14, 100 * post_counts["solved"] / 14]
    solved_of_graded = [100 * pre_counts["solved"] / pre_graded, 100 * post_counts["solved"] / post_graded]
    xw = np.arange(2)
    width = 0.32
    ax2.bar(xw - width / 2, solved_rate, width, color=WIN_GREEN, label="solved / all 14 attempted", edgecolor="#1a1a1a")
    ax2.bar(xw + width / 2, solved_of_graded, width, color="#7fb08a", label="solved / graded-only", edgecolor="#1a1a1a")
    for xi, v in zip(xw - width / 2, solved_rate):
        ax2.text(xi, v + 1, f"{v:.1f}%", ha="center", fontsize=8, fontweight="bold")
    for xi, v in zip(xw + width / 2, solved_of_graded):
        ax2.text(xi, v + 1, f"{v:.1f}%", ha="center", fontsize=8)
    ax2.set_xticks(xw)
    ax2.set_xticklabels(["pre-hardening\n(2 solved)", "hardened\n(4 solved)"])
    ax2.set_ylabel("solve rate (%)")
    ax2.set_ylim(0, 60)
    ax2.set_title("Solve rate -- NOT the same claim as coverage", fontsize=9.5)
    ax2.legend(fontsize=6.8, loc="upper left")
    ax2.grid(True, axis="y", alpha=0.25)

    h, l = ax1.get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=7.8, bbox_to_anchor=(0.5, 0.155), frameon=False)

    draw_title(
        fig, "[PAIRED]",
        "F09 -- Agent hardening: pre vs hardened, matched seed-7 sample",
        "same 14 Terminal-Bench 2.1 tasks, same agent, before/after the 3-fix hardening pass -- "
        "graded coverage 36% → 86% is a coverage metric, NOT accuracy; solved only goes 2/14 → 4/14.",
    )
    draw_footer(
        fig,
        sources="benchmark/results/agent_cost_calibration.csv (via load_agent_eras()), matched to "
                "job_name in {phase1-pilot-seed7c, phase1-pilot-seed7} (pre) vs seed7-hardened-rerun (post)",
        caveat=(
            agents.caveat + " MANDATORY: (1) this is graded COVERAGE, not correctness -- more attempts "
            "surviving to a verifier grade, not more attempts scoring 1.0; (2) this is a single "
            "non-deliberating coding agent (QuorumQAAgent), not the QA panel/tribunal this project is "
            "otherwise about; (3) this is exactly the sample the hardening fixes were tuned against "
            "(docs/capability-roadmap.md Sec.3.5) -- not a fresh-sample accuracy claim."
        ),
        y=0.010, fontsize=6.4, wrap=175,
    )
    fig.tight_layout(rect=(0, 0.235, 1, 0.885))

    out_rows = []
    for era_name, sub, counts_d, graded in (("pre-hardening", pre, pre_counts, pre_graded), ("hardened", post, post_counts, post_graded)):
        out_rows.append(dict(
            hardening_era=era_name, n_total=len(sub), n_graded=graded,
            graded_coverage_pct=100 * graded / len(sub),
            n_solved=counts_d["solved"], solved_rate_of_all_pct=100 * counts_d["solved"] / len(sub),
            solved_rate_of_graded_pct=100 * counts_d["solved"] / graded,
            n_failed_graded=counts_d["failed_graded"], n_ungraded_exception=counts_d["ungraded_exception"],
        ))
    return fig, pd.DataFrame(out_rows)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

BUILDERS = {
    "f04": ("f04_accuracy_vs_tokens_frontier", build_f04),
    "f05": ("f05_unanimous_wrong_vs_lever_delta", build_f05),
    "f07": ("f07_moo_delta_escalation_heatmap", build_f07),
    "f08": ("f08_subject_paired_deltas", build_f08),
    "f09": ("f09_agent_hardening", build_f09),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", choices=sorted(BUILDERS.keys()), default=None, help="Build only one figure.")
    args = parser.parse_args()

    keys = [args.only] if args.only else list(BUILDERS.keys())
    for key in keys:
        stem, builder = BUILDERS[key]
        print(f"[{key}] building {stem} ...")
        fig, plotted_df = builder()
        save_figure(fig, stem, plotted_df)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
