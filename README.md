# Mobile Money Fraud Monitoring Pipeline

An end-to-end transaction monitoring pipeline on **6.3M mobile-money transactions** (PaySim), built the way a bank's risk analytics team would run it: load → data quality → SQL features → rule-based alerts → ML risk score → controls, all from one command.

**Stack:** PostgreSQL 16 (Docker), Python 3.11 (pandas, scikit-learn, LightGBM), SQL window functions.

---

## Headline results

Test period = days 16–31 (4,196 frauds, ~262 frauds/day). The model threshold was set on the validation period and applied unchanged to test.

| Approach | Alerts/day | Precision | Fraud caught (recall) |
|---|---|---|---|
| Existing system flag (`isFlaggedFraud`) | 0.8 | 100% | **0.3%** |
| Best single rule (R02 empty mule account) | 106 | 100% | 40.3% |
| ML model, all features (LightGBM) | 259 | 99.98% | 98.8% |
| ML model, **no balance features** (robust run) | 136 | 52.1% | 27.1% |

**Takeaway:** the legacy flag misses almost everything. One well-designed rule catches 40% with zero false alarms. The ML score catches nearly all fraud, but most of that comes from balance columns that are a known simulation artefact (see [Limitations](#limitations)). The honest, robust model sits around **50% precision / 27% recall**.

---

## How it works

```
paysim.csv
   │  COPY (6.3M rows in ~15s)
   ▼
transactions_raw ──► data quality checks (stop on CRITICAL)
   │
   ▼
transactions_clean   (TRANSFER + CASH_OUT only, 2.77M rows: all fraud is in these two types)
   │
   ▼
features             (leakage-safe window functions on the destination account)
   │
   ├──► rules R01–R05 + legacy flag ──► alerts, rule_performance
   ├──► LightGBM / logistic regression ──► artifacts/ (model + metrics)
   ▼
controls             (reconciliation, completeness, alert integrity, capacity) ──► control_log
```

Every run gets a `run_id` and is recorded in `pipeline_runs` with status `SUCCESS`, `CONTROLS_FAILED` or `FAILED`. The script exits with code 1 on failure, so a scheduler (cron/Airflow) can pick it up.

---

## Quick start

```bash
# 1. database
cp .env.example .env              # set your own password
docker compose up -d

# 2. python
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. data (needs a Kaggle account)
python -m src.dataset             # downloads to data/paysim.csv

# 4. run everything
python run_pipeline.py            # full run, ~1.5 min
python run_pipeline.py --skip-load   # reuse data already in postgres
```

All thresholds, the train/valid/test split and the alert budget live in `config.yaml`.

---

## The pipeline, step by step

### 1. Load
Raw CSV is streamed into `transactions_raw` with PostgreSQL `COPY`: 6,362,620 rows in ~15 seconds. The raw table is never modified, so every later step can be traced back to the source.

### 2. Data quality
9 checks with a severity level. A failed **CRITICAL** check stops the pipeline.

| Severity | Checks | Result |
|---|---|---|
| CRITICAL | nulls in key columns, negative amounts, unknown types, invalid labels | all PASS |
| WARNING | duplicates, step out of range, zero amounts | 16 zero-amount rows (WARN) |
| INFO | sender balance doesn't reconcile, self-transfers | 3.6M balance mismatches (known PaySim behaviour, informational only) |

### 3. Features (SQL)
Built with window functions partitioned by **destination account**. In PaySim, sender accounts almost never repeat, but receiving accounts do, and that's also where mule accounts show up.

Every window ends at `1 PRECEDING`, so a transaction only "sees" the past, never itself or the future (no look-ahead leakage).

Examples: transactions and amount received by the destination in the last 24h, hours since the destination was last used, amount vs the destination's usual amount, whether the sender's account was drained.

### 4. Rule scenarios
Each rule maps to a real fraud typology and has its thresholds in `config.yaml`.

| Rule | Typology | Test alerts/day | Precision | Recall | Verdict |
|---|---|---|---|---|---|
| R01 Account drain | Account takeover | 14,174 | 1.8% | 94.4% | **Retire / redesign.** Catches fraud but buries investigators. Tuning the drain ratio and minimum amount didn't push precision above ~2%. |
| R02 Empty dest, high value | Mule / pass-through | 106 | 100% | 40.3% | **Keep.** Best rule by far. |
| R03 Mule fan-in | Collection account | 12.6 | 0.5% | 0.02% | **Retire.** PaySim doesn't simulate fan-in mules. |
| R04 Structuring | Smurfing | 0.6 | 0% | 0% | **Keep as coverage.** Typology not present in PaySim, but a real bank would need it. |
| R05 Balance mismatch | System / data anomaly | 24,890 | ~0% | 0.3% | **Move to data quality.** It flags simulation noise, not fraud. |
| Legacy flag | TRANSFER > 200k | 0.8 | 100% | 0.3% | Benchmark only. |

### 5. ML risk score
- **Time-based split:** train days 1–12, validation days 13–15, test days 16–31. Never random, because in production you always predict the future from the past.
- **Models:** logistic regression (baseline) vs LightGBM; the champion is picked on **validation PR-AUC only**.
- **Why PR-AUC:** fraud is ~0.3% of transactions, so accuracy is meaningless (predicting "no fraud" every time scores 99.7%).
- **Alert budget:** the threshold is set on validation to produce **200 alerts/day** (investigator capacity), then frozen and applied to test.

| Model | Features | PR-AUC valid | PR-AUC test |
|---|---|---|---|
| Logistic regression | all | 0.959 | 0.990 |
| **LightGBM (champion)** | all | 0.999 | 0.9999 |
| Logistic regression | no balance features | 0.008 | 0.067 |
| **LightGBM (champion)** | no balance features | 0.180 | 0.343 |

On test the frozen threshold produced **259 alerts/day** instead of 200, because fraud volume changes over time. That drift is exactly what control C05 watches.

### 6. Controls
Each run writes one row per control to `control_log`. Any FAIL marks the run `CONTROLS_FAILED`.

| Control | What it protects against | Result |
|---|---|---|
| C01 Load reconciliation | rows lost while loading | PASS (6,362,620 = 6,362,620) |
| C02 Scope | wrong population being monitored | PASS (2,770,409) |
| C03 Feature completeness | missing rows or null features feeding the model | PASS |
| C04 Alert integrity | alerts pointing at transactions that don't exist | PASS |
| C05 Capacity | model alert volume drifting away from investigator capacity (±30%) | PASS (259 vs 200) |

---

## Limitations

- **Balance-feature artefact.** PaySim's balance columns almost perfectly separate fraud (PR-AUC 0.9999). Real bank data wouldn't be this clean, so I reran the model without them. Results drop to PR-AUC 0.18 (validation) / 0.34 (test), and LightGBM stops early after very few trees. Treat the robust numbers as the realistic range, not the 99.98%.
- **Synthetic data.** Some typologies (fan-in mules, structuring) aren't simulated, so those rules can't be validated here.
- **Small validation window.** 3 days of validation makes threshold setting and early stopping noisy.
- **Activity drops after ~day 17**, so alerts per day on test aren't representative of a steady state.

## Next steps

- A per-day "top 200 queue" instead of a fixed score threshold, so alert volume always matches capacity.
- Score-drift monitoring (PSI) between training and new data.
- A Power BI dashboard on `rule_performance`, `dq_results` and `control_log`.

---

## Project structure

```
├── run_pipeline.py        # one command, runs every stage
├── config.yaml            # thresholds, split, alert budget
├── docker-compose.yml     # PostgreSQL 16
├── sql/                   # schema, quality checks, cleaning, features, rules/
├── src/                   # db, load, quality, features, rules, model, controls
├── artifacts/             # metrics JSON (model files git-ignored)
└── reports/               # PR curve, capacity curve, feature importance
```
