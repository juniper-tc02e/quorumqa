"""F10-F13 -- the 2026-08-01/02 findings set.

The half of the deck that answers "is any of this worth running?" and mostly
answers no. Every figure here is Tier A [PAIRED]: computed on the per-seed
question_id INTERSECTION of the arms it compares, never pooled across seeds.
That restriction is the point -- `f2_compute_frontier.csv` (Tier B) pools each
config over whatever seeds it happened to run on, and with the flagship's
measured 83.0/86.5/94.3% seed spread on GPQA a cross-seed frontier can invert
purely from sampling.

  F10  The paired cost frontier, GPQA-Diamond vs SuperGPQA-hard side by side.
       The headline: a single flagship call is 4.7x more token-efficient than
       the best QuorumQA config on GPQA and is never beaten there -- but on
       SuperGPQA-hard, where the flagship has 10 points more headroom,
       flagship_panel DOES beat it (+7, p=0.0327, seeds 7/42/123).
       Orchestration pays where the base model is weak and not where it is
       strong.

       (This docstring said p=0.0195 until 2026-08-03 -- the 2-seed figure.
       The rendered caption below is derived from the data and was already
       correct; the prose describing it was not. Same class of drift as the
       one docs/figures/README.md carried, and the reason
       tests/test_headline_consistency_offline.py now reads across docs.)
  F11  Cheap-worker scaling: plurality accuracy vs oracle coverage as N goes
       1->15, three arms. Coverage climbs steadily; plurality does not move
       after N=3. Includes the random-guess coverage reference that retires
       the "40-point opportunity" reading of the gap.
  F12  The kill list -- every mechanism this project tested for detecting a
       wrong-but-confident panel, with its measured effect and p-value. Every
       entry is a null; the count is len(F12_KILLS) and is deliberately NOT
       written out here. It said "Ten entries, ten nulls" while the list held
       eleven, which is the same defect as the F10 caption above. A docstring
       cannot derive a count, so it states none.
  F13  universal_gate's 3-seed result and its two controls, showing why the
       +25 and the +1 are both true: they are measured against comparators
       nine points apart.

Regenerate (no API calls, no network -- every input is a committed file):

    python benchmark/make_figures_frontier.py
"""

from __future__ import annotations

import subprocess
import textwrap
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from benchmark.analyze_cost_frontier import analyze as frontier_analyze  # noqa: E402
from benchmark.figure_data import NOISE_FLOOR_PP  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIGURES_DIR = PROJECT_ROOT / "docs" / "figures"
RESULTS_DIR = PROJECT_ROOT / "benchmark" / "results"

# Identical style contract to make_figures_analysis.py -- same salt, so a
# fresh checkout reproduces byte-identical SVGs.
matplotlib.rcParams["svg.hashsalt"] = "quorumqa-figures-fixed-salt"
matplotlib.rcParams["font.size"] = 9.5
matplotlib.rcParams["axes.titlesize"] = 10.5
matplotlib.rcParams["figure.facecolor"] = "white"
matplotlib.rcParams["savefig.facecolor"] = "white"

_SAVEFIG_METADATA = {"Date": None}

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
RIBBON_GREY = "#d9d9d9"
COVERAGE_BLUE = "#2b6ea8"


def _git_short_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, check=True, timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


_GIT_SHA = _git_short_sha()
_TODAY = date.today().isoformat()


def draw_title(fig, tag: str, headline: str, subtitle: str = "", y: float = 0.975) -> None:
    style = PROVENANCE_STYLE[tag]
    fig.text(
        0.01, y, f" {tag} ", fontsize=11, fontweight="bold", color=style["color"],
        fontstyle=style["style"], ha="left", va="top",
        bbox=dict(boxstyle="round,pad=0.3", fc=style["bg"], ec=style["color"], lw=1.1),
    )
    fig.text(0.98, y, headline, fontsize=13, fontweight="bold", color="#141414", ha="right", va="top")
    if subtitle:
        fig.text(0.98, y - 0.030, subtitle, fontsize=8.7, color="#3d3d3d",
                 ha="right", va="top", style="italic", wrap=True)


