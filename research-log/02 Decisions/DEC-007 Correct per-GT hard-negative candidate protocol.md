---
type: decision
id: DEC-007
date: 2026-08-03
status: accepted
project: DRA-personalization-attribution
supersedes:
superseded-by:
---

# DEC-007 Correct per-GT hard-negative candidate protocol

## Context

논문 Method와 frozen `manifest.json`은 각 ground-truth persona마다
`attribution_candidate_set_n3`를 별도로 정의한다. 기존 Solar matcher와
baseline lookup은 이 필드가 아니라 task-level `personas_n3`를
사용했다.

## Alternatives considered

1. 기존 결과를 그대로 hard-negative 결과로 보고한다.
2. 기존 결과를 task-cohort protocol의 잠정 분석으로 보존하고,
   matcher와 파생 분석을 frozen per-GT candidate로 재실행한다.
3. manifest를 기존 결과에 맞춰 사후 변경한다.

## Decision

2번을 채택한다. Frozen manifest는 변경하지 않는다. Full,
actionable-only, identity-only는 per-GT
`attribution_candidate_set_n3`를 사용한다. Shuffled-actionable만
identity shell과 cyclic actionable donor가 모두 후보에 있어야 하므로
사전 정의된 task cohort를 사용한다.

기존 `matches_sha256` 결과는 삭제하거나 덮어쓰지 않고 task-cohort
protocol의 잠정 결과로 보존한다. Corrected Solar 결과는 새
`matches_hardneg_v1` 디렉터리에 기록한다.

## Evidence

- Observed: `runs/confirmatory/candidate_protocol_audit.json`
  - audited match files: 120
  - frozen per-GT candidate exact matches: 6
  - mismatches: 114
  - SHA-256:
    `6b613496a1b9f389c23aeeb218bbff8b1fd379e79c66701edfa48720280f4daf`
- Observed: `provenance/candidate_sensitivity_plan.json`
  - confirmatory experiments: 60
  - recomputed N=3 manifest exact matches: 60/60
  - N=2/3/5 candidate sets frozen
  - SHA-256:
    `7e6dc1c1012b4d87d30057d0da29018e1a2d389e53cf103674e07b12f90c2218`
- Manifest SHA-256:
  `8110d1b3656fa5ba021f7b1bd053a92a11922c4efecd8d43d552e80cda4ad2a9`
- Commit: `14b08031fac8a1e2396317bd09b57e70cba405cb`
  (dirty worktree)
- Executed: 전체 test suite 67 passed.
- 실제 API 실행 없음. 이 결정 작업 중 새 matcher/generation API를
  호출하지 않았다.

## Consequences

### Benefits

- 논문 Method, manifest, matcher가 동일한 candidate protocol을 따른다.
- N=2/3/5 sensitivity가 동일 ranking의 prefix로 비교 가능하다.
- 기존 결과를 보존해 protocol 변경 전후를 추적할 수 있다.

### Risks

- 기존 primary, masked, search-view, baseline 수치와 figure는 final이
  아니며 corrected rerun 전까지 논문에 확정 수치로 사용할 수 없다.
- Full Solar two-seed만 480 stage calls가 필요하다. Masked와 search-view를
  유지하면 추가 matcher 비용이 발생한다.
- Shuffled-actionable은 full hard-negative 후보와 후보 집합이 다르므로
  배열 직접 비교 대신 각 조건의 SHA-256 order를 독립 검증해야 한다.

## Revisit trigger

- Corrected full, masked, search-view 결과와 baseline을 모두 재생성한 뒤
  기존 task-cohort 결과와 결론이 달라지는지 검토한다.
- Candidate-size sensitivity 또는 새로운 candidate construction을
  도입할 때는 manifest version을 올릴지 재결정한다.

## 2026-08-03 resolution update

- Corrected full Solar 480 decisions 완료.
- Candidate protocol audit 120/120 pass, mismatch 0.
- Primary 통계·baseline·figure·manuscript 수치 교체 완료.
- Identifier-masked와 Search-view corrected rerun은 아직 pending이며,
  그 전까지 기존 control 수치를 논문 주장에 사용하지 않는다.
- Experiment: [[EXP-012 Corrected per-GT Solar matching]]

## Related

- Daily: [[2026-08-03]]
- Experiment: [[EXP-011 Generation-time shortcut ablation]]
- Notion:
  [DRA Personalization — Content/Intent-layer Attribution](https://app.notion.com/p/396780c0050b8143a21fdfbbb1d613fc)
