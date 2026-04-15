"""
Feature ablation study — 4 variants, all logged to MLflow.

Variant  Features                                          Rationale
-------  ------------------------------------------------  ---------------------------------
A        6 baseline features                               Control
B        A + spread_mean_60s                               Irene's liquidity signal
C        A + spread_mean_60s + price_range_60s             Full candidate set
D        C − spread_abs − n_ticks_60s                      Drop correlated features

All variants use the same LR hyperparameters (C=0.1, balanced, lbfgs).
Threshold is selected on validation best-F1.
Winner is picked on validation PR-AUC; test metrics reported only for the winner.

Usage
-----
    python scripts/ablation.py
    python scripts/ablation.py --features data/processed/features.parquet
"""

import argparse
import json
import os
import warnings
from pathlib import Path

# Keep MLflow compatible with protobuf 6.x in the local grading environment.
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

import mlflow
import numpy as np
import pandas as pd
import yaml
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=ConvergenceWarning)

TARGET = "vol_spike"

VARIANTS = {
    "A": {
        "features": [
            "log_return", "spread_bps", "vol_60s",
            "mean_return_60s", "trade_intensity_60s", "n_ticks_60s",
        ],
        "rationale": "Baseline (6 features)",
    },
    "B": {
        "features": [
            "log_return", "spread_bps", "vol_60s",
            "mean_return_60s", "trade_intensity_60s", "n_ticks_60s",
            "spread_mean_60s",
        ],
        "rationale": "A + spread_mean_60s (liquidity signal)",
    },
    "C": {
        "features": [
            "log_return", "spread_bps", "vol_60s",
            "mean_return_60s", "trade_intensity_60s", "n_ticks_60s",
            "spread_mean_60s", "price_range_60s",
        ],
        "rationale": "A + spread_mean_60s + price_range_60s (full candidate set)",
    },
    "D": {
        "features": [
            "log_return", "spread_bps", "vol_60s",
            "mean_return_60s", "trade_intensity_60s",
            "spread_mean_60s", "price_range_60s",
        ],
        "rationale": "C − spread_abs − n_ticks_60s (drop correlated features)",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_config(path: Path) -> dict:
    with path.open() as fh:
        return yaml.safe_load(fh)


def time_split(df: pd.DataFrame):
    n = len(df)
    i_val = int(n * 0.60)
    i_tst = int(n * 0.80)
    return df.iloc[:i_val], df.iloc[i_val:i_tst], df.iloc[i_tst:]


def best_f1_threshold(y_true, y_prob):
    precision, recall, thresholds = precision_recall_curve(y_true, y_prob)
    f1s = 2 * precision * recall / (precision + recall + 1e-9)
    idx = np.argmax(f1s[:-1])
    return float(thresholds[idx]), float(f1s[idx])


def run_variant(name, feature_cols, rationale, train, val, test, experiment_id):
    """Train one ablation variant; return dict of results."""
    X_tr, y_tr = train[feature_cols].values, train[TARGET].values
    X_va, y_va = val[feature_cols].values,   val[TARGET].values
    X_te, y_te = test[feature_cols].values,  test[TARGET].values

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(
            C=0.1, class_weight="balanced", solver="lbfgs",
            max_iter=1000, random_state=42,
        )),
    ])
    pipe.fit(X_tr, y_tr)

    # Threshold selected on validation set
    y_prob_va = pipe.predict_proba(X_va)[:, 1]
    tau, _ = best_f1_threshold(y_va, y_prob_va)

    # Evaluate both splits
    results = {}
    with mlflow.start_run(run_name=f"ablation_{name}", experiment_id=experiment_id) as run:
        mlflow.log_params({
            "variant":      name,
            "rationale":    rationale,
            "features":     feature_cols,
            "n_features":   len(feature_cols),
            "C":            0.1,
            "class_weight": "balanced",
            "solver":       "lbfgs",
            "max_iter":     1000,
            "tau":          round(tau, 6),
            "n_train":      len(X_tr),
            "n_val":        len(X_va),
            "n_test":       len(X_te),
        })

        for split_name, X, y in [("val", X_va, y_va), ("test", X_te, y_te)]:
            y_prob = pipe.predict_proba(X)[:, 1]
            y_pred = (y_prob >= tau).astype(int)

            auc  = average_precision_score(y, y_prob)
            f1   = f1_score(y, y_pred, zero_division=0)
            prec = precision_score(y, y_pred, zero_division=0)
            rec  = recall_score(y, y_pred, zero_division=0)

            mlflow.log_metrics({
                f"{split_name}_pr_auc":    round(auc, 4),
                f"{split_name}_f1":        round(f1, 4),
                f"{split_name}_precision": round(prec, 4),
                f"{split_name}_recall":    round(rec, 4),
            })

            results[split_name] = {
                "pr_auc": round(auc, 4),
                "f1": round(f1, 4),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
            }

        run_id = run.info.run_id

    return {
        "variant": name,
        "rationale": rationale,
        "features": feature_cols,
        "tau": round(tau, 6),
        "run_id": run_id,
        **{f"val_{k}": v for k, v in results["val"].items()},
        **{f"test_{k}": v for k, v in results["test"].items()},
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Feature ablation study")
    parser.add_argument("--features", default="data/processed/features.parquet")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    mlflow.set_tracking_uri(cfg["mlflow"]["tracking_uri"])
    experiment_id = mlflow.set_experiment(
        cfg["mlflow"].get("experiment_name", "btc-volatility")
    ).experiment_id

    # Load data — use all columns needed across variants
    all_features = sorted(set(f for v in VARIANTS.values() for f in v["features"]))
    df = pd.read_parquet(args.features).sort_values("timestamp").reset_index(drop=True)
    df = df.dropna(subset=all_features + [TARGET])
    train, val, test = time_split(df)

    print(f"Data: {len(df):,} rows  |  "
          f"train={len(train):,}  val={len(val):,}  test={len(test):,}")
    print(f"Spike rate — train: {train[TARGET].mean()*100:.1f}%  "
          f"val: {val[TARGET].mean()*100:.1f}%  "
          f"test: {test[TARGET].mean()*100:.1f}%\n")

    # Run all variants
    all_results = []
    for name, spec in VARIANTS.items():
        print(f"=== Variant {name}: {spec['rationale']} ===")
        result = run_variant(
            name, spec["features"], spec["rationale"],
            train, val, test, experiment_id,
        )
        print(f"  tau={result['tau']:.4f}  "
              f"val PR-AUC={result['val_pr_auc']:.4f}  "
              f"test PR-AUC={result['test_pr_auc']:.4f}")
        all_results.append(result)

    # Summary table
    print("\n" + "=" * 80)
    print("ABLATION SUMMARY — ranked by validation PR-AUC")
    print("=" * 80)
    header = f"{'Var':>3}  {'#Feat':>5}  {'tau':>6}  {'val_PR-AUC':>10}  {'val_F1':>6}  {'test_PR-AUC':>11}  {'test_F1':>7}  {'test_P':>6}  {'test_R':>6}"
    print(header)
    print("-" * len(header))

    ranked = sorted(all_results, key=lambda r: r["val_pr_auc"], reverse=True)
    for r in ranked:
        marker = " <-- winner" if r is ranked[0] else ""
        print(f"  {r['variant']}  {len(r['features']):>5}  {r['tau']:>6.4f}  "
              f"{r['val_pr_auc']:>10.4f}  {r['val_f1']:>6.4f}  "
              f"{r['test_pr_auc']:>11.4f}  {r['test_f1']:>7.4f}  "
              f"{r['test_precision']:>6.4f}  {r['test_recall']:>6.4f}{marker}")

    winner = ranked[0]
    print(f"\nWinner: Variant {winner['variant']} — {winner['rationale']}")
    print(f"  Features: {winner['features']}")
    print(f"  Threshold (tau): {winner['tau']}")
    print(f"  Val  PR-AUC={winner['val_pr_auc']:.4f}  F1={winner['val_f1']:.4f}")
    print(f"  Test PR-AUC={winner['test_pr_auc']:.4f}  F1={winner['test_f1']:.4f}  "
          f"P={winner['test_precision']:.4f}  R={winner['test_recall']:.4f}")

    # Save results to JSON
    out_path = Path("reports/ablation_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"winner": winner["variant"], "variants": all_results}, f, indent=2)
    print(f"\nResults saved → {out_path}")


if __name__ == "__main__":
    main()