def draw_footer(fig, sources: str, caveat: str, wrap: int = 175, y: float = 0.012,
                fontsize: float = 6.6) -> None:
    lines = (f"Sources: {sources}", f"Commit {_GIT_SHA}  |  rendered {_TODAY}", "Caveat: " + caveat)
    fig.text(0.01, y, "\n".join(textwrap.fill(ln, wrap) for ln in lines),
             fontsize=fontsize, color="#4a4a4a", ha="left", va="bottom", family="monospace")


def save_figure(fig, stem: str, plotted_df: pd.DataFrame) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    svg_path, png_path = FIGURES_DIR / f"{stem}.svg", FIGURES_DIR / f"{stem}.png"
    fig.savefig(svg_path, format="svg", metadata=_SAVEFIG_METADATA)
    fig.savefig(png_path, format="png", dpi=fig.dpi, metadata=_SAVEFIG_METADATA)
    csv_path = RESULTS_DIR / f"figure_{stem}.csv"
    plotted_df.to_csv(csv_path, index=False)
    plt.close(fig)
    print(f"  wrote {svg_path.relative_to(PROJECT_ROOT)} ({svg_path.stat().st_size:,}B), "
          f"{png_path.relative_to(PROJECT_ROOT)} ({png_path.stat().st_size:,}B), "
          f"{csv_path.relative_to(PROJECT_ROOT)} ({csv_path.stat().st_size:,}B)")


# ---------------------------------------------------------------------------
# F10 -- the paired cost frontier
# ---------------------------------------------------------------------------

F10_LABEL = {
    "flagship_1x": "qwen3.7-max ×1",
    "universal_gate": "universal_gate\n(escalate all)",
    "flagship_panel": "flagship_panel",
    "flagship_sc3": "flagship SC@3",
    "cheap_panel": "cheap panel ×3",
}


