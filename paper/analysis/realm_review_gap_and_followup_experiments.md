# REALM 2026 리뷰 갭 & 추가 실험 정리

Date: 2026-08-04  
Paper: DRA-PULSE (`paper/main.tex`)  
Venue: REALM @ EMNLP 2026 (archival long)  
Constraint: **single backbone 유지** (`open_deep_research` + Gemini)  
Cash constraint: **Solar 비용 무시 / Gemini·GPT만 현금 고려**

이 문서는 (1) 비판적 리뷰 요약, (2) 기존 실험 확인 범위, (3) 추가 실험의 contribution ROI, (4) 비용 추정, (5) 실행 권장안을 한곳에 정리한다.

---

## 1. 한 줄 결론

| 질문 | 답 |
|---|---|
| 지금 논문, REALM에 낼 수 있나? | **Yes.** trajectory + controls 스택으로 workshop weak/borderline accept 가능 구간 |
| 추가 실험이 contribution을 크게 키우나? | **크진 않음.** 대부분 리뷰 방어/해석 보강 |
| 그래도 돌릴 가치 있나? | **Yes, 싸면.** 특히 Writing no-brief ablation |
| single backbone 버려야 하나? | **아니오.** 메커니즘 ablation으로 대체 가능 |
| 권장 현금 패키지 | Write-only no-brief **n=30** + GPT utility judge + (Solar) equal-budget ≈ **3–7천원** (상한 ~1.2만원) |

---

## 2. 논문 핵심 요약 (리뷰어 시점)

### 2.1 하는 일
- Deep Research Agent 4단계(Planning → Search → Compression → Writing)에서  
  **persona conditioning 신호가 어느 단계에서 회복 가능한지**를 측정
- Task: **N-way stage-wise persona attribution**
- Backbone: `open_deep_research` + Gemini 3.6 Flash
- Data: PDR-Bench confirmatory **120 reports** (20 groups × 3 personas × 2 seeds)

### 2.2 핵심 결과
- Dip-and-recovery: **0.808 / 0.550 / 0.592 / 0.800**
- Plan→Search: −0.258 (CI excludes 0)
- Comp→Write: +0.208 (CI excludes 0)
- Report-level: Plan✓Search✗ 32건 중 **24건 Writing 회복**
- Writing recovery 일부는 **Planning brief re-injection** (architectural)
- Controls: BM25, identity masking, GPT-5.4-nano 복제, N=2/3/5, search views, shuffled-actionable

### 2.3 REALM fit
- Agent Quality Evaluation / multi-step pipeline diagnostics에 잘 맞음
- 최종 답만 보는 personalization metric이 못 잡는 stage-level failure mode를 보여 주려는 동기 명확

---

## 3. 비판적 리뷰 요약

### 3.1 점수 (리뷰어 가정)
| Criterion | Score (1–5) | 메모 |
|---|---:|---|
| Novelty | 3.5 | task formalization + report-level localization 신선 |
| Soundness | 4.0 | controls/CI/replication 강함 |
| Significance | 3.0 | utility/intervention 연결 약함 |
| Clarity | 3.5 | abstract/control 밀도 높음 |
| REALM fit | 4.0 | 워크숍 토픽 정합 |
| **Recommendation** | **Borderline → Weak Accept** | multi-backbone 없이도 방어 가능 |

### 3.2 Strengths
1. multi-step agent evaluation 프레이밍이 REALM에 맞음
2. 실험 규율 강함 (bootstrap, hard-neg, baselines, masking, cross-matcher, quality gate)
3. report-level transition analysis가 aggregate curve보다 설득력 있음
4. Writing re-injection을 숨기지 않고 Plan×Write 조건확률로 정량화
5. Search-stage 약화가 BM25/search-view로 evaluator-only 설명이 아님

### 3.3 Major weaknesses (추가 실험 대상)

#### W1. Recovery의 architectural tautology 위험
- Writing prompt가 Planning brief를 re-inject하면 Plan high → Write high는 설계상 예측 가능
- 논문이 이미 observational 증거( prompt 구조 + `P(Write✓\|Plan✓)=0.887` )를 제시
- **없는 것:** brief 제거 시 Writing Acc가 실제로 붕괴하는지 (interventional)

#### W2. Attribution ≠ personalization utility
- persona를 맞춘다고 해서 유용한 personalization인 것은 아님
- shuffled-actionable은 identity shell ≫ actionable donor를 보여 줌
- **없는 것:** stage Acc와 end-to-end personalization score 상관

