"""
Threshold sweep — Variant B features × P85 / P90 / P95 label thresholds.

Re-derives the vol_spike label from future_vol_60s at each percentile,
trains LR with identical hyperparameters, and logs to MLflow.

Winner is picked on validation PR-AUC + stability (val-test gap).

Usage
-----
    python scripts/threshold_sweep.py
    python scripts/threshold_sweep.py --features data/processed/features.parquet
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

FEATURE_COLS = [
    "log_return", "spread_bps", "vol_60s",
    "mean_return_60s", "trade_intensity_60s", "n_ticks_60s",
    "spread_mean_60s",
]

PERCENTILES = [85, 90, 95]


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


def run_threshold(percentile, vol_threshold, train, val, test, experiment_id):
    """Train variant B at a given vol_spike threshold; return results dict."""
    # Copy to avoid mutating the caller's DataFrames — prevents label leakage across sweep runs
    train, val, test = train.copy(), val.copy(), test.copy()
    # Re-derive labels on the local copies
    for split in [train, val, test]:
        split["vol_spike"] = (split["future_vol_60s"] >= vol_threshold).astype(int)

    X_tr, y_tr = train[FEATURE_COLS].values, train["vol_spike"].values
    X_va, y_va = val[FEATURE_COLS].values,   val["vol_spike"].values
    X_te, y_te = test[FEATURE_COLS].values,  test["vol_spike"].values

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

    results = {}
    with mlflow.start_run(
        run_name=f"threshold_P{percentile}", experiment_id=experiment_id
    ) as run:
        mlflow.log_params({
            "variant":        "B",
            "percentile":     f"P{percentile}",
            "vol_threshold":  round(vol_threshold, 6),
            "features":       FEATURE_COLS,
            "n_features":     len(FEATURE_COLS),
            "C":              0.1,
            "class_weight":   "balanced",
            "solver":         "lbfgs",
            "max_iter":       1000,
            "tau":            round(tau, 6),
            "n_train":        len(X_tr),
            "n_val":          len(X_va),
            "n_test":         len(X_te),
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
                f"{split_name}_spike_rate": round(y.mean(), 4),
            })

            results[split_name] = {
                "pr_auc": round(auc, 4),
                "f1": round(f1, 4),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "spike_rate": round(y.mean(), 4),
            }

        run_id = run.info.run_id

    return {
        "percentile": f"P{percentile}",
        "vol_threshold": round(vol_threshold, 6),
        "tau": round(tau, 6),
        "run_id": run_id,
        **{f"val_{k}": v for k, v in results["val"].items()},
        **{f"test_{k}": v for k, v in results["test"].items()},
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Threshold sweep for variant B")
    parser.add_argument("--features", default="data/processed/features.parquet")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    mlflow.set_tracking_uri(cfg["mlflow"]["tracking_uri"])
    experiment_id = mlflow.set_experiment(
        cfg["mlflow"].get("experiment_name", "btc-volatility")
    ).experiment_id

    df = pd.read_parquet(args.features).sort_values("timestamp").reset_index(drop=True)
    df = df.dropna(subset=FEATURE_COLS + ["future_vol_60s"])

    # Compute percentile thresholds from the full dataset
    fv = df["future_vol_60s"]
    thresholds = {p: fv.quantile(p / 100) for p in PERCENTILES}

    train, val, test = time_split(df)

    print(f"Data: {len(df):,} rows  |  "
          f"train={len(train):,}  val={len(val):,}  test={len(test):,}\n")

    for p, t in thresholds.items():
        rate = (fv >= t).mean() * 100
        print(f"  P{p}: vol_threshold={t:.6f}  global_spike_rate={rate:.1f}%")
    print()

    # Run sweep — use .copy() so re-labeling doesn't leak across runs
    all_results = []
    for p in PERCENTILES:
        print(f"=== P{p}: vol_threshold={thresholds[p]:.6f} ===")
        result = run_threshold(
            p, thresholds[p],
            train, val, test,
            experiment_id,
        )
        gap = abs(result["val_pr_auc"] - result["test_pr_auc"])
        print(f"  tau={result['tau']:.4f}  "
              f"val PR-AUC={result['val_pr_auc']:.4f}  "
              f"test PR-AUC={result['test_pr_auc']:.4f}  "
              f"gap={gap:.4f}  "
              f"val spike_rate={result['val_spike_rate']:.1%}  "
              f"test spike_rate={result['test_spike_rate']:.1%}")
        result["val_test_gap"] = round(gap, 4)
        all_results.append(result)

    # Summary table
    print("\n" + "=" * 90)
    print("THRESHOLD SWEEP SUMMARY — Variant B features")
    print("=" * 90)
    header = (f"{'Pctl':>4}  {'σ_thresh':>10}  {'tau':>6}  "
              f"{'val_AUC':>7}  {'val_F1':>6}  {'val_spk%':>8}  "
              f"{'tst_AUC':>7}  {'tst_F1':>6}  {'tst_spk%':>8}  {'gap':>5}")
    print(header)
    print("-" * len(header))

    ranked = sorted(all_results, key=lambda r: r["val_pr_auc"], reverse=True)
    for r in ranked:
        marker = " <-- best" if r is ranked[0] else ""
        print(f"{r['percentile']:>4}  {r['vol_threshold']:>10.6f}  {r['tau']:>6.4f}  "
              f"{r['val_pr_auc']:>7.4f}  {r['val_f1']:>6.4f}  {r['val_spike_rate']:>7.1%}  "
              f"{r['test_pr_auc']:>7.4f}  {r['test_f1']:>6.4f}  {r['test_spike_rate']:>7.1%}  "
              f"{r['val_test_gap']:>5.4f}{marker}")

    winner = ranked[0]
    print(f"\nBest: {winner['percentile']} (vol_threshold={winner['vol_threshold']:.6f})")
    print(f"  Val  PR-AUC={winner['val_pr_auc']:.4f}  F1={winner['val_f1']:.4f}  "
          f"spike_rate={winner['val_spike_rate']:.1%}")
    print(f"  Test PR-AUC={winner['test_pr_auc']:.4f}  F1={winner['test_f1']:.4f}  "
          f"spike_rate={winner['test_spike_rate']:.1%}")
    print(f"  Val-test PR-AUC gap: {winner['val_test_gap']:.4f}")

    # Save results
    out_path = Path("reports/threshold_sweep_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"winner": winner["percentile"], "variants": all_results}, f, indent=2)
    print(f"\nResults saved → {out_path}")


if __name__ == "__main__":
    main()
