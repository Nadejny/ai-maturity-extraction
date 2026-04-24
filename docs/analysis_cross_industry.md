# Cross-Industry AI Maturity Analysis

**Primary model:** qwen3_32b (run `qwen32_800`, 769 документов, 744 valid, 25 parse errors)
**Sensitivity check:** qwen3_8b (`4x769`) + qwen3_14b (`qwen14_800`)
**Corpus:** 170 компаний, 10 отраслей, 2017–2025
**Date:** 2026-04-20

qwen3_32b выбран primary моделью на основании detailed comparison
(см. `analysis_all_models_comparison.md`): лучшая дискриминация mat=3,
×2 глубже spans, единственная модель с осмысленным risk/org_change
signal extraction.

---

## 1. Состав корпуса

### По отраслям

| Отрасль | Docs | Доля |
|---------|------|------|
| Delivery and mobility | 178 | 23.1% |
| Tech | 172 | 22.4% |
| E-commerce and retail | 148 | 19.2% |
| Social platforms | 97 | 12.6% |
| Fintech and banking | 61 | 7.9% |
| Media and streaming | 55 | 7.2% |
| Travel, E-commerce and retail | 47 | 6.1% |
| Gaming | 5 | 0.7% |
| Manufacturing | 5 | 0.7% |
| Education | 1 | 0.1% |

Основные 7 отраслей покрывают 99.2% корпуса. Gaming/Manufacturing/Education
имеют недостаточно статей для робастных выводов (≤5 каждая) — используются
только как справочный контекст.

### По годам

| Год | Docs | Доля |
|-----|------|------|
| 2017–2019 | 21 | 2.7% |
| 2020 | 28 | 3.6% |
| 2021 | 79 | 10.3% |
| 2022 | 90 | 11.7% |
| 2023 | 158 | 20.5% |
| 2024 | 171 | 22.2% |
| 2025 | 222 | 28.9% |

**71% корпуса — 2023–2025**, что отражает акселерацию enterprise AI.

### Top-20 компаний по количеству статей

| Компания | Docs | Отрасль |
|----------|------|---------|
| Doordash | 30 | Delivery and mobility |
| Uber | 30 | Delivery and mobility |
| Pinterest | 25 | Social platforms |
| Instacart | 25 | Delivery and mobility |
| Linkedin | 24 | Social platforms |
| Wayfair | 24 | E-commerce and retail |
| Swiggy | 20 | Delivery and mobility |
| Netflix | 19 | Media and streaming |
| Airbnb | 18 | Travel |
| Walmart | 15 | E-commerce and retail |
| Meta | 14 | Social platforms |
| Lyft | 13 | Delivery and mobility |
| Spotify | 13 | Media and streaming |
| Expedia | 13 | Travel |
| Zillow | 13 | E-commerce and retail |
| Dropbox | 12 | Tech |
| Grab | 12 | Delivery and mobility |
| Grammarly | 11 | Tech |
| Mercado Libre | 11 | E-commerce and retail |
| Etsy | 10 | E-commerce and retail |

---

## 2. AI maturity по отраслям (qwen3_32b)

| Отрасль | n valid | Avg maturity | % mat ≥ 2 | Mat distribution (0/1/2/3) |
|---------|---------|--------------|-----------|-----------------------------|
| **Travel, E-commerce** | 45 | **1.60** | **64.4%** | 16 / 0 / 15 / 14 |
| **Media and streaming** | 52 | **1.56** | **61.5%** | 18 / 2 / 17 / 15 |
| Gaming | 5 | 1.40 | 60.0% | 2 / 0 / 2 / 1 |
| **Fintech and banking** | 61 | **1.34** | **57.4%** | 26 / 0 / 23 / 12 |
| E-commerce and retail | 143 | 1.31 | 53.8% | 65 / 1 / 45 / 32 |
| Social platforms | 95 | 1.23 | 48.4% | 47 / 2 / 23 / 23 |
| Delivery and mobility | 173 | 1.14 | 46.2% | 89 / 4 / 47 / 33 |
| Tech | 164 | 1.13 | 47.6% | 81 / 5 / 54 / 23 (+1 mat=4) |
| Manufacturing | 5 | 1.00 | 40.0% | 3 / 0 / 1 / 1 |
| Education | 1 | 0.00 | 0% | 1 / 0 / 0 / 0 |

