"""Compute task-cluster bootstrap CIs for ablation experiments.

Computes paired (ablation - baseline) Acc@1 differences with 95% CI
for: matches_candidate_profile_masked, matches_prompt_no_background.

Usage:
    python scripts/compute_ablation_cis.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BASELINE_DIR = ROOT / "runs" / "confirmatory" / "matches_hardneg_v1"
ABLATIONS = {
    "candidate_profile_masked": ROOT / "runs" / "confirmatory" / "matches_candidate_profile_masked",
    "prompt_no_background": ROOT / "runs" / "confirmatory" / "matches_prompt_no_background",
}

STAGES = ["plan", "search", "compress", "write"]
N_BOOT = 5000
BOOT_SEED = 20260806


def load_matches(directory: Path) -> dict[str, dict[str, bool]]:
    """Returns {run_id: {stage: correct}} from a matches directory."""
    result: dict[str, dict[str, bool]] = {}
    for fpath in sorted(directory.glob("pilot_*_match.json")):
        records = json.loads(fpath.read_text())
        run_id = fpath.stem.replace("_match", "")
        result[run_id] = {r["stage"]: bool(r["correct"]) for r in records}
    return result


def task_id(run_id: str) -> str:
    """Extract task cluster: pilot_task12_User2_seed0 -> pilot_task12"""
    parts = run_id.split("_")
    return "_".join(parts[:2])


def bootstrap_ci(
    paired_diffs: list[float],
    task_ids: list[str],
    n_boot: int = N_BOOT,
    seed: int = BOOT_SEED,
) -> tuple[float, float, float]:
    """Task-cluster bootstrap CI. Returns (point_est, ci_low, ci_high)."""
    rng = random.Random(seed)
    clusters = {}
    for tid, diff in zip(task_ids, paired_diffs):
        clusters.setdefault(tid, []).append(diff)
    cluster_keys = sorted(clusters)
    n_clusters = len(cluster_keys)
    point_est = sum(paired_diffs) / len(paired_diffs)

    boot_means = []
    for _ in range(n_boot):
        sample_keys = [rng.choice(cluster_keys) for _ in range(n_clusters)]
        sample = []
        for k in sample_keys:
            sample.extend(clusters[k])
        boot_means.append(sum(sample) / len(sample))

    boot_means.sort()
    lo = boot_means[int(0.025 * n_boot)]
    hi = boot_means[int(0.975 * n_boot)]
    return point_est, lo, hi


def analyze(name: str, ablation_dir: Path) -> None:
    baseline = load_matches(BASELINE_DIR)
    ablation = load_matches(ablation_dir)

    common = sorted(set(baseline) & set(ablation))
    if not common:
        print(f"[{name}] No common run_ids with baseline.")
        return

    print(f"\n{'='*60}")
    print(f"Ablation: {name}  (n_runs={len(common)})")
    print(f"{'Stage':<10} {'Baseline':>9} {'Ablation':>9} {'Delta':>8} {'CI_lo':>8} {'CI_hi':>8}")

    for stage in STAGES:
        pairs = [(ablation[r].get(stage, False), baseline[r].get(stage, False), task_id(r))
                 for r in common if stage in baseline[r] and stage in ablation[r]]
        if not pairs:
            continue
        diffs = [float(a) - float(b) for a, b, _ in pairs]
        tids = [t for _, _, t in pairs]
        base_acc = sum(b for _, b, _ in pairs) / len(pairs)
        abl_acc = sum(a for a, _, _ in pairs) / len(pairs)
        point, lo, hi = bootstrap_ci(diffs, tids)
        print(f"{stage:<10} {base_acc:>9.3f} {abl_acc:>9.3f} {point:>+8.3f} {lo:>+8.3f} {hi:>+8.3f}")


def main() -> None:
    for name, ablation_dir in ABLATIONS.items():
        if not ablation_dir.exists():
            print(f"[{name}] directory not found: {ablation_dir}")
            continue
        analyze(name, ablation_dir)


if __name__ == "__main__":
    main()