#### W3. Single backbone / single benchmark
- 의도적으로 **안고 가기로 결정**
- re-injection ablation이 multi-backbone의 부분 대체재

#### W4. Diagnostic-only
- Search bottleneck 진단은 있으나, 고치면 좋아진다는 intervention 없음
- workshop에서는 optional

#### W5. Related work / presentation
- agent evaluation 문헌 확장, abstract 다이어트 등 → **실험 아님, writing 작업**

### 3.4 Medium / minor (실험 우선순위 낮음)
- character-budget confound (BM25/search-view가 부분 방어)
- domain n=12 exploratory overclaim 주의
- human attribution validation 없음 (비쌈, optional)
- ethics/impact statement 보강 (writing)

---

## 4. 기존 실험 확인 범위

### 4.1 확인한 것
| 출처 | 내용 |
|---|---|
| `paper/main.tex` | claim, tables, controls, limitations |
| `paper/analysis/contribution_insights_hardneg_v1.md` | primary freeze 수치 |
| `paper/analysis/README.md` | authoritative vs superseded protocol |
| `runs/confirmatory/` | matches_hardneg_v1, baselines, masking, GPT, N=2/5, search views |
| `runs/ablation/shuffled_actionable/` | generation-time control |
| `research-log/03 Experiments/Experiment Index.md` | EXP-008~016 completed |
| `next_experiment_priority.md` | “trajectory 존재는 이미 닫힘” 판단 |

### 4.2 확인하지 않은 것
- 120개 raw match JSON 전수 재집계
- billing dashboard 실지출 전수 검증
- → **artifact 존재 + analysis/논문 수치 일치** 수준까지 확인. 독립 통계 재현은 아님.

### 4.3 Completed experiments (권위 있는 것)

| ID | 내용 | 상태 |
|---|---|---|
| EXP-008 | contribution cross-condition / report-level analysis | completed |
| EXP-009 | Search queries-only vs snippets-only | completed |
| EXP-010 / 013 | candidate-derived identity masking | completed |
| EXP-012 | corrected per-GT Solar matching (primary) | completed |
| EXP-014 | GPT-5.4-nano matcher replication | completed |
| EXP-015 | shuffled-actionable generation control | completed |
| EXP-016 | N=2 / N=5 candidate-set-size sensitivity | completed |
| EXP-017 | Writing-only no-brief ablation (n=30 seed0) | **completed** |
| EXP-018 | Attribution–utility GPT-4o-mini judge (v1+v2, 120) | **completed** |
| EXP-019 | Equal char-budget Solar rematch (seed0, 3500) | **completed** |
| EXP-011 | actionable-only / identity-only | seed0 gate fail → confirmatory 제외 |

Primary freeze 수치 (hardneg_v1):

| Stage | Solar Acc@1 |
|---|---:|
| Planning | 0.808 |
| Search | 0.550 |
| Compression | 0.592 |
| Writing | 0.800 |

**이미 닫힌 질문:** trajectory가 이 파이프라인·프로토콜에서 재현 가능한가?  
**부분 닫힘 (2026-08-04):** re-injection 인과성(write-only n=30; residual Acc 0.833), attribution↔utility(약한 상관).  
**아직 열린 질문:** multi-backbone 일반화, equal-budget 위생, utility judge 품질.

---

## 5. 기존 contribution 분해

Rough weight (workshop paper 기준):

| 층 | 내용 | 비중 | 상태 |
|---|---|---:|---|
| C1 현상 발견 | dip-and-recovery + report-level 32→24 | ~45% | **완료** |
| C2 평가 규율 | hard-neg, BM25, bootstrap, quality, N-sens | ~20% | **완료** |
| C3 대안설명 차단 | masking, candidate prior, GPT κ | ~15% | **완료** |
| C4 Search 국소 해석 | queries vs snippets, URL overlap | ~8% | **완료** |
| C5 신호 종류 | shuffled-actionable (shell ≫ donor) | ~8% | **완료 (n=30 규모 작음)** |
| C6 메커니즘 | re-injection + write-only no-brief n=30 | ~6% | **완료 (modest Δ; residual Acc high)** |
| C7 utility 연결 | GPT judge 120 exploratory | ~3% | **완료 (약한/불안정 상관)** |

---

