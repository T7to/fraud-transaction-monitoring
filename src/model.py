"""Train a fraud risk model and check it against the daily alert budget."""

import json
import logging

import joblib
import lightgbm as lgb
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.db import copy_to_df, get_connection, load_config

logger = logging.getLogger(__name__)

NOT_FEATURES = ["txn_id", "step", "day", "isfraud"]
LOG_COLUMNS = ["error_balance_orig", "error_balance_dest", "dest_prior_amount_24h",
               "dest_prior_avg_amount", "pct_balance_moved", "amount_vs_dest_avg"]


def load_data(conn, cfg):
    df = copy_to_df(conn, "SELECT * FROM features ORDER BY txn_id")

    # Split by time, never randomly: train on the past, test on the future.
    train = df[df["step"] <= cfg["split"]["train_end_step"]]
    valid = df[(df["step"] > cfg["split"]["train_end_step"]) & (df["step"] <= cfg["split"]["valid_end_step"])]
    test = df[df["step"] > cfg["split"]["valid_end_step"]]
    return train, valid, test


def prepare(df, cfg):
    X = df.drop(columns=NOT_FEATURES + cfg["model"]["drop_features"])

    # Signed log: shrinks huge money values but keeps negatives negative.
    for col in LOG_COLUMNS:
        if col in X.columns:
            X[col] = np.sign(X[col]) * np.log1p(X[col].abs())

    # NULL means "undefined" (e.g. no history yet), so give it a value it can never have.
    X = X.fillna(-1)
    return X, df["isfraud"]


def train_models(X_train, y_train, X_valid, y_valid):
    logistic = make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000))
    logistic.fit(X_train, y_train)

    # Give fraud extra weight because it is rare (square root = a moderate boost).
    pos_weight = np.sqrt((y_train == 0).sum() / (y_train == 1).sum())
    lightgbm = lgb.LGBMClassifier(n_estimators=1000, learning_rate=0.05,
                                  scale_pos_weight=pos_weight, random_state=42, verbose=-1)
    # Stop adding trees once validation PR-AUC has not improved for 50 trees.
    lightgbm.fit(X_train, y_train, eval_set=[(X_valid, y_valid)], eval_metric="average_precision",
                 callbacks=[lgb.early_stopping(50, verbose=False)])

    return {"logistic": logistic, "lightgbm": lightgbm}


def alert_results(y, scores, threshold, n_days):
    alerts = scores >= threshold
    caught = int(y[alerts].sum())
    return {
        "alerts_per_day": round(int(alerts.sum()) / n_days, 1),
        "precision": round(caught / max(int(alerts.sum()), 1), 4),
        "recall": round(caught / int(y.sum()), 4),
    }


def run_model(conn, cfg):
    train, valid, test = load_data(conn, cfg)
    X_train, y_train = prepare(train, cfg)
    X_valid, y_valid = prepare(valid, cfg)
    X_test, y_test = prepare(test, cfg)

    models = train_models(X_train, y_train, X_valid, y_valid)

    pr_auc = {}
    for name, model in models.items():
        pr_auc[name] = {
            "valid": round(average_precision_score(y_valid, model.predict_proba(X_valid)[:, 1]), 4),
            "test": round(average_precision_score(y_test, model.predict_proba(X_test)[:, 1]), 4),
        }
        logger.info("%-8s PR-AUC %s", name, pr_auc[name])

    # The champion is chosen on validation only; test stays untouched for the final report.
    champion = max(pr_auc, key=lambda name: pr_auc[name]["valid"])
    model = models[champion]
    logger.info("Champion: %s", champion)

    # Threshold = score of the Nth highest validation transaction, N = budget x number of days.
    budget = cfg["model"]["alert_budget_per_day"]
    valid_scores = np.sort(model.predict_proba(X_valid)[:, 1])[::-1]
    threshold = valid_scores[budget * valid["day"].nunique() - 1]

    # Apply that same threshold to the test period, without adjusting it.
    test_scores = model.predict_proba(X_test)[:, 1]
    results = alert_results(y_test.to_numpy(), test_scores, threshold, test["day"].nunique())
    logger.info("Test at %d alerts/day budget: %s", budget, results)

    variant = "robust" if cfg["model"]["drop_features"] else "full"
    joblib.dump({"model": model, "features": list(X_train.columns), "threshold": threshold},
                f"artifacts/model_{variant}.joblib")
    metrics = {"variant": variant, "features": list(X_train.columns), "pr_auc": pr_auc,
               "champion": champion, "budget_per_day": budget, "threshold": float(threshold),
               "test_alerts": results}
    with open(f"artifacts/metrics_{variant}.json", "w") as f:
        json.dump(metrics, f, indent=2)
    logger.info("Saved artifacts/model_%s.joblib and artifacts/metrics_%s.json", variant, variant)
    return metrics


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = load_config()
    conn = get_connection(cfg)
    try:
        run_model(conn, cfg)
    finally:
        conn.close()
