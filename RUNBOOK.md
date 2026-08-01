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

## 2. SHA-256 순서로 Solar 재매칭

기존 `runs/confirmatory/matches/`는 보존한다. 수정된 matcher 결과는 새
디렉터리에 저장한다.

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
