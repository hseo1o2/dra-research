---
type: experiment
id: EXP-014
date: 2026-08-03
status: completed
project: DRA-personalization-attribution
rq: RQ1 evaluator robustness
---

# EXP-014 GPT-5.4-nano matcher replication

## Pre-run lock

- Objective: Solar의 stage trajectory가 독립 evaluator에서도 재현되는지
  확인한다.
- Hypothesis: Planning→Search 하락과 Writing 회복의 방향이 유지된다.
- Success / failure criteria: seed 0의 60 reports × 4 stages가 완결되고,
  corrected Solar와 candidate set/order mismatch가 0이어야 한다.
- Dataset manifest SHA-256:
  `8110d1b3656fa5ba021f7b1bd053a92a11922c4efecd8d43d552e80cda4ad2a9`
- Code commit: `14b08031fac8a1e2396317bd09b57e70cba405cb`
  (dirty worktree)
- Model snapshot: `gpt-5.4-nano-2026-03-17`
- Seed / replicate IDs: generation seed 0
- Candidate construction: frozen per-GT
  `attribution_candidate_set_n3`, SHA-256 run-stage ordering
- Expected ceiling: 240 main matcher calls after one smoke test.

## Execution

- Started / completed: 2026-08-03 KST
- Run ID: seed-0 confirmatory 60 reports
- Calls: 1 smoke + 240 main matcher calls
- Retries / missing: terminal output에서 API/schema failure 없음;
  60/60 match files, 240/240 stage rows 저장
- Main prompt characters: 6,588,904
- Smoke prompt characters: 23,070
- Actual token usage: **Unverified**. 실행 당시 matcher가 provider usage를
  직렬화하지 않았다.
- Actual cost: **Unverified**. OpenAI billing dashboard 확인 필요.

## Observed results

- GPT Acc@1: Planning 0.750, Search 0.467, Compression 0.617,
  Writing 0.850, macro 0.671.
- Planning→Search: -0.283, task-cluster bootstrap 95% CI
  [-0.433, -0.133].
- Search→Compression: +0.150, [0.050, 0.250].
- Compression→Writing: +0.233, [0.083, 0.383].
- Corrected Solar–GPT candidate set mismatch 0, order mismatch 0.
- 전체 prediction agreement 0.783, Cohen's κ 0.763.
- Stage agreement / κ:
  - Planning: 0.850 / 0.837
  - Search: 0.717 / 0.680
  - Compression: 0.700 / 0.673
  - Writing: 0.867 / 0.855

## Anomalies

- Agreement script의 기존 default가 superseded `matches_sha256/`를
  가리켜 최초 network-free 분석이 comparability error로 중단됐다.
  corrected `matches_hardneg_v1/`를 명시해 통과했고 default도 수정했다.
- 실행 후 matcher에 provider input/output/total tokens와 response ID를
  이후 호출부터 저장하도록 보강했다. 이미 완료된 241 calls의 정확한
  usage는 소급 복구하지 않았다.

## Interpretation

- **Observed:** 독립 GPT evaluator에서도 Search dip과 Writing recovery가
  같은 방향으로 나타나며 각 핵심 stage 차이의 cluster-bootstrap CI가
  0을 제외한다.
- **Inferred:** 핵심 trajectory가 Solar 한 모델의 특이적 판단 패턴만으로
  생겼다는 설명은 약해진다.
- Agreement는 human validity, personalization utility, causal signal
  propagation을 증명하지 않는다.

## Decision / Next step

- 논문에 seed-0 cross-matcher robustness와 κ를 보고한다.
- cross-dataset replication은 별도 후속 범위로 유지한다.
- OpenAI dashboard에서 실제 청구액을 확인하면 cost ledger만 보완한다.

## Artifacts

- Main matches:
  `runs/confirmatory/gpt54nano_seed0_matches/`
- Smoke:
  `runs/confirmatory/gpt54nano_smoke/`
- GPT stage analysis:
  `runs/confirmatory/analysis_gpt54nano_seed0_hardneg_v1/`
- Solar–GPT agreement:
  `runs/confirmatory/analysis_matcher_agreement_hardneg_v1/`
- Provenance:
  `provenance/gpt54nano_seed0_match_plan.json`