def build_f10() -> None:
    datasets = [("gpqa", "GPQA-Diamond"), ("supergpqa", "SuperGPQA-hard")]
    fig, axes = plt.subplots(1, 2, figsize=(15.2, 7.4), dpi=110)
    rows = []
    summary: dict[str, dict] = {}

    for ax, (ds, pretty) in zip(axes, datasets):
        r = frontier_analyze(ds)
        summary[ds] = r
        pts = r["points"]
        ref = pts["flagship_1x"]

        # Label placement is COLLISION-AWARE, not index-parity based. An
        # earlier parity rule still overprinted SuperGPQA's SC@3 and
        # flagship_panel, which sit 0.6pp apart in accuracy and ~1.3k tokens
        # apart in cost. Here each label is placed above unless a already-
        # placed label is near it in BOTH axes, in which case it flips below.
        ordered = sorted(pts.items(), key=lambda kv: kv[1]["tokens_per_item"])
        x_span = max(e["tokens_per_item"] for e in pts.values()) or 1.0
        placed: list[tuple[float, float, bool]] = []  # (x, y, was_above)

        # The vertical clearance a label needs is set by how tall the LABEL is
        # in axis units, not by how spread the DATA is.
        #
        # This used the data span, and arm C exposed why that is wrong: on GPQA
        # the three points span only 2.3pp, so the threshold came out at 0.88pp
        # while a three-line label occupies ~2.5pp of a 20-point axis. The rule
        # declared universal_gate and flagship_sc5 "not near" and printed one
        # straight through the other's marker.
        #
        # ~13% of the drawn y-range is a three-line label plus its offset.
        #
        # The final ylim is set further down (lo-11, hi+8), AFTER placement, so
        # ax.get_ylim() here would return matplotlib's autoscale default and
        # silently give the wrong clearance. Computed the same way instead, and
        # asserted identical below so the two cannot drift apart.
        _lo = min(e["accuracy"] for e in pts.values()) * 100
        _hi = max(e["accuracy"] for e in pts.values()) * 100
        y_range = (_hi + 8) - (_lo - 11)
        y_clear = 0.13 * y_range

        # Every point's MARKER, so a label can avoid printing through one.
        #
        # The rule only compared labels to other labels, which is why
        # universal_gate's label still ran through flagship_sc5's marker: the
        # two labels were correctly on opposite sides, but the upper one
        # occupied exactly the accuracy where the other point is drawn. A label
        # colliding with a marker is the more visible defect of the two.
        markers = [(e["tokens_per_item"], e["accuracy"] * 100) for e in pts.values()]

        def _side(x: float, y: float) -> bool:
            """True to place the label above; False to flip it below."""
            for px, py, pabove in placed:
                near = abs(px - x) < 0.30 * x_span and abs(py - y) < y_clear
                if near and pabove:
                    return False
            # Would a label placed ABOVE this point land on another marker?
            for mx, my in markers:
                if (mx, my) == (x, y):
                    continue
                if abs(mx - x) < 0.22 * x_span and 0 < (my - y) < y_clear:
                    return False
            return True

        for idx, (config, e) in enumerate(ordered):
            is_ref = config == "flagship_1x"
            beats = bool(e.get("beats_reference"))
            # Solid green only for a config that BEATS the reference at p<0.05.
            # Everything else is hollow: nothing hollow is a win.
            if is_ref:
                color, fill = FLAGSHIP_GOLD, "full"
            elif beats:
                color, fill = WIN_GREEN, "full"
            elif (e.get("net") or 0) < 0:
                color, fill = LOSS_RED, "none"
            else:
                color, fill = NEUTRAL_GREY, "none"

            ax.plot(
                e["tokens_per_item"], e["accuracy"] * 100,
                marker="*" if is_ref else "o", markersize=22 if is_ref else 13,
                markerfacecolor=color if fill == "full" else "none",
                markeredgecolor=color, markeredgewidth=1.8, linestyle="none", zorder=3,
            )
            note = "" if is_ref else f"\nnet {e['net']:+d}, p={e['p_one_sided']:.3f}"
            above = (not is_ref) and _side(e["tokens_per_item"], e["accuracy"] * 100)
            placed.append((e["tokens_per_item"], e["accuracy"] * 100, above))
            ax.annotate(
                F10_LABEL.get(config, config) + note,
                (e["tokens_per_item"], e["accuracy"] * 100),
                textcoords="offset points",
                xytext=(0, -40 if is_ref else (20 if above else -42)),
                ha="center", va="bottom" if above else "top", fontsize=8.2,
                color="#141414" if (is_ref or beats) else "#4a4a4a",
                fontweight="bold" if (is_ref or beats) else "normal",
            )
            rows.append({
                "benchmark": pretty, "config": config, "accuracy_pct": e["accuracy"] * 100,
                "tokens_per_item": e["tokens_per_item"], "n_items": e["n"],
                "accuracy_per_1k_tokens": e["accuracy_per_1k_tokens"],
                "net_vs_flagship_1x": e.get("net"), "p_one_sided": e.get("p_one_sided"),
                "beats_flagship_1x": beats, "on_frontier": e["on_frontier"],
            })

        # Efficiency callout, stated as the ratio rather than drawn as a line.
        # An "iso-efficiency" ray through the origin would imply 421% accuracy
        # at 13k tokens -- visually tidy and mathematically meaningless.
        worst = min(e["accuracy_per_1k_tokens"] for e in pts.values())
        ax.text(
            0.975, 0.045,
            f"one flagship call: {ref['accuracy_per_1k_tokens']:.3f} accuracy per 1k tokens\n"
            f"least efficient config here: {worst:.3f}  →  {ref['accuracy_per_1k_tokens'] / worst:.1f}× worse",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=7.8, color="#5a4300",
            bbox=dict(boxstyle="round,pad=0.42", fc="#fff8e8", ec=FLAGSHIP_GOLD, lw=1.0),
        )

        ax.axhline(ref["accuracy"] * 100, color=FLAGSHIP_GOLD, lw=1.0, ls="--", alpha=0.55, zorder=1)
        ax.axhspan((ref["accuracy"] * 100) - NOISE_FLOOR_PP, (ref["accuracy"] * 100) + NOISE_FLOOR_PP,
                   color=RIBBON_GREY, alpha=0.5, zorder=0)
        n_used = ref["n"]
        ax.set_title(f"{pretty}   (paired, n={n_used} shared items)", fontsize=11, pad=10)
        ax.set_xlabel("tokens per item  (measured, never dollars)")
        ax.set_ylabel("accuracy (%)")
        ax.set_xlim(0, max(e["tokens_per_item"] for e in pts.values()) * 1.35)
        lo = min(e["accuracy"] for e in pts.values()) * 100
        hi = max(e["accuracy"] for e in pts.values()) * 100
        # Must match the range the label-collision clearance was computed
        # against, or labels are placed for an axis that is never drawn.
        assert (lo, hi) == (_lo, _hi), "ylim drifted from the collision calc"
        ax.set_ylim(lo - 11, hi + 8)
        ax.grid(alpha=0.22, zorder=0)

    axes[0].legend(handles=[
        Line2D([], [], marker="*", ls="none", markersize=16, markerfacecolor=FLAGSHIP_GOLD,
               markeredgecolor=FLAGSHIP_GOLD, label="single flagship call (reference)"),
        Line2D([], [], marker="o", ls="none", markersize=10, markerfacecolor=WIN_GREEN,
               markeredgecolor=WIN_GREEN, label="beats reference, p<0.05 (solid)"),
        Line2D([], [], marker="o", ls="none", markersize=10, markerfacecolor="none",
               markeredgecolor=NEUTRAL_GREY, label="no significant gain (hollow)"),
        Line2D([], [], marker="o", ls="none", markersize=10, markerfacecolor="none",
               markeredgecolor=LOSS_RED, label="loses to reference (hollow red)"),
        Patch(facecolor=RIBBON_GREY, alpha=0.5, label=f"±{NOISE_FLOOR_PP:g}pp noise floor"),
    ], loc="upper left", fontsize=7.6, framealpha=0.95)

    # Subtitle and footer are DERIVED, never hand-typed: an earlier version
    # hardcoded "77.2%" and "p=0.0195" and went stale the moment a third seed
    # landed. Caption drift is the exact hazard this repo's ledger guards.
    g, sg = summary["gpqa"], summary["supergpqa"]
    sg_best = max((v for k, v in sg["points"].items() if k != "flagship_1x"),
                  key=lambda e: e["accuracy"])
    sg_best_name = next(k for k, v in sg["points"].items() if v is sg_best)
    draw_title(
        fig, "[PAIRED]",
        "Orchestration pays where the base model is weak — and nowhere else",
        f"Accuracy vs tokens on the per-seed question_id intersection. GPQA: the flagship is already at "
        f"{g['points']['flagship_1x']['accuracy'] * 100:.1f}%, and nothing beats it. SuperGPQA-hard: it sits at "
        f"{sg['points']['flagship_1x']['accuracy'] * 100:.1f}%, and {sg_best_name} wins by "
        f"{sg_best['net']:+d} (p={sg_best['p_one_sided']:.4f}).",
    )
    seed_txt = "; ".join(
        f"{d} seeds {'/'.join(str(x['seed']) for x in summary[d]['seeds_used'])}"
        for d in ("gpqa", "supergpqa")
    )
    draw_footer(
        fig,
        f"benchmark/analyze_cost_frontier.py over committed run files ({seed_txt}). GPQA arms "
        "TB1_flagship1x_*, lever_universal_gate_*; SuperGPQA arms lever_baseline_*, lever_flagship_panel_*, "
        "compute_matched_control_*, lever_control_*.",
        "Tokens, never dollars (cost_usd logs $0.00 after the Token-Plan migration). GPQA's three seeds overlap — "
        "269 rows cover 170 unique items — so its pooled figures are quoted conservatively elsewhere. On "
        "SuperGPQA the cheap_panel arm has no seed-42 file, so its ACCURACY is over fewer items than the "
        "reference's; its paired b/c/net/p still use only items it shares with the reference. flagship_panel's "
        "win is attributed to SAMPLING, not deliberation: vs its own compute-matched SC@3 control it is net +1, "
        "p=0.50.",
    )
    fig.subplots_adjust(left=0.055, right=0.985, top=0.870, bottom=0.215, wspace=0.19)
    save_figure(fig, "f10_paired_cost_frontier", pd.DataFrame(rows))


