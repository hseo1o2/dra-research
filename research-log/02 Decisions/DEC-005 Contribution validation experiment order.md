---
type: decision
id: DEC-005
date: 2026-08-03
status: accepted
project: DRA-personalization-attribution
supersedes:
superseded-by:
---

# DEC-005 Contribution validation experiment order

## Context

EXP-008에서 report-level loss-and-recovery와 stage-dependent
Solar–BM25 gap이 핵심 contribution 후보로 관측되었다. 남은 현금 hard
cap 안에서 이 해석을 직접 반증할 수 있는 검증을 우선해야 한다.

## Alternatives considered

1. LaMP-QA 90 reports 또는 PDR third seed를 즉시 생성한다.
2. existing artifacts에서 seed-1 baseline과 Search artifact view를 먼저
   검증하고, 저비용 matcher control 이후 generation ablation을 결정한다.
3. 추가 검증 없이 현재 two-seed 결과만 작성한다.

## Decision

다음 순서로 진행한다.

1. seed-1 Random/BM25/Embedding baseline — 외부 API 0회
2. Search query-only 및 snippet-only view matcher — Search bottleneck의
   cue carrier를 직접 분리
3. seed-1 identifier masking 및 matcher — masking robustness를 two-seed로
   확장
4. 결과를 본 뒤 actionable-only / identity-only generation ablation의
   정보가치를 다시 평가
5. LaMP-QA와 third generation seed는 후순위

Search-view와 masked matcher는 실제 Upstage API 호출 전 dry-run,
예상 call 수, output directory를 고정한다.

## Evidence

- [[EXP-008 Contribution cross-condition analysis]]
- two-seed Search Solar–BM25 gap +0.100, CI `[0.008, 0.192]`
- two-seed Writing Solar–BM25 gap +0.217, CI `[0.100, 0.333]`
- 누적 현금 사용은 billing dashboard 미확인 추정치 약 5만원이며,
  DEC-001 hard cap은 10만원이다.

## Consequences

### Benefits

- 새로운 generation 비용 없이 핵심 contribution의 대안 설명을 먼저
  검증한다.
- query formulation과 retrieved snippet 중 어느 쪽에서 persona
  recoverability가 약한지 구분한다.
- generation ablation 실행 여부를 관측 결과에 따라 결정한다.

### Risks

- Search-view 결과도 같은 Solar matcher에 의존한다.
- query-only/snippet-only는 post-hoc artifact decomposition이며
  intervention on generation이 아니다.
- seed-1 masking에는 추가 matcher 비용이 발생한다.

## Revisit trigger

- Search-view control이 query와 snippet 사이에 차이를 보이지 않거나,
  seed-1 baseline이 seed-0 패턴을 반박하면 contribution 해석을 수정한다.
- generation-time ablation 예상 비용과 이미 지출된 비용의 합이
  85,000원을 넘으면 DEC-001 축소 규칙을 적용한다.

## Related

- Daily: [[2026-08-03]]
- Experiment: [[EXP-008 Contribution cross-condition analysis]]
- Notion: frozen design은 아직 변경하지 않음
