---
title: DRA-PULSE Research Plan
project: DRA-personalization-attribution
status: active
updated: 2026-08-03
working_name_status: accepted
---

# DRA-PULSE Research Plan

> **문서 역할:** 현재 연구 질문, 벤치마크 프로토콜, 실행 범위, 진행
> 상태, 논문 완결 조건을 한곳에서 확인하기 위한 로컬 통합 계획서다.
> 설계 원문은 [Notion research specification](https://app.notion.com/p/396780c0050b8143a21fdfbbb1d613fc),
> 실행 사실과 수치는 repository artifact, 구체적인 실행 명령은
> [`RUNBOOK.md`](RUNBOOK.md)를 기준으로 한다.

## 1. 연구 정체성

### Working name

**DRA-PULSE** — *Deep Research Agent Persona-signal Uncovering and
Localization across Staged Execution*

권장 논문 제목:

> **DRA-PULSE: Localizing Persona Signals Across Deep Research Agent
> Pipelines**

`DRA-PULSE`는 2026-08-03에 working name으로 채택했다. 원천 dataset과
artifact schema 이름은 provenance 호환성을 위해 소급 변경하지 않는다.

### 무엇을 새로 만드는가

DRA-PULSE는 새로운 원천 persona 데이터셋이 아니다. 기존 PDR-Bench와
LaMP-QA를 사용해 다음을 제공하는 **stage-wise diagnostic benchmark
protocol**이다.

1. N-way closed-set conditioning-persona attribution task
2. DRA 중간 산출물의 stage-wise signal localization
3. 동일 query의 hard-negative persona candidate set
4. lexical/identity shortcut controls
5. seed, matcher, dataset에 대한 robustness protocol
6. 중간 산출물 수집기 DRATracer와 재현 가능한 evaluation harness

명칭 역할은 다음과 같이 분리한다.

| 이름 | 역할 |
|---|---|
| DRA-PULSE | 전체 benchmark/evaluation protocol |
| DRATracer | LangGraph 중간 산출물 수집 구현 |
| PDR-Bench | primary 원천 persona/query dataset |
| LaMP-QA | cross-dataset replication source |

## 2. 연구 목표와 주장 경계

### 핵심 목표

Persona로 conditioning된 DRA가 planning, search, compression, writing
단계를 통과할 때, 어느 단계에서 conditioning persona의
content-priority signal이 식별 가능하고 유지·소실·회복되는지를
측정한다.

### 직접 측정하는 것

- artifact에서 conditioning persona ID를 복원할 수 있는가
- stage별 attribution accuracy가 어떻게 변하는가
- 결과가 generation seed와 matcher에 얼마나 민감한가
- identifier, demographics, copied phrase 같은 shortcut으로 설명되는가
- 다른 source dataset에서도 trajectory가 재현되는가

### 주장하지 않는 것

- latent user intent를 복원했다는 주장
- attribution accuracy가 personalization quality 또는 utility라는 주장
- attribution 성공이 user satisfaction을 보장한다는 주장
- 관찰된 stage 차이만으로 인과 메커니즘을 식별했다는 주장
- LaMP-QA 결과를 DRA 전반의 generalization proof로 해석하는 주장

논문에서는 `causal diagnostic`보다 `localization diagnostic` 또는
`stage-wise recoverability diagnostic`을 사용한다.

## 3. 연구 질문

### RQ0 — Signal emergence

동일 query에서 persona 간 artifact representation 차이가 동일 persona의
seed 간 차이보다 커지는 최초 stage는 어디인가?

- 계획된 분석: BGE-M3 representation의 between-persona 대
  within-persona distance
- 현재 상태: **Planned / 미구현**
- 결정 필요: workshop 제출 범위에 유지할지, attribution 중심 논문에서
  제외할지 확정

### RQ1 — Stage-wise recoverability

N=3 hard-negative setting에서 conditioning persona attribution accuracy는
planning, search, compression, writing 단계에 따라 어떻게 변하는가?

- Primary matcher: Upstage Solar Pro (`solar-pro`)
- Primary metric: stage별 Acc@1
- **Frozen per-GT hard-negative protocol로 corrected Solar 120/120
  재매칭 및 candidate audit를 완료했다.**
- Corrected SHA-256 two-seed 관측: Planning 0.808, Search 0.550,
  Compression 0.592, Writing 0.800, macro Acc@1 0.688
- 120 reports와 20 task clusters를 대상으로 task-cluster bootstrap
  interval을 사용한다

### RQ2 — Shortcut robustness

관측된 attribution signal은 identifier, demographics, copied persona
phrases 같은 shortcut으로 얼마나 설명되는가?

- identifier-masked: 기존 artifact의 network-free post-processing
- Search query-only/snippet-only: post-hoc cue-carrier localization
- actionable-only: generation-time condition
- identity-only: generation-time condition
- shuffled-actionable: generation-time negative control
- style-normalized: 예산이 남을 때만 수행하는 선택 항목

### RQ3 — Robustness and replication

trajectory가 generation seed, non-LLM baseline, matcher provider,
source dataset 변화에도 유지되는가?

- generation seeds: 0, 1
- baselines: Random, BM25, Embedding
- matcher replication: GPT-5.4-nano, seed 0 reference configuration
- dataset replication: LaMP-QA
- SIGIR PDR human-authored reports: descriptive sanity check only

## 4. 벤치마크 설계

### 4.1 Primary dataset and split

- PDR-Bench English: 25 personas, 250 query-persona pairs, 10 domains
- sampling seed: `20260722`
- eligibility: identity masking 후 actionable token이 남는 persona가
  최소 3명인 task
- confirmatory: 20 query groups, 도메인별 2개
- candidate personas: group당 3명
- generation seeds: 0, 1
- primary report 수: 20 × 3 × 2 = **120**
- dev pilot: 5 groups × 3 personas × seed 0 = **15**,
  research result에서 제외

Frozen sampling과 candidate set은 `manifest.json`을 따른다.

### 4.2 Candidate construction

각 ground-truth persona에 대해 actionable-token Jaccard가 높은 동일
도메인 persona 2명을 distractor로 선택한다.

- threshold `>= 0.2`: hard negative
- threshold 미달: nearest fallback
- tie-break: userid 오름차순
- candidate order: run ID와 stage에서 파생한 SHA-256 seed로 shuffle

### 4.3 Pipeline artifacts

| Stage | Artifact | 주요 내용 |
|---|---|---|
| Planning | research brief | scope, topics, intended angle |
| Search | query/source trace | search queries와 selected snippets |
| Compression | compressed research | topic별 evidence synthesis |
| Writing | final report | long-form synthesized report |

DRATracer는 네 artifact와 `dra_trace_v2` schema, execution config,
prompt hash, query/source/token ledger를 저장한다.

### 4.4 Matcher and context policy

- Solar Pro: temperature 0, structured persona ID output
- Planning: 최대 4,000 characters
- Search: 최대 3,500 characters
- Compression: 최대 6,000 characters
- Writing: 최대 8,000 characters, opening과 tail 보존
- 동일 run/stage 재실행 시 candidate order가 같아야 함
- matcher summary는 resume/chunk의 마지막 batch가 아니라 전체 match
  파일에서 다시 집계

### 4.5 Baselines

| Baseline | 입력과 판정 |
|---|---|
| Random | candidate set에서 seeded uniform choice |
| BM25 | artifact와 persona text의 Okapi BM25 similarity |
| Embedding | sentence encoder cosine similarity |

Baseline은 API 없이 기존 artifact에 실행한다.

### 4.6 Shortcut controls

| Condition | 시점 | 추가 DRA reports | 목적 |
|---|---:|---:|---|
| Full | generation | reference 120 | 기준 조건 |
| Identifier-masked | post-processing | 0 | corrected two-seed surface identity mention 제거 |
| Actionable-only | generation | 30 | preference/content signal 분리 |
| Identity-only | generation | 30 | demographic shortcut 측정 |
| Shuffled-actionable | generation | 15 | persona-actionable 연결 파괴 |
| Style-normalized | post-processing call | 별도 | 표현 shortcut 측정, optional |

Identifier masking은 NER만이 아니라 frozen lexical-leakage policy의
copied phrase 통제와 구분해서 보고한다.

### 4.7 Replication

- LaMP-QA: 15 queries, 3 categories에서 각 5개
- query당 GT profile 1개와 hard-negative profile 2개
- 15 × 3 × 2 seeds = **90 reports**
- shortcut ablation은 LaMP-QA에서 반복하지 않음

### 4.8 전체 생성 예산

| Wave | Reports |
|---|---:|
| PDR full confirmatory | 120 |
| Actionable-only | 30 |
| Identity-only | 30 |
| Shuffled-actionable | 15 |
| LaMP-QA replication | 90 |
| **Confirmatory total** | **285** |

별도의 Flash dev pilot 15 reports가 존재한다. 실제 API 실행은 사용자가
명시적으로 터미널에서 수행하며, 자동으로 실행하지 않는다.

## 5. 분석 계획

### Primary statistics

- stage별 Acc@1와 macro Acc@1
- task ID를 cluster로 둔 bootstrap 95% confidence interval
- Planning→Search→Compression→Writing 인접 stage paired difference
- seed별 accuracy와 seed variance
- report별 0/4–4/4 correct distribution
- persona confusion과 hard-negative pair 분석
- schema-valid 전체와 quality-filtered subset sensitivity

### Supplementary statistics

- unclustered exact McNemar p-value
- matcher 간 prediction agreement와 Cohen's kappa
- actionable-token Jaccard와 attribution correctness의 관계
- N ∈ {2, 5} sensitivity는 시간과 구현 상태가 허용할 때만 수행

### Figure and table budget

본문 우선순위:

1. Stage trajectory figure: PDR seed 0+1, task-cluster bootstrap CI
2. Main attribution table: Solar + non-LLM baselines
3. Shortcut-control table
4. 가능하면 LaMP-QA replication 또는 matcher agreement 소형 표

`paper/figures/stage_attribution_trajectory.*`는 SHA-256 matcher의
two-seed 120-report 결과와 task-cluster bootstrap interval로 재생성했다.

## 6. 현재 진행 상태

아래 상태는 **2026-08-03** repository artifact를 읽어 확인한
snapshot이다.

| Workstream | 상태 | 확인된 근거 |
|---|---|---|
| Frozen manifest | **Completed** | `manifest.json` v1.1, `frozen: true` |
| DRATracer/schema/ledger | **Completed** | seed 0 artifact 60개가 schema-valid |
| Dev pilot | **Completed** | 15-report dev pilot artifact 존재 |
| PDR confirmatory seed 0 generation | **Completed** | 60/60 schema-valid; success criteria 43/60 |
| PDR confirmatory seed 1 generation | **Completed** | 60/60 schema-valid; success criteria 47/60; final report missing 0 |
| Legacy Solar seed 0 matching | **Completed, superseded for final use** | legacy match 60개 |
| SHA-256 Solar matching | **Corrected; completed** | `matches_hardneg_v1/` 120 reports, 480 stage decisions; frozen per-GT candidate audit 120/120 pass |
| Random/BM25/Embedding baseline | **Corrected; completed for both seeds** | per-GT hard-negative candidate로 seed별 180 match files, 총 360개; protocol audit 360/360 pass; API 0회 |
| Candidate-derived identity masking | **Corrected; completed for both seeds** | NER + 후보 3명의 identity-field phrase를 제거한 artifact 120개; per-GT matcher 480 decisions |
| Identity-masked attribution | **Corrected; completed** | candidate audit 120/120, full/masked order 480/480 일치; masked 0.725/0.558/0.575/0.783 |
| Statistical analysis script | **Completed on corrected primary** | `analysis_hardneg_v1/`; paired transitions, quality sensitivity, task-cluster bootstrap 산출물 존재 |
| Paper figure script | **Completed on corrected primary** | corrected PDF/SVG/PNG 생성 |
| Actionable-only generation | **Seed-0 complete; gate failed** | 15/15 schema-valid, strict 12/15, completeness 3, ledger issue 1; seed 1 미실행 |
| Identity-only generation | **Seed-0 complete; gate failed** | 15/15 schema-valid, strict 12/15, completeness 3; seed 1 미실행 |
| Shuffled-actionable generation | **Completed and matched** | 15/15 schema-valid, strict 8/15, 60 stage decisions, SHA-256 order audit 60/60 |
| Candidate-size sensitivity | **Plan frozen offline** | N=2/3/5 60개 candidate set; recomputed N=3 manifest exact match 60/60; API 0회 |
| Candidate-construction prior | **Completed offline** | artifact-free centrality 27/60=0.450, task-bootstrap CI [0.333, 0.567]; task-shared protocol에서도 trajectory 유지 |
| Corrected Solar rerun budget | **Completed** | full 480 + identity-masked 480 + Search views 240 완료 |
| LaMP-QA plan/runner | **Implemented, offline-validated** | 90 unique run plan; GT 30, hard negative 60; API 0회 |
| LaMP-QA generation | **Pending** | 0/90; PDR seed 1 종료 후 seed별 실행 |
| GPT matcher replication | **Completed** | seed 0 60 reports × 4 stages = 240 calls plus 1 smoke call; 60 match files, corrected candidate mismatch 0 |
| Cross-seed source stability | **Completed offline** | URL within 0.0422 vs between 0.0338; 차이 +0.0084, task-bootstrap CI가 0 포함 |
| SIGIR human-authored sanity check | **Offline descriptive freeze completed** | 공식 commit 및 5×3 file SHA-256 고정; 길이/형식 통계 생성 |
| Provenance inventory/checksums | **Prepared** | `provenance/` 산출물 존재 |
| Off-device backup | **Unverified** | repository evidence 없음 |
| Paper writing | **Submission-ready draft** | verified citations, 6-page anonymous PDF, full visual QA 완료 |

Seed 0의 completeness error는 primary exclusion 사유가 아니다. 사전
정의대로 모든 schema-valid run을 primary analysis에 포함하고,
quality-filtered 결과를 sensitivity analysis로 별도 보고한다.

## 7. Critical path

### Phase A — 현재 실행 마무리

- [x] seed 1 generation 60/60 완료
- [x] final report가 누락된 4건을 기술적 retry로 재실행
- [x] seed 1 전체 summary를 `--summarize-only`로 재생성
- [x] schema, completeness, ledger, success-criteria 상태 점검
- [ ] seed 1 artifact off-device backup

### Phase B — Primary result freeze

- [x] candidate-order shuffle을 process-independent SHA-256로 수정
- [x] 기존 결과의 candidate protocol audit 수행: 6/120 일치,
  114/120 불일치
- [x] matcher lookup을 frozen per-GT hard-negative candidate set으로 수정
- [x] seed 0·1을 `matches_hardneg_v1/`에 Solar 재매칭
- [x] corrected candidate로 Random/BM25/Embedding baseline 재실행
- [x] corrected full match와 통계 재생성
- [x] corrected stage trajectory PDF/SVG/PNG 재생성
- [x] 논문 primary 수치를 corrected 결과로 교체

### Phase C — Shortcut controls

- [x] corrected candidate-derived identity-masked two-seed matcher 및 trajectory 분석
- [x] corrected full과 masked의 480 candidate orders 일치 및 paired effect 재계산
- [x] corrected Search query-only/snippet-only 120-report paired control: 240/240 protocol audit pass
- [x] actionable/identity-only runner와 frozen profile audit 구현
- [x] seed-0 completeness retry와 generation gate 판정 완료: 두 condition 모두 fail
- [ ] actionable-only 30 reports 생성·매칭
- [ ] identity-only 30 reports 생성·매칭
- [x] shuffled-actionable 15 reports 생성·매칭 및 donor/shell 분석
- [ ] full 조건과 동일한 artifact inclusion/statistical policy 적용

### Phase D — Robustness

- [x] LaMP-QA 90-run plan-only 검증
- [x] full two-seed source/query stability 분석
- [x] candidate-only centrality prior 및 task-shared protocol sensitivity
- [ ] LaMP-QA 90 reports 생성·매칭
- [x] GPT-5.4-nano seed 0 dry estimate와 agreement 분석 코드 준비
- [x] GPT-5.4-nano seed 0 replication: 240 matcher calls + 1 smoke call
- [x] Solar–GPT agreement와 Cohen's kappa: agreement 0.783, κ=0.763
- [x] SIGIR human-authored report descriptive manifest·기술통계
- [ ] RQ0/BGE-M3 유지 여부 결정 후 실행 또는 scope에서 명시적으로 제거

### Phase E — Paper and release

- [x] DRA-PULSE 이름 채택
- [x] Introduction과 contribution 문구를 final cross-condition 분석에 맞춤
- [x] `causal` 표현을 recoverability/localization 범위로 수정
- [x] primary result의 seed 0-only placeholder와 예상 ablation 문구 제거
- [x] final figure/table 및 confidence interval 삽입
- [x] limitations에 utility validation 부재와 LLM matcher 의존성 명시
- [x] artifact/code 공개 위치가 생기기 전 release 완료형 문구 사용 금지
- [ ] provenance checksum 검증 후 비공개 off-device backup
- [x] PDF compile, 6-page limit, anonymous submission metadata와 전 페이지 visual QA

추가 API 예산이 승인될 경우의 최우선 실험은 corrected Search
queries-only/snippets-only paired control이다. 기존 120개 artifact를
재사용하므로 새 generation은 0회이고 matcher는 240회다. 근거와 stop
rule은 `paper/analysis/next_experiment_priority.md`에 고정했다.

구체적인 명령과 중복 실행 방지 규칙은 [`RUNBOOK.md`](RUNBOOK.md)를
사용한다.

## 8. 결정 게이트

### Gate 1 — Primary completeness

PDR 20 groups × 3 personas × 2 seeds와 SHA-256 matcher가 완결되지 않으면
seed 0 결과를 confirmatory two-seed 결과로 서술하지 않는다.

### Gate 2 — Benchmark claim

다음이 모두 충족되어야 DRA-PULSE를 benchmark contribution으로
전면에 둔다.

- task와 candidate construction이 frozen manifest로 재현 가능
- primary two-seed 결과가 완결
- 최소 Random/BM25/Embedding baseline 제공
- identifier-masked 또는 이에 준하는 shortcut control 결과 제공
- artifact schema, evaluator, sampling manifest를 공개 가능

미충족 시 `benchmark`보다 `evaluation framework` 또는
`diagnostic protocol`로 낮춰 표현한다.

**현재 판정: empirical requirements resolved, release gate pending.**
Full Solar와 non-LLM baselines는 frozen per-GT hard-negative candidate
protocol로 교정되었고 primary audit가 120/120 통과했다. 강화된
candidate-derived identity masking도 동일 protocol과 480/480 candidate
order로 완료됐다. 따라서 실험 요건은 충족했지만 공개 artifact 위치와
off-device backup이 검증되지 않았으므로 `benchmark`보다
`diagnostic framework/protocol` 표현을 유지한다.

### Gate 3 — Dip-and-recovery claim

seed 1과 SHA-256 rerun 이후에도 Planning→Search 하락과 이후 회복이
관측될 때만 title/abstract의 핵심 empirical hook으로 사용한다.
그렇지 않으면 중립적으로 `non-monotonic stage trajectory` 또는
`stage-dependent recoverability`로 표현한다.

### Gate 4 — Scope fallback

시간 또는 예산이 부족하면 다음 우선순위로 축소한다.

1. PDR full two seeds
2. identifier-masked와 non-LLM baselines
3. actionable-only / identity-only
4. LaMP-QA replication
5. GPT matcher replication
6. shuffled-actionable / style-normalized / N sensitivity

핵심 PDR 설계를 1 seed로 줄이는 대신 후순위 replication과 optional
control을 제외한다.

## 9. 현재 문서 간 충돌과 해결 필요 사항

| 항목 | Notion 설계 | 현재 repository/paper | 조치 |
|---|---|---|---|
| Main trajectory input | identifier-masked + Solar 제안 | corrected unmasked SHA-256 Solar를 primary, strong identity masking을 paired control로 확정 | 두 조건 모두 per-GT protocol 사용 |
| RQ0 | BGE-M3 between/within distance | 구현·결과 없음 | 유지 또는 제거 결정 |
| Candidate-order robustness | canonical order + 추가 permutation 기술 | SHA-256 single deterministic shuffle 구현 | 최종 protocol 하나로 통일 |
| Candidate-set lookup | per-GT top-2 hard negatives | corrected primary와 baselines가 per-GT 후보 사용 | 기존 task-cohort 수치는 superseded artifact로만 보존 |
| Diagnostic 표현 | identifiability, utility와 분리 | recoverability 진단과 non-claim으로 정리 완료 | causal claim을 사용하지 않음 |
| Release 상태 | artifact/code release 계획 | Git remote 및 공개 artifact 미확인 | 공개 전까지 future tense 사용 |
| 이름 | 기존 generic stage-wise attribution | DRA-PULSE 채택 | 논문 제목 반영; schema/provenance 식별자는 유지 |

이 표의 항목은 통합 과정에서 임의로 해결하지 않았다. 최종 설계 결정이
필요하다.

## 10. 완료 정의

연구가 논문 제출 가능한 상태가 되려면:

- [x] PDR seed 0·1 generation과 final matcher 결과가 완결
- [x] final primary 결과가 SHA-256 + frozen per-GT candidate protocol에서 재생성됨
- [x] corrected primary inclusion과 quality sensitivity가 생성됨
- [x] corrected non-LLM baselines와 최소 하나의 강한 shortcut control이 존재
- [x] corrected 통계표와 figure가 final artifact에서 자동 생성됨
- [x] manuscript의 primary 수치·model ID·dataset 규모가 corrected artifact와 일치
- [ ] benchmark/framework claim이 실제 공개 범위와 일치
- [x] limitation과 non-claims가 명시됨
- [ ] provenance와 off-device backup이 검증됨
- [x] 현재 ACL review PDF가 6-page limit, anonymity, visual layout 검수를 통과

## 11. Source map

- Frozen design: [Notion research specification](https://app.notion.com/p/396780c0050b8143a21fdfbbb1d613fc)
- Sampling/config: [`manifest.json`](manifest.json)
- Commands: [`RUNBOOK.md`](RUNBOOK.md)
- Manuscript: [`paper/main.tex`](paper/main.tex)
- Research journey: [`research-log/00 MOC/DRA Research Journey.md`](research-log/00%20MOC/DRA%20Research%20Journey.md)
- Experiment index: [`research-log/03 Experiments/Experiment Index.md`](research-log/03%20Experiments/Experiment%20Index.md)
- Provenance: [`provenance/README.md`](provenance/README.md)
