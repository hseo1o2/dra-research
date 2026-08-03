---
type: experiment
id: EXP-012
date: 2026-08-03
status: completed
project: DRA-personalization-attribution
rq: RQ1
---

# EXP-012 Corrected per-GT Solar matching

## Pre-run lock

- Objective: frozen per-GT hard-negative candidate protocol로 full-condition
  Solar stage attribution을 두 seed에서 재생성한다.
- Hypothesis: Planning→Search 하락과 이후 recovery가 corrected candidate
  protocol에서도 관측된다.
- Success / failure criteria: 120/120 reports, 480/480 stage decisions,
  candidate protocol audit 120/120 pass.
- Dataset manifest SHA-256:
  `8110d1b3656fa5ba021f7b1bd053a92a11922c4efecd8d43d552e80cda4ad2a9`
- Code commit: `14b08031fac8a1e2396317bd09b57e70cba405cb`
  (dirty worktree)
- Model snapshot: `solar-pro`
- Seed / replicate IDs: generation seeds 0 and 1, 각 60 reports
- Candidate construction: GT persona + 동일 domain actionable-Jaccard 상위
  hard negative 2명, `attribution_candidate_set_n3`
- Expected query/token/cost ceiling: 480 matcher calls. Prompt-character
  사전 추정 13,172,117; 실제 token과 청구액은 artifact에 기록되지 않음.

## Execution

- Started: 2026-08-03
- Completed: 2026-08-03
- Run ID: PDR confirmatory full, seeds 0 and 1
- Retries / missing: 최종 missing 0; retry별 세부 횟수는 Unverified
- Actual token usage: Unverified
- Serper successful queries: 해당 없음(기존 artifact의 matcher-only 실행)
- Actual cost: Unverified; Upstage billing 확인 필요

## Observed results

- Executed: Solar matcher 120 reports × 4 stages = 480 decisions.
- Observed: candidate protocol audit 120/120 pass, mismatch 0.
- Observed Acc@1: Planning 0.8083 (97/120), Search 0.5500 (66/120),
  Compression 0.5917 (71/120), Writing 0.8000 (96/120), macro 0.6875.
- Observed paired changes:
  - Planning→Search: -0.2583, task-cluster bootstrap 95% CI
    [-0.3333, -0.1750], 32 losses / 1 gain.
  - Search→Compression: +0.0417, [-0.0250, 0.1083],
    8 losses / 13 gains.
  - Compression→Writing: +0.2083, [0.1417, 0.2833],
    6 losses / 31 gains.
- Observed: Planning-correct/Search-wrong 32건 중 24건(75.0%)이
  Writing에서 회복.
- Observed: all four stages correct 55/120; zero stages correct 11/120.

## Anomalies

- 실제 matcher token usage와 청구액이 output artifact에 저장되지 않는다.
- 기존 identifier-masked와 Search-view 결과는 task-level candidate
  protocol이므로 이 실험의 corrected primary와 비교할 수 없다.

## Interpretation

- Inferred: corrected protocol에서도 dip-and-recovery가 유지되며,
  통계적으로 명확한 변화는 Planning→Search 하락과
  Compression→Writing 회복이다.
- Inferred: Compression의 작은 상승은 interval이 0을 포함하므로
  독립적인 recovery 단계로 강하게 주장하지 않는다.
- Inferred: corrected baseline 비교에서 Solar의 BM25 대비 우위는
  Planning과 Writing에 집중되고 Search/Compression에서는 명확하지 않다.

## Decision / Next step

- [[DEC-007 Correct per-GT hard-negative candidate protocol]]의 primary
  rerun 요건은 충족했다.
- 논문 primary 표·trajectory·transition·quality sensitivity를 corrected
  결과로 교체한다.
- Identifier-masked와 Search-view는 별도 승인 후 corrected protocol로
  재실행하기 전까지 논문 수치 주장에서 제외한다.

## Artifacts

- Config: `manifest.json`
- Ledger: matcher token/cost ledger 없음
- Output:
  - `runs/confirmatory/matches_hardneg_v1/`
  - `runs/confirmatory/analysis_hardneg_v1/`
  - `paper/figures/stage_attribution_trajectory.pdf`
- Key SHA-256:
  - match summary:
    `6dad2f17e6aafd38d1f55cb2c370d933de0f526c76d7dedca885727c4bc09934`
  - candidate audit:
    `430555ca4a75bc442b2a2d7abec0b2f3f856d8444d97f85373e5b9c86a0786b6`
  - analysis summary:
    `8243ad96da0c072c6948ca5508f0a283f3c284deb259d24ced0137445e12d32d`

