# DRA Research Log

이 폴더는 Obsidian vault로 사용할 DRA 연구 과정 기록이다.

## 역할 분리

- Notion: 현재 확정된 연구 설계와 실행 명세
- Obsidian: 진행 과정, 시행착오, 의사결정, 해석
- Repository: manifest, config, run ledger, 결과 원본

## 처음 열기

1. Obsidian에서 **Open folder as vault**를 선택한다.
2. `/Users/janghyeonseo/Desktop/DRA/research-log`를 연다.
3. Core plugins에서 **Templates**와 **Daily notes**를 활성화한다.
4. Templates folder를 `99 Templates`로 지정한다.
5. Daily notes folder를 `01 Daily`, template을 `99 Templates/Daily Note`로 지정한다.

## 반자동 사용법

평소에는 자동으로 노트를 만들지 않는다. 작업이 끝났을 때 Codex에 다음처럼 요청한다.

> 오늘 연구 로그 정리해줘. 확인한 사실, 실제 실행, 결정, 막힌 점, 다음 작업을 구분하고 기존 daily note에 append해줘. 관련 commit·manifest·실험·decision note도 연결해줘.

중요한 선택이 생겼을 때:

> 방금 결정한 내용을 decision note로 남기고 오늘 daily note에서 링크해줘. 기존 결정을 대체하면 superseded 관계도 기록해줘.

실험이 끝났을 때:

> 이번 run을 experiment note로 정리해줘. config와 ledger에서 값을 읽고, 기억으로 수치를 만들지 마. pre-run lock과 observed result를 분리해줘.

## 기록 원칙

- Daily는 5분 안에 읽을 수 있게 짧게 유지한다.
- 결정 이유는 Decision note에 남긴다.
- 수치는 experiment ledger에서 가져온다.
- 계획과 실제 실행을 분리한다.
- API key와 개인정보는 기록하지 않는다.
- 출판 전에는 private 상태를 유지한다.
