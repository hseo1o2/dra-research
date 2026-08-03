---
type: experiment
id: EXP-010
date: 2026-08-03
status: completed
project: DRA-personalization-attribution
rq: RQ2
---

# EXP-010 Corrected two-seed identifier masking

## Pre-run lock

- Objective: identifier masking robustness를 두 generation seed로 확장하고,
  v2 Search schema의 `sources` 누락 결함을 수정한 artifact로 기존 seed-0
  결과를 대체한다.
- Hypothesis: corrected identifier masking 후에도 Planning→Search
  loss-and-recovery ordering이 유지되고 original 대비 stage effect는 작다.
- Success / failure criteria: 120 artifacts, 480 run-stage pairs, 동일
  candidate set/order, parser failure 0, task-cluster paired CI 보고.
- Dataset manifest SHA-256:
  `8110d1b3656fa5ba021f7b1bd053a92a11922c4efecd8d43d552e80cda4ad2a9`
- Code commit: `14b08031fac8a1e2396317bd09b57e70cba405cb`
  (dirty worktree; masker fix는 미커밋)
- Model snapshot: Upstage API model ID `solar-pro`, temperature 0,
  structured tool output
- Seed / replicate IDs: generation seed 0·1, 120 reports
- Candidate construction: frozen N=3 hard-negative sets; SHA-256
  run-stage shuffle
- Mask labels: PERSON, ORG, GPE, NORP, FAC; plan/query/source
  title+snippet/compression/report text
- Dry estimate: 480 calls, 13,106,563 prompt characters
- Expected cost ceiling: 2,000원 including VAT. Conservative bound assumes
  at most 2 characters/input token and 500 output tokens/call.
- Input: `runs/confirmatory/masked_sha256/`
- Output: `runs/confirmatory/masked_sha256/matches/`

## Execution

- Started: 2026-08-03
- Completed: 2026-08-03
- Run ID: corrected masking, PDR seed 0·1
- Retries / missing: 0 / 0
- Actual token usage: Unverified (matcher records prompt characters)
- Serper successful queries: 0
- Actual cost: billing dashboard 미확인; EXP-009와 합친 신규 720 calls의
  기록량은 prompt 18,932,042자, reasoning 527,679자이며 list-price
  character estimate 약 1,200원, 보수적 상한 약 2,500원 (Unverified)

## Observed results

- Corrected masked trajectory:
  Planning 0.725, Search 0.550, Compression 0.608, Writing 0.725.
- Planning→Search -0.175, task-bootstrap CI `[-0.283, -0.075]`.
- Search→Writing +0.175, CI `[0.058, 0.292]`.
- Original 대비 masked effect:
  Planning -0.008 `[-0.033, 0.017]`,
  Search +0.008 `[-0.042, 0.067]`,
  Compression 0.000 `[-0.042, 0.042]`,
  Writing +0.017 `[-0.017, 0.050]`.
- 120 reports의 480 run-stage pair에서 candidate set, ground truth,
  SHA-256 candidate order가 모두 일치한다.

## Anomalies

- 기존 `scripts/mask_identifiers.py`는 Search results를 `results`에서만
  찾아 실제 v2 artifact의 `sources` title/snippet을 마스킹하지 않았다.
- 기존 seed-0 masking 수치와 해당 manuscript claim은 이 실행 결과로
  대체해야 한다.

## Interpretation

- 두 seed와 실제 source title/snippet masking으로 확장해도
  dip-and-recovery shape은 유지된다.
- masking effect의 절댓값은 최대 0.017이고 모든 CI가 0을 포함하므로,
  관측된 attribution을 common named-entity span만으로 설명하기 어렵다.
- NER가 포착하지 못한 lexical shortcut 가능성은 남는다.

## Decision / Next step

- corrected two-seed 결과가 기존 결론을 유지하는지 확인한 뒤 논문과
  EXP-008 contribution synthesis를 수정한다.

## Artifacts

- Code: `scripts/mask_identifiers.py`
- Masked artifacts: `runs/confirmatory/masked_sha256/`
- Matches: `runs/confirmatory/masked_sha256/matches/`
- Analysis: `runs/confirmatory/analysis_masked_sha256/`
