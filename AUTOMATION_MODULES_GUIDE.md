# Automation Modules — Complete Beginner's Guide

> This guide walks through **three modules** end-to-end: Inventory Forecasting,
> Transaction Analytics, and Lead Scoring. For each module, we follow what
> happens from the moment a user clicks a button all the way through the
> code, database, and back to the screen — in plain English.
>
> **Audience:** Someone seeing the codebase for the first time. No prior
> ML or backend knowledge assumed.
>
> **How to read this:** Pick the module you care about, or read all three
> top-to-bottom. Each section is self-contained.

---

## Table of Contents

1. [Module 1 — Inventory Forecasting](#module-1--inventory-forecasting)
2. [Module 2 — Transaction Analytics](#module-2--transaction-analytics)
3. [Module 3 — Lead Scoring](#module-3--lead-scoring)
4. [Shared concepts you'll see in all 3](#shared-concepts-youll-see-in-all-3)
5. [Common file locations](#common-file-locations)

---

# Module 1 — Inventory Forecasting

## 1.1 The problem it solves

Every store owner has the same headache: *"I don't want to run out of stock,
but I also don't want to tie up cash in excess inventory."* Getting this
wrong costs money in two directions — lost sales from stockouts, or
products sitting on shelves tying up capital.

**What this module does:** Looks at a product's sales history, predicts
when it'll run out of stock, and creates alerts so the owner can reorder
in time.

**How it's different from guessing:** Uses two statistical techniques —
Prophet (for products with 35+ days of history) or EWMA (for newer
products) — to produce a real prediction with a confidence score, not
a hunch.

---

## 1.2 What the user sees

When the user clicks **Inventory Forecasts** in the sidebar, they land on
a page with three parts:

```
┌──────────────────────────────────────────────────────────┐
│  Inventory Forecasting                                   │
│  🏪 Store selector  [Refresh]  [⚡ Forecast All (N)]     │
│  4,619 products · 5,852 customers · 802,632 transactions │
├──────────────────────────────────────────────────────────┤
│  (Optional) Bulk refresh progress bar                    │
├──────────────────────────────────────────────────────────┤
│  (If any exist) Stock Alerts panel — red warnings        │
├──────────────────────────────────────────────────────────┤
│  Products grid — 3 columns of product cards.             │
│  Each card shows: name, SKU, current stock, price,       │
│  predicted depletion date, and a "Generate AI Forecast"  │
│  button.                                                 │
└──────────────────────────────────────────────────────────┘
```

**Three buttons the user can click:**

1. **Store selector** — switches which store's inventory is shown
2. **Generate AI Forecast** on an individual product card — runs Prophet
   (or EWMA) on that one product
3. **Forecast All** — kicks off a background job that forecasts every
   product in the store

---

## 1.3 Flow 1 — user clicks "Generate AI Forecast" on one product

### Step 1 — frontend (InventoryManager.jsx)

**File:** `client/src/pages/InventoryManager.jsx`

The `handleForecast(productId)` function runs. It:
1. Shows a loading spinner on that specific card (`forecastingId` state)
2. Disables all other forecast buttons to prevent spam
3. Calls `inventoryApi.triggerForecast(productId, token)`

This fires an HTTP POST to `/inventory/forecast/{product_id}` with the
user's auth token in the header.

### Step 2 — backend route (inventory.py)

**File:** `routes/inventory.py`

The route `trigger_forecast(product_id)` receives the request. It simply
calls `generate_forecast(db, org_id, product_id)` from the service layer
and returns whatever comes back.

### Step 3 — the forecasting service (the interesting bit)

**File:** `services/inventory_service.py` → function `generate_forecast`

Here's what happens, step by step:

**a) Verify the product belongs to this org**
```
SELECT p FROM products p JOIN stores s
WHERE p.id = product_id AND s.organization_id = org_id
```
If not found, raise an error. This prevents org A from forecasting org B's
products.

**b) Fetch all sales transactions for this product**
```
SELECT * FROM sales_transactions
WHERE product_id = product_id
ORDER BY sale_date
```

**c) Aggregate by day**
Transactions can happen multiple times per day. Group by date, sum the
quantity. Fill missing days with zero (if no sales happened that day,
that's real info, don't skip it).

Now we have a clean time series like:
```
2010-01-01: 5 units
2010-01-02: 0 units
2010-01-03: 12 units
...
```

**d) Pick the model (Prophet or EWMA)**
- If **35+ days** of history AND Prophet library is installed → use Prophet
- Otherwise → use EWMA (simpler but works on thin data)

**e) Prophet path (the ML one)**

