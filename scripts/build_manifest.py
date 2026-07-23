"""
Manifest freeze script for DRA Personalization experiment.
Run ONCE before any generation. Output is read-only after creation.

Sampling seed: 20260722

Version 1.1 (pre-generation freeze completion):
- ablation 5-group subset from confirmatory
- generation seed protocol
- lexical leakage thresholds
- LaMP hard-negative pool labels
- fallback_pool flag on hard negatives
- actionable/identity ambiguous policy
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import subprocess
from collections import defaultdict
from pathlib import Path

SEED = 20260722
MANIFEST_VERSION = "1.1"
CREATED = "2026-07-24"
ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"

PDR_PERSONAS = DATA / "pdr-bench/persona_data/personas_en.jsonl"
PDR_QUERIES = DATA / "pdr-bench/prompt_data/queries250_en.jsonl"
LAMP_ROOT = DATA / "lamp-qa/data"
OUT = ROOT / "manifest.json"

LAMP_CATEGORIES = [
    "Art_and_Entertainment",
    "Lifestyle_and_Personal_Development",
    "Society_and_Culture",
]

# Hard-negative / leakage constants (frozen before generation)
HN_JACCARD_THRESHOLD = 0.20
HN_TOP_K = 2
LAMP_HN_POOL_N = 500
LEAKAGE_CONTIGUOUS_TOKEN_MIN = 5
LEAKAGE_SENTENCE_JACCARD_MIN = 0.50
LEAKAGE_TOKENIZER_ID = "regex_alnum_v1"
LEAKAGE_TOKEN_PATTERN = r"[a-z0-9]+"

# Generation seeds (Notion: confirmatory 2 seeds; shuffled/GPT use seed 0 only)
GENERATION_SEEDS_PILOT = [0]
GENERATION_SEEDS_CONFIRMATORY = [0, 1]
GENERATION_SEEDS_SHUFFLED_ACTIONABLE = [0]
MATCHER_SEEDS_GPT = [0]

# ── Actionable vs Identity field keys ────────────────────────────────────────
# Identity: fields that name/locate the person but don't constrain content.
# Actionable: fields that drive what content to prioritize.
IDENTITY_LEAF_KEYS = {
    "Name",
    "Age",
    "Gender",
    "Permanent Residence",
    "Hometown",
    "Educational Background",
    "Occupation",
    "Family Members and Relationships",
    "Pets",
    "Parental Expectations",
    "Environmental Influence",
    "Living Environment",
    "Hometown Memories",
}

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "to", "for", "is", "are", "was", "were",
    "he", "she", "they", "his", "her", "their", "it", "this", "that", "with", "on",
    "at", "by", "from", "as", "has", "have", "had", "not", "but", "also", "been",
    "which", "who", "when", "where", "what", "how", "its", "be", "do", "does", "did",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_seed(namespace: str) -> int:
    """Derive a process-independent seed for a named sampling namespace."""
    namespace_hash = hashlib.sha256(namespace.encode("utf-8")).digest()
    return SEED ^ int.from_bytes(namespace_hash[:8], "big")


def try_git_commit() -> str | None:
    """Return HEAD commit SHA if a git commit exists; else None."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        # Unborn branch / invalid
        if not out or out == "HEAD":
            return None
        # Verify object exists
        subprocess.check_output(
            ["git", "cat-file", "-e", f"{out}^{{commit}}"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
        )
        return out
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def load_jsonl(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def tokenize_alnum(text: str) -> list[str]:
    """Frozen tokenizer: lowercase alphanumeric tokens (regex_alnum_v1)."""
    return re.findall(LEAKAGE_TOKEN_PATTERN, text.lower())


def _flatten_leaves(obj, skip_keys: set, tokens: list):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in skip_keys:
                continue
            _flatten_leaves(v, skip_keys, tokens)
    elif isinstance(obj, list):
        for item in obj:
            _flatten_leaves(item, skip_keys, tokens)
    elif isinstance(obj, str):
        tokens.extend(tokenize_alnum(obj))


def actionable_tokens(persona: dict) -> set[str]:
    """Extract actionable (non-identity) token set from a PDR-Bench persona."""
    tokens: list[str] = []
    _flatten_leaves(persona, IDENTITY_LEAF_KEYS, tokens)
    return {t for t in tokens if t not in STOPWORDS and len(t) > 2}


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def largest_remainder(total: int, weights: list[float]) -> list[int]:
    """Allocate `total` integer slots proportionally with largest-remainder.
    Tie-break: remainder desc, then index asc (= domain-name asc for sorted domain lists).
    """
    floats = [total * w for w in weights]
    floors = [int(f) for f in floats]
    remainders = [(floats[i] - floors[i], i) for i in range(len(floats))]
    remaining = total - sum(floors)
    for _, i in sorted(remainders, key=lambda x: (-x[0], x[1]))[:remaining]:
        floors[i] += 1
    return floors


def label_pool(jaccard_score: float) -> str:
    return "hard_negative" if jaccard_score >= HN_JACCARD_THRESHOLD else "nearest_fallback"


# ── PDR-Bench manifest ────────────────────────────────────────────────────────

def build_pdr_manifest(personas: list[dict], queries: list[dict]) -> dict:
    # 1. Index
    userid2persona = {p["userid"]: p for p in personas}
    userid2tokens = {p["userid"]: actionable_tokens(p) for p in personas}

    # Group queries by taskid (English-only; source files are *_en but enforce explicitly)
    task_map: dict[int, dict] = {}
    for q in queries:
        if q.get("language") not in (None, "en"):
            continue
        tid = q["taskid"]
        if tid not in task_map:
            task_map[tid] = {
                "taskid": tid,
                "domain": q["domain"],
                "userids": [],
                "query_by_userid": {},
                "query_id_by_userid": {},
                "task": q["task"],
            }
        task_map[tid]["userids"].append(q["userid"])
        task_map[tid]["query_by_userid"][q["userid"]] = q["query"]
        task_map[tid]["query_id_by_userid"][q["userid"]] = q["id"]

    # 2. Eligibility check
    # Criteria: non-empty taskid/userid/query/domain, no dup (taskid,userid), ≥1 actionable field
    seen_pairs: set[tuple] = set()
    eligible_tasks: list[dict] = []
    excluded: list[dict] = []

    for tid, tinfo in sorted(task_map.items()):
        reasons = []
        if (
            not tinfo["domain"]
            or not tinfo["task"]
            or any(
                not uid or not tinfo["query_by_userid"].get(uid)
                for uid in tinfo["userids"]
            )
        ):
            reasons.append("empty_field")
        dedup_userids = []
        for uid in tinfo["userids"]:
            pair = (tid, uid)
            if pair in seen_pairs:
                reasons.append(f"dup_{uid}")
            else:
                seen_pairs.add(pair)
                dedup_userids.append(uid)
        tinfo["userids"] = dedup_userids
        # Check each persona has actionable content
        actionable_uids = [uid for uid in dedup_userids if userid2tokens.get(uid)]
        if len(actionable_uids) < 3:
            reasons.append("insufficient_actionable_personas")
        if reasons:
            excluded.append({"taskid": tid, "reasons": reasons})
        else:
            tinfo["userids"] = actionable_uids
            eligible_tasks.append(tinfo)

    print(f"PDR eligible tasks: {len(eligible_tasks)} / {len(task_map)} (excluded: {len(excluded)})")

    # 3. Domain-stratified sampling: 5 dev + 20 confirmatory
    domain_tasks: dict[str, list[dict]] = defaultdict(list)
    for t in eligible_tasks:
        domain_tasks[t["domain"]].append(t)

    domains_sorted = sorted(domain_tasks.keys())
    domain_sizes = [len(domain_tasks[d]) for d in domains_sorted]
    total_eligible = sum(domain_sizes)
    domain_weights = [s / total_eligible for s in domain_sizes]

    # Dev: 5 tasks
    dev_quota = largest_remainder(5, domain_weights)
    dev_tasks: list[dict] = []
    pool_tasks: list[dict] = []

    for domain, quota in zip(domains_sorted, dev_quota):
        tasks_shuffled = sorted(domain_tasks[domain], key=lambda t: t["taskid"])
        rng2 = random.Random(SEED)
        rng2.shuffle(tasks_shuffled)
        dev_tasks.extend(tasks_shuffled[:quota])
        pool_tasks.extend(tasks_shuffled[quota:])

    # Confirmatory: 20 tasks from pool, domain-stratified
    pool_by_domain: dict[str, list[dict]] = defaultdict(list)
    for t in pool_tasks:
        pool_by_domain[t["domain"]].append(t)

    pool_domain_sizes = [len(pool_by_domain.get(d, [])) for d in domains_sorted]
    pool_total = sum(pool_domain_sizes)
    pool_weights = [s / pool_total if pool_total else 0 for s in pool_domain_sizes]
    conf_quota = largest_remainder(20, pool_weights)

    conf_tasks: list[dict] = []
    for domain, quota in zip(domains_sorted, conf_quota):
        pool = sorted(pool_by_domain.get(domain, []), key=lambda t: t["taskid"])
        rng3 = random.Random(SEED)
        rng3.shuffle(pool)
        conf_tasks.extend(pool[:quota])

    print(f"Dev tasks: {len(dev_tasks)}, Confirmatory tasks: {len(conf_tasks)}")

    # 4. Select 3 personas per task (seeded shuffle of task's assigned userids)
    def pick_3_personas(task: dict) -> list[str]:
        uids = sorted(task["userids"])
        rng_local = random.Random(SEED ^ task["taskid"])
        rng_local.shuffle(uids)
        return uids[:3]

    # 5. Hard negatives per (task, gt_persona): top-2 by Jaccard from same domain
    def get_hard_negatives(task: dict, gt_uid: str, all_tasks: list[dict]) -> list[dict]:
        same_domain_uids: set[str] = set()
        all_uids: set[str] = set()
        for t in all_tasks:
            all_uids.update(t["userids"])
            if t["domain"] == task["domain"]:
                same_domain_uids.update(t["userids"])
        same_domain_uids.discard(gt_uid)
        all_uids.discard(gt_uid)

        fallback_pool = False
        candidate_uids = same_domain_uids
        if len(candidate_uids) < HN_TOP_K:
            # Notion: expand to full pool only when same-domain candidates < 2
            candidate_uids = all_uids
            fallback_pool = True

        gt_tokens = userid2tokens[gt_uid]
        scored = []
        for uid in sorted(candidate_uids):
            score = jaccard(gt_tokens, userid2tokens[uid])
            scored.append({"userid": uid, "jaccard": round(score, 4)})
        scored.sort(key=lambda x: (-x["jaccard"], x["userid"]))
        top2 = scored[:HN_TOP_K]
        for item in top2:
            item["pool"] = label_pool(item["jaccard"])
            item["fallback_pool"] = fallback_pool
        return top2

    # Build task entries
    def build_task_entry(task: dict, split: str) -> dict:
        personas_3 = pick_3_personas(task)
        experiments = []
        for gt_uid in personas_3:
            hn = get_hard_negatives(task, gt_uid, eligible_tasks)
            experiments.append({
                "gt_userid": gt_uid,
                "source_query_id": task["query_id_by_userid"][gt_uid],
                "query": task["query_by_userid"][gt_uid],
                "hard_negatives": hn,
                "attribution_candidate_set_n3": [gt_uid] + [h["userid"] for h in hn],
            })
        return {
            "taskid": task["taskid"],
            "domain": task["domain"],
            "split": split,
            "task": task["task"],
            "personas_n3": personas_3,
            "experiments": experiments,
        }

    dev_entries = [build_task_entry(t, "dev") for t in sorted(dev_tasks, key=lambda x: x["taskid"])]
    conf_entries = [
        build_task_entry(t, "confirmatory") for t in sorted(conf_tasks, key=lambda x: x["taskid"])
    ]

    # 6. Ablation subset: domain-stratified 5 groups from confirmatory 20
    # Notion §5.4-1: sampling seed 20260722, domain-stratified largest-remainder
    ablation = select_ablation_subset(conf_entries)

    return {
        "dev": dev_entries,
        "confirmatory": conf_entries,
        "ablation_subset": ablation,
        "excluded": excluded,
        "domain_dev_quota": dict(zip(domains_sorted, dev_quota)),
        "domain_conf_quota": dict(zip(domains_sorted, conf_quota)),
    }


def select_ablation_subset(conf_entries: list[dict]) -> dict:
    """Freeze 5 confirmatory groups for generation-time shortcut ablation."""
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for t in conf_entries:
        by_domain[t["domain"]].append(t)

    domains_sorted = sorted(by_domain.keys())
    sizes = [len(by_domain[d]) for d in domains_sorted]
    total = sum(sizes)
    weights = [s / total for s in sizes]
    quota = largest_remainder(5, weights)

    selected: list[dict] = []
    domain_quota_actual: dict[str, int] = {}
    for domain, q in zip(domains_sorted, quota):
        pool = sorted(by_domain[domain], key=lambda t: t["taskid"])
        rng = random.Random(SEED)
        rng.shuffle(pool)
        picked = pool[:q]
        domain_quota_actual[domain] = q
        for t in picked:
            selected.append({
                "taskid": t["taskid"],
                "domain": t["domain"],
                "personas_n3": t["personas_n3"],
            })

    selected.sort(key=lambda x: x["taskid"])
    print(
        f"Ablation subset: {len(selected)} tasks "
        f"{[s['taskid'] for s in selected]} quota={domain_quota_actual}"
    )

    return {
        "n": 5,
        "method": "domain-stratified largest-remainder from confirmatory; seed=20260722",
        "source_split": "confirmatory",
        "domain_quota": domain_quota_actual,
        "taskids": [s["taskid"] for s in selected],
        "groups": selected,
        "generation_conditions": {
            "actionable_only": {
                "seeds": GENERATION_SEEDS_CONFIRMATORY,
                "reports": 5 * 3 * len(GENERATION_SEEDS_CONFIRMATORY),
            },
            "identity_only": {
                "seeds": GENERATION_SEEDS_CONFIRMATORY,
                "reports": 5 * 3 * len(GENERATION_SEEDS_CONFIRMATORY),
            },
            "shuffled_actionable": {
                "seeds": GENERATION_SEEDS_SHUFFLED_ACTIONABLE,
                "reports": 5 * 3 * len(GENERATION_SEEDS_SHUFFLED_ACTIONABLE),
            },
        },
        "generation_time_ablation_reports_total": 30 + 30 + 15,
    }


# ── LaMP-QA manifest ──────────────────────────────────────────────────────────

# LaMP HN token filter is intentionally narrower than STOPWORDS and has no len>2
# filter, matching the original freeze used for candidate selection.
LAMP_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "to", "for", "is", "are", "was", "were",
    "he", "she", "they", "his", "her", "their", "it", "this", "that",
}


def lamp_profile_tokens(profile_items: list) -> set[str]:
    tokens: set[str] = set()
    for pi in profile_items:
        tokens.update(tokenize_alnum(pi.get("text", "")))
    return tokens - LAMP_STOPWORDS


def build_lamp_manifest() -> dict:
    # 5 per category (3 cats × 5 = 15)
    cat_quota = largest_remainder(15, [1 / 3, 1 / 3, 1 / 3])
    print(f"LaMP-QA category quota: {dict(zip(LAMP_CATEGORIES, cat_quota))}")

    selected: list[dict] = []
    for cat, quota in zip(LAMP_CATEGORIES, cat_quota):
        path = LAMP_ROOT / cat / "train" / "train.json"
        with open(path) as f:
            items = json.load(f)

        # Eligibility
        eligible = [
            it for it in items
            if it.get("question") and it.get("profile") and len(it["profile"]) >= 1
        ]
        rng = random.Random(SEED)
        rng.shuffle(eligible)
        chosen = eligible[:quota]

        # Precompute token sets for chosen items + 500-item HN candidate pool
        chosen_ids = {it["id"] for it in chosen}
        hn_pool_rng = random.Random(stable_seed(f"lamp_qa_hn_pool:{cat}"))
        non_chosen = [it for it in eligible if it["id"] not in chosen_ids]
        hn_pool_rng.shuffle(non_chosen)
        hn_pool = non_chosen[:LAMP_HN_POOL_N]

        print(f"  {cat}: {len(eligible)} eligible, HN pool={len(hn_pool)}")
        hn_token_cache: dict[str, set[str]] = {
            it["id"]: lamp_profile_tokens(it["profile"]) for it in hn_pool
        }

        for item in chosen:
            gt_tokens = lamp_profile_tokens(item["profile"])
            hn_candidates = [
                {
                    "item_id": iid,
                    "jaccard": round(jaccard(gt_tokens, itokens), 4),
                }
                for iid, itokens in hn_token_cache.items()
            ]
            hn_candidates.sort(key=lambda x: (-x["jaccard"], x["item_id"]))
            hard_negs = hn_candidates[:HN_TOP_K]
            for h in hard_negs:
                h["pool"] = label_pool(h["jaccard"])
                # LaMP HN pool is always the fixed 500-item category pool (not expanded)
                h["fallback_pool"] = False

            selected.append({
                "category": cat,
                "item_id": item["id"],
                "question": item["question"],
                "gt_profile_len": len(item["profile"]),
                "hard_negatives": hard_negs,
                "attribution_candidate_set_n3": [item["id"]] + [h["item_id"] for h in hard_negs],
            })

    return {"queries": selected, "total": len(selected)}


# ── Main ──────────────────────────────────────────────────────────────────────

def build_generation_protocol() -> dict:
    return {
        "sampling_seed": SEED,
        "pilot": {
            "split": "dev",
            "groups_n": 5,
            "personas_per_group": 3,
            "seeds": GENERATION_SEEDS_PILOT,
            "reports_per_model": 5 * 3 * len(GENERATION_SEEDS_PILOT),
            "note": "engineering gate only; not used for RQ0",
        },
        "confirmatory_pdr": {
            "split": "confirmatory",
            "groups_n": 20,
            "personas_per_group": 3,
            "seeds": GENERATION_SEEDS_CONFIRMATORY,
            "reports": 20 * 3 * len(GENERATION_SEEDS_CONFIRMATORY),
        },
        "replication_lamp": {
            "groups_n": 15,
            "personas_per_group": 3,
            "seeds": GENERATION_SEEDS_CONFIRMATORY,
            "reports": 15 * 3 * len(GENERATION_SEEDS_CONFIRMATORY),
        },
        "shuffled_actionable_seeds": GENERATION_SEEDS_SHUFFLED_ACTIONABLE,
        "gpt_matcher_seeds": MATCHER_SEEDS_GPT,
        "report_budget": {
            "pdr_full_reference": 120,
            "lamp_full_reference": 90,
            "reference_configuration_total": 210,
            "pdr_generation_time_ablation": 75,
            "confirmatory_with_ablation_total": 285,
            "backbone_gate_pilot_two_models": 30,
            "flash_main_path_with_pilot": 315,
        },
        "seed_semantics": (
            "Integer seeds [0, 1] are generation/report seeds distinct from sampling_seed. "
            "Confirmatory full and actionable/identity ablation use both seeds; "
            "pilot, shuffled-actionable, and GPT-5.4 nano matcher use seed 0 only."
        ),
    }


def build_lexical_leakage() -> dict:
    return {
        "tokenizer_id": LEAKAGE_TOKENIZER_ID,
        "token_pattern": LEAKAGE_TOKEN_PATTERN,
        "normalization": "lowercase; extract alphanumeric tokens via regex_alnum_v1",
        "contiguous_token_match_min": LEAKAGE_CONTIGUOUS_TOKEN_MIN,
        "sentence_token_jaccard_min": LEAKAGE_SENTENCE_JACCARD_MIN,
        "action": (
            "Mask copied-phrase spans in artifacts before matcher input: "
            "any contiguous ≥5-token match between persona/profile and artifact, "
            "or any sentence with token-Jaccard ≥0.50 against a persona/profile sentence."
        ),
        "stopwords_for_jaccard": "none for leakage spans (raw alnum tokens); "
        "actionable HN Jaccard uses STOPWORDS + len>2 filter separately",
        "frozen_before_generation": True,
    }


def build_actionable_identity_split() -> dict:
    return {
        "identity_leaf_keys": sorted(IDENTITY_LEAF_KEYS),
        "actionable_definition": (
            "목표·선호·예산·위험·시간·경험·출력 제약처럼 content 선택을 바꿀 수 있는 속성 "
            "(all non-identity leaf fields)"
        ),
        "ambiguous_policy": (
            "If a leaf/sentence mixes identity and actionable content, mask only identity spans "
            "and keep the remainder as actionable. If classification is impossible, exclude the "
            "span from ablation profiles and record it under ambiguous_spans (not used as "
            "actionable or identity evidence)."
        ),
        "ambiguous_recording": {
            "field": "ambiguous_spans",
            "scope": "per persona/profile at ablation profile construction time",
            "required_before_ablation_generation": True,
        },
        "version": "identity_leaf_keys_v1",
    }


def main():
    print("=== Computing file hashes ===")
    hashes = {
        "pdr_personas_en": sha256(PDR_PERSONAS),
        "pdr_queries250_en": sha256(PDR_QUERIES),
        "build_manifest_py": sha256(Path(__file__)),
    }
    for cat in LAMP_CATEGORIES:
        p = LAMP_ROOT / cat / "train" / "train.json"
        hashes[f"lamp_{cat.lower()}_train"] = sha256(p)
    for k, v in hashes.items():
        print(f"  {k}: {v[:16]}…")

    code_commit = try_git_commit()
    print(f"  git commit: {code_commit or '(none — unborn/no commits)'}")

    print("\n=== Building PDR-Bench manifest ===")
    personas = load_jsonl(PDR_PERSONAS)
    queries = load_jsonl(PDR_QUERIES)
    pdr = build_pdr_manifest(personas, queries)

    print("\n=== Building LaMP-QA manifest ===")
    lamp = build_lamp_manifest()

    manifest = {
        "version": MANIFEST_VERSION,
        "created": CREATED,
        "updated": CREATED,
        "frozen": True,
        "seed": SEED,
        "code_commit": code_commit,
        "description": (
            "Frozen experiment manifest for DRA Personalization attribution study "
            "(REALM@EMNLP 2026). Pre-generation freeze: sampling, candidates, ablation "
            "subset, generation seeds, leakage thresholds."
        ),
        "file_hashes": hashes,
        "eligibility_rules": {
            "pdr_bench": [
                "language=en (explicit filter; source files are *_en)",
                "non-empty taskid, userid, query, domain, task",
                "no duplicate (taskid, userid) pairs",
                "persona has ≥1 actionable token after identity masking",
                "task has ≥3 eligible personas",
            ],
            "lamp_qa": [
                "non-empty question",
                "profile length ≥1",
            ],
        },
        "sampling": {
            "pdr_bench": {
                "method": "domain-stratified largest-remainder",
                "dev_n": 5,
                "confirmatory_n": 20,
                "ablation_subset_n": 5,
                "ablation_subset_source": "confirmatory",
                "personas_per_task_n": 3,
                "persona_selection": (
                    "seeded-shuffle of task-assigned userids, take first 3 (seed XOR taskid)"
                ),
                "hard_negative_rule": (
                    f"top-{HN_TOP_K} same-domain personas by actionable-token Jaccard; "
                    f"≥{HN_JACCARD_THRESHOLD} = hard_negative else nearest_fallback; "
                    "tie-break by userid ascending; if same-domain candidates < 2, "
                    "expand to all eligible personas and set fallback_pool=true"
                ),
            },
            "lamp_qa": {
                "method": "category-stratified largest-remainder",
                "total_n": 15,
                "per_category_n": 5,
                "hard_negative_candidate_pool_n": LAMP_HN_POOL_N,
                "hard_negative_pool_seed": (
                    "SEED XOR first 64 bits of SHA-256('lamp_qa_hn_pool:' + category)"
                ),
                "hard_negative_rule": (
                    f"exclude selected GT items; seeded-shuffle eligible same-category items; "
                    f"take first {LAMP_HN_POOL_N} as candidate pool; select top-{HN_TOP_K} by "
                    f"profile-token Jaccard; ≥{HN_JACCARD_THRESHOLD} = hard_negative else "
                    "nearest_fallback; tie-break by item_id ascending"
                ),
            },
        },
        "generation": build_generation_protocol(),
        "lexical_leakage": build_lexical_leakage(),
        "actionable_identity_split": build_actionable_identity_split(),
        "sigir_pdr_sanity": {
            "status": "pending_data",
            "n": 5,
            "role": "descriptive human-authored sanity check only; not inferential main test",
            "note": (
                "Freeze task IDs when SIGIR 2026 PDR input/output/profile files are available. "
                "Do not start confirmatory generation blocked on this section."
            ),
        },
        "pdr_bench": pdr,
        "lamp_qa": lamp,
    }

    # Allow overwrite of previously chmod'd read-only freeze during intentional rebuild
    if OUT.exists():
        OUT.chmod(0o644)
    with open(OUT, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    OUT.chmod(0o444)

    print(f"\n✓ Manifest written to {OUT} (mode 444)")
    print(f"  version: {MANIFEST_VERSION}")
    print(f"  PDR dev: {len(pdr['dev'])} tasks")
    print(f"  PDR confirmatory: {len(pdr['confirmatory'])} tasks")
    print(f"  PDR ablation subset: {pdr['ablation_subset']['taskids']}")
    print(f"  LaMP-QA queries: {lamp['total']}")
    print(f"  SHA-256: {sha256(OUT)}")


if __name__ == "__main__":
    main()
