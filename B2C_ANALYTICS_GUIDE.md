# B2C Ecommerce Analytics — Beginner's Guide

> Read this top-to-bottom if you're studying the module for the first time.
> Every section explains **what** the feature does, **why** it matters,
> **how** it works at a high level, and includes the **research foundation**
> that backs it up. Plain English — no prior stats knowledge assumed.

---

## 1. What problem does this module solve?

**The real-world problem:** A small-to-mid ecommerce store (Shopify-level, 100–10,000
customers) produces two kinds of data every day:
transactions (who bought what, when, for how much) and inventory events
(stock coming in, selling out). Most store owners only look at surface
metrics like "daily revenue". They miss three critical questions:

1. **Which customers should I prioritise?** (not all customers are equal)
2. **How much is a customer worth to me over their lifetime?** (not just this month)
3. **Am I retaining customers or churning silently?** (cohort quality over time)

**What this module does:** A research-backed analytics pipeline that
produces answers to these three questions on top of the existing SalesForge
database. Plus a generic "Connect your store" layer so users don't have
to manually upload CSVs — they just click **Connect** and their platform
(Fake Store API today, Shopify/Swell in future) streams data in.

**Who uses this:** Store owners, marketing managers, retention specialists,
and anyone making customer-segmentation or inventory-planning decisions.

---

## 2. The three core analytics features

### 2.1 RFM Segmentation

#### What it does (plain English)

Scores every customer on three dimensions and groups them into
actionable buckets:

- **R**ecency: how recently did they last buy?
- **F**requency: how often do they buy?
- **M**onetary: how much do they spend total?

Each dimension gets a 1–5 score (5 = best). Combining the three scores
produces labels like **Champions**, **Loyal Customers**, **At Risk**,
**Lost**, etc. The store owner can then act on those labels:

- Send "thank you" rewards to Champions
- Send "we miss you" emails to At Risk
- Send onboarding tips to New Customers

#### Why it matters

You can't treat every customer the same. Sending a discount email to a
**Champion** teaches them to wait for discounts; sending one to a **Lost**
customer won't bring them back. Segmentation turns marketing from a shotgun
into a sniper rifle.

#### How it works (high level)

Under the hood we compute, per customer:
- R = days since last purchase
- F = number of distinct orders (distinct invoice_no)
- M = sum of spend

Then `pandas.qcut` splits each dimension into 5 equal-sized groups
(quintiles). Each customer ends up with a 3-digit score like `555` or `231`.
Segment labels are mapped via a rule set (e.g. R>=4 AND F>=4 AND M>=4 →
Champions).

#### Research foundation

Hughes, A.M. (1994). **Strategic Database Marketing**. Classic direct-marketing
text that introduced RFM as a practical customer-value scoring framework.
Still the most-taught segmentation method in marketing textbooks three
decades later.

#### What you'll see in the UI

8 segments ranked by customer count + a bar chart. Each segment shows:
count, % of base, average monetary, average frequency, average recency.
Top 10 customers listed with their RFM score.

---

### 2.2 BG/NBD Customer Lifetime Value (CLV)

#### What it does (plain English)

Predicts how much money each customer will spend **over the next 12 months**
and how likely they are to still be an active customer at all.