Prophet is Meta's open-source time-series library. You give it
`(date, y)` pairs and it gives you predictions.

```python
m = Prophet(daily_seasonality=True, yearly_seasonality=False)
m.fit(df)  # train on historical
future = m.make_future_dataframe(periods=90)  # next 90 days
forecast = m.predict(future)
```

What Prophet does internally (the simple version):
- Fits a trend line (is the product selling more or less over time?)
- Adds weekly seasonality (Saturdays spike vs Mondays)
- Clips negative predictions to zero (can't sell negative units)

**Depletion date calculation:**
```python
remaining = current_stock
for predicted_day in future:
    remaining -= predicted_day.predicted_sales
    if remaining <= 0:
        depletion_date = predicted_day.date
        break
```

Translation: start with current stock, subtract each day's predicted
sales, note the day you hit zero.

**f) EWMA fallback (simpler)**

EWMA stands for Exponentially Weighted Moving Average. Recent sales
matter more than old ones.

```
daily_velocity = weighted_average(last_14_days_sales)
days_to_depletion = current_stock / daily_velocity
depletion_date = today + days_to_depletion
```

Uses roughly 60% confidence (vs Prophet's ~80%) because the math is
much simpler.

**g) Save the result**
```
INSERT INTO inventory_forecasts (
  product_id, forecast_date=now, predicted_depletion_date, model_used, confidence_score
)
```

**h) Auto-generate stock alerts**
`_manage_alerts(db, product, depletion_date)` runs. It creates alert rows if:
- `current_stock <= 0` → **OUT_OF_STOCK** alert
- `current_stock <= reorder_point` → **LOW_STOCK** alert
- Forecast says we'll hit reorder_point in ≤ 14 days → **REORDER_SOON**
- Forecast says we'll hit zero in ≤ 14 days → **DEPLETION_WARNING**

### Step 4 — back to the frontend

The service returns a dict:
```python
{
  "product_id": 42,
  "product_name": "WHITE HANGING HEART T-LIGHT HOLDER",
  "current_stock": 100,
  "predicted_depletion_date": "2010-03-15T...",
  "model_used": "prophet",
  "confidence_score": 0.82
}
```

Frontend calls `fetchData()` which re-fetches all products. The product
card's "Forecasted Depletion" field now shows the new date instead of
"No forecast calculated". If an alert was created, the red alerts panel
at the top updates too.

---

## 1.4 Flow 2 — user clicks "Forecast All (N products)"

One product takes ~3 seconds. 4,619 products would take ~4 hours. HTTP
requests typically timeout at 60-120 seconds. So we can't do this in a
single HTTP request.

**Solution: background job with live progress.**

### Step 1 — confirmation

Frontend shows a browser `confirm()` dialog with estimated time:
*"This will forecast 3,760 products. Estimated ~188 minutes. Continue?"*

### Step 2 — kick off async job

Clicking Continue calls `inventoryApi.startRefreshJob(token, storeId)`
→ POST `/inventory/refresh-all-forecasts/async?store_id=N`.

### Step 3 — backend registers job, returns immediately

**File:** `services/forecast_jobs.py`

```python
def start_job(store_id, org_id):
    job_id = str(uuid.uuid4())
    _JOBS[job_id] = {
        "status": "queued",
        "total": 0, "processed": 0,
        "succeeded": 0, "failed": 0, "errors": [],
        ...
    }
    threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
    return job
```

Key details:
- Generates a random UUID for the job
- Stores state in an in-memory dict `_JOBS`
- Spawns a **daemon thread** that runs the actual forecasting
- **Returns immediately** with the job_id — HTTP request completes in <1s

### Step 4 — thread runs in background

The thread:
1. Counts all products in the store that have at least one sale
2. Updates `job["total"]` so frontend can compute progress %
3. Loops over each product:
   - Calls `generate_forecast(db, org_id, product_id)` (same code as the single-product flow)
   - Increments `processed` counter
   - On success increments `succeeded`; on failure increments `failed`
     and appends the error (capped at 10 errors)
4. Marks status as `succeeded` or `failed`, sets `finished_at`

### Step 5 — frontend polls every 2 seconds

```javascript
useEffect(() => {
    if (!activeJobId) return;
    const interval = setInterval(async () => {
        const state = await inventoryApi.getRefreshJob(token, activeJobId);
        setJobState(state);
        if (state.status !== 'running' && state.status !== 'queued') {
            clearInterval(interval);
            setActiveJobId(null);
            await fetchData(selectedStoreId);  // refresh product list
        }
    }, 2000);
    return () => clearInterval(interval);
}, [activeJobId]);
```

