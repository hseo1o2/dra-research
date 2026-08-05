# DRA-PULSE: Tracing Persona Recoverability Across Stages of a Deep Research Agent

Code and data for the paper **"DRA-PULSE: Tracing Persona Recoverability Across Stages of a Deep Research Agent"** (REALM @ EMNLP 2026).

## Overview

DRA-PULSE is a diagnostic framework for N-way stage-wise persona attribution in multi-stage Deep Research Agent (DRA) pipelines. Given artifacts produced at each pipeline stage (Planning → Search → Compression → Writing), DRA-PULSE measures whether an LLM evaluator can recover which of N candidate personas generated each artifact — revealing where persona signal is preserved or lost.

Key finding: a dip-and-recovery trajectory (Planning: 0.808 → Search: 0.550 → Compression: 0.592 → Writing: 0.800) where Search and Compression artifacts shed persona signal and Writing recovers it via brief re-injection.

## Repository Structure

```
scripts/
  llm_matcher.py              # Core N-way Solar Pro / GPT-5.4-nano matcher
  batch_runner.py             # DRATracer artifact generation pipeline
  candidate_protocol.py       # Hard-negative candidate set construction
  baseline_matcher.py         # BM25, embedding, random baselines
  run_*.py                    # Shortcut control experiments
  analyze_*.py                # Analysis and figure generation
  compute_ablation_cis.py     # Task-cluster bootstrap CI computation

runs/confirmatory/
  matches_hardneg_v1/         # Primary Solar Pro match results (both seeds)
  gpt54nano_seed*/            # GPT-5.4-nano replication matches
  baselines_hardneg_v1_*/     # BM25, embedding, random baseline results
  masked_identity_hardneg_v1/ # Artifact-side identity-masked artifacts
  matches_candidate_profile_masked/   # Candidate-side masking control
  matches_dual_masked/        # Dual-masked control (both sides)
  matches_prompt_no_background/       # Prompt ablation (background keyword)
  matches_sensitivity_n2/     # N=2 candidate sensitivity
  matches_sensitivity_n5/     # N=5 candidate sensitivity
  analysis_*/                 # Per-experiment analysis outputs

paper/
  main.tex                    # LaTeX source (ACL 2026 style)
  figures/                    # All figures (PDF + PNG + SVG)
```

## Requirements

```bash
pip install openai upstage tiktoken numpy scipy scikit-learn rank-bm25 spacy
python -m spacy download en_core_web_sm
```

API keys required (set in `.env`):
```
UPSTAGE_API_KEY=...    # Solar Pro matcher
OPENAI_API_KEY=...     # GPT-5.4-nano replication
SERPER_API_KEY=...     # Web search (DRATracer generation)
GEMINI_API_KEY=...     # DRATracer backbone LLM
```

## Reproducing Results

### 1. Run the primary Solar Pro matcher on existing artifacts

```bash
python scripts/llm_matcher.py \
  --batch-dir runs/confirmatory \
  --output-dir runs/confirmatory/matches_hardneg_v1
```

### 2. Compute main accuracy numbers

```bash
python scripts/analyze_matches.py \
  --match-dir runs/confirmatory/matches_hardneg_v1
```

### 3. Run shortcut control experiments

**Artifact-side identity masking** (Table 6):
```bash
python scripts/run_identifier_masking.py \
  --artifact-dir runs/confirmatory \
  --output-dir runs/confirmatory/masked_identity_hardneg_v1
python scripts/llm_matcher.py \
  --batch-dir runs/confirmatory/masked_identity_hardneg_v1 \
  --output-dir runs/confirmatory/matches_masked_identity
```

**Candidate-side masking** (§6.3):
```bash
python scripts/run_candidate_profile_masked.py
```

**Dual-masked** (§6.3):
```bash
python scripts/run_dual_masked.py
```

**Prompt ablation** (Limitations):
```bash
python scripts/run_prompt_background_removed.py
```

### 4. Bootstrap confidence intervals for ablations

```bash
python scripts/compute_ablation_cis.py
```

### 5. Non-LLM baselines

```bash
python scripts/baseline_matcher.py \
  --artifact-dir runs/confirmatory \
  --output-dir runs/confirmatory/baselines_hardneg_v1_seed0
```

### 6. Candidate set construction (to regenerate from scratch)

```bash
python scripts/candidate_protocol.py \
  --manifest manifest.json \
  --output-dir runs/confirmatory/candidates
```

## Pre-computed Results

All primary match results, baseline outputs, and shortcut control results are committed under `runs/confirmatory/`. The main accuracy numbers can be verified by running `analyze_matches.py` on the committed match files without any API calls.

## Artifact Generation (DRATracer)

To regenerate DRA artifacts from scratch (requires all API keys and significant compute):

```bash
python scripts/batch_runner.py \
  --split confirmatory \
  --seed 0 \
  --output-dir runs/confirmatory \
  --execute
```

Note: artifact generation is expensive (~480 LLM calls per seed). Pre-generated artifacts are committed in `runs/confirmatory/pilot_*/`.

## Data

PDR-Bench task specifications and persona profiles are in `manifest.json`. Persona profiles contain synthetic, fictional user descriptions generated for research purposes.

## License

Code: MIT. Data (artifacts, persona profiles): CC BY 4.0.
