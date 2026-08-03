---
type: moc
project: DRA-personalization-attribution
status: active
---

# DRA Research Journey

## Project source of truth

- [Notion research specification](https://app.notion.com/p/396780c0050b8143a21fdfbbb1d613fc)
- [Local integrated research plan](../../RESEARCH_PLAN.md)
- Repository root: `/Users/janghyeonseo/Desktop/DRA`
- [[Logging Workflow]]

Notion은 frozen design, `RESEARCH_PLAN.md`는 repository evidence를 반영한
현재 통합 상태, `RUNBOOK.md`는 실행 명령을 담당한다.

## Current research frame

- Task: N-way conditioning-persona attribution over DRA intermediate artifacts and final reports
- Core questions: RQ0 emergence, RQ1 recoverability/stage trajectory, RQ2 shortcut robustness
- Core data: PDR-Bench English
- Replication: LaMP-QA
- Descriptive sanity check: SIGIR 2026 PDR human-authored reports

## Navigation

### Daily

- [[2026-07-22]]
- [[2026-08-03]]

### Decisions

- [[DEC-001 100000 KRW hard cap]]
- [[DEC-002 Serper custom adapter]]
- [[DEC-003 Flex and Batch routing]]
- [[DEC-005 Contribution validation experiment order]]
- [[DEC-006 Stage generation ablations by seed]]
- [[DEC-007 Correct per-GT hard-negative candidate protocol]]

### Experiments

- [[Experiment Index]]

### Literature

- [[Literature Index]]

### Publication

- [[Publication Backlog]]

## Current gates

상세 진행률과 완료 조건은 repository evidence를 반영하는
[`RESEARCH_PLAN.md`](../../RESEARCH_PLAN.md)의 `현재 진행 상태`,
`Critical path`, `결정 게이트`를 따른다.

- [x] sampling manifest freeze
- [x] Serper/tracing adapter와 schema 검증
- [x] backbone pilot
- [x] PDR confirmatory seed 0 generation
- [x] PDR confirmatory seed 1 generation
- [ ] per-GT hard-negative candidate로 Solar two-seed primary result 재동결
- [ ] corrected candidate의 identifier-masked shortcut control
- [ ] generation-time shortcut ablations: seed-0 gate failed, design review
  필요; cross-dataset replication 미실행
- [ ] off-device backup 검증