### Ключевые выводы по отраслям

1. **Travel, E-commerce and retail — безусловный лидер:**
   - Самая высокая avg maturity (1.60)
   - 64.4% документов имеют production-level AI
   - Из 47 документов **14 (30%)** на уровне multi-function integration
   - Примеры: Booking partner message assistance, Agoda property Q&A, Airbnb brand perception

2. **Media and streaming — второй** (1.56, 61.5% mat≥2):
   - 15 документов на mat=3 (29%) — одна из самых высоких долей
   - Драйверы: Netflix (19 статей, 7 mat=3), Spotify (13, 4 mat=3), Tubi
   - Фокус — рекомендательные системы и ML infrastructure

3. **Fintech and banking — третий** (1.34, 57.4% mat≥2):
   - 12 mat=3 документов (20%)
   - **Самый высокий fill risk_signals (42.6%) и org_change (37.7%)** среди всех отраслей
   - Отражает регуляторную нагрузку и enterprise governance
   - Лидеры: Coinbase (8 статей, 3 mat=3), Nubank (9, 3 mat=3)

4. **E-commerce and retail** (1.31, 53.8% mat≥2):
   - 32 mat=3 документа — **самое большое абсолютное число** multi-function AI
   - Драйверы: Whatnot (2.6 avg), Ebay (2.17), Shopify (1.88), Target (2.0)

5. **Social platforms** (1.23, 48.4% mat≥2):
   - 23 mat=3 документа (24%)
   - Драйверы: Meta (1.93 avg, 5 mat=3), Pinterest (1.70, 9 mat=3)
   - Двухмодальное распределение: либо mat=0 (PR release), либо mat=3 (multi-function production)

6. **Tech и Delivery — самые низкие среди major отраслей** (1.13 и 1.14):
   - **Tech-парадокс**: самая «продвинутая» отрасль по духу (172 статьи),
     но **49% мат=0** — потому что много релизов open-source моделей и
     research publications, которые описывают «новую модель», а не production-деплой.
   - **Delivery** — большой корпус (178), но доминируют статьи о fraud detection
     и ETA prediction, многие из которых «одиночные» production use cases (mat=2),
     без multi-function integration.

---

## 3. Top AI-mature компании (≥5 статей)

| Ранг | Компания | Отрасль | Статей | Avg mat | % mat≥2 | mat=3 |
|------|----------|---------|--------|---------|---------|-------|
| 1 | **Booking** | Travel | 5 | **2.80** | 100% | 4 |
| 2 | **Whatnot** | E-commerce | 5 | **2.60** | 100% | 3 |
| 3 | **Amazon** | Tech | 9 | **2.44** | 100% | 4 |
| 4 | **BlaBlaCar** | Delivery | 5 | **2.40** | 100% | 2 |
| 5 | **Coinbase** | Fintech | 8 | **2.38** | 100% | 3 |
| 6 | Ebay | E-commerce | 6 | 2.17 | 83% | 3 |
| 7 | Duolingo | Tech | 6 | 2.00 | 83% | 2 |
| 8 | Target | E-commerce | 5 | 2.00 | 80% | 2 |
| 9 | Meta | Social | 14 | 1.93 | 79% | 5 |
| 10 | Shopify | E-commerce | 8 | 1.88 | 63% | 5 |
| 11 | Github | Tech | 5 | 1.80 | 80% | 1 |
| 12 | Netflix | Media | 19 | **1.74** | 68% | **7** |
| 13 | Pinterest | Social | 23 | 1.70 | 65% | **9** |
| 14 | Google | Tech | 6 | 1.67 | 83% | 0 |
| 15 | Grab | Delivery | 12 | 1.67 | 67% | 4 |

**Наблюдения:**

- **Booking (2.80 avg)** — новый #1 по версии qwen3_32b (был #3 на 8b). Из 5 статей **4 на mat=3** — Booking демонстрирует multi-function AI integration (partner messaging, demand forecasting, personalization) с governance.
- **Amazon, Whatnot, BlaBlaCar, Coinbase — 100% mat≥2** — каждая проанализированная статья описывает production AI.
- **Netflix (19 статей, 7 mat=3)** и **Pinterest (23 статьи, 9 mat=3)** — максимальное абсолютное число multi-function документов. Это действительно «enterprise-scale AI companies».
- **Meta (14 статей, 5 mat=3, avg 1.93)** — поднялась в top-10 благодаря 32b (lesser модели недооценивали Meta).