Every poll hits `GET /inventory/refresh-jobs/{job_id}` which returns a
serialized snapshot:
```json
{
  "status": "running",
  "processed": 450, "total": 3760,
  "succeeded": 448, "failed": 2,
  "progress_pct": 11.9,
  "last_product_name": "WHITE HANGING HEART T-LIGHT HOLDER",
  "errors": [...]
}
```

### Step 6 — progress bar updates live

The React state updates → progress bar redraws with new %. User sees
"processed 450 / 3,760 (11.9%)" with succeeded/failed breakdown.
When status flips to `succeeded`, polling stops, product grid refreshes
and now shows all new forecast dates.

### Safety features

- **One job per scope** — second click on same store returns 409 Conflict
- **TTL cleanup** — finished jobs auto-purged from memory after 1 hour
- **Per-product failure doesn't kill the job** — if Prophet fails on product
  42 (e.g. not enough sales history), it's logged and the loop continues
- **Error cap** — only first 10 errors kept (prevents memory bloat)

---

## 1.5 Complete file map for Module 1

**Frontend:**
- `client/src/pages/InventoryManager.jsx` — the page
- `client/src/utils/api.js` — `inventory` section (getProducts, triggerForecast, startRefreshJob, getRefreshJob)

**Backend routes:**
- `routes/inventory.py` — 5 endpoints (list, forecast one, list alerts, refresh sync, refresh async)

**Backend services:**
- `services/inventory_service.py` — Prophet + EWMA + alert generation
- `services/forecast_jobs.py` — async job registry + worker thread

**Database tables:**
- `products` — what's in the store
- `sales_transactions` — history for Prophet to learn from
- `inventory_forecasts` — where predictions are saved
- `stock_alerts` — auto-generated warnings

**Config:**
- `config/settings.py` — has `ENABLE_SCHEDULED_FORECAST_REFRESH` flag (off by default; the 6-hour auto refresh is disabled because it would take hours on 4,619 products)

---

# Module 2 — Transaction Analytics

## 2.1 The problem it solves

A store has hundreds of thousands of transactions. The owner wants to
answer basic questions fast:
- *"How much revenue in the last 30 days?"*
- *"Is revenue growing or declining?"*
- *"Which products are selling best?"*
- *"Was yesterday unusually bad, or normal for a Sunday?"*

Spreadsheets can answer these, but not quickly and not visually. This
module computes all of these metrics in the backend and renders them as
a dashboard with charts.

---

## 2.2 What the user sees

When the user clicks **Transaction Analytics** in the sidebar:

```
┌──────────────────────────────────────────────────────────┐
│  Transaction Analytics                                   │
│  🏪 Store selector  [Refresh]                            │
│  4,619 products · 5,852 customers · 802,632 transactions │
├──────────────────────────────────────────────────────────┤
│  ℹ Window anchored to January 28, 2010 (historical data) │
├──────────────────────────────────────────────────────────┤
│  [Revenue card]   [Orders card]   [AOV card]             │
│     $498k            19,310         $25.79               │
│     +15% growth      +12%           +2.7%                │
├──────────────────────────────────────────────────────────┤
│  Revenue Trend (last 30 days) — line chart               │
├──────────────────────────────────────────────────────────┤
│  Top Products list    |    Sales Anomalies list          │
└──────────────────────────────────────────────────────────┘
```

**Things the user can do:**
- Switch store via dropdown
- Click **Refresh** to re-fetch fresh data
- Hover over chart points to see exact values

---

## 2.3 Full flow — from page load to dashboard

### Step 1 — page mounts, fetches stores

**File:** `client/src/pages/TransactionAnalytics.jsx`

The page has two `useEffect` hooks:

**Hook 1 (runs once):**
```javascript
customerAnalytics.listStores(token)
  → gets the list of stores for this org
  → defaults to biggest store by transaction count
```

**Hook 2 (runs when store changes):**
```javascript
storeAnalytics.getDashboard(token, storeId)
  → GET /analytics/dashboard?store_id=N
```

### Step 2 — backend route

**File:** `routes/analytics.py`

The `get_analytics_dashboard()` function calls **four service functions
in sequence** and returns all four results in one JSON response:

