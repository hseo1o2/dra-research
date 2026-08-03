# DRA execution runbook

실제 API 실행은 사용자가 터미널에서 명시적으로 수행한다. 같은 seed의
`batch_runner.py --execute` 프로세스를 동시에 두 개 실행하지 않는다.

## 1. Confirmatory seed 1 생성

이미 실행 중이면 아래 명령을 다시 실행하지 않는다.

```bash
python scripts/batch_runner.py \
  --split confirmatory \
  --seed 1 \
  --output-dir runs/confirmatory \
  --execute \
  --resume
```

중단되면 같은 명령을 다시 실행한다. schema-valid artifact는 `--resume`이
건너뛴다.

완료 후 API 없이 전체 60개 summary를 다시 집계한다.

```bash
python scripts/batch_runner.py \
  --split confirmatory \
  --seed 1 \
  --output-dir runs/confirmatory \
  --summarize-only
```

필수 artifact가 누락된 기술적 실패만 재시도할 때는 원본과 retry output을
분리하고, 정확한 run ID를 반복 지정한다. content 품질이나 attribution
결과를 보고 retry 대상을 고르지 않는다.

```bash
DRA_ALLOW_EXTERNAL_API=1 python scripts/batch_runner.py \
  --split confirmatory \
  --seed 1 \
  --output-dir runs/confirmatory/retries/<retry-name> \
  --run-id <exact-run-id> \
  --execute
```

## 2. SHA-256 순서로 Solar 재매칭

기존 `runs/confirmatory/matches/`는 보존한다. 수정된 matcher 결과는 새
디렉터리에 저장한다.

> **2026-08-03 protocol correction:** 기존
> `runs/confirmatory/matches_sha256/`는 deterministic shuffle은
> 충족하지만 task-level `personas_n3`를 사용했다. frozen 설계의 per-GT
> `attribution_candidate_set_n3`와 120건 중 114건이 다르므로 논문
> hard-negative 결과로 사용하지 않는다. 아래 예전 명령은 provenance
> 참고용이며, 최종 결과는 반드시 `matches_hardneg_v1/`에 생성한다.

API를 실제 호출하기 전 estimate-only:

```bash
python scripts/llm_matcher.py \
  --batch-dir runs/confirmatory \
  --output-dir runs/confirmatory/matches_hardneg_v1 \
  --stage all \
  --estimate-only
```

실제 실행은 별도 비용 승인 후 `--estimate-only` 대신 seed별 실행 옵션을
사용한다. 기존 디렉터리를 덮어쓰지 않는다.

Corrected non-LLM baseline은 외부 API 없이 다음처럼 생성한다. Embedding
model은 network metadata check를 막기 위해 local-cache offline mode로
실행한다.

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python scripts/baseline_matcher.py \
  --batch-dir runs/confirmatory \
  --artifact-dir runs/confirmatory \
  --output-dir runs/confirmatory/baselines_hardneg_v1_seed0 \
  --method all \
  --seed 0

HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python scripts/baseline_matcher.py \
  --batch-dir runs/confirmatory \
  --artifact-dir runs/confirmatory \
  --output-dir runs/confirmatory/baselines_hardneg_v1_seed1 \
  --method all \
  --seed 1
```

각 seed의 180개 match file이 frozen candidate를 사용하는지 검증한다.

```bash
python scripts/audit_candidate_protocol.py \
  --match-dir runs/confirmatory/baselines_hardneg_v1_seed0 \
  --output runs/confirmatory/baselines_hardneg_v1_seed0/candidate_protocol_audit.json

python scripts/audit_candidate_protocol.py \
  --match-dir runs/confirmatory/baselines_hardneg_v1_seed1 \
  --output runs/confirmatory/baselines_hardneg_v1_seed1/candidate_protocol_audit.json
```

seed 0:

```bash
python scripts/llm_matcher.py \
  --batch-dir runs/confirmatory \
  --output-dir runs/confirmatory/matches_sha256 \
  --stage all \
  --seed 0