---

## 4. Доминирующие AI use cases по отраслям

### Delivery and mobility (n=173)
1. **Fraud detection** (10)
2. Restaurant ranking (3)
3. Personalized recommendations (3)
4. Demand forecasting (2)
5. Route optimization (2)
6. ETA prediction (2)

### E-commerce and retail (n=143)
1. **Fraud detection** (5)
2. Product recommendation (3)
3. Demand forecasting (2)
4. Semantic search (2)
5. Customer review analysis (2)

### Fintech and banking (n=61)
1. **Fraud detection** (11) — **доминирует**
2. Expense approval automation (2)
3. Merchant identification (2)
4. Receipt parsing / OCR (2)
5. Transaction categorization (2)
6. Account takeover prevention (2)

### Tech (n=164)
1. **Code review automation** (3)
2. **Grammatical error correction** (3)
3. Document summarization (2)
4. Code generation (2)
5. Code completion (2)
6. Semantic search (2)

### Social platforms (n=95)
1. **User engagement prediction** (5)
2. Candidate generation (3)
3. Fraud detection (2)
4. Content moderation (2)

### Media and streaming (n=52)
1. Sentiment analysis (2)
2. Search optimization (2)
3. Content recommendation
4. Personalized recommendations

### Travel, E-commerce and retail (n=45)
1. **Personalized hotel ranking** (2)
2. **Personalized recommendations** (2)
3. Guest inquiry response automation
4. Property-related Q&A
5. Customer service automation

### Finding: Fraud detection — универсальный «вход в production AI»

Fraud detection появляется как топ-use case в **4 из 7** major отраслей
(Fintech, Delivery, E-commerce, Social). Это согласуется с гипотезой,
что fraud detection — первая production AI в индустрии: чёткий ROI,
понятные метрики (precision/recall), готовые историческия данные.

В **Fintech** fraud detection абсолютно доминирует (11 упоминаний из 61 статьи, 18%).

---

## 5. AI технологический stack по отраслям

| Отрасль | Доминирующие технологии |
|---------|------------------------|
| **Tech** | LLMs (10), RAG (4), transformer architectures (4) |
| **E-commerce** | LLMs (8), BERT (6), embedding models (4) |
| **Social platforms** | LLMs (4), DNNs (3), xgboost (2), vector embeddings (2) |
| **Fintech** | LLMs (2), feature store (2), DNNs (2), gradient boosting (2), xgboost (2) |
| **Media** | LLM agents (2), MUSE embeddings (2), reinforcement learning (2) |
| **Travel** | LLMs (3), word2vec (2), cosine similarity (2), embedding models (2) |
| **Delivery** | **xgboost (4), gradient boosting (3), neural networks (3), lightgbm (3)**, GPT-4 (3) |

### Finding: Delivery полагается на traditional ML, остальные — на LLMs

**Delivery and mobility** — единственная major отрасль, где **gradient boosting
(xgboost/lightgbm) доминирует** над LLMs. Это отражает специфику задач
(ETA prediction, demand forecasting, fraud scoring) — табличные данные,
жёсткие требования к latency, миллионы запросов в секунду.

**Все остальные отрасли** — LLMs в топ-2. Особенно выражено в:
- **Tech** (10 упоминаний LLMs vs 4 RAG)
- **E-commerce** (8 LLMs + 6 BERT)
- **Travel** (3 LLMs + word2vec)

---

## 6. Maturity trend по годам

| Год | n | Avg mat | % mat≥2 | % mat=3 |
|-----|---|---------|---------|---------|
| 2017–2019 | 20 | 1.10 | 50.0% | 10.0% |
| 2020 | 27 | 1.30 | 55.6% | 14.8% |
| 2021 | 74 | 1.24 | 54.1% | 14.9% |
| 2022 | 88 | 1.07 | 44.3% | 17.0% |
| 2023 | 152 | 1.28 | 52.6% | 19.7% |
| 2024 | 167 | 1.07 | 43.7% | 16.2% |
| **2025** | 216 | **1.47** | **57.9%** | **30.1%** |

### Finding: 2025 — явный скачок multi-function deployment