```python
kpis = get_store_kpis(db, org_id, store_id)
trends = get_sales_trends(db, org_id, days=30, store_id=store_id)
top_products = get_top_products(db, org_id, limit=5, days=30, store_id=store_id)
anomalies = detect_sales_anomalies(db, org_id, days=60, store_id=store_id)

return {
    "as_of_date": kpis["as_of_date"],
    "kpis": kpis,
    "trends": trends,
    "top_products": top_products,
    "anomalies": anomalies
}
```

Why call four functions instead of one big query? Separation of concerns —
each function has its own logic and can be tested independently. Also
if one of them fails (e.g. anomaly detector returns empty), the others
still work.

---

## 2.4 The four service functions explained

### Function 1 — `get_store_kpis`

**File:** `services/analytics_service.py`

**What it answers:** Revenue, Orders, Average Order Value (AOV), and
percentage change vs the prior 30 days.

**The "anchor date" trick:**

Normally "last 30 days" means today minus 30 days. But what if the data
is historical (from 2010)? Today's query would match zero transactions.

**Solution:** Instead of anchoring to `datetime.utcnow()`, we anchor
to `max(sale_date)` for this org/store. For a live store that's basically
today. For historical data, it becomes "last 30 days ending at the most
recent transaction in the data".

```python
anchor = max(sale_date for this store)  # e.g. 2010-01-28 for OR-II
thirty_days_ago = anchor - 30 days        # e.g. 2009-12-29

current_revenue = SUM(total_amount)
                  WHERE sale_date BETWEEN thirty_days_ago AND anchor

prev_revenue    = SUM(total_amount)
                  WHERE sale_date BETWEEN (anchor - 60d) AND thirty_days_ago

growth_pct = (current - prev) / prev * 100
```

This returns:
```json
{
  "as_of_date": "2010-01-28T16:39:00",
  "revenue": {"value": 498098.64, "growth": 15.3},
  "orders": {"value": 19310, "growth": 12.0},
  "aov": {"value": 25.79, "growth": 2.7}
}
```

### Function 2 — `get_sales_trends`

**What it answers:** Daily revenue + quantity for the last 30 days.

**How it works:**

