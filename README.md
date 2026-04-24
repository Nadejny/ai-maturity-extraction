# Diploma: Enterprise AI-Maturity Signal Extraction

Automated corpus construction and LLM-based extraction of enterprise AI-adoption
signals from web articles.

Given a list of ~800 URLs of industry articles about AI deployment, the system
(1) scrapes clean article text, (2) runs multiple LLMs to extract structured
payloads (use cases, stack, KPIs, budget/org/risk signals, deployment scope,
maturity level 0–4, evidence spans), and (3) evaluates the models against a
manually annotated golden subset to pick the best one for the final analytics
dataset.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full component diagram and
design rationale.

## Two subsystems

**Phase 1 — Corpus Collection** (`ParsingLinks/scripts/`)

| Step | Script | Purpose |
|---|---|---|
| B0 | `B0_make_dsVKR_http.py` | Fast HTTP scrape with `requests` + `trafilatura`, quality filter, bucket routing |
| B1 | `B1_medium.py` | Medium articles via AMP / JSON endpoints with Playwright fallback |
| B2 | `B2_a2_playwright.py` | General Playwright scraper for JS-protected / dynamic pages |
| Merge | `final_merge_and_export.py` | Pick best text per URL across sources, export unified CSV + `texts/` |

Shared utilities (`canonicalize_url`, Playwright helpers, `ExtractResult`) live
in `scripts/scraping_utils.py`.

**Phase 2 — Extraction & Evaluation** (`ParsingLinks/src/`)

| Step | CLI | Stage module | Purpose |
|---|---|---|---|
| 1 | `cli.build_dataset` | `stages/dataset.py` | Build immutable `dataset_base` from the corpus export (769 good docs) |
| 2 | `cli.build_golden` | `stages/golden.py` | Stratified golden split (180 docs: 120 train / 30 dev / 30 test, seed=42) |
| 3 | `cli.run_inference` | `stages/inference.py` | Run extraction across models (Ollama, Gemini, OpenAI-compatible, mock) |
| 4 | `cli.evaluate` | `stages/evaluation.py` | Strict (70%) + semantic (30%) scoring vs. golden; leaderboard |
| 5 | `cli.build_final` | `stages/final_dataset.py` | Final analytics dataset from the winning model |

See [`ParsingLinks/src/README.md`](ParsingLinks/src/README.md) for step-by-step
pipeline docs.

## Quick start

```bash
# 1. Clone and enter the project
git clone <your-fork-url> Diploma
cd Diploma

# 2. Create venv and install dependencies
python -m venv .venv
.venv\Scripts\activate                 # Windows
# source .venv/bin/activate            # Linux/Mac
pip install -r requirements.txt
playwright install chromium            # only if re-running Phase 1

# 3. Configure model endpoints (Phase 2 only)
cp ParsingLinks/src/config/model_registry.example.json \
   ParsingLinks/src/config/model_registry.json
# Edit model_registry.json: set <your-ollama-host> / API keys

# 4. Smoke-test Phase 2 with the mock provider
cd ParsingLinks/src
python -m cli.run_inference --models mock_baseline --max_docs 15
```

To reproduce the full Phase 2 run:

```bash
cd ParsingLinks/src
python -m cli.build_dataset
python -m cli.build_golden
python -m cli.run_inference --model_registry config/model_registry.json
python -m cli.evaluate --inference_run_dir artifacts/inference_runs/<RUN_ID>
python -m cli.build_final --inference_run_dir artifacts/inference_runs/<RUN_ID>
```

Unit tests: `cd ParsingLinks/src && python -m unittest discover tests`

## Repository layout

```
Diploma/
├── README.md                   ← you are here
├── ARCHITECTURE.md             ← component diagram + design rationale
├── LICENSE
├── requirements.txt
├── docs/                       ← analysis reports and session notes
│   ├── analysis_all_models_comparison.md
│   ├── analysis_cross_industry.md
│   ├── analysis_prompt_ceiling_ablation.md
│   └── ...
└── ParsingLinks/
    ├── data/                   ← original xlsx (NOT in repo — copyright)
    ├── scripts/                ← Phase 1: scraping
    ├── out/                    ← scraping outputs (mostly gitignored)
    │   └── final/
    │       └── best_per_url_export.csv   ← metadata only; texts/ is excluded
    └── src/                    ← Phase 2: extraction & evaluation
        ├── cli/
        ├── pipeline_core/
        ├── config/
        ├── artifacts/          ← inference runs (final runs tracked)
        └── tests/
```

## Data availability

The repo contains all code, configs, analysis reports, and **final inference
run artifacts** for reproducibility. Raw article texts and the original URL
list are **not redistributed**:

| Artifact | Included? | Why |
|---|---|---|
| `ParsingLinks/scripts/` — scraping code | yes | |
| `ParsingLinks/src/` — pipeline code | yes | |
| `ParsingLinks/out/final/best_per_url_export.csv` | yes | Metadata only (URL, title, company, industry, word count) |
| Article texts (`out/final/texts/`, `dataset_base.csv`) | no | Third-party copyright |
| `data/dsVKR.xlsx` — original URL list | no | Source dataset; keep local |
| Final inference runs (`4x769`, `qwen14_800`, `qwen32_800`, `opus47_160`, `qwen_ceiling_80`) | yes | Thesis reproducibility |
| Experimental / mock runs | no | Not part of thesis findings |
| `model_registry.json` with real server IPs / API keys | no | Use `model_registry.example.json` as template |
| Golden scaffold (empty payloads) | no | Not informative until annotated |

To re-run Phase 1 from scratch, provide your own URL list in the same format
(`data/dsVKR.xlsx` with a `Link` column).

## Corpus notes

- `dsVKR.xlsx` has **805 rows** → **801 unique documents** after URL
  canonicalization (4 duplicates in source). 769 of those pass the quality
  threshold (`word_count >= 300` and `text_len >= 1000`).
- Canonicalization strips `#fragment` and tracking params (`utm_*`, `gclid`,
  `fbclid`, `ref`, `source`, …).
- `url_canonical` is the universal join key across all pipeline stages.
- In `best_per_url_export.csv`, `merged_text_path` points to the corresponding
  `.txt` file (UTF-8). Empty values typically mean YouTube / video links or
  pages that could not be extracted.

## Status

**Done**
- Phase 1 complete: 769 "good" articles collected.
- Phase 2 library code complete and refactored.
- Inference on the full 769 docs for 6 open-weight models
  (`qwen3_{8b,14b,32b}`, `llama31_8b`, `gemma4_e4b`, `mistral_7b`) plus a
  small Opus 4.7 run on 160 docs — see `docs/analysis_*.md`.
- Cross-industry analysis on the primary model (`qwen3_32b`).

**In progress**
- Manual golden annotations (currently empty scaffold).
- Evaluation (step 4) and final analytics dataset (step 5) — blocked on
  golden annotations.

## License

[MIT](LICENSE) — free for any use, just keep the copyright notice.