Output per customer:
- Predicted number of purchases in 12 months
- Predicted average order value
- Predicted total CLV (the two multiplied, discounted for present value)
- Probability the customer is "still alive" (i.e. hasn't silently churned)

#### Why it matters

Two customers can have identical RFM scores but very different futures. A
store with £1M annual revenue might discover that the top 20% of customers
will drive 92% of future revenue (Pareto distribution) — telling the
owner exactly where to focus retention spend.

#### How it works (high level — don't panic)

Two statistical models, both probabilistic:

**Model A — BG/NBD (Beta Geometric / Negative Binomial Distribution)**
Answers: "Given what I know about a customer's past purchases, how many
purchases will they make in the future, and are they still active?"

- Every customer has a hidden "purchase rate" (how often they naturally buy)
- After each purchase, they flip a coin — keep being a customer, or "die"
- The model fits probability distributions over these hidden values
  using everyone's observed data

**Model B — Gamma-Gamma (the monetary value model)**
Answers: "Given a customer's past spending, what's their expected
average order value going forward?"

- Order sizes follow a Gamma distribution per customer
- Customers differ in their "average order size", also Gamma-distributed
- Fit both levels of distribution to the data

**Combined CLV =** predicted_purchases × predicted_avg_order_value × discount_factor

#### Research foundation

Fader, P.S., Hardie, B.G.S., & Lee, K.L. (2005). **"RFM and CLV: Using
Iso-Value Curves for Customer Base Analysis"**. *Journal of Marketing
Research*, 42(4), 415–430. Cited ~2,000+ times. This paper set the
industry standard for non-contractual ecommerce CLV modelling.

Python implementation via the `lifetimes` library (Cam Davidson-Pilon).

#### Fallback for small samples

Gamma-Gamma doesn't always converge on small customer samples. The code
retries with progressively stronger regularisation (penalizer_coef
0.001 → 0.01 → 0.1 → 1.0). If all four fail it falls back to a simple
heuristic: `predicted_txns × avg_monetary × discount_factor`. Not as rigorous,
but produces sensible numbers for demo purposes.

#### What you'll see in the UI

Four summary metric cards (total CLV, avg CLV, top-20% Pareto share, customer
count), a model-info banner citing Fader 2005, and a table of the top
20 customers by predicted CLV — with pred txns, pred AOV, and
"alive probability" percentages.

---

### 2.3 Cohort Retention Analysis

#### What it does (plain English)

Groups customers by the month they first purchased (their "acquisition
cohort"). Tracks what percentage of each cohort returned to buy again in
subsequent months.

Presented as a **triangular heatmap** where:
- Rows = acquisition months (cohorts)
- Columns = months since first purchase (M0 = acquisition month, M1 = next month, etc.)
- Cell colour = retention percentage (green = high, grey = low)

#### Why it matters

Retention quality changes over time. If your Dec 2010 cohort retained 35%
at month 6 but your Dec 2011 cohort only retained 15%, something changed
in 2011 — product, marketing, competition, etc. Cohort charts make this
drift visible.

#### How it works (high level)

Pure pandas — no ML:

1. For each customer, find their earliest purchase month (their cohort)
2. For every subsequent month they purchased, compute "months since cohort"
3. Pivot into a 2D matrix: cohort × months-since
4. Divide each cell by the cohort's initial size → retention %

#### Research foundation

Standard SaaS/ecommerce analytical technique. Popularised by:
- Jonathan Silverstein (1980s pharma research — origin of the cohort concept)
- David Skok (SaaS Metrics 2.0 industry standard)
- Product analytics tools Mixpanel, Amplitude

#### What you'll see in the UI

- 4 metric cards (avg retention at M1 / M3 / M6 / M12)
- Colour-coded triangular heatmap showing cohort × month retention %
- Each cell shows the percentage (e.g. "35%")

---

## 3. Supporting infrastructure

These aren't research features — they're the plumbing that makes everything
work and demoable.

### 3.1 Customer model (new DB table)

Before this module, SalesForge had no concept of "customer" — only
transactions linked to products. Added `customers` table with:

- `external_id` — the platform's customer id (Shopify customer id, CustomerID
  from Online Retail II, etc.)
- `email`, `country`
- `first_purchase_date` — auto-backfilled after ingestion
- FK to `Store` (each customer belongs to one store)

Also added two new columns to `sales_transactions`:
- `customer_id` — FK to `customers` (nullable; may not exist for guest checkouts)
- `invoice_no` — groups transactions into orders (for market basket analysis
  and proper frequency counting)

### 3.2 Store Integrations module

#### Why

Store owners shouldn't have to manually upload CSVs. They should click
**Connect Shopify**, paste an API key, and analytics should appear.

#### Architecture

```
  External Platforms (credentials per org)
  ─────────────────────────────────────────
  Shopify      ┐
  Swell        ├──>  BaseIntegration  ──>  sync_service  ──>  DB tables
  Woo          ┤     (abstract class)       (upsert +                 │
  Fake Store   ┘                              dedup)                  │
                                                                      ▼
                                                     RFM / CLV / Cohort / KPIs
                                                     (all run on same uniform schema)
```

Each platform implements one class with four methods:
- `test_connection()` — validates credentials
- `fetch_products()` — pulls product catalogue
- `fetch_customers()` — pulls customer list
- `fetch_transactions(since)` — pulls orders

The sync orchestrator then upserts the returned data into the common
`Product`, `Customer`, `SalesTransaction` tables. **Analytics are
source-agnostic** — they don't know or care whether data came from
Shopify, Fake Store, or a CSV import.

#### What's implemented today

**FakeStoreIntegration** (public demo API, no authentication). Hit
`fakestoreapi.com` endpoints, return ~20 products, 10 users, 14 carts.
Useful as a zero-friction demo when real credentials aren't available.

#### What's stubbed for the future

`StoreIntegration` model already has encrypted credential columns
(`api_key_encrypted`, `api_secret_encrypted`, `base_url`). The registry
pattern in `sync_service.py` just needs a new class to add another
platform — one line in `INTEGRATION_REGISTRY` and it shows up in the UI.

#### API endpoints

- `GET  /integrations/platforms` — list supported platforms
- `POST /integrations/connect` — test credentials + save
- `GET  /integrations` — list connected stores for this org
- `POST /integrations/{id}/sync` — pull latest data
- `DELETE /integrations/{id}` — disconnect (synced data kept)

### 3.3 Online Retail II Ingestion

The integration layer is for live stores. For **analytics validation
against an academic benchmark**, we also support direct CSV ingestion
from the UCI Machine Learning Repository's Online Retail II dataset.

#### What's in this dataset

- 1,067,371 raw transactions from a UK online gift retailer (2009–2011)
- After cleaning: ~802,632 usable transactions
- 5,852 unique customers, 4,619 products, 2 years of data
- Public dataset; used in hundreds of academic papers

#### Why this particular dataset

Fader, Hardie & Lee's 2005 CLV paper was validated on datasets just like
this. Citing "our analytics ran on UCI Online Retail II" in a viva is
instant academic credibility.

#### Ingestion script

`scripts/ingest_online_retail_ii.py` handles:
- Download from UCI (~45 MB xlsx)
- Clean (drop null CustomerIDs, cancellations, negative quantities, etc.)
- Create Store + Products + Customers
- Bulk-insert transactions in 5,000-row batches

Flags:
```
--org-id N               Required — attaches data to this org's new Store
--download               Auto-fetch from UCI if xlsx not present locally
--force                  Wipe + re-ingest if store already has data
--sample N               First N rows chronologically (narrow time window, bad for cohorts)
--sample-customers N     Pick N random customers, keep ALL their transactions
                         (preserves 24-month span + per-customer history — recommended)
--store-name "..."       Custom store name (default: "Online Retail II (Demo)")
--sku-prefix "..."       Custom SKU prefix (default: "OR2_")
```

#### The "Demo 500" sample trick

The full 800k dataset is impressive but **slow** — RFM/CLV/Cohort each
take ~14 seconds. For snappy demos we also ingested a **500 random
customer** sample (`Online Retail II (Demo 500)`) — ~65k transactions,
full 24-month span preserved, BG/NBD fits correctly, analytics run in
**1–2 seconds**. Different viva moments, different stores.

---

## 4. Inventory Forecasting (existing module, enhanced)

### What it does

Uses Facebook Prophet (or EWMA fallback for short history) to predict
when each product will run out of stock. Generates **StockAlerts** when
depletion is predicted within 14 days.

### Enhancements added today

1. **Store selector** — Inventory page now scopes to a single store
   (matches the analytics pages' pattern). No more aggregated mess.

2. **Async "Forecast All" button** with progress bar — click → background
   thread forecasts every product in the store → UI polls every 2s and
   shows live progress (processed / total, succeeded / failed, current
   product name).

3. **Disabled scheduled auto-refresh** — the 6-hour APScheduler job that
   forecasts every product globally is off by default. With 4,619 OR-II
   products, each refresh took ~4 hours of CPU. Enable via
   `ENABLE_SCHEDULED_FORECAST_REFRESH=true` in `.env` when you have a
   real (smaller) live store.

### The async job pattern

```
User clicks "Forecast All (X products)"
           │
           ▼
 POST /inventory/refresh-all-forecasts/async?store_id=N
           │
           ▼
 Backend: spawn thread, register job in in-memory dict, return job_id
           │
           ▼
 UI:  setInterval every 2s → GET /inventory/refresh-jobs/{job_id}
                            ← {status, processed/total, succeeded, failed,
                               errors, last_product_name}
           │
           ▼ (when status in {succeeded, failed})
 UI:  clear polling, refetch products, show completion
```

Key properties:
- **Non-blocking** — HTTP request returns immediately
- **One job per scope** — second click on same store returns 409 Conflict
- **TTL cleanup** — finished jobs purged after 1 hour
- **Per-product graceful failure** — one bad forecast doesn't kill the job
- **Error cap** — only first 10 errors retained (prevents memory bloat)

### Why this matters for viva

"Background job with progress bar" is a production-grade pattern
(comparable to Shopify webhook handlers, Stripe async charges). Panels
respect it because it demonstrates you understand HTTP timeouts, thread
safety, and UX for long-running operations.

---

## 5. Transaction Analytics (existing, enhanced)

### What it does

Classic store dashboard:
- **KPIs**: revenue, orders, AOV, % change vs prior 30 days
- **Trends**: daily revenue chart
- **Top products** by revenue
- **Anomalies**: day-of-week-aware Z-score detector for revenue spikes/drops

### Enhancements added today

1. **Store selector** (same pattern as other pages)
2. **Anchor date fix** — previously the "last 30 days" window anchored to
   `datetime.utcnow()` (today). Historical datasets (OR-II from 2010)
   matched zero rows → empty page. Now anchors to `max(sale_date)` per
   org/store — so the page populates regardless of data age.
3. **Honest "as of" banner** — the UI tells the user when the anchor
   date is in the past so they understand they're looking at a historical
   window.

### Day-of-week aware anomaly detection

A naive Z-score over daily revenue flags every weekend dip as a "drop".
This detector compares each day against the exponentially weighted mean
of the **same weekday** (Mondays vs Mondays, Sundays vs Sundays). This
removes the weekly seasonality baseline so real spikes/drops stand out.
Cited as "DoW-aware EWM baseline" in the codebase — a Netflix/Uber-style
pattern for retail time series.

---

## 6. End-to-end data flow

```
  ┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
  │ UCI Online Retail│       │ Fake Store API   │       │ Shopify (future) │
  │  II (CSV)        │       │ (live HTTP)      │       │  (OAuth)         │
  └────────┬─────────┘       └────────┬─────────┘       └────────┬─────────┘
           │                          │                          │
           │ ingest script            │ BaseIntegration.         │ BaseIntegration.
           │                          │ fetch_*                  │ fetch_*
           ▼                          ▼                          ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                    Common DB schema (MySQL)                             │
  │                                                                         │
  │   stores  ──  products  ──  sales_transactions  ──  customers           │
  │                  │                     │                                │
  │                  └─── inventory_forecasts, stock_alerts                 │
  └─────────────────────────────┬───────────────────────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────────┐
                    │  Analytics services          │
                    │                              │
                    │  • customer_analytics (RFM,  │
                    │    CLV, Cohort)              │
                    │  • analytics (KPIs, trends,  │
                    │    top products, anomalies)  │
                    │  • inventory_service         │
                    │    (Prophet forecasting)     │
                    │  • forecast_jobs (async)     │
                    └─────────────┬────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │      FastAPI routes         │
                    │  (org-scoped, store-filter) │
                    └─────────────┬────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │   React frontend pages      │
                    │                              │
                    │  • TransactionAnalytics      │
                    │  • CustomerAnalyticsPage     │
                    │    (3 tabs: RFM/CLV/Cohort)  │
                    │  • InventoryManager          │
                    │  • IntegrationsPage          │
                    └─────────────────────────────┘
```

**Key insight:** every analytics feature reads from the same three
tables. Whether data came from Shopify, a CSV, or a live API doesn't
matter — analytics are data-source-agnostic.

---

## 7. Setup & prerequisites

### One-time dependency install

```bash
# Activate your project venv first
/d/fyp-2026/venv313/Scripts/python.exe -m pip install lifetimes==0.11.3
/d/fyp-2026/venv313/Scripts/python.exe -m pip install openpyxl
```

`lifetimes` is the BG/NBD + Gamma-Gamma library. `openpyxl` is required
by pandas to read the xlsx format used by Online Retail II.

### Schema migration

Run once — creates the `customers` + `store_integrations` tables and
adds `customer_id` + `invoice_no` columns to `sales_transactions`:

```bash
cd /d/final-year-project-v1
PYTHONIOENCODING=utf-8 /d/fyp-2026/venv313/Scripts/python.exe scripts/migrate_customer_schema.py
```

**Warning:** this drops and recreates `sales_transactions` — you lose
any existing transaction data. Safe when starting fresh.

### Ingest data (pick one or both)

**Full academic benchmark:**
```bash
python scripts/ingest_online_retail_ii.py --download --org-id 1 --force
```
~5-10 min. 800k transactions, 5,852 customers.

**Fast demo sample (recommended for viva):**
```bash
python scripts/ingest_online_retail_ii.py --org-id 1 \
    --sample-customers 500 \
    --store-name "Online Retail II (Demo 500)" \
    --sku-prefix "DEMO_"
```
~1-2 min. ~65k transactions, 500 customers, full 24-month date range.

### Start the app

```bash
# Terminal 1 — backend
cd /d/final-year-project-v1
uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
cd /d/final-year-project-v1/client
npm run dev
# open http://localhost:5173
```

---

## 8. Typical demo workflow

1. **Login** → dashboard
2. **Left sidebar → Integrations**
   - Shows "Fake Store API" as an available platform
   - Click **Connect** → modal → **Connect**
   - A new "Fake Store API Store" appears
   - Click **Sync Now** → 10 seconds → counts update
3. **Left sidebar → Customer Analytics**
   - Dropdown defaults to biggest store ("Online Retail II Demo" for full)
   - Tab switcher: RFM | Lifetime Value | Cohort Retention
   - For **fast clicks**, switch store to **Demo 500**
   - For **impressive numbers**, switch to full OR-II
4. **Left sidebar → Inventory Forecasts**
   - Pick a store
   - Click **Forecast All (N products)** → background job starts
   - Progress bar updates every 2 seconds
   - When complete, the products grid repopulates with forecast dates
5. **Left sidebar → Transaction Analytics**
   - Store selector at top
   - KPI cards, daily revenue chart, top products, DoW anomaly list
   - Note the "Window anchored to..." banner explaining the as-of date

---

## 9. Research foundations (for citations / viva)

| Feature | Paper / Source | Year | What it contributes |
|---|---|---|---|
| RFM Segmentation | Hughes, A.M. *Strategic Database Marketing* | 1994 | The 3-dimensional scoring framework itself |
| BG/NBD CLV | Fader, Hardie & Lee. *J. of Marketing Research* | 2005 | The probabilistic model used for predicted purchases + alive probability |
| Gamma-Gamma | Fader & Hardie. Note | 2013 | The monetary-value model paired with BG/NBD |
| Online Retail II | Chen, D. et al. UCI ML Repository | 2012 | The academic-benchmark dataset we validate against |
| Cohort Retention | Skok, D. *SaaS Metrics 2.0* | 2013 | The industry standard for longitudinal customer health |
| Prophet | Taylor & Letham, Facebook Research | 2017 | The time-series forecasting model used for inventory |
| DoW-aware anomaly | Twitter SeasonalESD (inspiration) | 2014 | Day-of-week baseline removal for retail seasonality |

---

## 10. Glossary

- **AOV** (Average Order Value): total revenue ÷ total orders
- **BG/NBD**: Beta Geometric / Negative Binomial Distribution — a
  probability model for customer purchase counts
- **Cohort**: a group of customers who share an acquisition month
- **CLV** (Customer Lifetime Value): predicted total revenue from a
  customer over a future horizon
- **EWMA** (Exponentially Weighted Moving Average): fallback forecasting
  method when there isn't enough sales history for Prophet
- **Gamma-Gamma**: a probability model for customer spend amounts,
  paired with BG/NBD
- **KPI**: Key Performance Indicator (revenue, orders, AOV)
- **Pareto check**: testing whether the top 20% of customers account for
  ~80% of CLV (named after economist Vilfredo Pareto)
- **Prophet**: Meta (Facebook)'s open-source time-series forecasting library
- **Quintile**: one of five equal-sized groups (used in RFM scoring)
- **Recency**: days since last purchase (R in RFM; lower = better)
- **RFM**: Recency, Frequency, Monetary
- **Store**: a connected commerce channel (one org can have many)
- **Upsert**: insert-if-missing, update-if-present — used during syncs
  to make them idempotent

---

## 11. Likely viva questions and model answers

**Q. Why RFM + CLV? Isn't one enough?**
A. RFM is descriptive (what is this customer *now*?). CLV is predictive
(what will they be *worth*?). You need both: RFM tells you who to
*contact* today; CLV tells you who to *invest* in.

**Q. Why BG/NBD instead of a neural network for CLV?**
A. Three reasons. **Interpretability** — each parameter has a business
meaning (churn rate, purchase rate). **Sample efficiency** — BG/NBD
works with thousands of customers, deep learning would need millions.
**Citability** — Fader 2005 is a foundational paper; panel respects
that more than a generic "we fit an LSTM".

**Q. Why did you ingest 800k transactions when you only demo 500 customers?**
A. Two stories in one. The **full dataset** validates our analytics
against the canonical academic benchmark. The **500-customer sample**
(still from the same dataset, preserving full date span and customer
histories) gives us a 1-second UI experience for the live demo. Same
code path, different scale.

**Q. Why is Fake Store API part of the demo if it's fake?**
A. It proves the **integration layer works end-to-end** — real HTTP
request, real JSON parsing, real upsert into our uniform schema. The
*analytics* are demoed on the academic benchmark; the *integration
pattern* is demoed on Fake Store. Two different proofs.

**Q. The scheduled forecast refresh is disabled. Isn't that a missing feature?**
A. It's behind a `.env` flag. On 4,619 products a single refresh cycle
runs for 4 hours — not practical for a dev machine. For real stores
with 50–500 products it becomes reasonable. Flipping one boolean enables
it. This is **configuration, not missing code**.

**Q. Why in-memory job registry instead of Redis / Celery?**
A. FYP scope. The job registry only tracks *progress*; the actual
forecast results are persisted to the DB by `generate_forecast`. If the
server restarts mid-job, the forecast rows already written survive, and
the job status simply disappears from the UI. In production you'd swap
the registry for Redis — the interface (`start_job`, `get_job`,
`serialize_job`) stays the same.

**Q. The CLV on the full dataset once showed negative total. Bug?**
A. Was a multi-store snapshot issue. When the analytics service
aggregated across OR-II (2011) **and** Fake Store (2020), the snapshot
date anchored on 2020 — making OR-II customers look "dead" (8-year gap).
BG/NBD correctly concluded near-zero purchase probability → CLV near
zero. Fixed by defaulting the frontend + verify script to **filter to
one store**. When panel selects OR-II alone, total CLV is a healthy $6.5M.
Honest framing: this was a real debugging session.

---

## 12. Files you should know

### Backend
- `models/inventory.py` — `Store`, `Product`, `Customer`, `SalesTransaction`,
  `InventoryForecast`, `StockAlert`
- `models/store_integration.py` — `StoreIntegration` (new)
- `services/customer_analytics_service.py` — `compute_rfm`, `compute_clv`,
  `compute_cohort_retention`
- `services/analytics_service.py` — KPIs, trends, top products, DoW anomalies
- `services/inventory_service.py` — Prophet + EWMA forecasting
- `services/forecast_jobs.py` — async background job registry (new)
- `services/integrations/base.py` — `BaseIntegration` abstract class (new)
- `services/integrations/fake_store.py` — FakeStore platform adapter (new)
- `services/integrations/sync_service.py` — upsert orchestrator (new)
- `routes/customer_analytics.py` — `/analytics/rfm`, `/clv`, `/cohort-retention`,
  `/stores` (new)
- `routes/integrations.py` — `/integrations/*` (new)
- `routes/inventory.py` — extended with `/refresh-all-forecasts/async` +
  `/refresh-jobs/{id}`
- `routes/analytics.py` — extended with `store_id` query param

### Frontend
- `client/src/pages/CustomerAnalyticsPage.jsx` — the 3-tab analytics page (new)
- `client/src/pages/IntegrationsPage.jsx` — connect/sync/disconnect UI (new)
- `client/src/pages/InventoryManager.jsx` — store selector + async job UI
- `client/src/pages/TransactionAnalytics.jsx` — store selector + as-of banner
- `client/src/utils/api.js` — new API helper sections: `customerAnalytics`,
  `integrations`, `inventory`

### Scripts (under `scripts/`)
- `migrate_customer_schema.py` — one-shot schema migration
- `ingest_online_retail_ii.py` — UCI dataset ingestion with sampling flags
- `verify_customer_analytics.py` — runs RFM/CLV/Cohort and prints summary
- `test_integration_fakestore.py` — end-to-end integration smoke test

---

## 13. What's deliberately not built (known gaps)

1. **Credential encryption**: `StoreIntegration.api_key_encrypted`
   currently stores plaintext. The column exists, the encryption
   (`cryptography.fernet`) is not yet wired. Trivial to add — documented
   as a production-readiness TODO.
2. **Shopify / Swell adapters**: the abstract base class + FakeStore
   prove the pattern. Adding Shopify is 1 new file (`services/integrations/shopify.py`)
   + 1 registry line.
3. **Frontend for integration OAuth flow**: current UI accepts API keys.
   True OAuth (redirect flow) would need a callback route.
4. **Scheduled forecast refresh on smaller stores**: disabled by default;
   enable via `.env` when a customer has < 500 products.
5. **Churn prediction**: intentionally dropped from scope (explained in
   earlier design discussions — RFM/CLV cover the same ground for FYP
   purposes; adding XGBoost for churn was judged scope creep).
6. **Market basket analysis**: same reasoning — dropped from scope.
   `invoice_no` column is present so the feature can be added later
   with Apriori / FP-Growth on 1-2 days of work.

---

## 14. One last thing — if you remember nothing else

**Three features, three papers, one uniform data pipeline.**

- RFM → Hughes 1994
- CLV → Fader, Hardie & Lee 2005
- Cohort → industry standard (Skok)

All run on the same three tables (`Store`, `Customer`, `SalesTransaction`).
Any data source that fills those tables — CSV ingestion, API integration,
manual entry — gets all three analytics for free. That's the whole trick.
