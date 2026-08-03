---
type: decision
id: DEC-006
date: 2026-08-03
status: accepted
project: DRA-personalization-attribution
supersedes:
superseded-by:
---

# DEC-006 Stage generation ablations by seed

## Context

EXP-009와 EXP-010으로 Search cue carrier와 named-entity robustness는
강화되었지만, actionable content와 identity attribute 중 어느 component가
generation을 통해 recoverability를 만드는지는 아직 직접 검증하지 않았다.

Frozen design은 5 task × 3 personas × 2 seeds를 actionable-only와
identity-only 각각 생성해 총 60 reports를 요구한다. 기존 full
generation ledger에서 120 reports는 18,736,232 tokens와 약 12.95시간을
사용했으므로, 60-report ablation은 약 9.37M tokens와 6.5시간 규모다.

## Alternatives considered

1. 두 조건의 두 seed 60 reports를 한 번에 실행한다.
2. seed 0의 두 조건 30 reports를 먼저 실행·검증하고, gate 통과 후 seed
   1의 30 reports를 실행한다.
3. corrected identifier masking만으로 shortcut analysis를 종료한다.

## Decision

대안 2를 채택한다.

1. actionable-only seed 0: 15 reports
2. identity-only seed 0: 15 reports
3. schema/completeness, token/query ledger, matcher 4-stage 결과를 검증
4. 두 condition이 해석 가능한 차이를 보이고 budget projection이
   85,000원 미만이면 seed 1을 동일 설계로 실행

Profile은 manifest의 `identity_leaf_keys_v1`을 그대로 operationalize한다.
Actionable-only는 identity leaf key를 제거하고, identity-only는 해당
key만 유지한다. Full/actionable/identity matcher candidate order는
condition prefix를 제거한 canonical run key의 SHA-256 seed로 맞춘다.

## Evidence

- `runs/ablation/profile_audit.json`: 30 profile rows, violations 0
- actionable-only: 평균 41.6 leaves, identity key leakage 0
- identity-only: 평균 10.1 leaves, non-identity key leakage 0
- full generation ledger: seed 0 9,460,088 tokens; seed 1 9,276,144 tokens
- [[EXP-009 Search-view controls]]
- [[EXP-010 Corrected two-seed identifier masking]]

## Consequences

### Benefits

- 약 3.25시간·30-report gate 후 남은 generation의 정보가치를 판단한다.
- 두 조건의 catastrophic quality failure 또는 profile wiring 문제를
  seed 1 비용 전에 발견한다.
- 최종 실행 시 frozen two-seed design은 유지된다.

### Risks

- seed-0 중간 결과는 confirmatory conclusion으로 보고하지 않는다.
- leaf-key split은 within-leaf semantic ambiguity를 판정하지 않는다.
- 5 task clusters라 uncertainty가 넓을 수 있다.

## Revisit trigger

- seed-0 condition 중 schema-valid <15, severe completeness issue >2,
  또는 예상 누적비용 >85,000원이면 seed 1 실행 전 설계를 재검토한다.

## Related

- Daily: [[2026-08-03]]
- Experiment: [[EXP-011 Generation-time shortcut ablation]]