## 6. 제안 추가 실험 vs 기존 실험 (contribution ROI)

### 6.1 점수 기준
- **Δ-Science:** 새 claim / 새 사실 (0–10)
- **Δ-Defense:** 리뷰 방어력 (0–10)
- **중복도:** 기존 실험과 겹침 (높을수록 중복)

| 제안 실험 | Δ-Science | Δ-Defense | 중복도 | 판정 |
|---|---:|---:|---:|---|
| Writing **no-brief ablation** | 6–7 | 9 | 낮음 | **가장 추천** |
| Attribution ↔ **utility** 상관 | 5–7 | 8 | 낮음 | 추천 (결과 의존) |
| Equal **char-budget** rematch | 1–2 | 6 | 중 | 싸면 같이 |
| Search intervention pilot | 4–6 | 5 | 낮음 | optional |
| multi-backbone / LaMP | 7–8 | 7 | 낮음 | **스킵 결정** |

### 6.2 정직한 총평
- 제안 실험은 primary 120 + 현재 controls보다 **contribution 절대량이 작음**
- 성격은 “새 발견”보다 **리뷰 방어막 / 해석층**
- 이전 “P0 필수 3개” 표현은 과장 가능 → 아래가 수정된 표현:

| 표현 | 수정 |
|---|---|
| P0 필수 3개 | workshop 기준 **필수 0~1개**, 나머지 nice-to-have |
| equal budget almost required | 기여 낮음. 위생 control |
| utility nearly required | claim을 utility로 안 밀면 한계 문장으로도 버팀 |
| 없으면 Weak Accept | 과장 가능. **현재만으로도 weak/borderline 가능** |

### 6.3 실험별 상세

#### (A) Writing no-brief ablation — 최고 ROI
- **리뷰 공격:** re-injection이면 recovery는 당연하다
- **이미 있음:** prompt 구조, Plan×Write 2×2
- **추가가 주는 것:** brief 제거 시 Writing Acc 붕괴 여부 → observational → interventional
- **single backbone과 충돌 없음** (같은 파이프라인 내부 조작)
- **성공 시 claim:** recovery is largely architectural; residual Writing signal may remain
- **실패 시 claim:** re-injection is not the main driver (더 흥미로운 결과일 수도)

**설계 옵션**
1. **Write-only rewrite (권장, 저비용):** frozen plan/search/compress 재사용, Writing prompt에서 brief 제거 후 재생성
2. Full pipeline regen: 전 단계 재실행 (비싸고 불필요에 가까움)
3. (선택) shuffled-brief: 다른 persona brief 주입 (더 강한 인과)

**최소 규모:** n=15 (pilot)  
**권장 규모:** n=30 (10 groups × 3 personas, seed0)  
**이상적:** n=45–60

**보고 지표**
- Writing Acc@1 (full vs no-brief)
- `P(Write✓ | Plan✓)` 변화
- Plan✓Search✗ 중 Writing recovery rate 변화

#### (B) Attribution ↔ personalization utility — so-what 보강
- **리뷰 공격:** recoverability가 personalization 성공을 말하나?
- **이미 있음:** claim boundary 문장, shuffled-actionable
- **추가가 주는 것:** 120 final report에 대한 personalization score와 Writing/stage Acc 상관
- generation 불필요 (기존 artifact 재사용)

**설계**
- PDR-Eval 스타일 LLM judge (content / presentation personalization 등)
- GPT로 채점 (Solar 아님 → 현금 소액)
- 분석:
  1. Writing correct vs incorrect의 score 차이
  2. recovered vs non-recovered score 차이
  3. (가능하면) always-correct / never-correct 비교

**해석**
- 양의 상관 → attribution이 utility proxy로 일부 방어
- 무상관/음 → “diagnostic of recoverability, not utility”로 포지션 선명화 (shuffled-actionable과 정합)

#### (C) Equal character-budget — 위생
- **리뷰 공격:** Search 3.5k vs Writing 8k
- **이미 있음:** BM25 dip 재현, queries-only 결과
- 전 stage 동일 char budget으로 Solar rematch
- **과학 기여 낮음, Solar 무료면 거스름돈**

#### (D) Search intervention — optional
- persona-aware query injection / re-rank pilot
- diagnostic → constructive 전환
- pilot 15면 incomplete contribution 위험 → **후순위**

