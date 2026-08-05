"""Generate DRA-PULSE pipeline overview figure for §3 Method."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".mplconfig"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

INK   = "#20252B"
MUTED = "#66707A"
GRID  = "#DDE2E6"
BLUE      = "#2865A8"
BLUE_DARK = "#184A7A"
BLUE_LIGHT = "#D6E4F7"
GREEN_LIGHT = "#D4EDDA"
GREEN_DARK  = "#1A6B35"
ORANGE_LIGHT = "#FDE8D0"
ORANGE_DARK  = "#8B3A0A"
GREY_LIGHT  = "#EAECEE"
GREY_DARK   = "#4A5058"


def _rounded_box(ax, x, y, w, h, label, sublabel, fc, ec, fontsize=7.2):
    box = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.02",
        facecolor=fc, edgecolor=ec, linewidth=1.0, zorder=3,
    )
    ax.add_patch(box)
    ax.text(x, y + 0.02, label, ha="center", va="center",
            fontsize=fontsize, fontweight="bold", color=ec, zorder=4)
    if sublabel:
        ax.text(x, y - 0.10, sublabel, ha="center", va="center",
                fontsize=5.8, color=MUTED, zorder=4, style="italic")


def _arrow(ax, x0, y0, x1, y1, color=MUTED, lw=1.0):
    ax.annotate(
        "", xy=(x1, y1), xytext=(x0, y0),
        arrowprops=dict(arrowstyle="-|>", color=color,
                        lw=lw, mutation_scale=9),
        zorder=2,
    )


def _probe_box(ax, x, y, acc, is_low=False):
    fc = ORANGE_LIGHT if is_low else BLUE_LIGHT
    ec = ORANGE_DARK  if is_low else BLUE_DARK
    w, h = 0.38, 0.21
    box = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.015",
        facecolor=fc, edgecolor=ec, linewidth=0.8, zorder=3,
    )
    ax.add_patch(box)
    ax.text(x, y + 0.015, f"{acc:.3f}", ha="center", va="center",
            fontsize=6.5, fontweight="bold", color=ec, zorder=4)
    ax.text(x, y - 0.060, "Acc@1", ha="center", va="center",
            fontsize=5.2, color=MUTED, zorder=4)


def main():
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "font.size": 7.5,
        "text.color": INK,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
    })

    fig, ax = plt.subplots(figsize=(6.5, 2.55))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(0, 6.5)
    ax.set_ylim(0, 2.55)
    ax.axis("off")

    # ── Input block ───────────────────────────────────────────────────────────
    inp_x, inp_y = 0.62, 1.65
    _rounded_box(ax, inp_x, inp_y, 0.90, 0.52,
                 "Persona $p^*$", "identity + prefs",
                 fc=GREEN_LIGHT, ec=GREEN_DARK, fontsize=6.8)
    _rounded_box(ax, inp_x, inp_y - 0.70, 0.90, 0.30,
                 "Query $q$", None,
                 fc=GREY_LIGHT, ec=GREY_DARK, fontsize=6.8)

    # brace / merge arrow into pipeline
    ax.annotate("", xy=(1.25, 1.28), xytext=(inp_x + 0.45, inp_y),
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8,
                                connectionstyle="arc3,rad=-0.25"), zorder=2)
    ax.annotate("", xy=(1.25, 1.28), xytext=(inp_x + 0.45, inp_y - 0.70),
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8,
                                connectionstyle="arc3,rad=0.25"), zorder=2)
    _arrow(ax, 1.25, 1.28, 1.45, 1.28, color=MUTED, lw=0.9)

    # ── Pipeline stages ───────────────────────────────────────────────────────
    stages = [
        ("Planning",    "research brief",  1.80, BLUE_LIGHT, BLUE_DARK),
        ("Search",      "queries + results", 2.80, ORANGE_LIGHT, ORANGE_DARK),
        ("Compression", "evidence synthesis", 3.85, ORANGE_LIGHT, ORANGE_DARK),
        ("Writing",     "final report",    4.90, BLUE_LIGHT, BLUE_DARK),
    ]
    stage_y = 1.28
    box_w, box_h = 0.72, 0.48

    for label, sub, sx, fc, ec in stages:
        _rounded_box(ax, sx, stage_y, box_w, box_h, label, sub,
                     fc=fc, ec=ec, fontsize=7.0)

    # arrows between stages
    gaps = [(1.80, 2.80), (2.80, 3.85), (3.85, 4.90)]
    for x0, x1 in gaps:
        _arrow(ax, x0 + box_w / 2, stage_y,
               x1 - box_w / 2, stage_y, color=MUTED, lw=0.9)

    # ── Attribution probes (below each stage) ────────────────────────────────
    probe_y = stage_y - 0.62
    accs    = [0.808, 0.550, 0.592, 0.800]
    low     = [False, True,  True,  False]

    for (label, sub, sx, fc, ec), acc, isl in zip(stages, accs, low):
        _arrow(ax, sx, stage_y - box_h / 2, sx, probe_y + 0.09,
               color=MUTED, lw=0.7)
        _probe_box(ax, sx, probe_y, acc, is_low=isl)

    # "N-way attribution" label left of probes
    ax.text(1.32, probe_y, "N-way\nattribution\nprobe",
            ha="center", va="center", fontsize=5.8, color=MUTED,
            linespacing=1.35)
    _arrow(ax, 1.48, probe_y, 1.63, probe_y, color=MUTED, lw=0.6)

    # ── Candidate set ─────────────────────────────────────────────────────────
    cand_x, cand_y = 5.82, probe_y
    box = FancyBboxPatch(
        (cand_x - 0.48, cand_y - 0.26), 0.96, 0.52,
        boxstyle="round,pad=0.015",
        facecolor=GREY_LIGHT, edgecolor=GREY_DARK, linewidth=0.8, zorder=3,
    )
    ax.add_patch(box)
    for i, (label, dy) in enumerate([
            ("$p_1$", 0.09), ("$p_2$", 0.0), ("$p_3$", -0.09)]):
        fw = "bold" if i == 0 else "normal"
        col = GREEN_DARK if i == 0 else MUTED
        ax.text(cand_x, cand_y + dy, label + (" ← GT" if i == 0 else ""),
                ha="center", va="center", fontsize=6.0, color=col,
                fontweight=fw, zorder=4)

    ax.text(cand_x, cand_y + 0.40, "Candidates $\\mathcal{C}$",
            ha="center", va="center", fontsize=6.2, color=GREY_DARK,
            fontweight="bold", zorder=4)

    # arrow from candidate set to each probe (shared)
    _arrow(ax, cand_x - 0.48, cand_y, 4.90 + box_w / 2 + 0.02, probe_y,
           color=GRID, lw=0.6)

    # ── Dip-and-recovery annotation ───────────────────────────────────────────
    # small curve annotation above stages
    ax.annotate(
        "", xy=(4.90, stage_y + 0.36), xytext=(1.80, stage_y + 0.36),
        arrowprops=dict(arrowstyle="<->", color=BLUE_DARK, lw=0.8,
                        connectionstyle="arc3,rad=-0.30"), zorder=5,
    )
    ax.text(3.35, stage_y + 0.70, "dip-and-recovery trajectory",
            ha="center", va="center", fontsize=6.2, color=BLUE_DARK,
            fontstyle="italic", zorder=5)

    # ── Legend / title ────────────────────────────────────────────────────────
    # title omitted — appears in LaTeX \caption

    high_patch = mpatches.Patch(facecolor=BLUE_LIGHT, edgecolor=BLUE_DARK,
                                linewidth=0.8, label="High recoverability")
    low_patch  = mpatches.Patch(facecolor=ORANGE_LIGHT, edgecolor=ORANGE_DARK,
                                linewidth=0.8, label="Low recoverability")
    ax.legend(handles=[high_patch, low_patch], loc="lower right",
              fontsize=5.8, frameon=False, ncol=2,
              bbox_to_anchor=(1.0, 0.0))

    out_dir = ROOT / "paper" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = "pipeline_overview"
    for fmt in ("pdf", "svg", "png"):
        kwargs = {"facecolor": "white"}
        if fmt == "png":
            kwargs["dpi"] = 300
        fig.savefig(out_dir / f"{stem}.{fmt}", format=fmt, **kwargs,
                    bbox_inches="tight")
        print(f"→ {out_dir / f'{stem}.{fmt}'}")
    plt.close(fig)


if __name__ == "__main__":
    main()