1. Pull all transactions in the window
2. Group by date, sum revenue and quantity
3. **Reindex** to a complete date range (fill missing days with zero —
   important so the chart doesn't skip days)
4. Return as `[{date: "2010-01-01", revenue: 15234.50, quantity: 620}, ...]`

Frontend feeds this array to Recharts' `AreaChart` component. Done.

### Function 3 — `get_top_products`

**What it answers:** Best-selling products in the window, by revenue.

**Single SQL query:**
```python
SELECT Product.id, Product.name, Product.sku,
       SUM(total_amount) AS revenue,
       SUM(quantity) AS qty
FROM sales_transactions
JOIN products ON ...
JOIN stores ON ...
WHERE store_id = N AND sale_date >= window_start
GROUP BY Product.id
ORDER BY revenue DESC
LIMIT 5
```

No ML, just a well-designed SQL query. Fast.

### Function 4 — `detect_sales_anomalies` (the interesting one)

**What it answers:** Which days had unusually high or low revenue?

**Naive approach (DOESN'T work well):** Compute average revenue over the
last 60 days, flag days that are 2 standard deviations away from average.

**Problem:** Weekends systematically have lower revenue than weekdays.
This naive approach would flag every single Saturday as "drop" — which
is nonsense, Saturdays are *normally* lower.

**Our approach — day-of-week aware baseline:**

Compare each day only against the baseline of the SAME weekday.
- Mondays compared against past Mondays
- Sundays compared against past Sundays
- etc.

```python
for each weekday (Mon..Sun):
    compute exponentially-weighted mean of past observations of THAT weekday
    compute exponentially-weighted std of past observations of THAT weekday
    for each day in that weekday group:
        z_score = (revenue - dow_mean) / dow_std
        if |z_score| > 1.8:
            flag as spike (+) or drop (-)
```

**Why "exponentially weighted"?** Recent weekends matter more than 8-week-
old weekends. EWMA gives recent observations higher weight automatically.

**Why threshold 1.8 instead of 2.0?** Because the day-of-week baseline is
sharper (less noise), we can afford a tighter threshold without triggering
false positives.

**Extra safeguards:**
- Proportional standard deviation floor (prevents tiny variance windows
  from producing huge z-scores on small absolute swings)
- Filter zero-revenue days where the weekday is also normally near-zero
  (handles permanently-closed Sundays correctly)

**Returns:**
```json
[
  {
    "date": "2010-01-15", "weekday": "Fri",
    "actual_revenue": 85000, "expected_revenue": 45000,
    "type": "spike", "z_score": 3.2, "severity": "high"
  },
  ...
]
```

### Step 3 — frontend renders

React state updates with the dashboard JSON. Each sub-component reads
the piece it cares about:
- `<StatCard>` × 3 → renders KPIs
- `<AreaChart>` → renders trend
- Top products `<div>` → renders product list with ranking
- Anomalies `<div>` → renders red/green pills per flagged day

---

## 2.5 Complete file map for Module 2

**Frontend:**
- `client/src/pages/TransactionAnalytics.jsx` — the page
- `client/src/utils/api.js` — `storeAnalytics` section (getDashboard, getAnomalies)

**Backend routes:**
- `routes/analytics.py` — `/analytics/dashboard`, `/analytics/anomalies`

**Backend services:**
- `services/analytics_service.py` — all four functions above

**Database tables used (read-only):**
- `sales_transactions`, `products`, `stores` — all joined to scope to org + store

**No ML model files.** Everything is SQL + pandas.

---

# Module 3 — Lead Scoring

## 3.1 The problem it solves

A B2B salesperson has 500 leads sitting in a spreadsheet. Which 50
should they prioritize? Which 200 should get automated nurture emails?
Which 250 are time-wasters?

Doing this manually takes hours and is subjective. This module:
1. **Scores each lead** with a win probability (0-100%)
2. **Buckets each lead** into one of three allocation decisions:
   - AI_OUTREACH — good enough to bother emailing
   - MANUAL_REVIEW — high-value, needs human attention
   - NURTURE_CAMPAIGN — long-shot, send periodic content only
3. **Drafts + sends** the initial outreach email via AI (for AI_OUTREACH
   leads), tracking conversation state

---

## 3.2 What the user sees

When the user clicks **Lead Scoring** in the sidebar:

```
┌──────────────────────────────────────────────────────────┐
│  Lead Scoring                                            │
│  [📄 Drop CSV file here or click to browse]              │
│                                                          │
│  Total: 0  |  AI: 0  |  Review: 0  |  Nurture: 0         │
│                                                          │
│  [Filter: All ▼]  [Send AI Outreach]  [Refresh] [Delete] │
├──────────────────────────────────────────────────────────┤
│  (Empty state — upload a CSV to get started)             │
└──────────────────────────────────────────────────────────┘
```

After uploading a CSV:
```
┌──────────────────────────────────────────────────────────┐
│  Total: 200  |  AI: 87  |  Review: 23  |  Nurture: 90    │
├──────────────────────────────────────────────────────────┤
│  │ Company         │ Email      │ Industry │ Score │ Status │
│  │ Acme Corp       │ j@acme.com │ Software │ 82%   │ AI     │
│  │ Bob's Tacos     │ b@tacos.co │ Food     │ 12%   │ Nurture│
│  │ Mega Bank       │ m@bank.com │ Finance  │ 78%   │ Review │
│  ...                                                    │
└──────────────────────────────────────────────────────────┘
```

---

## 3.3 Flow 1 — CSV upload with smart column mapping

### Step 1 — user drops a CSV

**File:** `client/src/pages/LeadManager.jsx`

The drop zone calls `leadsApi.analyzeColumns(file, token)` FIRST (not
upload yet) — we need to figure out which columns in their CSV map to
which fields in our database.

### Step 2 — column detection endpoint

**POST `/leads/columns`**

**File:** `routes/leads.py`

Reads the CSV header row only. Runs fuzzy matching to suggest mappings:

```python
canonical_fields = {
  "company_name": ["company", "business_name", "org_name", "account_name"],
  "email": ["email", "email_address", "contact_email", "e-mail"],
  "phone": ["phone", "telephone", "mobile"],
  "decision_maker_job_title": ["job_title", "title", "role", "position"],
  "industry": ["industry", "sector", "vertical"],
  ... etc
}
```

For each column in the user's CSV, find the closest canonical field name
(difflib's `get_close_matches` with cutoff 0.7). Return the suggestions
as a dictionary.

### Step 3 — column mapping UI

The frontend shows:

```
╔══════════════════════════════════════╗
║  Map your columns                    ║
║                                      ║
║  Your CSV Column  →  System Field    ║
║  "Company"        →  [company_name▼] ║  ← pre-selected via fuzzy match
║  "Work Email"     →  [email▼]        ║
║  "Biz Type"       →  [industry▼]     ║
║  "# Staff"        →  [employee_count▼]║
║  "Phone"          →  [-- skip --▼]   ║  ← user manually skipped
║                                      ║
║  [Cancel]  [Upload and Score]        ║
╚══════════════════════════════════════╝
```

User can adjust any dropdown manually, then click "Upload and Score".

### Step 4 — scoring endpoint

**POST `/leads/upload`** (with file + confirmed mapping as form data)

**File:** `routes/leads.py` → service function

**What happens:**

**a) Parse CSV**
Read all rows into a pandas DataFrame. Rename columns per the user's
mapping.

**b) Normalize bucket fields**
- `employee_count` — parse raw strings like "450" or "250k" → bucket into
  "1-50", "51-200", "201-1000", "1000+"
- `annual_revenue_range` — similar bucketing: "<$1M", "$1-10M", "$10-50M", ">$50M"

This normalization is critical because the ML model was trained on
bucketed values, not raw numbers.

**c) Duplicate detection**
For each lead, check if `(email, company_name)` pair already exists in
this org. If yes, skip.

