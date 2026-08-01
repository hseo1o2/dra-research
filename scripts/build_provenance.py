"""Build network-free checksums and an inventory for local experiment outputs.

This does not upload or copy data. It records enough metadata to detect missing
or modified artifacts after a backup or transfer.

Usage:
    python scripts/build_provenance.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT / "provenance"
RUN_DIRS = (ROOT / "runs" / "pilot", ROOT / "runs" / "confirmatory")
TRACKED_INPUTS = (
    ROOT / "manifest.json",
    ROOT / "RUNBOOK.md",
    ROOT / "scripts",
    ROOT / "paper",
    ROOT / "provenance" / "README.md",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_files(paths: Iterable[Path]) -> list[Path]:
    files: set[Path] = set()
    for path in paths:
        if path.is_file():
            files.add(path)
        elif path.is_dir():
            files.update(
                child
                for child in path.rglob("*")
                if child.is_file()
                and child.suffix != ".lock"
                and "__pycache__" not in child.parts
            )
    return sorted(files)


def _git_value(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def _run_inventory() -> dict[str, Any]:
    inventory: dict[str, Any] = {}
    for run_dir in RUN_DIRS:
        if not run_dir.exists():
            continue
        artifacts = sorted(run_dir.glob("*_artifacts.json"))
        summaries = sorted(run_dir.glob("*_summary.json"))
        matches = sorted((run_dir / "matches").glob("*_match.json"))
        seeds = Counter()
        for artifact in artifacts:
            for seed in (0, 1):
                if artifact.name.endswith(f"_seed{seed}_artifacts.json"):
                    seeds[str(seed)] += 1
        inventory[str(run_dir.relative_to(ROOT))] = {
            "artifacts": len(artifacts),
            "per_run_summaries": len(
                [
                    path
                    for path in summaries
                    if not path.name.startswith("batch_")
                ]
            ),
            "match_files": len(matches),
            "artifacts_by_seed": dict(sorted(seeds.items())),
        }
    return inventory


def build(output_dir: Path = DEFAULT_OUTPUT_DIR) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = _iter_files((*TRACKED_INPUTS, *RUN_DIRS))

    checksum_path = output_dir / "experiment_files.sha256"
    checksum_lines = [
        f"{_sha256(path)}  {path.relative_to(ROOT)}"
        for path in files
    ]
    checksum_path.write_text(
        "\n".join(checksum_lines) + ("\n" if checksum_lines else ""),
        encoding="utf-8",
    )

    status = _git_value("status", "--porcelain")
    inventory = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_head": _git_value("rev-parse", "HEAD"),
        "repository_dirty": bool(status),
        "manifest_sha256": _sha256(ROOT / "manifest.json"),
        "checksummed_files": len(files),
        "checksummed_bytes": sum(path.stat().st_size for path in files),
        "runs": _run_inventory(),
        "notes": [
            "Secrets and .env files are excluded.",
            "Public source datasets are represented by hashes in manifest.json.",
            "This inventory verifies a backup but is not itself an off-device backup.",
        ],
    }
    inventory_path = output_dir / "run_inventory.json"
    inventory_path.write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return checksum_path, inventory_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    checksum_path, inventory_path = build(args.output_dir)
    print(f"Checksums → {checksum_path}")
    print(f"Inventory → {inventory_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
