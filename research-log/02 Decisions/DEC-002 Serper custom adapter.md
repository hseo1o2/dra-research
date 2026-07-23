---
type: decision
id: DEC-002
date: 2026-07-22
status: accepted
project: DRA-personalization-attribution
---

# DEC-002 Serper custom adapter

## Context

`open_deep_research`는 Gemini backbone에서 Serper를 네이티브 검색 옵션으로 제공하지 않는다. Tavily는 구현이 쉽지만 현금 비용이 추가된다.

## Alternatives considered

1. 원 코드의 Tavily 기본 경로
2. Serper custom adapter
3. Gemini native search

## Decision

Serper adapter를 구현하고 `organic[]`을 query/title/link/domain/rank/snippet으로 정규화한다.

- report당 최대 7 queries
- 계획 최대 2,205 queries
- global hard stop 2,400 successful queries
- 무료 2,500회 초과 및 $50 Starter 자동 구매 금지

## Risks

- Serper는 raw-content extraction이 없어 snippet-only retrieval이 report 품질을 낮출 수 있다.
- custom adapter 자체가 새로운 구현·검증 범위다.

## Revisit trigger

- pilot에서 non-empty organic results 기준 또는 actionable checklist를 통과하지 못할 때
- deterministic top-URL fetch를 추가해도 report 품질이 충분하지 않을 때

## Related

- [[2026-07-22]]
- [Notion research specification](https://app.notion.com/p/396780c0050b8143a21fdfbbb1d613fc)