# ---------------------------------------------------------------------------
# F11 -- cheap-worker scaling
# ---------------------------------------------------------------------------

F11_ARMS = [
    ("lever_diversified_panel_supergpqa_seed19.jsonl", "SuperGPQA-hard · diversified", 19),
    ("lever_cycled_panel_supergpqa_seed19.jsonl", "SuperGPQA-hard · cycled", 19),
    ("KI1BC_compute_matched_n9_gpqa_seed2311.jsonl", "GPQA-Diamond · diversified", 2311),
]


def _scaling_curve(path: Path):
    import json
    from collections import Counter

    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    k = min(len(r["seat_answers"]) for r in rows)
    out = []
    for n in range(1, k + 1, 2):
        acc = cov = 0
        for r in rows:
            letters = [s["letter"] for s in r["seat_answers"][:n]]
            gold = r["engine"]["item"]["correct_letter"]
            acc += Counter(letters).most_common(1)[0][0] == gold
            cov += gold in letters
        out.append((n, acc / len(rows) * 100, cov / len(rows) * 100))
    return out, len(rows)


def build_f11() -> None:
    fig, axes = plt.subplots(1, 3, figsize=(16.0, 6.6), dpi=110, sharey=True)
    rows = []

    for ax, (fname, pretty, seed) in zip(axes, F11_ARMS):
        curve, n_items = _scaling_curve(RESULTS_DIR / fname)
        ns = [c[0] for c in curve]
        plur = [c[1] for c in curve]
        cov = [c[2] for c in curve]

        ax.plot(ns, cov, marker="s", markersize=7, color=COVERAGE_BLUE, lw=2.0,
                label="oracle coverage (answer is present)")
        ax.plot(ns, plur, marker="o", markersize=8, color=NEUTRAL_GREY, lw=2.2,
                markerfacecolor="none", markeredgewidth=1.8,
                label="plurality accuracy (answer is picked)")

        # Random-guess coverage: 1-(3/4)^N. Retires the "40-point opportunity"
        # reading -- 15 random 4-choice guesses already cover 98.7%.
        rand = [(1 - 0.75 ** n) * 100 for n in ns]
        ax.plot(ns, rand, ls=":", lw=1.6, color="#9a5b00",
                label="coverage from RANDOM 4-choice guessing")

        ax.fill_between(ns, plur, cov, color=COVERAGE_BLUE, alpha=0.10, zorder=0)
        # Flatness annotation: the paired N=3 -> N=max verdict.
        ax.axvline(3, color="#666666", lw=1.0, ls="--", alpha=0.7)
        ax.text(3.15, 8, "almost all the\ngain is 1→3", fontsize=7.4, color="#555555", va="bottom")
        ax.set_title(f"{pretty}\nseed {seed}, n={n_items} items", fontsize=10)
        ax.set_xlabel("N cheap solver seats (vote-only, no tribunal)")
        ax.set_xticks(ns)
        ax.grid(alpha=0.22)
        ax.set_ylim(0, 105)

        for n, p, c in curve:
            rows.append({"arm": pretty, "seed": seed, "n_items": n_items, "N_seats": n,
                         "plurality_accuracy_pct": p, "oracle_coverage_pct": c,
                         "random_guess_coverage_pct": (1 - 0.75 ** n) * 100})

    axes[0].set_ylabel("percent of items")
    axes[0].legend(loc="lower right", fontsize=7.6, framealpha=0.95)

    draw_title(
        fig, "[PAIRED]",
        "Scaling cheap workers buys coverage, not answers",
        "Plurality accuracy is flat after N=3 in all three arms. Coverage climbs — but so does random guessing, "
        "which is why the coverage/accuracy gap is NOT a 40-point opportunity.",
    )
    draw_footer(
        fig,
        "lever_diversified_panel_supergpqa_seed19.jsonl, lever_cycled_panel_supergpqa_seed19.jsonl, "
        "KI1BC_compute_matched_n9_gpqa_seed2311.jsonl — every intermediate N derived offline by prefix "
        "subsampling of the logged per-seat answers (zero additional tokens).",
        "Single seed per arm; vote-only (--no-tribunal), so this measures VOTING scaling, not the full engine. "
        "Paired N=3→N=9 on GPQA is b=5 c=5, net EXACTLY 0, p=0.62. The pre-registered +5-item bar was never "
        "cleared on any arm (best observed +3). 15 random 4-choice guesses reach 98.7% coverage — above the "
        "measured 90.8% — so most of the coverage climb is guessing entropy, not harvestable signal.",
    )
    fig.subplots_adjust(left=0.05, right=0.99, top=0.845, bottom=0.235, wspace=0.08)
    save_figure(fig, "f11_cheap_worker_scaling", pd.DataFrame(rows))


