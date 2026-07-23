---
type: decision
id: DEC-003
date: 2026-07-22
status: accepted
project: DRA-personalization-attribution
---

# DEC-003 Flex and Batch routing

## Context

DRA research loop는 model function call, 외부 검색 실행, 결과 반환이 반복되는 순차 구조다. 전체 generation에 Batch 할인율을 일괄 적용하면 실제 실행 구조와 맞지 않는다.

## Decision

- planning/search/compression/writing의 순차 model calls: Gemini Flex
- GPT matcher와 독립 style-normalization: Batch
- Solar matcher: 보유 credit을 사용하는 realtime
- Flex 실패 시 standard tier로 무제한 자동 전환하지 않는다.

## Consequences

- 순차 agent loop를 유지하면서 generation 비용을 낮춘다.
- Flex의 variable latency와 best-effort availability를 pilot gate에서 측정해야 한다.
- Batch 결과는 최대 24시간 turnaround를 고려해 일정에 넣는다.

## Revisit trigger

- Flex 성공률이 pilot gate를 통과하지 못할 때
- standard tier 전환 projection이 현금 hard cap을 위협할 때

## Related

- [[2026-07-22]]
- [[DEC-001 100000 KRW hard cap]]
- [Notion research specification](https://app.notion.com/p/396780c0050b8143a21fdfbbb1d613fc)

