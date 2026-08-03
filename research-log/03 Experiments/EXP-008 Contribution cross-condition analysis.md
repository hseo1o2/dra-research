---
type: experiment
id: EXP-008
date: 2026-08-03
status: completed
project: DRA-personalization-attribution
rq: RQ1/RQ2
---

# EXP-008 Contribution cross-condition analysis

## Pre-run lock

- Objective: final two-seed 결과를 baseline, masking, quality filter,
  seed variation, report-level transition과 교차 비교해 논문 contribution
  후보를 검증한다.
- Hypothesis: aggregate dip-and-recovery가 동일 report의
  correct→wrong→correct transition으로도 관측되고, Search와 Writing의
  Solar–BM25 gap이 다를 것이다.
- Success / failure criteria: source artifact와 denominator가 일치하고,
  모든 paired comparison을 run-stage grain에서 재계산하며, taskid
  cluster bootstrap interval을 보고한다.
- Dataset manifest SHA-256:
  `8110d1b3656fa5ba021f7b1bd053a92a11922c4efecd8d43d552e80cda4ad2a9`
- Code commit: `14b08031fac8a1e2396317bd09b57e70cba405cb`
  (dirty worktree; analysis code는 미커밋)
- Model snapshot: existing Solar Pro (`solar-pro`) match artifacts만 사용
- Seed / replicate IDs: PDR seed 0·1; baseline은 seed 0·1, masking은 seed 0
- Candidate construction: frozen N=3 hard-negative candidate sets
- Expected query/token/cost ceiling: 외부 API 0회

## Execution

- Started: 2026-08-03
- Completed: 2026-08-03
- Run ID: offline cross-condition analysis
- Retries / missing: 없음
- Actual token usage: 0
- Serper successful queries: 0
- Actual cost: 0원

## Observed results

- Primary trajectory: Planning 0.733, Search 0.542, Compression 0.608,
  Writing 0.708, 120 reports.
- Planning→Search: correct→wrong 27, wrong→correct 4.
- Search→Compression: correct→wrong 9, wrong→correct 17.
- Compression→Writing: correct→wrong 6, wrong→correct 18.
- Planning에서 맞고 Search에서 틀린 27개 중 21개(77.8%)가 Writing에서
  다시 맞음.
- Solar–BM25 seed-0 gap: Planning +0.167, Search +0.050,
  Compression +0.117, Writing +0.300.
- Search gap CI `[-0.067, 0.167]`; Writing gap CI `[0.167, 0.450]`.
- 최초 identifier masking의 seed-0 stage effect 절댓값은 최대
  0.033이었으나, 아래 corrected two-seed extension으로 대체됨.
- Writing seed-1-minus-seed-0 차이는 -0.117,
  task-bootstrap CI `[-0.233, -0.033]`.

### Post-decision extension: two-seed non-LLM baselines

- Random baseline에서도 Python process마다 달라지는 `hash()` 사용을
  발견해 SHA-256 첫 64비트 기반 seed로 수정하고 두 seed를 재생성했다.
- 통합 Solar–BM25 gap: Planning +0.150 `[0.075, 0.225]`,
  Search +0.100 `[0.008, 0.192]`, Compression +0.108
  `[0.025, 0.192]`, Writing +0.217 `[0.100, 0.333]`.
- Search gap이 가장 작고 Writing gap이 가장 큰 순서는 두 개별 seed에서
  모두 유지되지만, 크기는 Search 0.050/0.150, Writing 0.300/0.133으로
  seed에 따라 달라진다.
- 두-seed baseline Acc@1:
  BM25 0.583/0.442/0.500/0.492, Embedding
  0.467/0.358/0.367/0.483, Random 0.242/0.333/0.350/0.383.
- 외부 API 호출 및 현금 비용: 0.

### Post-decision extension: Search views and corrected masking

- Search query-only 0.608은 full 0.542보다 +0.067
  `[0.017, 0.117]`; snippet-only 0.525는 full과 구분되지 않는다.
- 기존 masker의 v2 `sources` 누락을 수정하고 seed 0·1 전체를
  재실행했다. Corrected masking effect는
  -0.008/+0.008/0.000/+0.017이며 모든 CI가 0을 포함한다.
- 위 결과가 앞선 seed-0 masking 수치를 대체한다.

## Anomalies

- Planning aggregate accuracy는 두 seed가 같지만 paired correctness는
  양방향으로 각각 3개씩 바뀐다.
- recovery shape은 두 seed에 존재하지만 Writing endpoint는 seed에
  민감하다.

## Interpretation

- aggregate curve보다 report-level loss-and-recovery transition이 더
  강한 empirical contribution이다.
- Search에서 Solar와 BM25가 근접하고 Writing에서 gap이 커지는 현상은
  recoverable cue가 lexical overlap에서 contextual/distributed cue로
  바뀐다는 해석과 일치한다.
- 이는 internal causal mechanism 또는 utility 개선의 증거는 아니다.

## Decision / Next step

- [[DEC-005 Contribution validation experiment order]]에 따라 seed-1
  baseline, Search-view control, seed-1 masking 순으로 검증한다.

## Artifacts

- Config: `manifest.json`
- Ledger: `runs/confirmatory/analysis_sha256/`
- Output: `paper/analysis/contribution_insights.json`
- Notebook: `paper/analysis/contribution_insights.ipynb`
- Synthesis: `paper/analysis/contribution_insights.md`
- Baselines: `runs/confirmatory/baselines_sha256_seed0/`,
  `runs/confirmatory/baselines_sha256_seed1/`
