# TODO

## RQ (research question)

> Can large language models be employed for the reproducible extraction of structured features describing enterprise AI adoption from unstructured web materials, with **acceptable quality** and **documented error characteristics**?

## Стратегия quality-assessment (без formal human gold)

«Acceptable quality» определяется по 4 измерениям:

1. **Structural validity** — % valid JSON, parse errors, schema adherence
2. **Inter-model reliability** — pairwise agreement, unanimous-vote coverage
3. **Scaling consistency** — монотонное улучшение 8B→14B→32B (Qwen family)
4. **External triangulation** — alignment с Opus 4.7 (soft reference) + codebook (60 docs human, 5 cross-walked полей)

Формальный 180-doc human gold из `cli.build_golden` **не пересоздаётся** — scaffold остаётся как артефакт, но не используется для primary evaluation.

---

## Приоритет 1 — Блокирующие (закрыты 2026-04-20)

- [x] Прогнать qwen3_14b на все 769 документов
- [x] Прогнать qwen3_32b на все 769 документов
- [x] Отчёт по qwen3_14b на полном корпусе (`analysis_qwen3_14b.md`)
- [x] Полное сравнение 6 моделей на 769 (`analysis_all_models_comparison.md`)
- [x] Cross-industry анализ на primary model qwen3_32b (`analysis_cross_industry.md`)

## Приоритет 2 — Prompt-engineering ablation (закрыта 2026-04-21)

- [x] Prompt ceiling v2 builder в `pipeline_core/prompting.py`
- [x] CLI поддержка `--prompt_version ceiling` + `--doc_ids_file`
- [x] Opus baseline (v1) на 80 doc_ids из `doc_ids_batch1.txt` — 100% valid, 89% mat=2 clustering, conf=0.73
- [x] Opus ceiling (v2) на 80 doc_ids из `doc_ids_batch2.txt` — 100% valid, 85% mat=2, conf=0.76 (secondary fields ↑)
- [x] Qwen3_32b ceiling на 80 doc_ids (batch2) — 79/80 valid, mat-avg 1.36 → 0.50
- [x] Qwen3_14b ceiling на 80 doc_ids (batch2) — 79/80 valid, mat-avg 1.14 → 0.48
- [x] Qwen3_8b ceiling на 80 doc_ids (batch2) — 76/80 valid, mat-avg 1.20 → 0.49
- [x] Cross-analysis 2×4 (baseline vs ceiling × 4 models) — `analysis_prompt_ceiling_ablation.md` + dedicated Opus-vs-Opus subsection 2a
- [ ] Scaling-plot «prompt-engineering uplift as function of model size» (визуализация, можно отложить)

### Главный вывод ablation
- **Гипотеза «более насыщенный промпт улучшит экстракцию» отвергнута для sub-frontier моделей и подтверждена нейтральной для frontier.** Opus avg-maturity Δ=−0.05 (шум на disjoint батчах), qwen Δ=−0.66/−0.71/−0.86. Opus inter-batch конфиденс +0.034, secondary signal fill rates ↑ (risk +32 pp, org_change +21 pp, budget +11 pp); основные поля saturated на обоих промптах.
- **Baseline промпт НЕ теряет существенный сигнал** — Opus-ceiling прирост сосредоточен на edge-полях, а не на maturity. Это легитимирует baseline qwen3_32b результаты на 769 документах как primary thesis findings.
- **Mechanism:** sub-frontier модели читают «нужна verbatim quote» как exact-phrase-match → литеральная интерпретация cascade → fill rates halved → mat=0 collapse. Согласуется с Wei et al. 2022 (CoT emergent at scale), Madaan et al. 2023 (self-refine fails sub-frontier), Huang et al. 2023 (LLMs cannot self-correct yet).

## Приоритет 3 — Quality assessment (4 измерения)

### 3.1 Structural validity
- [x] Parse error rates per model (есть в `analysis_all_models_comparison.md`)
- [x] Schema adherence: wrong field names, alias used (уже посчитано)
- [ ] Сводная таблица «structural validity dashboard» в dediсated section

### 3.2 Inter-model reliability
- [x] Pairwise agreement matrix 6×6 (есть)
- [x] Unanimous agreement count (366/769 = 47.6%)
- [x] Majority-vote distribution (есть)
- [ ] Cohen's kappa / Fleiss' kappa для maturity — **посчитать**
- [ ] Per-field reliability (какие сигналы устойчивы между моделями, какие расходятся) — **посчитать**

### 3.3 Scaling consistency (Qwen family)
- [x] Монотонное улучшение 8B→14B→32B в `analysis_qwen3_14b.md` и `analysis_all_models_comparison.md`
- [ ] Scaling-plot в тексте диплома (компактная таблица/график)

### 3.4 External triangulation
- [x] **Opus как soft reference (частично):** alignment qwen baseline vs Opus-ceiling на batch2 (80 docs) — section 8 в `analysis_prompt_ceiling_ablation.md`. Exact match 35-41%, within-1-level 57-58%.
- [ ] **Opus baseline (batch1) vs qwen baselines на тех же 80 docs** — для второй точки отсчёта (другая выборка, тот же промпт). Симметричное к section 8.
- [ ] **Codebook 60 docs как external validation:**
  - [ ] Cross-walk table codebook-поля ↔ pipeline-поля (методологический раздел)
  - [ ] Загрузить все 60 codebook строк в evaluation-compatible формат
  - [ ] Посчитать agreement qwen3_32b vs codebook на 5 пересекающихся полях
  - [ ] **НЕ** formal benchmark — spot-check + error analysis material