# ---------------------------------------------------------------------------
# F12 -- the kill list
# ---------------------------------------------------------------------------

# Every mechanism tested for "can we detect a confident-but-wrong panel?",
# with the measured effect that killed it. Each row traces to a committed doc.
F12_KILLS = [
    ("Verbalized confidence (selector)", "S7 held-out ship gate",
     "net +76 in-sample → −4 held out", 0.78, "s7_live_ship_gate_result.md"),
    ("Confidence-weighted selector", "S7 held-out ship gate",
     "net +3, under bar, disc 11<12", 0.2744, "s7_live_ship_gate_result.md"),
    ("Permutation instability", "META-2, 3 seeds, n=139 unanimous",
     "contrast +7.1pp (needed ≥25)", 0.4552, "meta2_permutation_instability_findings.md"),
    ("Resample instability", "permutation-null control",
     "lift lands ON the null mean", 0.48, "improvement-loop-state.md (FREE SPRINT #2)"),
    ("Self-authored CAS verification", "KI-0R replay, n=151+151",
     "fires 24/151 wrong AND 24/151 right", 1.0000, "ki0r_cas_gate_findings.md"),
    ("Reasoning length (junk control)", "S1 selector audit",
     "net −314 pooled", 0.9999, "selector_audit.md"),
    ("Stronger judge", "9/9 overturns correct",
     "zero net accuracy gain", 0.50, "negative-results.md"),
    ("Panel scaling N=3→15 (cheap)", "Tier D harvest, seed 19",
     "best +3 vs a +5 bar", 0.252, "panel_scaling_n15_seed19.md"),
    ("Deliberation (vs self-consistency)", "compute-matched control",
     "tribunal leg +2 of +10", 0.344, "verify_compute_matched_control.py"),
    ("Whole stack vs one flagship call", "TB-1, 3 seeds, n=265",
     "net +1 at 4.7× the tokens", 0.5000, "tb1_flagship_comparison_result.md"),
    # Added 2026-08-03. The only row measured on the benchmark where
    # orchestration DOES beat a flagship call -- which is what makes it
    # informative rather than one more null: same benchmark, same headroom,
    # same escalate-everything gate as flagship_panel's +7, but cheap seats
    # instead of flagship seats, and the sign flips.
    ("Cheap seats + escalate-all vs flagship", "TB-1B, seed 7, n=87",
     "net −2 at 5.1× the tokens", 0.8906, "tb1b_supergpqa_result.md"),
    # Added 2026-08-03. The strongest row in the list: not "the scaffold fails
    # to beat one call" but "the scaffold LOSES to its own budget spent on
    # plain sampling", on identical items at all three seeds.
    ("Scaffolding vs the same budget sampled", "TB-1 arm C, 3 seeds, n=255",
     "net −6; 90.6% vs SC@5's 92.9%", 0.9807, "tb1_flagship_comparison_result.md"),
]