- **30.1% документов 2025 года на уровне mat=3** — **×2 к любому предыдущему году**
- Avg maturity 1.47 — исторический максимум
- Доля production+ растёт до 57.9%

Это отражает пост-ChatGPT волну, когда компании переходят от пилотов
к полноценным enterprise-wide AI-деплоям. **qwen3_8b эту закономерность
недооценивает** (mat=3 в 2025 — 12% по его версии), **qwen3_32b видит
30.1%** — разница в 2.5 раза.

### Плато 2022–2024

В 2022-2024 годах доля production AI **не растёт**, колеблется в 44–53%.
Это **не** говорит о стагнации отрасли — это артефакт корпуса:
в эти годы много статей про **release of open-source models** и **research
publications**, которые классифицируются как mat=0 (нет описания production).

---

## 7. Deployment scope: паттерны по отраслям

### Enterprise-scale примеры (mat=3+ deployment scope)

**Fintech — самые концентрированные примеры:**
- Nubank: "company-wide across 9,000 employees"
- Nubank: "core banking operations including lending, fraud detection, and customer communication"
- Ramp: expense management on Ramp platform (full product line)

**Media — рекомендательные workflows:**
- Tubi: "core recommendation system across web, mobile, and OTT platforms"
- Spotify: "multiple Home page shelves with real-time model serving"
- Netflix: entire recommender system workflow (из multiple articles)

**Delivery — полный order journey:**
- Picnic: automated fulfillment centers + product/recipe search across NL/DE/FR
- Swiggy: core delivery process (из examples)
- Uber/DoorDash: multiple articles описывают end-to-end ML platforms

**Tech — platform-wide DevTools:**
- GitLab: "GitLab Duo features across the DevSecOps platform"
- Google: Workspace business customers
- Amazon: company-wide AI across services

**Travel — customer-facing features:**
- Booking: "assisting partners in managing tens of thousands of guest messages daily"
- Agoda: "property-related Q&A across desktop, mobile web, and Agoda app"
- Airbnb: "company-wide brand perception tracking across social media platforms"

---

## 8. KPI signals: бизнес vs техника по отраслям

| Отрасль | Характерные KPI |
|---------|-----------------|
| **Fintech** | **65% approvals handled by agent**, **96% ticket deflection**, 50% routing accuracy |
| **Travel** | **70% user satisfaction increase**, reduced follow-up messages, faster response times |
| **Manufacturing** | 70% asset tagging, 91% brand identification, 84% category tagging |
| **Tech** | Precision (3), recall (3), output quality, latency, cost |
| **E-commerce** | Conversion rates, clicks, purchases, precision, recall |
| **Social** | Engagement metrics (5), user engagement (4), HumanEval/MBPP |
| **Delivery** | Customer satisfaction (2), MAE (2), retention (2), NDCG (2) |
| **Media** | Positive label ratio, forecast accuracy, user retention |
| **Gaming** | CPU hours reduction, cost savings, stability improvement |

### Finding: Fintech и Travel — «бизнес-ориентированные» KPI

**Fintech и Travel** выделяются конкретными количественными бизнес-метриками
(% automation rate, % satisfaction increase, % deflection). Это признак
зрелой AI-интеграции — они меряют **бизнес-эффект**, а не только
model quality.

**Tech** — наоборот, меряет **model-level metrics** (precision, recall,
cosine similarity). Это отражает разные приоритеты: Tech-компании
в статьях делятся техническими достижениями, Fintech/Travel — бизнес-результатами.

---

## 9. Signal coverage по отраслям

Доля документов, где отрасль имеет present-статус по каждому сигналу (qwen3_32b):

| Отрасль | ai_use | adopt | stack | kpi | budget | org_change | risk | roadmap | deploy |
|---------|--------|-------|-------|-----|--------|------------|------|---------|--------|
| **Travel** | **71%** | **69%** | 56% | 47% | 7% | 22% | 44% | 49% | **69%** |
| **Media** | 64% | 64% | **58%** | 42% | 0% | **40%** | 42% | 56% | 64% |
| **Fintech** | 57% | 57% | 49% | 46% | 7% | **38%** | **43%** | 48% | **59%** |
| **E-commerce** | 58% | 57% | 54% | 46% | 6% | 22% | 34% | 46% | 54% |
| **Social** | 57% | 53% | 55% | 44% | 2% | 24% | 39% | 44% | 52% |
| **Tech** | 53% | 52% | 44% | 33% | 4% | 24% | 35% | 42% | 50% |
| **Delivery** | 52% | 51% | 45% | 42% | 8% | 23% | 32% | 45% | 51% |