**d) Batch score via XGBoost**

**File:** `services/lead_scoring_service.py` → `score_leads_batch()`

This is where the ML happens. Full pipeline:

```
Input lead dict
    │
    ▼
Check feature count (≥2 non-empty model features?)
    │
   ┌┴─────────────────┐
   NO                YES
   │                  │
   ▼                  ▼
Fallback score     Apply preprocessing
= 0.30             (OneHotEncoder + TargetEncoder)
                     │
                     ▼
                   Feed to XGBoost
                     │
                     ▼
                   predict_proba()[:, 1]
                     │
                     ▼
                   win_probability (0-1)
```

**What XGBoost actually is:**
XGBoost = "Extreme Gradient Boosting". It's an ensemble of decision
trees. Each tree makes a rough prediction, and each successive tree
corrects the errors of the previous ones. The final prediction is a
weighted sum.

For **classification** (our case), XGBoost outputs a probability — how
likely is this lead to convert?

**The 6 features it uses:**
1. City (e.g. "New York")
2. Decision Maker Job Title (e.g. "VP of Engineering")
3. Industry (e.g. "Software")
4. Country (e.g. "United States")
5. Employee Count bucket (e.g. "201-1000")
6. Annual Revenue Range bucket (e.g. "$10-50M")

**Where the trained model lives:**
`D:\final-year-project-v1\lead_scorer_pipeline.pkl` (~400KB)

**When was it trained:**
Training script is `train_lead_scorer.py` at project root. Trained once
on 20,000 synthetic B2B leads (generated via CTGAN). Achieved ~0.8+
AUC-ROC on validation. Not retrained automatically — to retrain, re-run
the script with new data.

**e) Map probability to allocation bucket**

**Function:** `get_allocation_decision(probability)`

```python
if probability >= 0.60:
    return "MANUAL_REVIEW"      # hot lead — deserves human attention
elif probability >= 0.10:
    return "AI_OUTREACH"        # decent prospect — AI can handle
else:
    return "NURTURE_CAMPAIGN"   # low signal — long-shot
```

**Why these thresholds?**
- 60%+ leads are high-value enough that a human should review before
  automation
- 10-60% is the sweet spot for AI drafting — these leads are
  plausible but not certain winners
- Below 10% just needs long-term nurture (a blog drip), not a direct
  pitch

**f) Save leads to DB**

For each lead:
```python
lead = Lead(
    organization_id=org_id,
    company_name=..., email=..., industry=...,
    win_probability=0.82,
    allocation_decision="AI_OUTREACH",
    status="PENDING",
)
db.add(lead)
db.commit()
```

**g) Return summary to frontend**

```json
{
  "new_leads": 187,
  "duplicates_skipped": 13,
  "allocations": {"AI_OUTREACH": 87, "MANUAL_REVIEW": 23, "NURTURE_CAMPAIGN": 77},
  "avg_win_probability": 0.37,
  "warnings": ["3 rows missing email", "5 rows with invalid employee_count"]
}
```

### Step 5 — frontend updates table

Frontend calls `leadsApi.getLeads(token)` → re-fetches full lead list →
table re-renders with new rows + updated counts in the stats bar.

---

## 3.4 Flow 2 — user clicks "Send AI Outreach"

This is the coolest part. The system auto-drafts + sends personalized
emails via a local LLM.

### Step 1 — user opens outreach modal

Button click opens `<BulkOutreachModal>`. User enters a campaign goal:
*"Introduce our new pricing tier to mid-market leads"* (pre-filled with
a sensible default).