```

seed 1 생성이 모두 끝난 후:

```bash
python scripts/llm_matcher.py \
  --batch-dir runs/confirmatory \
  --output-dir runs/confirmatory/matches_sha256 \
  --stage all \
  --seed 1
```

두 seed를 합친 summary는 API 호출 없이 기존 match 파일을 읽어 만든다.

```bash
python scripts/llm_matcher.py \
  --batch-dir runs/confirmatory \
  --output-dir runs/confirmatory/matches_sha256 \
  --stage all \
  --resume
```

## 3. 최종 검증과 provenance

```bash
pytest -q

python scripts/batch_runner.py \
  --split confirmatory \
  --seed 0 \
  --output-dir runs/confirmatory \
  --summarize-only

python scripts/batch_runner.py \
  --split confirmatory \
  --seed 1 \
  --output-dir runs/confirmatory \
  --summarize-only

python scripts/build_provenance.py

shasum -a 256 -c provenance/experiment_files.sha256
```

`runs/pilot/`, `runs/confirmatory/`, `manifest.json`, `provenance/`를
오프디바이스 비공개 저장소에 복사한 후 체크섬 검증을 다시 수행한다.

## 4. 통계 분석과 논문 표 산출

corrected hard-negative matcher 결과가 존재하는 시점에 다음 명령을
실행한다. 외부 API를
호출하지 않는다.

```bash
python scripts/analyze_matches.py \
  --match-dir runs/confirmatory/matches_hardneg_v1 \
  --run-dir runs/confirmatory \
  --output-dir runs/confirmatory/analysis_sha256
```

stage별 정확도, task-cluster bootstrap 95% CI, 인접 stage paired 비교,
seed variance, run 분포, persona confusion, completeness sensitivity와
LaTeX macro 파일이 생성된다.

논문용 vector figure와 PNG preview:

```bash
python scripts/plot_paper_figures.py \
  --analysis-dir runs/confirmatory/analysis_sha256 \
  --output-dir paper/figures
```

Candidate-derived identity masking은 NER와 후보 3명의 frozen identity
field phrase를 함께 제거한다. Artifact 생성과 산정은 외부 API를
호출하지 않는다.

```bash
python scripts/mask_identifiers.py \
  --artifact-dir runs/confirmatory \
  --output-dir runs/confirmatory/masked_identity_hardneg_v1 \
  --canonical-output-names \
  --identity-derived

python scripts/llm_matcher.py \
  --batch-dir runs/confirmatory/masked_identity_hardneg_v1 \
  --artifact-dir runs/confirmatory/masked_identity_hardneg_v1 \
  --output-dir runs/confirmatory/masked_identity_hardneg_v1/matches \
  --stage all \
  --estimate-only
```

실제 matcher는 별도 승인 후 `--estimate-only`를 제거하고 `--resume`을
추가한다. 완료 후 다음 network-free 분석을 실행한다.

```bash
python scripts/analyze_masked_control.py \
  --original-dir runs/confirmatory/matches_hardneg_v1 \
  --masked-dir runs/confirmatory/masked_identity_hardneg_v1/matches \
  --output-dir runs/confirmatory/analysis_masked_identity_hardneg_v1
```

현재 full과 strong identity-masked의 SHA-256 candidate order는 두
seed의 480/480 run-stage pairs에서 일치한다.

Candidate-construction prior와 symmetric task-shared sensitivity:

```bash
python scripts/analyze_candidate_prior.py
```

Corrected Search artifact view control은 기존 task-cohort 결과 디렉터리를
절대 재사용하지 않는다. 아래 산정 명령은 외부 API를 호출하지 않는다.

```bash
python scripts/llm_matcher.py \
  --batch-dir runs/confirmatory \
  --artifact-dir runs/confirmatory \
  --output-dir runs/confirmatory/search_view_queries_hardneg_v1_matches \
  --stage search \
  --search-view queries \
  --estimate-only