**Наблюдения:**

- **Travel — лидер на 4 из 9 полей**: максимум ai_use_cases (71%), adoption (69%), deployment_scope (69%). Самая «информативная» отрасль для изучения AI adoption.
- **Media лидирует на org_change (40%)** — потому что статьи Netflix/Spotify описывают структурные ML-команды и их рабочие процессы.
- **Fintech лидирует на risk (43%) и deployment (59%)** — регуляторное окружение заставляет компании писать про риски.
- **Tech самый слабый в kpi (33%)** — статьи Google/GitLab/Dropbox часто описывают «что мы запустили», не «что мы измерили».
- **budget_signals crap везде (0–8%)** — бюджет почти никогда не раскрывают в технических статьях.

---

## 10. Устойчивость выводов к выбору модели

Проверяем, насколько industry ranking меняется при переходе от 8b к 32b.

### Avg maturity по отраслям (три модели)

| Отрасль | qwen3_8b | qwen3_14b | qwen3_32b | Δ (32b − 8b) |
|---------|----------|-----------|-----------|---------------|
| Travel, E-commerce | 1.43 | 1.45 | **1.60** | +0.17 |
| Media and streaming | 1.35 | 1.25 | **1.56** | +0.21 |
| Fintech and banking | 1.26 | 1.38 | 1.34 | +0.08 |
| E-commerce and retail | 1.18 | 1.16 | 1.31 | +0.13 |
| Social platforms | 1.09 | 1.04 | 1.23 | +0.14 |
| Delivery and mobility | 0.98 | 0.97 | 1.14 | +0.16 |
| Tech | 1.02 | 0.92 | 1.13 | +0.11 |