Click "Start Campaign" → `leadsApi.triggerBulkOutreach(goal, token)` →
POST `/leads/bulk-outreach`.

### Step 2 — endpoint queues background task

**File:** `routes/leads.py`

```python
# Find all leads eligible for outreach
leads = query(Lead).filter(
    org_id == current_user.organization_id,
    allocation_decision == "AI_OUTREACH",
    status == "PENDING",
    email.isnot(None),
)

# Mark them as "drafting" so user knows we're working
leads.update(status="DRAFTING_OUTREACH")

# Fire and forget — background task
BackgroundTasks.add_task(process_bulk_outreach, org_id, goal, lead_ids)

return {"status": "success", "count": len(leads)}
```

Frontend sees success immediately. Real work happens in the background.

### Step 3 — background task generates emails

**File:** `services/outreach_service.py`

For each lead, the `generate_initial_email` function runs a **multi-step
AI pipeline**:

```
1. RAG retrieval
   └── Fetch org knowledge base chunks relevant to the lead's industry

2. Build prompt
   └── System prompt + user prompt with:
       - Lead data (company, contact, industry)
       - Campaign goal
       - RAG context (our product info)
       - Sender identity (name, company)

3. Call local LLM (Ollama)
   └── Model: llama3.1:8b-instruct-q8_0
   └── Max 300 tokens (emails should be short)

4. Deterministic validator
   └── Strip [bracket placeholders]
   └── Ensure email has a signoff
   └── Truncate if > 200 words

5. LLM quality-check agent (optional second pass)
   └── Re-evaluate email against 5 criteria
   └── Rewrite if it fails

6. Final email string
```

### Step 4 — send + log

**Function:** `send_and_log_email`

```python
# Send via Gmail SMTP (uses SMTP_EMAIL/SMTP_PASSWORD from .env)
smtp.send(to=lead.email, subject=email.subject, body=email.body)

# Create/update AutomatedOutreach record
outreach = AutomatedOutreach(
    lead_id=lead.id,
    conversation_state=[
        {"role": "assistant", "content": email.body, "type": "outreach", "sent_via_smtp": True}
    ],
    last_message_at=datetime.utcnow(),
    outcome="IN_PROGRESS",
)

# Flip lead status
lead.status = "AI_ACTIVE"
```

### Step 5 — progress (poll for status)

User can refresh the page any time. Lead statuses transition from
DRAFTING_OUTREACH → AI_ACTIVE as emails go out.

---

## 3.5 Lead status lifecycle (what the status column means)

```
NEW CSV UPLOAD
      │
      ▼
  PENDING ──────────────────┐
      │                     │
      │ (bulk outreach)     │ (manual override)
      ▼                     ▼
 DRAFTING_OUTREACH    MANUAL_REVIEW
      │                     │
      ▼                     ▼
  AI_ACTIVE      human takes over
      │                     │
      │                     ▼
      │            (sales team
      │             closes deal
      │             manually)
      ▼
  CLOSED_WON or CLOSED_LOST
      │
      ▼
  (if CLOSED_WON) ──► auto-triggers
                      MCQ generation from
                      conversation transcript
                      (lead_to_mcq_service)
```

**Status meanings:**
- `PENDING` — just uploaded, no action taken yet
- `DRAFTING_OUTREACH` — bulk task is generating email, brief transient state
- `AI_ACTIVE` — outreach sent, awaiting response
- `MANUAL_REVIEW` — high-value lead flagged for human review
- `CLOSED_WON` — deal closed, system auto-generates an MCQ test from
  the conversation for training other reps
- `CLOSED_LOST` — deal lost, archived

---

## 3.6 Complete file map for Module 3

**Frontend:**
- `client/src/pages/LeadManager.jsx` — the whole page
- `client/src/utils/api.js` — `leadsApi` section (8 methods)

**Backend routes:**
- `routes/leads.py` — 8 endpoints

**Backend services:**
- `services/lead_scoring_service.py` — XGBoost inference + allocation decision
- `services/outreach_service.py` — email generation + SMTP sending
- `services/email_service.py` — Gmail SMTP wrapper
- `services/lead_to_mcq_service.py` — auto-MCQ from closed-won conversation

**ML artifacts:**
- `lead_scorer_pipeline.pkl` — trained XGBoost pipeline (~400KB)
- `train_lead_scorer.py` — training script
- `b2b_leads_final.csv` — training data (20k synthetic leads)

**Database tables:**
- `leads` — all scored leads
- `automated_outreach` — 1:1 with leads, tracks email conversation state

