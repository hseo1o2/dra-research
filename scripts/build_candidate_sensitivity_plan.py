"""Freeze network-free N=2/N=3/N=5 PDR attribution candidate sets.

N=2 and N=5 are deterministic prefixes of the same same-domain,
actionable-token Jaccard ranking used by the frozen N=3 manifest. The script
refuses to write a plan unless every recomputed N=3 set exactly matches the
manifest, preventing a silent candidate-protocol fork.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_manifest import (
    PDR_PERSONAS,
    PDR_QUERIES,
    actionable_tokens,
    jaccard,
    load_jsonl,
)

DEFAULT_OUTPUT = ROOT / "provenance" / "candidate_sensitivity_plan.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _eligible_tasks(
    personas: list[dict[str, Any]],
    queries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    persona_tokens = {
        row["userid"]: actionable_tokens(row) for row in personas
    }
    grouped: dict[int, dict[str, Any]] = {}
    for query in queries:
        if query.get("language") not in (None, "en"):
            continue
        taskid = int(query["taskid"])
        task = grouped.setdefault(taskid, {
            "taskid": taskid,
            "domain": query.get("domain"),
            "task": query.get("task"),
            "queries": [],
        })
        task["queries"].append(query)

    seen_pairs: set[tuple[int, str]] = set()
    eligible = []
    for taskid, task in sorted(grouped.items()):
        invalid = not task["domain"] or not task["task"]
        userids = []
        duplicate = False
        for query in task["queries"]:
            userid = query.get("userid")
            pair = (taskid, userid)
            if (
                not userid
                or not query.get("query")
                or pair in seen_pairs
            ):
                duplicate = True
                continue
            seen_pairs.add(pair)
            userids.append(userid)
        actionable = [
            userid for userid in userids if persona_tokens.get(userid)
        ]
        if not invalid and not duplicate and len(actionable) >= 3:
            eligible.append({
                "taskid": taskid,
                "domain": task["domain"],
                "userids": actionable,
            })
    return eligible


def build_plan(
    manifest: dict[str, Any],
    personas: list[dict[str, Any]],
    queries: list[dict[str, Any]],
) -> dict[str, Any]:
    tokens = {row["userid"]: actionable_tokens(row) for row in personas}
    eligible = _eligible_tasks(personas, queries)
    domain_users: dict[str, set[str]] = defaultdict(set)
    all_users: set[str] = set()
    for task in eligible:
        domain_users[task["domain"]].update(task["userids"])
        all_users.update(task["userids"])

    rows = []
    mismatches = []
    for task in manifest["pdr_bench"]["confirmatory"]:
        domain = task["domain"]
        for experiment in task["experiments"]:
            gt = experiment["gt_userid"]
            pool = set(domain_users[domain])
            pool.discard(gt)
            fallback = len(pool) < 4
            if fallback:
                pool = set(all_users)
                pool.discard(gt)
            ranked = [
                {
                    "userid": userid,
                    "jaccard": round(
                        jaccard(tokens[gt], tokens[userid]), 4
                    ),
                }
                for userid in sorted(pool)
            ]
            ranked.sort(key=lambda row: (-row["jaccard"], row["userid"]))
            if len(ranked) < 4:
                raise ValueError(
                    f"Fewer than four negatives for task={task['taskid']} "
                    f"gt={gt}"
                )
            candidate_sets = {
                "2": [gt, ranked[0]["userid"]],
                "3": [gt] + [row["userid"] for row in ranked[:2]],
                "5": [gt] + [row["userid"] for row in ranked[:4]],
            }
            frozen = experiment["attribution_candidate_set_n3"]
            if candidate_sets["3"] != frozen:
                mismatches.append({
                    "taskid": task["taskid"],
                    "gt_userid": gt,
                    "recomputed": candidate_sets["3"],
                    "frozen": frozen,
                })
            rows.append({
                "taskid": task["taskid"],
                "domain": domain,
                "gt_userid": gt,
                "candidate_sets": candidate_sets,
                "ranked_negatives_top4": ranked[:4],
                "fallback_to_all_domains": fallback,
            })
    if mismatches:
        sample = mismatches[:3]
        raise ValueError(
            f"N=3 recomputation disagrees with manifest for "
            f"{len(mismatches)} experiments: {sample}"
        )
    return {
        "schema_version": 1,
        "external_api_calls": 0,
        "purpose": "candidate-set-size sensitivity plan",
        "method": (
            "GT plus top-k same-domain hard negatives ranked by actionable-"
            "token Jaccard; score descending, userid ascending tie-break"
        ),
        "candidate_sizes": [2, 3, 5],
        "experiments": len(rows),
        "n3_manifest_exact_matches": len(rows),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "manifest.json"
    )
    parser.add_argument(
        "--personas", type=Path, default=PDR_PERSONAS
    )
    parser.add_argument("--queries", type=Path, default=PDR_QUERIES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = build_plan(
        json.loads(args.manifest.read_text(encoding="utf-8")),
        load_jsonl(args.personas),
        load_jsonl(args.queries),
    )
    result["input_sha256"] = {
        "personas": _sha256(args.personas),
        "queries": _sha256(args.queries),
        "manifest": _sha256(args.manifest),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(
        f"Candidate sensitivity plan -> {args.output} "
        f"({result['experiments']} experiments, API 0)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
