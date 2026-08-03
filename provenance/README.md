# Experiment provenance

`runs/`와 원본 `data/`는 크기와 개인정보·라이선스 가능성 때문에 일반 Git
추적 대상에서 제외한다. 대신 다음 명령으로 로컬 실험 산출물의 체크섬과
inventory를 갱신한다.

```bash
python scripts/build_provenance.py
```

생성 파일:

- `experiment_files.sha256`: manifest, 코드, 논문, pilot/confirmatory 결과 체크섬
- `run_inventory.json`: Git HEAD, dirty 여부, seed별 artifact와 match 개수

이 파일은 백업의 무결성을 검증하지만 백업 자체는 아니다. `runs/pilot/`,
`runs/confirmatory/`, `runs/ablation/`, `manifest.json`, `provenance/`를
암호화된 비공개 저장소나 외장 저장장치에 함께 복사한 뒤 체크섬을 다시
검증해야 한다.

```bash
shasum -a 256 -c provenance/experiment_files.sha256
```

API 키가 있는 `.env` 파일은 체크섬과 백업 목록에서 제외한다.

추가 오프라인 재현 자료:

- `lamp_qa_run_plan.json`: 15 queries × 3 profiles × 2 seeds의 90-run
  LaMP-QA 계획과 source/profile/prompt 해시
- `sigir_pdr_sanity_manifest.json`: 공식 SIGIR 2026 PDR report 5개를
  특정 upstream commit과 파일 SHA-256으로 고정한 manifest
- `sigir_pdr_sanity_summary.json`: 위 5개 report의 길이·형식 기술통계와
  해석 한계
- `candidate_sensitivity_plan.json`: 동일 actionable-Jaccard ranking의
  prefix로 구성한 confirmatory N=2/3/5 candidate set. N=3 manifest
  exact match 60/60을 강제한다.
- `hardneg_rerun_estimate.json`: corrected per-GT candidate protocol에서
  full, masked, Search views를 모두 유지할 때의 Solar estimate-only call
  수와 prompt character 수. 실제 API 실행 기록이 아니다.

기존 `runs/confirmatory/matches_sha256/`의 candidate protocol 검사는
`runs/confirmatory/candidate_protocol_audit.json`에 있다. Audit 결과가
fail이면 해당 결과를 frozen hard-negative 결과로 사용하지 않는다.

LaMP plan과 SIGIR summary는 각각 다음 명령으로 외부 API 없이 재생성한다.

```bash
python scripts/lamp_batch_runner.py --seed all
python scripts/analyze_sigir_sanity.py
```
