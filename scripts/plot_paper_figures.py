"""Render publication-ready DRA paper figures from analysis CSV files.

No external API is used. Outputs are vector PDF/SVG plus a 300-DPI PNG preview.

Usage:
    python scripts/plot_paper_figures.py \
      --analysis-dir runs/confirmatory/analysis_legacy_seed0 \
      --output-dir paper/figures
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MultipleLocator

STAGES = ("plan", "search", "compress", "write")
STAGE_LABELS = {
    "plan": "Planning",
    "search": "Search",
    "compress": "Compression",
    "write": "Writing",
}

# Restrained, colorblind-safe research palette.
INK = "#20252B"
MUTED = "#66707A"
GRID = "#DDE2E6"
BLUE = "#2865A8"
BLUE_DARK = "#184A7A"
SEED_GREYS = ("#8B949D", "#B0B7BE")
ORANGE = "#C0540A"
ORANGE_LIGHT = "#E07A3A"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _float(row: dict[str, str], field: str) -> float:
    return float(row[field])


def _configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "font.size": 7.5,
            "axes.titlesize": 9.0,
            "axes.labelsize": 7.5,
            "xtick.labelsize": 7.2,
            "ytick.labelsize": 7.0,
            "legend.fontsize": 6.8,
            "axes.edgecolor": INK,
            "axes.linewidth": 0.7,
            "text.color": INK,
            "axes.labelcolor": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def _load_gpt_values(summary_path: Path) -> list[float]:
    """Return [plan, search, compress, write] accuracy from a GPT summary JSON."""
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    acc = data["accuracy"]
    return [acc["plan"], acc["search"], acc["compress"], acc["write"]]


def plot_stage_trajectory(
    analysis_dir: Path,
    output_dir: Path,
    stem: str = "stage_attribution_trajectory",
    gpt_seed0_summary: Path | None = None,
    gpt_seed1_summary: Path | None = None,
) -> list[Path]:
    """Plot stage-wise Acc@1 with task-cluster bootstrap uncertainty."""
    accuracy_rows = _read_csv(analysis_dir / "stage_accuracy.csv")
    ci_rows = _read_csv(
        analysis_dir / "stage_accuracy_cluster_bootstrap.csv"
    )

    combined = {
        row["stage"]: row
        for row in accuracy_rows
        if row["seed"] == "all"
    }
    ci = {row["stage"]: row for row in ci_rows}
    missing = [
        stage for stage in STAGES
        if stage not in combined or stage not in ci
    ]
    if missing:
        raise ValueError(f"Missing stages in analysis CSV: {missing}")

    seed_labels = sorted(
        {
            row["seed"] for row in accuracy_rows
            if row["seed"] != "all"
        },
        key=int,
    )
    x = list(range(len(STAGES)))
    values = [_float(combined[stage], "accuracy") for stage in STAGES]
    low = [_float(ci[stage], "ci95_low") for stage in STAGES]
    high = [_float(ci[stage], "ci95_high") for stage in STAGES]
    yerr = [
        [value - lower for value, lower in zip(values, low)],
        [upper - value for value, upper in zip(values, high)],
    ]

    _configure_style()
    figure, axis = plt.subplots(figsize=(3.35, 2.55))
    figure.patch.set_facecolor("white")
    axis.set_facecolor("white")

    # Seed-specific paths provide context without competing with the aggregate.
    if len(seed_labels) >= 2:
        for index, seed in enumerate(seed_labels):
            seed_rows = {
                row["stage"]: row
                for row in accuracy_rows
                if row["seed"] == seed
            }
            seed_values = [
                _float(seed_rows[stage], "accuracy") for stage in STAGES
            ]
            axis.plot(
                x,
                seed_values,
                color=SEED_GREYS[index % len(SEED_GREYS)],
                linewidth=0.9,
                linestyle=("--" if index % 2 == 0 else ":"),
                marker=("o" if index % 2 == 0 else "s"),
                markersize=3.2,
                markerfacecolor="white",
                markeredgewidth=0.7,
                label=f"Seed {seed}",
                zorder=2,
            )

    axis.errorbar(
        x,
        values,
        yerr=yerr,
        color=BLUE_DARK,
        ecolor=BLUE,
        linewidth=1.65,
        elinewidth=1.0,
        capsize=2.5,
        capthick=0.8,
        marker="o",
        markersize=4.7,
        markerfacecolor="white",
        markeredgecolor=BLUE_DARK,
        markeredgewidth=1.2,
        label=("Combined" if len(seed_labels) >= 2 else "Seed 0"),
        zorder=4,
    )

    # GPT overlay — individual seeds as thin orange lines, combined as medium dashed.
    gpt_summaries = [
        (p, label)
        for p, label in [
            (gpt_seed0_summary, "GPT seed 0"),
            (gpt_seed1_summary, "GPT seed 1"),
        ]
        if p is not None
    ]
    if gpt_summaries:
        gpt_seed_styles = [
            dict(linestyle="--", linewidth=0.85, color=ORANGE_LIGHT, marker="^",
                 markersize=2.8, markerfacecolor="white", markeredgewidth=0.6, zorder=3),
            dict(linestyle=":", linewidth=0.85, color=ORANGE_LIGHT, marker="v",
                 markersize=2.8, markerfacecolor="white", markeredgewidth=0.6, zorder=3),
        ]
        all_gpt = []
        for (path, label), style in zip(gpt_summaries, gpt_seed_styles):
            gpt_vals = _load_gpt_values(path)
            all_gpt.append(gpt_vals)
            axis.plot(x, gpt_vals, label=label, **style)
        # Combined GPT mean
        combined_gpt = [
            sum(v[i] for v in all_gpt) / len(all_gpt) for i in range(len(STAGES))
        ]
        axis.plot(
            x, combined_gpt,
            color=ORANGE, linewidth=1.35, linestyle=(0, (5, 2)),
            marker="D", markersize=3.6,
            markerfacecolor="white", markeredgecolor=ORANGE, markeredgewidth=1.0,
            label="GPT-nano (combined)", zorder=4,
        )

    chance = 1 / 3
    axis.axhline(
        chance,
        color=MUTED,
        linewidth=0.9,
        linestyle=(0, (3, 2)),
        zorder=1,
    )
    axis.text(
        3.02,
        chance + 0.018,
        "Chance 0.333",
        color=MUTED,
        fontsize=6.4,
        ha="right",
        va="bottom",
    )

    for position, value in zip(x, values):
        axis.annotate(
            f"{value:.3f}",
            (position, value),
            xytext=(0, 7),
            textcoords="offset points",
            ha="center",
            va="bottom",
            color=BLUE_DARK,
            fontsize=6.8,
            fontweight="bold",
            bbox={
                "boxstyle": "square,pad=0.12",
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.94,
            },
            zorder=6,
        )

    n_reports = int(float(combined["plan"]["n"]))
    n_tasks = int(float(ci["plan"]["n_tasks"]))
    seed_scope = (
        f"Seeds {', '.join(seed_labels)}"
        if len(seed_labels) >= 2
        else f"Seed {seed_labels[0]}"
    )
    axis.set_title(
        "Stage-wise persona attribution accuracy",
        loc="left",
        pad=17,
        fontweight="bold",
    )
    axis.text(
        0,
        1.045,
        f"{seed_scope} · n={n_reports} reports · "
        f"{n_tasks} task clusters · 95% CI",
        transform=axis.transAxes,
        color=MUTED,
        fontsize=6.5,
        ha="left",
        va="bottom",
    )

    axis.set_xticks(x, [STAGE_LABELS[stage] for stage in STAGES])
    axis.set_ylabel("Attribution accuracy (Acc@1)")
    axis.set_xlim(-0.15, 3.15)
    axis.set_ylim(0, 1.0)
    axis.yaxis.set_major_locator(MultipleLocator(0.25))
    axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.2f}"))
    axis.grid(axis="y", color=GRID, linewidth=0.55)
    axis.grid(axis="x", visible=False)
    axis.tick_params(axis="both", length=2.5, width=0.6)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)

    if len(seed_labels) >= 2 or gpt_summaries:
        axis.legend(
            loc="lower right",
            frameon=False,
            ncol=3,
            handlelength=1.7,
            columnspacing=0.8,
            borderaxespad=0.2,
            labelspacing=0.3,
        )

    figure.subplots_adjust(left=0.17, right=0.98, bottom=0.19, top=0.80)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        output_dir / f"{stem}.pdf",
        output_dir / f"{stem}.svg",
        output_dir / f"{stem}.png",
    ]
    figure.savefig(outputs[0], format="pdf", facecolor="white")
    figure.savefig(outputs[1], format="svg", facecolor="white")
    figure.savefig(outputs[2], format="png", dpi=300, facecolor="white")
    plt.close(figure)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--gpt-seed0-summary", type=Path, default=None,
                        help="GPT seed-0 match_accuracy_summary.json")
    parser.add_argument("--gpt-seed1-summary", type=Path, default=None,
                        help="GPT seed-1 match_accuracy_summary.json")
    args = parser.parse_args()

    outputs = plot_stage_trajectory(
        args.analysis_dir, args.output_dir,
        gpt_seed0_summary=args.gpt_seed0_summary,
        gpt_seed1_summary=args.gpt_seed1_summary,
    )
    for path in outputs:
        print(f"Figure → {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