python scripts/llm_matcher.py \
  --batch-dir runs/confirmatory \
  --artifact-dir runs/confirmatory \
  --output-dir runs/confirmatory/search_view_snippets_hardneg_v1_matches \
  --stage search \
  --search-view snippets \
  --estimate-only
```

2026-08-03 estimate는 각 view 120 calls, 합계 240 calls와
5,846,315 prompt characters이다. 실제 matcher는 별도 승인 뒤
`--estimate-only`를 제거하고 `--resume`을 추가한다. 두 view가 모두
완료된 뒤에만 다음 network-free 분석을 실행한다.

```bash
python scripts/analyze_search_views.py
```

Full seed 0·1의 within-persona cross-seed search stability와
between-persona same-seed overlap 비교:

```bash
python scripts/analyze_source_stability.py
```

이 분석은 외부 API를 호출하지 않는다. URL과 query Jaccard를 task 단위로
집계하고 within-minus-between 차이에 task bootstrap CI를 적용한다.

## 5. Generation-time shortcut ablation

먼저 profile wiring을 API 없이 검증한다.

```bash
python scripts/audit_ablation_profiles.py

python scripts/batch_runner.py \
  --split confirmatory \
  --condition actionable_only \
  --seed 0 \
  --output-dir runs/ablation/actionable_only

python scripts/batch_runner.py \
  --split confirmatory \
  --condition identity_only \
  --seed 0 \
  --output-dir runs/ablation/identity_only

python scripts/evaluate_ablation_generation_gate.py
```

마지막 명령은 DEC-006의 generation sub-gate만 판정하며 외부 API를
호출하지 않는다. `seed1_authorized_by_this_gate`는 항상 false다. Gate가
통과해도 seed 1 또는 matcher 실제 실행에는 별도 사용자 승인이 필요하다.

`DEC-006` gate에 따라 seed 0의 두 condition을 먼저 실행한다. 아래 두
명령은 Gemini와 Serper API를 실제 호출한다.

```bash
DRA_ALLOW_EXTERNAL_API=1 python scripts/batch_runner.py \
  --split confirmatory \
  --condition actionable_only \
  --seed 0 \
  --output-dir runs/ablation/actionable_only \
  --execute \
  --resume

DRA_ALLOW_EXTERNAL_API=1 python scripts/batch_runner.py \
  --split confirmatory \
  --condition identity_only \
  --seed 0 \
  --output-dir runs/ablation/identity_only \
  --execute \
  --resume
```

두 condition 모두 15/15 schema-valid이고 비용 gate를 통과한 뒤에만
`--seed 1`로 반복한다. Ablation run ID의 condition prefix는 matcher
candidate shuffle key에서 제외되므로 full condition과 후보 순서가 같다.

생성 중에는 아래 명령으로 현재 상태를 확인할 수 있다. 외부 API는 호출하지
않으며, 15/15 완료·schema valid·success criteria 충족·ledger 오류 0이
아니면 종료 코드 1을 반환한다.

```bash
python scripts/analyze_generation_ablation.py \
  --quality-only \
  --seed-count 1
```

Seed-0 quality gate가 통과한 뒤 matcher 비용을 먼저 산정한다. 다음 두
명령도 외부 API를 호출하지 않는다.

```bash
python scripts/llm_matcher.py \
  --batch-dir runs/ablation/actionable_only \
  --artifact-dir runs/ablation/actionable_only \
  --output-dir runs/ablation/actionable_only/matches \
  --stage all \
  --estimate-only

python scripts/llm_matcher.py \
  --batch-dir runs/ablation/identity_only \
  --artifact-dir runs/ablation/identity_only \
  --output-dir runs/ablation/identity_only/matches \
  --stage all \
  --estimate-only