def _spell(n: int) -> str:
    """Small integers as words, for prose in figure titles.

    Falls back to digits past twenty rather than growing a lookup table that
    nobody maintains -- a title reading "23 mechanisms" is fine; one reading
    "Ten" over 23 bars is not.
    """
    words = ("Zero One Two Three Four Five Six Seven Eight Nine Ten Eleven "
             "Twelve Thirteen Fourteen Fifteen Sixteen Seventeen Eighteen "
             "Nineteen Twenty").split()
    return words[n] if 0 <= n < len(words) else str(n)


def build_f12() -> None:
    df = pd.DataFrame(F12_KILLS, columns=["mechanism", "test", "measured", "p_value", "source"])
    df = df.sort_values("p_value").reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(14.6, 8.4), dpi=120)
    y = range(len(df))
    ax.barh(list(y), df["p_value"], color=LOSS_RED, alpha=0.80, height=0.62, zorder=2)
    ax.axvline(0.05, color="#141414", lw=1.6, ls="--", zorder=3)
    # Threshold label sits BELOW the lowest bar, where there is empty space --
    # at the top it overprinted the longest bar's annotation.
    ax.text(0.062, -0.62, "p = 0.05 significance threshold",
            fontsize=8.6, color="#141414", va="bottom", fontweight="bold")

    for i, row in df.iterrows():
        ax.text(-0.014, i, row["mechanism"], ha="right", va="center", fontsize=9.4, fontweight="bold")
        ax.text(row["p_value"] + 0.014, i, f"{row['measured']}   (p={row['p_value']:.4g})",
                ha="left", va="center", fontsize=8.2, color="#333333")

    ax.set_yticks([])
    # Widened so the longest annotation (the p=1.0000 CAS row) is not clipped.
    # The xlim runs past 1.0 only to leave room for the right-hand annotations
    # (the longest is the p=1.0000 CAS row). Ticks stop at 1.0, because a
    # p-value axis labelled 1.2 / 1.4 / 1.6 tells the reader p can exceed 1 --
    # a false statement about the statistic, in a figure whose whole subject is
    # statistics.
    ax.set_xlim(0, 1.72)
    ax.set_xticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    # Stop the axis line where the statistic stops too, so the annotation
    # margin does not read as unlabelled axis, and centre the label under the
    # data rather than under the blank margin.
    ax.spines["bottom"].set_bounds(0.0, 1.0)
    ax.set_ylim(-0.95, len(df) - 0.3)
    ax.set_xlabel("p-value of the measured effect  (all far above 0.05 — none is a detector)")
    # AFTER set_xlabel -- set_xlabel resets the label position, so calling this
    # first silently does nothing (it did, on the first attempt).
    ax.xaxis.set_label_coords(1.0 / 1.72 / 2, -0.085)
    ax.grid(axis="x", alpha=0.22, zorder=0)
    ax.spines[["top", "right", "left"]].set_visible(False)

    draw_title(
        fig, "[PAIRED]",
        # DERIVED, not typed. This title read "Ten mechanisms ... Ten nulls."
        # while the chart underneath it drew eleven bars, the moment TB-1B was
        # added -- the same failure as the F10 caption, in the same module,
        # three weeks later. A count in a title must come from the data it
        # counts.
        f"{_spell(len(df))} mechanisms tested for finding a confident-but-wrong "
        f"panel. {_spell(len(df))} nulls.",
        "Every technique that re-reads what the model already generated has failed. Any new proposal whose "
        "readout is cross-seat agreement or a transcript property must argue past all of these.",
    )
    draw_footer(
        fig,
        "; ".join(sorted(set(df["source"]))),
        "p-values are the measured statistic each result was killed on and are NOT mutually comparable — they "
        "come from exact McNemar, Fisher exact, and permutation nulls depending on the design. The bar chart "
        "ranks them only to show that none approaches 0.05. Two rows (resample instability, stronger judge) are "
        "quoted from earlier committed write-ups rather than recomputed here.",
    )
    fig.subplots_adjust(left=0.235, right=0.985, top=0.855, bottom=0.185)
    save_figure(fig, "f12_kill_list", df)


