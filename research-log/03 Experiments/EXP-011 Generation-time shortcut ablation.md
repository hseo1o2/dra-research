---
type: experiment
id: EXP-011
date: 2026-08-03
status: blocked
project: DRA-personalization-attribution
rq: RQ2
---

# EXP-011 Generation-time shortcut ablation

## Pre-run lock

- Objective: persona의 actionable non-identity leaves와 frozen identity
  leaves를 각각 단독 conditioning했을 때 stage-wise recoverability가
  어떻게 달라지는지 측정한다.
- Conditions:
  - actionable-only: frozen identity leaf keys 제거
  - identity-only: frozen identity leaf keys만 유지
- Stage gate: [[DEC-006 Stage generation ablations by seed]]에 따라 seed 0
  30 reports를 먼저 실행하고 검증 후 seed 1을 연다.
- Seed-0 population: 5 tasks × 3 personas × 2 conditions = 30 reports.
- Final population: 60 reports across seeds 0 and 1.
- Success / failure criteria:
  - condition별 seed 0 schema-valid 15/15
  - severe completeness issue condition별 2 이하
  - candidate set/order가 paired full과 60/60 stage pairs에서 일치
  - generation token/query ledger와 matcher 4-stage denominator 완전
- Dataset manifest SHA-256:
  `8110d1b3656fa5ba021f7b1bd053a92a11922c4efecd8d43d552e80cda4ad2a9`
- Code commit: `14b08031fac8a1e2396317bd09b57e70cba405cb`
  (dirty worktree; ablation runner는 미커밋)
- Model snapshot: `google_genai:gemini-3.6-flash`, generation seed 0 gate
- Candidate construction: frozen N=3 candidates; condition prefix를 제거한
  canonical full run key로 SHA-256 matcher shuffle
- Profile audit: `runs/ablation/profile_audit.json`, 30 rows,
  violations 0; within-leaf semantic ambiguity는 판정하지 않음
- Expected seed-0 budget: 약 4.7M generation tokens, 약 3.25시간,
  15,000원 ceiling
- Output:
  - `runs/ablation/actionable_only/`
  - `runs/ablation/identity_only/`

## Execution

- Started: 2026-08-03 01:52 KST
- Seed-0 generation/retry completed: 2026-08-03 14:03 KST
- Run ID: `ablation_actionable_only_*_seed0`,
  `ablation_identity_only_*_seed0`
- Retries: actionable-only 6 technical retries, identity-only 7 technical
  retries
- Missing: 0 artifacts; all 30 schema-valid
- Actual token usage in final selected artifacts:
  - actionable-only: 2,361,234
  - identity-only: 2,426,862
  - total: 4,788,096
- Serper ledger:
  - successful queries: 74 + 81 = 155
  - failed queries: 31 + 24 = 55
- Actual cost: Unverified; billing artifact 없음
- Matcher: 실제 실행 0. Estimate-only는 actionable 59 calls
  (Writing artifact 1개 empty), identity 60 calls.

## Observed results

- Actionable-only: completed 15/15, schema-valid 15/15,
  success-criteria 12/15, completeness issue 3, ledger issue 1.
- Identity-only: completed 15/15, schema-valid 15/15,
  success-criteria 12/15, completeness issue 3, ledger issue 0.
- `runs/ablation/seed0_generation_gate.json`:
  `generation_gate_passed=false`.
- Seed-1 generation은 이 gate로 승인되지 않았다.

## Anomalies

- Actionable `task2_User7`: final report 미캡처로 Writing matcher
  denominator가 14가 된다.
- Actionable `task27_User2`: topic 2·3 source 없음과 query/source ledger
  mismatch.
- Actionable `task7_User10`: topic 3 source 없음.
- Identity `task22_User14`, `task27_User2`, `task7_User10`: 각각 topic 3
  source 없음.

## Interpretation

- Seed-0 result는 gate diagnostic이며 최종 confirmatory claim으로 단독
  보고하지 않는다.

## Decision / Next step

- DEC-006의 completeness issue ≤2 조건을 두 condition 모두 위반했고,
  actionable은 ledger-clean 조건도 위반했다.
- Seed 1을 실행하기 전에 설계 검토가 필요하다. 현재 gate는 seed 1을
  승인하지 않는다.
- Seed-0 corrected matcher는 119 calls로 산정됐지만 실제 실행하지
  않았다. 사용자 비용 승인과 denominator 처리 결정 후 실행한다.

## Artifacts

- Runner: `scripts/batch_runner.py`
- Profile projection: `scripts/persona_ablation.py`
- Audit: `scripts/audit_ablation_profiles.py`
- Audit output: `runs/ablation/profile_audit.json`
- Generation gate:
  `runs/ablation/seed0_generation_gate.json`