#### (E) 스킵
| 실험 | 이유 |
|---|---|
| multi-backbone | 결정적으로 스킵; no-brief가 부분 대체 |
| LaMP-QA 90 | 비용 대비 workshop 필수 아님 |
| 3rd generation seed | seed0/1 이미 stable |
| actionable/identity-only seed1 | gate fail 규율 유지 |
| human attribution 대규모 | 비쌈; optional 소표본만 |

---

## 7. 비용 추정 (Solar = ₩0)

### 7.1 실측 앵커
| 항목 | 관측 |
|---|---|
| 생성 tokens / report | 평균 ~156k (120 reports 합 18.7M) |
| Serper queries / report | 시도 ~6.9 |
| Solar matcher prompt | stage당 ~27.4k chars |
| DEC-001 | hard cap 10만원, 초기 projection ~7만원 |
| Solar | **현금 무시** (credit) |
| 현금 | **Gemini + GPT만** |

환율 가정: 1 USD ≈ 1,380 KRW  
Gemini 단가는 Flash 밴드 proxy (공식 3.6 단가 불명확). thinking token 시 ×2~3 가능.

### 7.2 실험별 현금

#### Writing no-brief (Gemini)

| 방식 | n | 현실적 | thinking 많으면 |
|---|---:|---:|---:|
| Write-only | 15 | ~1–3천원 | ~3–7천원 |
| Write-only | **30** | **~2–5천원** | ~5–1.1만원 |
| Write-only | 45–60 | ~3–9천원 | ~1–2만원 |
| Full pipeline + Serper | 30 | ~4–8천원 | ~1–2만원 |
| Full pipeline + Serper | 45 | ~5–1.3만원 | ~1.5–3만원 |

#### Utility judge (GPT only)

| 설정 | calls | 예상 |
|---|---:|---:|
| 1 score × 120 | 120 | ~200–700원 |
| **2 scores × 120** | 240 | **~400–1,500원** |
| 4 scores × 120 | 480 | ~700–3,000원 |

#### Equal-budget rematch
- Solar only → **현금 0원**

### 7.3 패키지 현금 합계

| 패키지 | 구성 | 현금 (현실적) | 안전 상한 |
|---|---|---:|---:|
| **A 최소** | write-only 15 + GPT util 120 | **1–4천원** | ~8천원 |
| **B 권장** | write-only **30** + GPT util 240 + equal(Solar) | **3–7천원** | **~1.2만원** |
| **C 넉넉** | fullgen 45 + GPT util 240 + equal | 1–1.5만원 | ~3만원 |

→ Solar 제외 시 **B는 hard cap 대비 사실상 거스름돈**.

### 7.4 비용 대비 우선순위
```text
fullgen 60          비쌈, 필수는 아님
fullgen 30          중간
write-only 30       ★ 가성비 1위 (Gemini)
utility judge 120   ★ 가성비 공동 1위 (GPT, 매우 저렴)
equal-budget        현금 0 (Solar)
```

---

## 8. 실행 권장안

### 8.1 권장: Package B

1. **Writing-only no-brief ablation, n=30** (seed0, 10 groups × 3 personas)
   - frozen artifacts의 research brief를 Writing prompt에서 제거
   - Solar로 Writing stage (및 필요 시 전체 trajectory 비교용 메타) matching
2. **GPT utility judge, 120 reports × 2 scores**
   - content personalization + presentation personalization (또는 PDR-Eval 부분집합)
3. **Equal char-budget Solar rematch, seed0 (240 calls)**
   - 현금 0, 리뷰 한 줄 방어

### 8.2 실행 순서
```text
1. equal-budget (Solar, 즉시, 현금 0)
2. utility judge (GPT, 기존 120, 저비용)
3. write-only no-brief (Gemini, 핵심)
4. (optional) fullgen no-brief if write-only 결과가 애매할 때만
```

### 8.3 Stop rules
- write-only n=15 pilot에서 Writing Acc가 full 대비 크게 안 떨어지면 → n=30 확장 또는 shuffled-brief 검토
- utility 상관이 0에 가까워도 실패 아님 → claim boundary 강화로 사용
- 현금이 예상 상한(B ~1.2만원) 넘기 시작하면 fullgen/C 패키지 금지

### 8.4 논문 서사 재정렬 (실험 후)
1. Search에서 persona recoverability 붕괴 (기존)
2. Writing recovery는 **brief re-injection에 크게 의존** (신규 ablation)
3. recoverability는 personalization utility와 **부분적으로만 겹침** (신규 judge)
4. 따라서 DRA-PULSE = end-to-end 품질 점수가 아니라  
   **multi-step agent persona-signal localization diagnostic**

