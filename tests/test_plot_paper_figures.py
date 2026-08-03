from __future__ import annotations

import csv

from scripts.plot_paper_figures import plot_stage_trajectory


def _write_csv(path, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_stage_trajectory_exports_all_formats(tmp_path):
    analysis_dir = tmp_path / "analysis"
    output_dir = tmp_path / "figures"
    analysis_dir.mkdir()
    stages = ("plan", "search", "compress", "write")
    values = (0.70, 0.55, 0.65, 0.80)
    _write_csv(
        analysis_dir / "stage_accuracy.csv",
        [
            {
                "seed": seed,
                "stage": stage,
                "correct": int(value * 60),
                "n": 60,
                "accuracy": value,
            }
            for seed in ("0", "all")
            for stage, value in zip(stages, values)
        ],
    )
    _write_csv(
        analysis_dir / "stage_accuracy_cluster_bootstrap.csv",
        [
            {
                "stage": stage,
                "accuracy": value,
                "ci95_low": value - 0.1,
                "ci95_high": value + 0.1,
                "bootstrap_unit": "taskid",
                "bootstrap_repetitions": 100,
                "bootstrap_seed": 7,
                "n_reports": 60,
                "n_tasks": 20,
            }
            for stage, value in zip(stages, values)
        ],
    )

    outputs = plot_stage_trajectory(analysis_dir, output_dir)

    assert {path.suffix for path in outputs} == {".pdf", ".svg", ".png"}
    assert all(path.exists() and path.stat().st_size > 0 for path in outputs)
