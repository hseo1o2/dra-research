---
type: experiment
id: EXP-013
date: 2026-08-03
status: completed
project: DRA-personalization-attribution
rq: RQ1, RQ2
---

# EXP-013 Candidate prior and strong identity masking

## Pre-run lock

- Objective: per-GT candidate construction prior를 artifact-free하게
  측정하고, NER보다 강한 candidate-derived identity masking 후에도
  stage trajectory가 유지되는지 검증한다.
- Hypothesis: candidate prior는 absolute Acc@1에 영향을 줄 수 있지만
  stage ordering을 설명하지 못하며, direct identity phrase 제거 후에도
  Planning→Search 하락과 Writing recovery가 유지된다.
- Success / failure criteria: candidate-prior artifact 생성; masked artifact
  120/120; Solar 480 decisions; candidate audit 120/120; full/masked order
  480/480 일치.
- Dataset manifest SHA-256:
  `8110d1b3656fa5ba021f7b1bd053a92a11922c4efecd8d43d552e80cda4ad2a9`
- Code commit: `14b08031fac8a1e2396317bd09b57e70cba405cb`
  (dirty worktree)
- Model snapshot: `solar-pro`
- Seed / replicate IDs: generation seeds 0 and 1, 각 60 reports
- Candidate construction: frozen per-GT
  `attribution_candidate_set_n3`; task-shared cohort는 secondary sensitivity
- Expected query/token/cost ceiling: Solar 480 calls, prompt characters
  13,148,222. 실제 token과 청구액은 output에 기록되지 않음.

## Execution

- Started: 2026-08-03
- Completed: 2026-08-03 18:23 KST
- Run ID: PDR confirmatory identity-masked, seeds 0 and 1
- Retries / missing: final missing 0; retry별 세부 횟수 Unverified
- Actual token usage: Unverified
- Serper successful queries: 해당 없음
- Actual cost: Unverified; Upstage billing 확인 필요

## Observed results

- Candidate-only centrality: 27/60 = 0.450, task-cluster bootstrap 95% CI
  [0.333, 0.567].
- Task-shared protocol trajectory: 0.733/0.542/0.608/0.708.
- Strong mask protocol: spaCy PERSON/ORG/GPE/NORP/FAC + 후보 3명의
  name/age/occupation/education/residence/family identity-field phrases.
- Identity phrase replacements:
  Planning 187, Search 654, Compression 1,649, Writing 779.
- Masked Solar Acc@1:
  Planning 0.725, Search 0.558, Compression 0.575, Writing 0.783.
- Masked-minus-full:
  - Planning -0.083, 95% CI [-0.150, -0.025].
  - Search +0.008, [-0.050, 0.075].
  - Compression -0.017, [-0.058, 0.025].
  - Writing -0.017, [-0.050, 0.017].
- Masked within-condition:
  - Planning→Search -0.167, [-0.258, -0.067].
  - Compression→Writing +0.208, [0.100, 0.308].
- Candidate audit 120/120 pass; full/masked candidate order 480/480 match.

## Anomalies

- NER false positive가 task-relevant organization/platform phrase도
  제거하므로 strong mask는 보수적이며 identity-only 조작이 아니다.
- Exact phrase masking은 paraphrased identity cue를 모두 제거하지 못한다.
- Solar token usage와 실제 청구액이 artifact에 저장되지 않는다.
- GPT-5.4-nano 240-call replication은 사용자 승인을 받았으나
  `OPENAI_API_KEY`가 environment에 없어 실행하지 못했다.

## Interpretation

- Inferred: candidate construction prior 때문에 absolute hard-negative
  Acc@1은 보수적으로 해석해야 한다.
- Inferred: 동일 trajectory가 task-shared 후보에서도 나타나므로
  candidate prior만으로 stage ordering을 설명할 수 없다.
- Inferred: direct identity phrase는 Planning recoverability 일부를
  설명하지만 later-stage accuracy와 Writing recovery를 설명하지 못한다.

## Decision / Next step

- Strong identity masking을 corrected primary의 paired shortcut control로
  논문에 포함한다.
- `benchmark`보다 `diagnostic framework/protocol` 표현을 유지한다.
- GPT replication은 key 연결 후 같은 240-call plan으로 재개한다.
- Search-view, LaMP, 추가 generation은 현재 우선순위에서 제외한다.

## Artifacts

- Candidate prior:
  `runs/confirmatory/analysis_candidate_prior/candidate_prior_summary.json`
- Mask audit:
  `runs/confirmatory/masked_identity_hardneg_v1/masking_audit_summary.json`
- Matches:
  `runs/confirmatory/masked_identity_hardneg_v1/matches/`
- Paired analysis:
  `runs/confirmatory/analysis_masked_identity_hardneg_v1/`
- Key SHA-256:
  - candidate prior:
    `1e9c5bc86978eb067f06538690a1468b921d617e1824322c1b635d753f802594`
  - masking audit:
    `dc77c637d2cc6299362e6549f0fbd8c7a47c5bcab29291215ceeb2acc952d278`
  - masked match summary:
    `2e3dfe457ad33e60dfd4c8512678bbe96dde8249aa3646aecbfec8c1ad222f97`
  - paired summary:
    `77908030b6342f2fc777e8e32c612f6fccbea508ec2b98440924e205b8193f57`