# ---------------------------------------------------------------------------
# F13 -- why +25 and +1 are both true
# ---------------------------------------------------------------------------


def build_f13() -> None:
    r = frontier_analyze("gpqa")
    ug = r["points"]["universal_gate"]
    fl = r["points"]["flagship_1x"]

    # Measured, from the committed result docs (all recomputed in this session).
    bars = [
        ("cheap panel\n(shipped rule:\nescalate splits only)", 80.8, NEUTRAL_GREY, ""),
        ("universal_gate\n(escalate every item)", ug["accuracy"] * 100, WIN_GREEN,
         "+25 vs cheap panel\np = 3.0e-8"),
        ("qwen3.7-max\n×1 call", fl["accuracy"] * 100, FLAGSHIP_GOLD,
         f"gate is net {ug['net']:+d}\nvs this, p={ug['p_one_sided']:.2f}"),
    ]
    # TB-1 arm C, appended only when it is registered AND has data. Kept
    # conditional rather than hardcoded so this figure gains its fourth bar the
    # moment analyze_cost_frontier registers flagship_sc5, without a second
    # edit here -- and so the figure is never drawn with a partially-fired arm,
    # since frontier_analyze only returns points for arms it actually loaded.
    sc5 = r["points"].get("flagship_sc5")
    if sc5:
        bars.append((
            "qwen3.7-max\nSC@5\n(compute-matched)",
            sc5["accuracy"] * 100, LOSS_RED,
            f"gate is net {-sc5['net']:+d}\nvs this, p={sc5['p_one_sided']:.2f}"
            if sc5.get("net") is not None else "",
        ))

    fig, ax = plt.subplots(figsize=(11.6 + 1.4 * (len(bars) - 3), 7.4), dpi=125)
    xs = range(len(bars))
    ax.bar(list(xs), [b[1] for b in bars], color=[b[2] for b in bars], width=0.56, zorder=2, alpha=0.9)

    for i, (label, val, color, note) in enumerate(bars):
        ax.text(i, val + 0.7, f"{val:.1f}%", ha="center", fontsize=12, fontweight="bold")
        if note:
            ax.text(i, val - 4.6, note, ha="center", fontsize=8.4, color="#ffffff", fontweight="bold")

    # The comparator SPREAD -- the whole explanation. Drawn as a vertical span
    # to the RIGHT of the bars: an earlier diagonal arrow cut straight through
    # the middle bar's own label.
    #
    # Spans lowest bar to highest, whichever they are. This said "the two
    # comparators" while four bars were drawn, because arm C added a third.
    gap_x = len(bars) - 0.48
    ys = [b[1] for b in bars]
    lo_y, hi_y = min(ys), max(ys)
    n_comparators = len(bars) - 1  # every bar except universal_gate itself
    ax.annotate("", xy=(gap_x, lo_y), xytext=(gap_x, hi_y),
                arrowprops=dict(arrowstyle="<->", color="#444444", lw=1.6))
    for yv in (lo_y, hi_y):
        ax.plot([len(bars) - 0.72, gap_x], [yv, yv], color="#8a8a8a", lw=0.9, ls=":", zorder=1)
    ax.text(gap_x + 0.06, (lo_y + hi_y) / 2,
            f"{_spell(n_comparators).lower()} comparators,\n{hi_y - lo_y:.1f} points apart",
            ha="left", va="center", fontsize=8.8, color="#333333", style="italic")

    ax.set_xticks(list(xs))
    ax.set_xticklabels([b[0] for b in bars], fontsize=9.2)
    ax.set_ylabel("GPQA-Diamond accuracy (%)")
    ax.set_xlim(-0.55, len(bars) + 0.25)
    ax.set_ylim(70, 95)
    ax.grid(axis="y", alpha=0.22, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)

    # Title DERIVED. It read "Why +25 and +1 are both true" after arm C had
    # moved the flagship comparison to net +0 -- naming a number the chart no
    # longer showed. Fourth stale count in this module; the pattern is settled.
    n_cmp = _spell(len(bars) - 1).lower()
    sc5_txt = (f", and net {-sc5['net']:+d} against that same budget sampled"
               if sc5 and sc5.get("net") is not None else "")
    draw_title(
        fig, "[PAIRED]",
        f"One lever, {n_cmp} comparators, {n_cmp} different verdicts",
        f"universal_gate is +25 against the cheap panel, net {ug['net']:+d} against a single flagship call"
        f"{sc5_txt} — same lever, same items, same seeds. The comparator decides the verdict, which is why "
        f"the comparator has to be named every time.",
    )
    draw_footer(
        fig,
        "universal_gate_3seed_result.md, tb1_flagship_comparison_result.md, gpqa_paired_cost_frontier.md; "
        "arms paired in-run on seeds 1001/2311/3407.",
        "universal_gate issues one qwen3.7-max judge call on EVERY item (judge calls/item = 1.00), so this is a "
        "SCAFFOLDED flagship call, not cheap seats replacing a flagship. Its +25 vs the cheap panel is +21 "
        "counting each item once (three 90-item seeds over a ~198-question benchmark cover 170 unique items). "
        f"Cost on THIS item set: {ug['tokens_per_item']:,.0f} vs {fl['tokens_per_item']:,.0f} tok/item"
        + (f"; the compute-matched control spends {sc5['tokens_per_item']:,.0f}." if sc5 else "."),
    )
    fig.subplots_adjust(left=0.085, right=0.975, top=0.850, bottom=0.195)
    save_figure(fig, "f13_two_comparators", pd.DataFrame(
        [{"config": b[0].replace("\n", " "), "accuracy_pct": b[1]} for b in bars]))


def main() -> None:
    print("Building F10-F13 (2026-08-02 findings set)...")
    build_f10()
    build_f11()
    build_f12()
    build_f13()
    print("Done.")


if __name__ == "__main__":
    main()
