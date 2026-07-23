---
type: workflow
status: active
---

# Logging Workflow

## 무엇을 어디에 기록하는가

| 상황 | 기록 위치 |
|---|---|
| 오늘 한 일과 막힌 점 | `01 Daily` |
| 설계·모델·비용·데이터 선택 변경 | `02 Decisions` |
| 실행 전 설정과 관측 결과 | `03 Experiments` |
| 논문 원문에서 확인한 내용 | `04 Literature` |
| 나중에 글로 발전시킬 소재 | `05 Publication Ideas` |
| 자동 수집됐지만 미확인인 내용 | `Inbox` |

## Codex 호출 규칙

### 하루 마감

> 오늘 연구 로그 정리해줘. git status와 오늘 변경 파일을 확인하되, 실행 사실은 파일·terminal·ledger로 검증해. 오늘 daily note에 append하고 새 결정이 있으면 별도 decision note를 만들어 링크해줘.

### 결정 기록

> 이 결정을 ADR 형식의 decision note로 남겨줘. context, alternatives, decision, evidence, consequences, revisit trigger를 포함하고 기존 결정을 대체하면 양쪽 상태와 링크를 갱신해줘.

### 실험 기록

> 이 run을 experiment note로 정리해줘. pre-run lock과 post-run result를 분리하고 commit SHA, manifest SHA, model ID, seed, run ID, query/token/cost ledger를 원본에서 읽어 기록해줘.

## 사실성 규칙

- `Planned`: 아직 실행하지 않은 항목
- `Executed`: 명령·artifact·ledger로 확인된 항목
- `Observed`: 결과 파일에서 직접 확인한 값
- `Inferred`: 관측에서 도출한 해석
- `Decision`: 선택과 적용 범위

Codex가 근거를 찾지 못한 내용은 `Unverified`로 표시한다.

## 출판 전환

채택 결과가 나온 뒤 Decision note를 시간순으로 배열해 글의 뼈대를 만든다. Daily note는 맥락과 시행착오를 복원하는 보조 자료로만 사용하고, 실험 수치는 항상 repository artifact에서 다시 확인한다.

