# Mobile Money Fraud Monitoring

A fraud monitoring pipeline on 6.3M mobile-money transactions (PaySim dataset). It loads the data, checks its quality, flags suspicious transactions with rules and an ML model, and checks that every step ran correctly. One command runs it all.

**Tools:** PostgreSQL (Docker), Python, SQL, LightGBM

## Results

Test period: days 16-31, 4,196 frauds.

| Approach | Alerts/day | Precision | Fraud caught |
|---|---|---|---|
| Existing system flag | 0.8 | 100% | 0.3% |
| Best rule (R02) | 106 | 100% | 40.3% |
| ML model, all features | 259 | 99.98% | 98.8% |
| ML model, no balance features | 136 | 52.1% | 27.1% |

- The existing flag misses almost all fraud.
- One good rule catches 40% with no false alarms.
- The ML model looks near perfect, but that's because PaySim's balance columns give the answer away. Without them it catches 27% at 52% precision, which is closer to what real data would give.

## How it works

```
paysim.csv
  -> load            all 6.3M rows into PostgreSQL
  -> quality checks  stop if the data is broken
  -> clean           keep TRANSFER and CASH_OUT only (2.77M rows, all the fraud is here)
  -> features        built in SQL, using only past data
  -> rules           2 fraud rules
  -> model           LightGBM, limited to 200 alerts/day (investigator capacity)
  -> controls        check nothing went wrong
  -> alert queue     reports/alert_queue.csv, the list the fraud team works through
```

## Output: the alert queue

Each run saves `reports/alert_queue.csv`: every transaction the team should check, which account was drained and where the money went.

| day | rule | amount | victim account | sender before | sender after | suspected mule | receiver before | receiver after |
|---|---|---|---|---|---|---|---|---|
| 1 | R02 | 6,188,514.81 | C135832352 | 6,188,514.81 | 0 | C2009346140 | 0 | 0 |

The victim's account was emptied, and the receiving account had 0 before and 0 after: the money went straight through. The investigator would freeze the suspected mule account and contact the victim.

## Run it

```bash
cp .env.example .env               # set a database password
docker compose up -d
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m src.dataset              # download the data
python run_pipeline.py             # run everything (~1.5 min)
```

All thresholds and settings are in `config.yaml`.

## Rules

| Rule | What it looks for | Precision | Fraud caught | Decision |
|---|---|---|---|---|
| R01 | sender's account emptied | 1.8% | 94.4% | catches most fraud but 14,000 alerts/day, too many to check |
| R02 | big transfer to an empty account | 100% | 40.3% | keep |

I also tried rules for mule accounts with many senders, amounts just under a limit, and balances that don't add up. None caught real fraud in this data, so I removed them.

## Controls

Every run checks that no rows were lost while loading, the right transactions were kept, the features have no gaps, every alert points to a real transaction, and the model's alerts per day stay close to 200. All pass.

## Limitations

- PaySim is synthetic. The balance columns make fraud too easy to spot, so the realistic result is the model without them.
- Some real fraud types (like many small payments into one mule account) aren't in PaySim, so rules for them couldn't be tested.