```

산정값을 검토하고 실제 matcher 호출을 승인한 뒤에만 `--estimate-only`를
`--resume`으로 바꿔 실행한다. 두 condition의 matcher가 모두 끝나면
candidate set/order와 paired denominator를 강제 검증하면서 seed-0 gate
결과를 생성한다.

```bash
python scripts/analyze_generation_ablation.py
```

Seed 1까지 완료한 최종 분석에서는 먼저 `--quality-only --seed-count 2`를
실행하고, matcher 두 조건을 `--seed 1 --resume`으로 실행한 뒤 같은 분석
명령을 다시 실행한다. 결과는
`runs/ablation/analysis/generation_ablation_summary.json` 및 CSV 두 개에
저장된다. Seed-0 결과는 기술적 gate이며 논문 claim에 사용하지 않는다.

## 6. 추가 replication 작업

### GPT-5.4-nano secondary matcher

아래 명령은 seed-0 reference 60 reports의 4개 stage prompt를 산정만 하며
외부 API를 호출하지 않는다.

```bash
python scripts/llm_matcher.py \
  --batch-dir runs/confirmatory \
  --artifact-dir runs/confirmatory \
  --output-dir runs/confirmatory/gpt54nano_seed0_matches \
  --stage all \
  --seed 0 \
  --model gpt-5.4-nano-2026-03-17 \
  --base-url https://api.openai.com/v1 \
  --estimate-only
```

2026-08-03에 1-call smoke test 후 seed-0 240 matcher calls를 완료했다.
실제 main-run prompt 합계는 6,588,904 characters이며 결과 60개는
`runs/confirmatory/gpt54nano_seed0_matches/`에 저장되어 있다. 실행 당시
matcher가 provider token usage를 직렬화하지 않아 정확한 token/billing은
OpenAI billing dashboard에서만 확인할 수 있다. 이후 호출부터는 각
match row에 input/output/total tokens와 response ID를 저장한다.

240개 결과와 corrected Solar의 candidate set/order는 모두 일치한다.
분석 결과는
`runs/confirmatory/analysis_matcher_agreement_hardneg_v1/`에 저장되며,
전체 agreement는 0.783, Cohen's kappa는 0.763이다.

```bash
python scripts/analyze_matcher_agreement.py
```

### LaMP-QA 90-run 계획 검증

다음 명령은 15 queries × 3 candidate profiles × 2 seeds = 90개의 실행
계획만 만들며 외부 API를 호출하지 않는다.

```bash
python scripts/lamp_batch_runner.py --seed all
```

계획은 `provenance/lamp_qa_run_plan.json`에 저장된다. 각 run에는 source,
profile, prompt SHA-256이 포함되며 profile 본문은 계획 파일에 복제하지
않는다.

실제 LaMP 생성은 PDR seed 1 프로세스가 완전히 끝난 뒤 seed별로 실행한다.
실행기는 실수로 동시 실행하지 않도록 `--acknowledge-pdr-finished`를
요구하며, PDR과 같은 global query ledger를 사용한다.

```bash
DRA_ALLOW_EXTERNAL_API=1 python scripts/lamp_batch_runner.py \
  --seed 0 \
  --execute \
  --acknowledge-pdr-finished \
  --resume
```

seed 1도 동일하게 실행하되 `--seed 1`을 사용한다. 실제 API 실행은
사용자가 명시적으로 수행한다.

### SIGIR 2026 PDR 5-report sanity check

다음 명령은 공식 저장소의 공개 report 폴더 5개를 완전 열거하고 파일
해시와 기술통계를 재생성한다. 외부 API를 호출하지 않는다.

```bash
python scripts/analyze_sigir_sanity.py
```

산출물은 `provenance/sigir_pdr_sanity_manifest.json`과
`provenance/sigir_pdr_sanity_summary.json`이다. 이는 format/length
sanity check일 뿐이며 stage attribution 또는 generalization 검증으로
사용하지 않는다.

## 7. Paper PDF build and QA

```bash
tectonic paper/main.tex \
  --outdir output/pdf \
  --keep-logs \
  --keep-intermediates
```

최종 파일은 `output/pdf/main.pdf`이고, 현재 6-page anonymous ACL review
build의 시각 검수 기록은 `paper/PDF_QA.md`에 있다. Manuscript 또는
figure가 바뀌면 compile, 전 페이지 raster inspection, anonymity scan을
반복한다.