## Приоритет 4 — Error characterization (главная сила RQ)

- [x] Parse error patterns per model (есть)
- [x] Confidence calibration per model (есть)
- [x] Maturity bias per model (Opus mat=2 clusters, qwen32 mat=3 leader, llama org_change over-detection) — есть качественно
- [x] **Sub-frontier prompt fragility:** литеральная интерпретация под ceiling-промптом — qwen fill rates halved, mat=0 collapse (доказано в `analysis_prompt_ceiling_ablation.md` §9)
- [ ] Систематизировать в **«Error characterization catalog»** — отдельный раздел/таблица в дипломе
- [ ] Per-model error fingerprint (визуально: radar chart / heatmap)

## Приоритет 5 — Cross-industry analysis (надёжность выводов)

- [x] qwen3_32b primary на 769 (`analysis_cross_industry.md`)
- [x] Model robustness check: industry ranking stability across qwen3_8b/14b/32b (есть в analysis_cross_industry.md §10)
- [x] ~~«Ceiling-run uplift» к cross-industry findings~~ — **не применимо:** ceiling-промпт даёт degradation на qwen (см. ablation). Cross-industry продолжает использовать qwen3_32b baseline, update не нужен.

## Приоритет 6 — Финализация диплома

### Structure
- [ ] Methodology chapter с 4-dimension quality framework
- [ ] Limitations section (3-4 предложения): no formal human gold, descriptive not predictive claims, corpus selection bias
- [ ] Defensive framing: "human annotation at 769-doc scale was infeasible within project timeline; quality assessment relies on internal validity + inter-model reliability + scaling + external triangulation"

### Deliverables
- [ ] Обновить session log за 2026-04-20 + 2026-04-21 (включая prompt-engineering ablation)
- [ ] Написать итоговый README.md для репозитория
- [ ] Подготовить таблицы и графики для текста диплома (включая 2×4 ceiling-ablation table)
- [ ] Cross-walk table (codebook ↔ pipeline schema) — для methodology chapter

## Приоритет 7 — GitHub

- [x] Добавить qwen3_14b и qwen3_32b в `model_registry.example.json` — все 6 Ollama моделей теперь в шаблоне с placeholder host
- [x] Решить какие inference runs пушить — финальные `4x769`, `qwen14_800`, `qwen32_800`, `opus47_160`, `qwen_ceiling_80` allowed; experimental (4x10/4x3/mock/qwen8_800/qwen32_3/qwen_3{,_v2}) excluded
- [x] Обновить `.gitignore` — granular per-folder excludes; final artifacts allowed
- [x] Sanitize 16 run_summary.json + dataset_base_report.json — abs paths с username убраны
- [x] Sanitize 3 hardcoded paths в opus_annotator_helper{,_v2}.py + prompt_opus_annotator.md
- [x] Sanitize server IP в session_2026-04-17.md
- [ ] Очистить `artifacts/_tmp_ceiling_analysis.{py,json}` или переместить под `tools/` если нужно сохранить
- [ ] Написать корневой `README.md` (см. Priority 6 deliverables)
- [ ] Первый коммит + push на https://github.com/Nadejny/ai-maturity-extraction.git

### Вопросы к решению (отложено на 2026-04-22)

Перед первым push'ем нужно решить:

1. **Root `README.md`** — писать ли публичный entry-point для репозитория? Сейчас есть `ParsingLinks/README` (текстовый, про scraping) и `ParsingLinks/src/README.md` (pipeline-инструкции), но нет верхнеуровневого. Если да — что включать: краткое описание диплома, RQ, links на 5 ключевых analysis-докладов в `docs/`, инструкцию запуска, статус «research artifact, не production»?
2. **Cleanup `_tmp_ceiling_analysis.{py,json}`** — gitignored локально, но загромождают `artifacts/`. Удалить или переместить в `ParsingLinks/src/tools/` как методический артефакт (скрипт, который сгенерировал 2×4 факториал)?
3. **Первый push** — когда? Готовы 93 файла / 47.1 MB / 0 leak-паттернов. Repo: `https://github.com/Nadejny/ai-maturity-extraction.git` (master уже local). Push необратим — требуется явное подтверждение.

---

## Что НЕ делаем (отказались)

- ~~Полная human-annotation 180 docs через `cli.build_golden`~~ — scaffold остаётся, но не пересоздаётся
- ~~F1 vs gold как primary evaluation metric~~ — заменено 4-dimension quality framework
- ~~qwen8/gemma/mistral с ceiling-промптом~~ — литература предсказывает degradation, не стоит GPU-часов
- ~~Full retrospective Opus run на 769 docs~~ — $157 слишком много для diploma budget, 160-doc выборка достаточна
- ~~Ceiling-промпт как primary results для thesis~~ — ablation 2026-04-21 подтвердила degradation на qwen и нейтральный эффект на Opus; baseline остаётся primary
- ~~Ceiling-промпт на полных 769 docs для qwen~~ — нет смысла, эффект уже измерен на 80; масштабировать заведомо провальный конфиг бесполезно