**Configuration (`.env`):**
- `SMTP_EMAIL` — Gmail address for sending
- `SMTP_PASSWORD` — Gmail app password

---

# Shared concepts you'll see in all 3

## Authentication flow

Every API request sends an `Authorization: Bearer <jwt>` header. On the
backend, the `get_current_user` dependency validates the JWT and loads
the User object from the DB. The `organization_id` on User scopes every
query — org A can never see org B's data.

## Tables scoped by `organization_id`

Products, SalesTransactions, Leads, etc. all have an `organization_id`
foreign key. All queries filter on this. It's not optional — every route
uses `current_user.organization_id` automatically.

## Store scoping

Beyond org scoping, three of our modules also have a `store_id` query
param on their endpoints so a user can drill into one store when they
have multiple connected.

## React `useEffect` polling

Two places use this pattern:
- Inventory: polling `/inventory/refresh-jobs/{job_id}` every 2s during
  a background forecast job
- Lead Scoring: polling `/leads/` on a refresh button to see new emails
  go out

Both stop polling automatically when the job finishes or component unmounts.

## Background tasks

Two patterns:
- **Threading-based** (inventory forecasts) — `threading.Thread` with
  an in-memory job registry
- **FastAPI BackgroundTasks** (bulk outreach) — runs after the HTTP
  response is sent

Neither survives a server restart. For production, we'd add Redis/Celery.

---

# Common file locations

```
project_root/
├── routes/
│   ├── inventory.py          # Module 1 endpoints
│   ├── analytics.py          # Module 2 endpoints
│   └── leads.py              # Module 3 endpoints
│
├── services/
│   ├── inventory_service.py        # Prophet/EWMA forecasting + alerts
│   ├── forecast_jobs.py            # Async forecast refresh registry
│   ├── analytics_service.py        # KPIs, trends, top products, anomalies
│   ├── lead_scoring_service.py     # XGBoost inference
│   ├── outreach_service.py         # LLM email generation
│   ├── email_service.py            # SMTP sender
│   └── lead_to_mcq_service.py      # Closed-won → MCQ auto-generation
│
├── models/
│   ├── inventory.py          # Store, Product, SalesTransaction,
│   │                         # InventoryForecast, StockAlert, Customer
│   └── lead.py               # Lead, AutomatedOutreach
│
├── client/src/
│   ├── pages/
│   │   ├── InventoryManager.jsx
│   │   ├── TransactionAnalytics.jsx
│   │   ├── LeadManager.jsx
│   │   └── App.jsx                 # routes all 3 pages
│   └── utils/
│       └── api.js                  # API helper sections
│
├── lead_scorer_pipeline.pkl        # Trained XGBoost model
├── train_lead_scorer.py            # Training script
└── b2b_leads_final.csv             # Training data
```

---

# One-paragraph summary per module (in case you forget everything)

**Inventory Forecasting:**
Looks at sales history per product, uses Prophet (or EWMA for short
history) to predict when stock will run out, creates alerts before
it happens. Single-product forecast is synchronous (~3s). Bulk refresh
is async with a progress bar because 4,619 products × 3s = 4 hours.

**Transaction Analytics:**
Four SQL/pandas queries for revenue, trends, top products, and
day-of-week aware anomaly detection. Anchors all time windows to the
latest transaction date (not today) so historical datasets work. No
ML, just well-designed aggregations.

**Lead Scoring:**
CSV upload with fuzzy column auto-detection → XGBoost scores each
lead (6 features, ~400KB model) → buckets into AI_OUTREACH /
MANUAL_REVIEW / NURTURE_CAMPAIGN. Bulk outreach triggers background
task that uses local LLM (Llama 3.1 via Ollama) + RAG to draft
personalized emails, sends via Gmail SMTP, tracks conversation state.
On CLOSED_WON, auto-generates MCQ test from the conversation.

---

# Where to look for ML details

| Module | What's ML | Library | File |
|---|---|---|---|
| Inventory | Prophet time-series | `prophet==1.3.0` | `services/inventory_service.py` |
| Transaction | None (pure SQL + pandas) | — | — |
| Lead Scoring | XGBoost classifier | `xgboost==3.2.0` | `lead_scorer_pipeline.pkl` |

---

# When to read this guide again

- **Before viva** — reinforces the "what happens when X is clicked" story panel asks
- **When debugging** — shows the exact file → function → DB path for any feature
- **When adding a new module** — use one of these as a template. Same
  pattern: Page → `api.js` helper → route → service → model → DB → JSON
  back up the chain.
