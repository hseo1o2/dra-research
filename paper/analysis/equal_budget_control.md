# Equal character-budget Solar rematch (seed 0)

Date: 2026-08-05  
Status: completed  
Cash: Solar only (ignored)

## Protocol
- Population: all **60** confirmatory seed-0 reports
- Matcher: Solar Pro, same hard-neg candidate sets/orders as primary
- Intervention: truncate **every** stage artifact to **3,500** characters
  (`--equal-char-budget 3500`)
- Default caps for comparison: plan 4k / search 3.5k / compress 6k / write 8k
- Artifacts: `runs/confirmatory/matches_equal_budget_3500_seed0/`
- Analysis: `runs/confirmatory/analysis_equal_budget_3500_seed0/summary.json`
- Scripts: `scripts/llm_matcher.py --equal-char-budget 3500`,
  `scripts/analyze_equal_budget.py`

## Paired results (n=60 seed0)

| Stage | Default Acc | Equal-budget Acc | Δ (eq−def) | 95% CI |
|---|---:|---:|---:|---|
| Planning | 0.800 | 0.800 | 0.000 | [0.000, 0.000] |
| Search | 0.533 | 0.517 | −0.017 | [−0.050, 0.000] |
| Compression | 0.567 | 0.600 | +0.033 | [−0.033, +0.100] |
| Writing | 0.817 | 0.800 | −0.017 | [−0.067, +0.033] |

- Dip-and-recovery **preserved**: Search < Plan and Write > Search under equal budget.
- Absolute seed-0 default levels differ slightly from the full 120-report freeze
  (0.808/0.550/0.592/0.800) because this table is seed-0 only.

## Interpretation
Equalizing matcher input length does **not** create or remove the Search dip.
The Search–Writing gap is therefore unlikely to be a pure character-budget
artifact under this protocol (consistent with BM25 / queries-only controls).

## Claim language
> On seed 0 (n=60), re-matching with a uniform 3,500-character budget leaves
> stage Acc@1 within a few points of the default protocol and preserves
> dip-and-recovery.
