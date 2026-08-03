---
type: experiment
id: EXP-009
date: 2026-08-03
status: completed
project: DRA-personalization-attribution
rq: RQ2
---

# EXP-009 Search-view controls

## Pre-run lock

- Objective: Search artifact의 recoverable persona cue가 query formulation과
  retrieved title/snippet 중 어디에 존재하는지 post-hoc view control로
  분리한다.
- Conditions:
  - query-only: 성공한 search call의 query와 topic ID만 matcher에 제공
  - snippet-only: query 문자열을 제외하고 상위 3개 title/snippet만 제공
- Hypothesis: query-only와 snippet-only의 Acc@1이 다르면 Search
  bottleneck의 주된 cue carrier를 국소화할 수 있다.
- Success / failure criteria: 두 condition 모두 120/120 결과, 동일
  run-stage candidate order, parse failure 0, full Search와 paired 비교.
- Dataset manifest SHA-256:
  `8110d1b3656fa5ba021f7b1bd053a92a11922c4efecd8d43d552e80cda4ad2a9`
- Code commit: `14b08031fac8a1e2396317bd09b57e70cba405cb`
  (dirty worktree; control code는 미커밋)
- Model snapshot: Upstage API model ID `solar-pro`, temperature 0,
  structured tool output
- Seed / replicate IDs: generation seed 0·1, 120 reports
- Candidate construction: frozen N=3 hard-negative sets; SHA-256
  run-stage shuffle
- Dry estimate:
  - query-only: 120 calls, 2,773,625 prompt characters
  - snippet-only: 120 calls, 3,051,854 prompt characters
  - total: 240 calls, 5,825,479 prompt characters
- Expected cost ceiling: 1,000원 including VAT. Conservative ceiling assumes
  at most 2 characters/input token and 500 output tokens/call; official list
  price checked 2026-08-03 is input $0.15/M and output $0.60/M tokens.
- Output directories:
  - `runs/confirmatory/search_view_queries_matches/`
  - `runs/confirmatory/search_view_snippets_matches/`

## Execution

- Started: 2026-08-03
- Completed: 2026-08-03
- Run ID: Search query-only/snippet-only, PDR seed 0·1
- Retries / missing: 0 / 0
- Actual token usage: Unverified (matcher currently records prompt characters)
- Serper successful queries: 0
- Actual cost: billing dashboard 미확인; list-price character estimate로
  1,000원 ceiling 이내 (Unverified)

## Observed results

- Full query+snippet Search: 0.542 (seed 0: 0.567, seed 1: 0.517).
- Query-only: 0.608 (0.633/0.583); full 대비 +0.067,
  task-cluster bootstrap CI `[0.017, 0.117]`.
- Snippet-only: 0.525 (0.567/0.483); full 대비 -0.017,
  CI `[-0.100, 0.083]`.
- Query-only minus snippet-only: +0.083, CI `[0.000, 0.167]`.
- Query-only는 full에서 틀린 10개를 맞추고, 반대로 full이 맞은 2개를
  틀렸다.
- full 3,500-character serialization에서 629개 성공 query 중 626개가
  노출되었고, 120 report 중 117개는 모든 query가 노출되었다.

## Anomalies

- single-stage summary가 기존 `len(results)/4`로 denominator를 계산해
  `N=30`으로 표기되는 버그를 발견했다. 결과 JSON은 정상이었고,
  denominator를 stage별 최대 count와 `n_by_stage`로 수정해 `N=120`으로
  재생성했다.
- 36/120 full Search artifact가 3,500-character cap에 도달했으나,
  누락된 query header는 전체 629개 중 3개뿐이었다.

## Interpretation

- query formulation만으로도 persona recoverability가 상당하며, query와
  retrieved snippet을 함께 제시할 때 matcher recoverability가 낮아진다.
- 이는 “planner가 persona signal을 query로 거의 압축해 버린다”는 기존
  단순 해석을 반박한다. 더 정확한 해석은 query formulation에서 일부
  loss가 발생하고, retrieved-result mixture가 추가 dilution을 만든다는
  것이다.
- snippet content의 causal harm 또는 generation 내부 signal loss를
  증명하지는 않는다. 관측된 효과는 fixed matcher가 보는 post-hoc
  artifact view에 대한 recoverability 차이다.

## Decision / Next step

- 다음으로 seed-1 identifier masking을 실행한다.
- 이 실험은 generation intervention이 아니므로 causal mechanism으로
  해석하지 않는다.

## Artifacts

- Code: `scripts/llm_matcher.py`
- Query-only output: `runs/confirmatory/search_view_queries_matches/`
- Snippet-only output: `runs/confirmatory/search_view_snippets_matches/`
- Analysis:
  `runs/confirmatory/analysis_search_views/search_view_summary.json`