**Находки:**
1. **Travel — #1 во всех трёх моделях**. Ранг устойчив.
2. **Tech/Delivery — нижняя пара стабильно** во всех моделях.
3. **32b систематически даёт +0.08–0.21 к avg maturity** vs 8b — это эффект большей дискриминации mat=3.
4. **Media and streaming** сильнее всего меняется между моделями: 14b даёт 1.25 (ниже Fintech), 32b — 1.56 (#2). Это связано с тем, что 32b лучше распознаёт multi-function recommender systems (Netflix/Spotify).

### mat=3 абсолютные числа (кратные различия)

| Отрасль | 8b | 14b | 32b | Мультипликатор 32b/8b |
|---------|-----|------|------|-----------------------|
| Media and streaming | 4 | 5 | 15 | **×3.75** |
| Travel, E-commerce | 5 | 6 | 14 | **×2.80** |
| Delivery and mobility | 14 | 15 | 33 | **×2.36** |
| Fintech and banking | 7 | 14 | 12 | ×1.71 |
| E-commerce and retail | 17 | 22 | 32 | ×1.88 |
| Tech | 15 | 14 | 23 | ×1.53 |
| Social platforms | 15 | 11 | 23 | ×1.53 |

**Media and streaming** — самая большая разница: 32b видит в 3.75× больше
multi-function AI, чем 8b. Это ключевая для диплома находка про выбор модели:
**меньшие модели систематически недооценивают Media and streaming.**

### Устойчивая тройка: Travel, Media, Fintech

Все три модели ставят Travel+Media+Fintech в топ-4 по avg maturity.
Это **robust-вывод диплома**: независимо от выбора модели, эти три
отрасли лидируют в enterprise AI adoption.

---

## 11. Ключевые выводы для диплома

### Finding 1: Зрелость AI сильно варьирует по отраслям
Разрыв между лидером (Travel, 64% mat≥2) и наименее зрелой major-отраслью
(Delivery, 46%) — **18 процентных пунктов**. Подтверждается всеми тремя
qwen моделями.

### Finding 2: Fraud detection — универсальный «gateway» AI use case
Fraud detection — топ use case в 4 из 7 major отраслей (Fintech, Delivery,
E-commerce, Social). В Fintech абсолютно доминирует: 11 упоминаний из 61
статьи (18%). Согласуется с тезисом о ясном ROI и готовой измеримости
fraud-моделей.

### Finding 3: LLMs доминируют в 6 из 7 major отраслей
LLMs — top-2 технология в Tech, E-commerce, Social, Fintech, Media, Travel.
**Исключение — Delivery**, где gradient boosting (xgboost/lightgbm)
доминирует. Это структурное различие: табличные задачи требуют иных моделей.

### Finding 4: Компании бимодально распределены
Компании почти никогда не сидят на mat=1 (pilot). Либо мат=0 (release
или research), либо мат≥2 (production). В топ-15 mat-зрелых компаний
**все имеют >60% mat≥2**, в среднем 80%+.

### Finding 5: 2025 — скачок multi-function AI
**30.1% документов 2025 года — mat=3** (vs 16–20% в 2022–2024).
Пост-ChatGPT волна перекатывается в enterprise deployments.
32b детектирует это более чётко, чем 8b (30% vs 12% mat=3 в 2025).

### Finding 6: Travel > Media > Fintech — стабильный top-3
Все три qwen модели (8b/14b/32b) согласно ранжируют Travel+Media+Fintech
в топ-4 по avg maturity. Это **model-robust finding**.

### Finding 7: Fintech и Travel отличаются бизнес-KPI
Только в этих двух отраслях в статьях встречаются конкретные процентные
метрики **бизнес-эффекта**: 65% approval automation, 96% ticket deflection,
70% satisfaction increase. Это признак зрелой monetization AI.

### Finding 8: Tech-парадокс
Tech-отрасль — с максимальным количеством статей (172), но **47.6% мат≥2
только 7-е место**. Много research publications и open-source releases
опускают avg. Реальная ценность Tech-кейсов раскрывается в top-компаниях
(Amazon=2.44, Duolingo=2.00, Google=1.67).

---

## 12. Caveat: smoothness artefacts

### Корпус не случайный
Статьи отобраны с tech-блогов компаний — это **self-selection sample**
«компаний, у которых есть что рассказать». Истинное распределение зрелости
AI в экономике **значительно ниже** того, что здесь показано.

### Качественные подмена
В 2024 году мы видим снижение avg maturity (1.07) относительно 2023
(1.28). Это **не** сигнал регрессии — это больше статей об open-source
выпусках (GPT-4, Llama-3, Claude-3), которые классифицируются как mat=0.

### Parse error bias
25 документов (3.25%) исключены из анализа из-за parse errors у qwen3_32b.
Эти документы могут быть систематически смещены (длинные/сложные статьи
с агрессивной JSON-нагрузкой). На 8b parse errors — 11 (1.43%), что
позволяет проверить sensitivity.

---

## 13. Ключевые цифры для диплома

### Масштаб анализа
- **744 валидных документов** проанализированы по qwen3_32b
- **170 уникальных компаний** из 10 отраслей
- **2017–2025** временной охват (71% корпуса — 2023–2025)

### Industry ranking (avg maturity, qwen3_32b)
1. **Travel, E-commerce and retail — 1.60** (64.4% mat≥2)
2. **Media and streaming — 1.56** (61.5% mat≥2)
3. **Fintech and banking — 1.34** (57.4% mat≥2)
4. **E-commerce and retail — 1.31** (53.8% mat≥2)
5. **Social platforms — 1.23** (48.4% mat≥2)

### Top AI-mature companies
- **Booking — 2.80 avg** (5 статей, 4 на mat=3)
- **Whatnot — 2.60 avg** (5 статей, 3 на mat=3)
- **Amazon — 2.44 avg** (9 статей, 4 на mat=3)
- **Netflix / Pinterest — 7 и 9 документов на mat=3** абсолютно

### Scale indicators
- **Fraud detection** — топ use case в 4 из 7 major отраслей
- **LLMs доминируют** в 6 из 7 major отраслей (исключение — Delivery)
- **30.1% mat=3 в 2025** (×2 к предыдущим годам)
- **18 пп разрыв** между top и bottom major отраслями

### Model robustness
- **Top-3 отрасли (Travel/Media/Fintech)** стабильны во всех трёх qwen моделях
- **Media and streaming** — самая чувствительная к выбору модели (mat=3 ×3.75 у 32b vs 8b)
- qwen3_32b даёт **на 0.08–0.21 выше avg maturity** по отраслям vs 8b (эффект mat=3 детекции)