---

## 9. 추가 실험 없이 유지/약화할 claim

### 유지 가능 (현재 증거로)
- stage-wise attribution task 정의
- this pipeline에서 dip-and-recovery 관측
- report-level loss-and-recovery (32→24)
- Solar–BM25 gap은 Plan/Write에 집중
- masking 후에도 trajectory shape 유지
- GPT matcher가 shape 복제
- N=2/3/5에서도 shape 유지
- shuffled-actionable에서 shell > donor at Plan/Write
- **attribution ≠ utility** (한계로 명시)

### 약화하거나 hedging 유지할 것
- “Writing recovery mechanism = re-injection” → **partly / consistent with** 수준 (ablation 전)
- domain-level 패턴 → exploratory only
- Search가 “harmful”하다는 함의 → recoverability loss ≠ utility loss
- general DRA property → **this architecture characterisation**

### ablation/utility 후에 강화 가능
- re-injection causal role
- diagnostic vs utility 관계의 실증

---

## 10. Writing-only 작업 (실험 아님, 같이 하면 좋음)

실험 예산과 무관하게 원고에서 할 일:

1. [x] Abstract 다이어트 (숫자 과밀 해소)
2. [x] Contribution bullet을 3개로 압축  
   - task formalization  
   - report-level loss/recovery  
   - architectural recovery path (+ controls)
3. [x] Related work를 agent evaluation / process supervision 쪽으로 확장
4. [~] shuffled-actionable을 main narrative에 더 가까이 (이미 Analysis 표 있음; intro 재배치 optional)
5. [x] Ethics / broader impact 짧은 단락
6. [ ] Table budget(120 only) 정보량 낮으면 축소/병합 (layout 보고 optional)

---

## 11. 최종 의사결정 체크리스트

- [x] single backbone 유지
- [x] Solar 비용 무시
- [x] Package B 핵심 실행 (write-only **30** + GPT util 120 + equal-budget seed0)
- [x] write-only n=15 pilot → n=30 확장 완료
- [x] utility judge v1 붕괴 → **v2 재실행** (identical axes 60.8%; 약한 상관 유지)
- [x] no-brief prompt / output dir: `runs/ablation/nobrief_writeonly/`
- [x] API 실행 완료 (Gemini+GPT 현금 소액; Solar equal-budget 현금 0)
- [x] `nobrief_and_utility_results.md` + `main.tex` Analysis 반영
- [x] equal-budget Solar rematch seed0 n=60 (3500 chars; dip 유지)
- [x] utility v2 + **proxy** spot-check n=20 (author-side; not independent human)
- [x] abstract diet / contribution 3-bullet / related-work / ethics
---

## 12. 관련 파일

| 파일 | 역할 |
|---|---|
| `paper/main.tex` | 원고 |
| `paper/analysis/contribution_insights_hardneg_v1.md` | primary freeze 합성 |
| `paper/analysis/next_experiment_priority.md` | 이전 우선순위 (Search-view/shuffled 시점) |
| `paper/analysis/shuffled_actionable_control.md` | shell vs donor |
| `paper/analysis/search_view_control_hardneg_v1.md` | queries vs snippets |
| `runs/confirmatory/matches_hardneg_v1/` | primary Solar matches |
| `research-log/02 Decisions/DEC-001 100000 KRW hard cap.md` | 예산 cap |
| `research-log/03 Experiments/Experiment Index.md` | 실험 인덱스 |

---

## 13. Changelog

| Date | Note |
|---|---|
| 2026-08-04 | 초안: REALM 비판 리뷰 + 기존 실험 대조 + 추가 실험 ROI + Solar=0 현금 추정 + Package B 권장 |
| 2026-08-04 | Package B 핵심 실행: no-brief n=15→**30**, utility judge 120; 결과 `nobrief_and_utility_results.md`; equal-budget 보류 |
| 2026-08-05 | equal-budget seed0 완료 (dip 유지); utility v2 재실행; human spot-check 템플릿; abstract/ethics/contribution polish |
| 2026-08-05 | REALM framing lock: title→recoverability; abstract slim; Results 위계 (aggregate→report-level→robustness); symmetric 표; shuffled-actionable as metric boundary; conclusion 3-paragraph |
