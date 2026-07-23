---
type: decision
id: DEC-001
date: 2026-07-22
status: accepted
project: DRA-personalization-attribution
---

# DEC-001 100000 KRW hard cap

## Context

전체 실험의 현금 예산은 100,000원이다. 연구 질문을 보존하면서 optional component부터 줄이는 중단 규칙이 필요하다.

## Decision

- 현금 hard cap: 100,000원
- 실행 목표선: 85,000원
- 최종 buffer: 최소 5,000원
- 15 reports마다 비용 projection을 갱신한다.
- 비용 절감 순서는 style normalization → shuffled-actionable → GPT permutation → LaMP 15→10이다.
- PDR core 20 groups와 2 seeds는 우선 보존한다.

## Evidence

- Flash+Flex+Serper-free 기본 projection: 약 69,900원
- Pro full은 이론상 약 92,900원이나 buffer가 작다.
- Pro가 필요하고 실측 projection이 높으면 240-report 축소안을 사용한다.

## Revisit trigger

- pilot p90 token usage로 계산한 projection이 85,000원을 넘을 때
- 이미 지출·예약·잔여 필수 run 합계가 95,000원을 넘을 때

## Related

- [[2026-07-22]]
- [Notion research specification](https://app.notion.com/p/396780c0050b8143a21fdfbbb1d613fc)

