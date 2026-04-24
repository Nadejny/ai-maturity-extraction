# AI Maturity Dataset Pipeline

This folder contains an end-to-end pipeline for:

1. Building immutable `dataset_base` from parsed texts.
2. Building stratified `golden` dataset scaffold.
3. Running extraction inference for multiple model providers.
4. Evaluating strict + semantic quality against golden split.
5. Building final analytics dataset from the best model.

## Project layout

```
src/
  pipeline_core/          # library code
    __init__.py           # constants re-exports
    constants.py
    schema.py
    io_utils.py
    prompting.py
    providers.py
    metrics.py
    stages/               # pipeline stages (one module per step)
      __init__.py
      dataset.py          # step 1
      golden.py           # step 2
      inference.py        # step 3
      evaluation.py       # step 4
      final_dataset.py    # step 5
  cli/                    # command-line entry points (run via -m cli.<name>)
    build_dataset.py      # step 1 entry point
    build_golden.py       # step 2
    run_inference.py      # step 3
    evaluate.py           # step 4
    build_final.py        # step 5
  config/                 # LLM settings, prompt contract, model registry
  artifacts/              # generated at runtime (gitignored subfolders)
  tests/                  # unittest suite
```

## Run from

```powershell
cd ParsingLinks/src
```

All CLI invocations below assume this working directory.

## Step 1: Build dataset_base

```powershell
python -m cli.build_dataset
```

Outputs:
- `artifacts/data/dataset_base.csv`
- `artifacts/data/dataset_base.jsonl`
- `artifacts/data/dataset_base_report.json`

## Step 2: Build golden scaffold (180 docs)

```powershell
python -m cli.build_golden
```

Outputs:
- `artifacts/golden/golden.csv`
- `artifacts/golden/golden.jsonl`
- split files and QA sample

## Step 3: Configure models

Edit `config/model_registry.example.json` or copy it to your own file and set:
- Gemini API model + key env var
- Local ~24B endpoint
- GCP ~12B endpoint

## Step 4: Run inference

```powershell
python -m cli.run_inference --model_registry config/model_registry.example.json
```

Optional smoke run:

```powershell
python -m cli.run_inference --models mock_baseline --max_docs 15
```

Resume an interrupted run (same `run_id` + `--skip-existing`):

```powershell
python -m cli.run_inference --run_id qwen32_800 --skip-existing --models qwen3_32b
```

## Step 5: Evaluate benchmark

```powershell
python -m cli.evaluate --inference_run_dir artifacts/inference_runs/<RUN_ID>
```

Optional semantic judge:

```powershell
python -m cli.evaluate `
  --inference_run_dir artifacts/inference_runs/<RUN_ID> `
  --judge_model_registry config/model_registry.example.json `
  --judge_model_alias gemini_api_primary `
  --judge_settings config/judge_settings.json
```

## Step 6: Build final analytics dataset

```powershell
python -m cli.build_final --inference_run_dir artifacts/inference_runs/<RUN_ID>
```

Outputs:
- `artifacts/final/final_analytics_dataset.csv`
- `artifacts/final/final_analytics_dataset.jsonl`

## Unit tests

```powershell
python -m unittest discover tests
```
