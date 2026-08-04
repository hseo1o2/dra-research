"""Publication figures for REALM review-followup analyses.

Reads frozen analysis JSON / match dirs. No external API.

Usage:
  open_deep_research/.venv/bin/python scripts/plot_review_followup_figures.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".mplconfig"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch

# Reuse palette from plot_paper_figures
INK = "#20252B"
MUTED = "#66707A"
GRID = "#DDE2E6"
BLUE = "#2865A8"
BLUE_DARK = "#184A7A"
ORANGE = "#C0540A"
GREEN = "#2F7D4A"
PURPLE = "#6B4C9A"
TEAL = "#1F7A7A"
SEED_GREY = "#8B949D"

STAGES = ("plan", "search", "compress", "write")
STAGE_LABELS = {
    "plan": "Planning",
    "search": "Search",
    "compress": "Compression",
    "write": "Writing",
}


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "font.size": 7.5,
            "axes.titlesize": 8.5,
            "axes.labelsize": 7.5,
            "xtick.labelsize": 7.0,
            "ytick.labelsize": 7.0,
            "legend.fontsize": 6.5,
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


def _save(fig: plt.Figure, out_dir: Path, stem: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for fmt in ("pdf", "svg", "png"):
        path = out_dir / f"{stem}.{fmt}"
        kw = {"facecolor": "white", "bbox_inches": "tight", "pad_inches": 0.02}
        if fmt == "png":
            kw["dpi"] = 300
        fig.savefig(path, format=fmt, **kw)
        paths.append(path)
    plt.close(fig)
    return paths


def plot_protocol_trajectories(summary: dict, out_dir: Path) -> list[Path]:
    """Hard-neg vs symmetric vs prior-wrong Acc@1 trajectories."""
    series = [
        ("Per-GT hard-neg", summary["hardneg_per_gt"], BLUE),
        ("Symmetric task-shared", summary["symmetric_task_shared"], ORANGE),
        (
            "Prior-wrong subset",
            summary["prior_adjusted"]["prior_wrong_only"]["trajectory"],
            GREEN,
        ),
    ]
    x = np.arange(len(STAGES))
    fig, ax = plt.subplots(figsize=(3.45, 2.65))
    for i, (label, block, color) in enumerate(series):
        ys = [block["stages"][s]["acc"] for s in STAGES]
        los = [block["stages"][s]["ci95"][0] for s in STAGES]
        his = [block["stages"][s]["ci95"][1] for s in STAGES]
        yerr = np.array(
            [[y - lo for y, lo in zip(ys, los)], [hi - y for y, hi in zip(ys, his)]]
        )
        ax.errorbar(
            x + (i - 1) * 0.08,
            ys,
            yerr=yerr,
            fmt="-o",
            color=color,
            lw=1.3,
            ms=3.6,
            capsize=1.6,
            elinewidth=0.7,
            label=label,
            zorder=3 + i,
        )
    ax.axhline(1 / 3, color=MUTED, ls="--", lw=0.8, label="Chance (N=3)")
    ax.set_xticks(x)
    ax.set_xticklabels([STAGE_LABELS[s] for s in STAGES])
    ax.set_ylabel("Acc@1")
    ax.set_ylim(0.28, 0.98)
    ax.set_xlim(-0.25, 3.25)
    ax.yaxis.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend(
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
        ncol=2,
        columnspacing=1.0,
        handlelength=1.6,
    )
    ax.set_title("Recoverability by candidate protocol")
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.28)
    return _save(fig, out_dir, "protocol_trajectory_comparison")


def plot_transition_flows(summary: dict, out_dir: Path) -> list[Path]:
    """Bar chart of report-level transitions for hard-neg vs symmetric."""
    # Recompute lost/gained from match files for both protocols
    from scripts.analyze_review_followup import STAGES as _S  # noqa
    import re
    from collections import defaultdict

    RUN_RE = re.compile(r"task(?P<taskid>\d+)_User(?P<user>\d+)_seed(?P<seed>\d+)")

    def transitions(match_dir: Path) -> dict[str, tuple[int, int]]:
        by_run: dict[str, dict[str, bool]] = defaultdict(dict)
        for path in sorted(match_dir.glob("*_match.json")):
            for rec in json.loads(path.read_text(encoding="utf-8")):
                by_run[rec["run_id"]][rec["stage"]] = bool(rec["correct"])
        pairs = [
            ("plan", "search"),
            ("search", "compress"),
            ("compress", "write"),
        ]
        out = {}
        for a, b in pairs:
            lost = gained = 0
            for st in by_run.values():
                if a not in st or b not in st:
                    continue
                if st[a] and not st[b]:
                    lost += 1
                if (not st[a]) and st[b]:
                    gained += 1
            out[f"{a}→{b}"] = (lost, gained)
        return out

    hard = transitions(ROOT / "runs/confirmatory/matches_hardneg_v1")
    sym = transitions(ROOT / "runs/confirmatory/matches_sha256")
    labels = ["Plan→Search", "Search→Comp.", "Comp.→Write"]
    keys = ["plan→search", "search→compress", "compress→write"]

    fig, axes = plt.subplots(1, 2, figsize=(5.9, 2.55), sharey=True)
    handles = None
    for ax, data, title, color in [
        (axes[0], hard, "Per-GT hard-neg", BLUE),
        (axes[1], sym, "Symmetric task-shared", ORANGE),
    ]:
        lost = [data[k][0] for k in keys]
        gained = [data[k][1] for k in keys]
        x = np.arange(len(labels))
        w = 0.36
        b1 = ax.bar(x - w / 2, lost, w, color=color, alpha=0.9, label="Lost")
        b2 = ax.bar(
            x + w / 2,
            gained,
            w,
            color=color,
            alpha=0.35,
            edgecolor=color,
            label="Gained",
        )
        for i, (L, G) in enumerate(zip(lost, gained)):
            ax.text(i - w / 2, L + 0.5, str(L), ha="center", va="bottom", fontsize=6.2)
            ax.text(i + w / 2, G + 0.5, str(G), ha="center", va="bottom", fontsize=6.2)
        ax.set_xticks(x)
        ax.set_xticklabels(["P→S", "S→C", "C→W"])
        ax.set_title(title)
        ax.set_ylim(0, 38)
        ax.yaxis.grid(True, color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        handles = [b1, b2]
    axes[0].set_ylabel("# reports")
    fig.legend(
        handles,
        ["Lost (correct→wrong)", "Gained (wrong→correct)"],
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.02),
        ncol=2,
        fontsize=6.5,
    )
    fig.suptitle("Report-level attribution transitions", y=0.98, fontsize=9)
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))
    return _save(fig, out_dir, "report_level_transitions")


def plot_chance_normalized_n(summary: dict, out_dir: Path) -> list[Path]:
    block = summary["n_sensitivity_chance_normalized"]
    fig, ax = plt.subplots(figsize=(3.4, 2.35))
    colors = {2: TEAL, 3: BLUE, 5: PURPLE}
    x = np.arange(len(STAGES))
    for i, n in enumerate((2, 3, 5)):
        key = f"N={n}"
        ys = [block[key]["stages"][s]["chance_normalized"] for s in STAGES]
        ax.plot(
            x,
            ys,
            "-o",
            color=colors[n],
            lw=1.4,
            ms=4.0,
            label=f"$N={n}$ (chance {1/n:.2f})",
        )
    ax.axhline(0.0, color=MUTED, ls="--", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([STAGE_LABELS[s] for s in STAGES])
    ax.set_ylabel(r"Chance-normalized Acc")
    ax.set_ylim(-0.05, 0.85)
    ax.yaxis.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend(frameon=False, loc="upper right")
    ax.set_title(r"Chance-normalized recoverability by $N$")
    fig.tight_layout()
    return _save(fig, out_dir, "chance_normalized_n_sensitivity")


def plot_user10_exposure(summary: dict, out_dir: Path) -> list[Path]:
    by = summary["user10_exposure"]["by_stage"]
    rates = [by[s]["false_rate_given_exposure"] for s in STAGES]
    x = np.arange(len(STAGES))
    fig, ax = plt.subplots(figsize=(3.3, 2.25))
    bars = ax.bar(x, rates, color=BLUE, width=0.62, edgecolor=BLUE_DARK, lw=0.6)
    ax.axhline(1 / 3, color=ORANGE, ls="--", lw=1.0, label="Chance (1/3)")
    ax.set_xticks(x)
    ax.set_xticklabels([STAGE_LABELS[s] for s in STAGES])
    ax.set_ylabel("False rate to User10 | exposed")
    ax.set_ylim(0, 0.55)
    for b, r in zip(bars, rates):
        ax.text(
            b.get_x() + b.get_width() / 2,
            r + 0.015,
            f"{r:.2f}",
            ha="center",
            va="bottom",
            fontsize=6.5,
        )
    ax.yaxis.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend(frameon=False, loc="upper right")
    ax.set_title("User10 false rate after exposure control")
    fig.tight_layout()
    return _save(fig, out_dir, "user10_exposure_false_rate")


def plot_recovery_sankey_lite(out_dir: Path) -> list[Path]:
    """Compact flow diagram: Plan✓Search✗ → Write recover / non-recover."""
    # numbers from primary hard-neg
    n_loss = 32
    recover = 24
    non = 8
    fig, ax = plt.subplots(figsize=(3.5, 2.0))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

    def box(x, y, w, h, text, color):
        patch = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            facecolor=color,
            edgecolor=INK,
            linewidth=0.7,
            alpha=0.9,
        )
        ax.add_patch(patch)
        ax.text(
            x + w / 2,
            y + h / 2,
            text,
            ha="center",
            va="center",
            fontsize=6.8,
            color=INK,
        )

    box(0.3, 2.0, 2.8, 1.8, f"Plan correct\nSearch wrong\n$n={n_loss}$", "#DCE8F5")
    box(6.8, 3.4, 2.8, 1.6, f"Write recover\n$n={recover}$ (75%)", "#D9EBDD")
    box(6.8, 0.8, 2.8, 1.6, f"Non-recover\n$n={non}$ (25%)", "#F5E0D6")
    ax.annotate(
        "",
        xy=(6.8, 4.2),
        xytext=(3.2, 3.2),
        arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.3),
    )
    ax.annotate(
        "",
        xy=(6.8, 1.6),
        xytext=(3.2, 2.5),
        arrowprops=dict(arrowstyle="->", color=ORANGE, lw=1.3),
    )
    ax.set_title("Primary report-level recovery flow (hard-neg)", fontsize=8.5, pad=6)
    fig.tight_layout()
    return _save(fig, out_dir, "recovery_flow_plan_search_write")


def plot_nobrief_paired(out_dir: Path) -> list[Path]:
    """Paired full vs no-brief Write Acc for n=30 if available."""
    path = ROOT / "runs/ablation/nobrief_writeonly/analysis_paired.json"
    if not path.exists():
        return []
    d = json.loads(path.read_text(encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(2.8, 2.15))
    labels = ["Full", "No-brief"]
    vals = [d["full_write_acc"], d["nobrief_write_acc"]]
    colors = [BLUE, ORANGE]
    bars = ax.bar(labels, vals, color=colors, width=0.55, edgecolor=INK, lw=0.5)
    ax.axhline(1 / 3, color=MUTED, ls="--", lw=0.8, label="Chance")
    ax.set_ylabel("Write Acc@1")
    ax.set_ylim(0, 1.08)
    for b, v in zip(bars, vals):
        ax.text(
            b.get_x() + b.get_width() / 2,
            v + 0.03,
            f"{v:.3f}",
            ha="center",
            fontsize=7,
        )
    ci = d.get("task_bootstrap_95ci_delta", [None, None])
    ax.set_title(f"No-brief write-only (n={d['n']})", fontsize=8.0)
    ax.text(
        0.5,
        0.08,
        f"Δ={d['delta_nobrief_minus_full']:+.3f}  CI [{ci[0]}, {ci[1]}]",
        transform=ax.transAxes,
        ha="center",
        fontsize=6.5,
        color=MUTED,
    )
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.yaxis.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper right", fontsize=6.5)
    fig.tight_layout()
    return _save(fig, out_dir, "nobrief_write_paired")


def plot_brief_interventions(out_dir: Path) -> list[Path]:
    """Full / no-brief / other-brief on shared n=15 slice."""
    path = ROOT / "runs/ablation/otherbrief_writeonly/analysis_paired.json"
    if not path.exists():
        return []
    d = json.loads(path.read_text(encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(3.35, 2.35))
    labels = ["Full", "No-brief", "Other brief"]
    vals = [
        d["full_write_acc"],
        d["nobrief_write_acc"],
        d["otherbrief_write_acc"],
    ]
    colors = [BLUE, ORANGE, PURPLE]
    x = np.arange(len(labels))
    bars = ax.bar(x, vals, color=colors, width=0.62, edgecolor=INK, lw=0.5)
    ax.axhline(1 / 3, color=MUTED, ls="--", lw=0.8, label="Chance")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Write Acc@1")
    ax.set_ylim(0, 1.08)
    for b, v in zip(bars, vals):
        ax.text(
            b.get_x() + b.get_width() / 2,
            v + 0.03,
            f"{v:.3f}",
            ha="center",
            fontsize=7,
        )
    ci = d.get("task_bootstrap_95ci_delta_other_minus_full", [None, None])
    ax.set_title(f"Write-only brief interventions (n={d['n']})", fontsize=8.0)
    ax.text(
        0.5,
        0.06,
        f"other−full Δ={d['delta_other_minus_full']:+.3f}  "
        f"CI [{ci[0]}, {ci[1]}]",
        transform=ax.transAxes,
        ha="center",
        fontsize=6.4,
        color=MUTED,
    )
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.yaxis.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper right", fontsize=6.5)
    fig.tight_layout()
    return _save(fig, out_dir, "brief_intervention_write_acc")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT
        / "runs/confirmatory/analysis_review_followup/review_followup_summary.json",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "paper/figures"
    )
    args = parser.parse_args()
    _style()

    if not args.summary.exists():
        # regenerate summary first
        from scripts.analyze_review_followup import main as analyze_main

        analyze_main([])
    summary = json.loads(args.summary.read_text(encoding="utf-8"))

    written: list[Path] = []
    written += plot_protocol_trajectories(summary, args.output_dir)
    written += plot_transition_flows(summary, args.output_dir)
    written += plot_chance_normalized_n(summary, args.output_dir)
    written += plot_user10_exposure(summary, args.output_dir)
    written += plot_recovery_sankey_lite(args.output_dir)
    written += plot_nobrief_paired(args.output_dir)
    written += plot_brief_interventions(args.output_dir)

    print("Wrote:")
    for p in written:
        print(" ", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
