"""
Train baseline (z-score rule) and ML (Logistic Regression) models.

Time-based split: 60% train / 20% val / 20% test  (no shuffle).

MLflow run 1 — Z-score baseline
    params : zscore_threshold
    metrics: pr_auc, f1_at_threshold  (val + test)
    artifact: predictions CSV

MLflow run 2 — Logistic Regression
    params : C, class_weight, solver, tau
    metrics: pr_auc, f1_at_threshold  (val + test)
    artifacts: mlflow model + models/artifacts/ pickle

Usage
-----
    python models/train.py
    python models/train.py --features data/processed/features.parquet
    python models/train.py --features data/processed/features.parquet --tau 0.5  # manual override
"""

import argparse
import hashlib
import json
import logging
import os
import pickle
import sys
import warnings
from pathlib import Path

# MLflow 3.x can trip over protobuf 6.x in some local environments unless
# the pure-Python protobuf implementation is selected before mlflow imports it.
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import scipy.special
import yaml
from mlflow.exceptions import MlflowException
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_recall_curve,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from sklearn.exceptions import ConvergenceWarning
# Surface convergence issues as logged warnings instead of silencing them
logging.captureWarnings(True)
warnings.filterwarnings("default", category=ConvergenceWarning)
log = logging.getLogger(__name__)

ROOT      = Path(__file__).parent.parent
ARTIFACTS = ROOT / "models" / "artifacts"

FEATURE_COLS = [
    "log_return",          # midprice return
    "spread_bps",          # bid-ask spread (basis points)
    "vol_60s",             # rolling std of log-returns (60s window)
    "mean_return_60s",     # mean log-return over 60s
    "trade_intensity_60s", # ticks/sec
    "n_ticks_60s",         # tick count in window
    "spread_mean_60s",     # mean spread over 60s window (Variant B)
]
TARGET = "vol_spike"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Features parquet not found: {path}")
    df = pd.read_parquet(path).sort_values("timestamp").reset_index(drop=True)
    required = {"timestamp", *FEATURE_COLS, TARGET}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Features parquet is missing required columns: {sorted(missing)}")
    df = df.dropna(subset=FEATURE_COLS + [TARGET])
    if "future_vol_60s" in df.columns:
        df = df.dropna(subset=["future_vol_60s"])
    if df.empty:
        raise ValueError(f"No rows remain after dropping nulls from {path}")
    return df


def load_config(path: Path) -> dict:
    with path.open() as fh:
        return yaml.safe_load(fh)


def time_split(df: pd.DataFrame):
    n     = len(df)
    i_val = int(n * 0.60)
    i_tst = int(n * 0.80)
    train, val, test = df.iloc[:i_val], df.iloc[i_val:i_tst], df.iloc[i_tst:]
    if min(len(train), len(val), len(test)) == 0:
        raise ValueError("Time split produced an empty train/val/test partition")
    return train, val, test


def pr_auc(y_true, y_prob):
    return average_precision_score(y_true, y_prob)


def f1_at_tau(y_true, y_prob, tau):
    return f1_score(y_true, (y_prob >= tau).astype(int), zero_division=0)


def best_f1_threshold(y_true, y_prob):
    """Return threshold that maximises F1 on the given split."""
    precision, recall, thresholds = precision_recall_curve(y_true, y_prob)
    f1s = 2 * precision * recall / (precision + recall + 1e-9)
    idx = np.argmax(f1s[:-1])
    return float(thresholds[idx]), float(f1s[idx])


# ---------------------------------------------------------------------------
# Run 1 — Z-score baseline
# ---------------------------------------------------------------------------

def run_zscore(train, val, test, experiment_id: str, zscore_threshold: float = 2.0):
    col   = "vol_60s"
    mu    = train[col].mean()
    sigma = train[col].std()
    if pd.isna(sigma) or sigma == 0:
        raise ValueError("Baseline z-score cannot train because train vol_60s has zero variance")

    def predict(df):
        z     = (df[col] - mu) / sigma
        prob  = scipy.special.expit(z)        # sigmoid → calibrated [0, 1]
        pred  = (z >= zscore_threshold).astype(int)
        return prob.values, pred.values

    with mlflow.start_run(run_name="zscore_baseline", experiment_id=experiment_id) as run:
        mlflow.log_params({
            "zscore_threshold": zscore_threshold,
            "z_col":            col,
            "train_mu":         round(mu, 8),
            "train_sigma":      round(sigma, 8),
        })

        results = {}
        for split_name, split_df in [("val", val), ("test", test)]:
            y_true        = split_df[TARGET].values
            y_prob, y_pred = predict(split_df)

            auc           = pr_auc(y_true, y_prob)
            _tau, f1      = best_f1_threshold(y_true, y_prob)
            f1_fixed      = f1_at_tau(y_true, y_prob, 0.5)

            mlflow.log_metrics({
                f"{split_name}_pr_auc":          round(auc,       4),
                f"{split_name}_f1_best":         round(f1,        4),
                f"{split_name}_f1_at_0.5":       round(f1_fixed,  4),
                f"{split_name}_spike_rate":       round(y_true.mean(), 4),
                f"{split_name}_predicted_rate":   round(y_pred.mean(), 4),
            })
            results[split_name] = {
                "y_true": y_true, "y_prob": y_prob, "y_pred": y_pred,
                "pr_auc": auc,
            }
            print(f"  [{split_name}] PR-AUC={auc:.4f}  F1-best={f1:.4f}")

        # Predictions artifact (test set)
        pred_df = test[["timestamp"]].copy()
        pred_df["y_true"] = results["test"]["y_true"]
        pred_df["y_prob"] = results["test"]["y_prob"]
        pred_df["y_pred"] = results["test"]["y_pred"]
        tmp = ARTIFACTS / "zscore_predictions.csv"
        pred_df.to_csv(tmp, index=False)
        mlflow.log_artifact(str(tmp), artifact_path="predictions")

        print(f"  MLflow run_id: {run.info.run_id}")
        return run.info.run_id


# ---------------------------------------------------------------------------
# Run 2 — Logistic Regression
# ---------------------------------------------------------------------------

def run_logistic(train, val, test, experiment_id: str, tau: float = None):
    if train[TARGET].nunique() < 2:
        raise ValueError("Training split must contain both classes for logistic regression")
    X_tr, y_tr = train[FEATURE_COLS].values, train[TARGET].values
    X_va, y_va = val[FEATURE_COLS].values,   val[TARGET].values
    X_te, y_te = test[FEATURE_COLS].values,  test[TARGET].values

    C            = 0.1
    class_weight = "balanced"
    solver       = "lbfgs"
    max_iter     = 1000

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr",     LogisticRegression(
            C=C, class_weight=class_weight, solver=solver,
            max_iter=max_iter, random_state=42,
        )),
    ])
    pipe.fit(X_tr, y_tr)

    # Auto-select tau from validation set (NOT test) to avoid data leakage
    y_prob_va = pipe.predict_proba(X_va)[:, 1]
    best_tau, best_f1_va = best_f1_threshold(y_va, y_prob_va)
    if tau is None:
        tau = best_tau
        print(f"  Auto-selected tau = {tau:.4f} (val F1 = {best_f1_va:.4f})")
    else:
        print(f"  Using manual tau = {tau:.4f} (best-F1 tau would be {best_tau:.4f})")

    with mlflow.start_run(run_name="logistic_regression", experiment_id=experiment_id) as run:
        mlflow.log_params({
            "C":            C,
            "class_weight": class_weight,
            "solver":       solver,
            "max_iter":     max_iter,
            "tau":          tau,
            "features":     FEATURE_COLS,
            "n_train":      len(X_tr),
            "n_val":        len(X_va),
            "n_test":       len(X_te),
        })

        split_metrics = {}
        for split_name, X, y, split_df in [
            ("val",  X_va, y_va, val),
            ("test", X_te, y_te, test),
        ]:
            y_prob  = pipe.predict_proba(X)[:, 1]
            y_pred  = (y_prob >= tau).astype(int)
            auc     = pr_auc(y, y_prob)
            f1_fix  = f1_at_tau(y, y_prob, tau)
            _, f1b  = best_f1_threshold(y, y_prob)

            mlflow.log_metrics({
                f"{split_name}_pr_auc":        round(auc,   4),
                f"{split_name}_f1_at_tau":     round(f1_fix, 4),
                f"{split_name}_f1_best":       round(f1b,   4),
                f"{split_name}_spike_rate":    round(y.mean(), 4),
                f"{split_name}_predicted_rate": round(y_pred.mean(), 4),
            })
            split_metrics[split_name] = {
                "pr_auc": round(auc, 4),
                "f1_at_tau": round(f1_fix, 4),
                "spike_rate": round(y.mean(), 4),
            }
            print(f"  [{split_name}] PR-AUC={auc:.4f}  F1@tau={f1_fix:.4f}  F1-best={f1b:.4f}")

        # Save pickle to models/artifacts/ with SHA-256 checksum for integrity verification
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        pkl_path = ARTIFACTS / "lr_pipeline.pkl"
        with open(pkl_path, "wb") as f:
            pickle.dump({"pipeline": pipe, "feature_cols": FEATURE_COLS, "tau": tau}, f)
        # Write checksum so infer.py can verify the artifact before deserializing
        sha_path = pkl_path.with_suffix(".sha256")
        h = hashlib.sha256()
        with open(pkl_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        sha_path.write_text(f"{h.hexdigest()}  {pkl_path.name}\n")
        mlflow.log_artifact(str(pkl_path), artifact_path="artifacts")
        mlflow.log_artifact(str(sha_path), artifact_path="artifacts")

        # Save human-readable metadata alongside the pickle
        metadata = {
            "feature_cols":    FEATURE_COLS,
            "tau":             tau,
            "train_rows":      len(X_tr),
            "val_rows":        len(X_va),
            "test_rows":       len(X_te),
            "val_pr_auc":      split_metrics["val"]["pr_auc"],
            "val_f1_at_tau":   split_metrics["val"]["f1_at_tau"],
            "val_spike_rate":  split_metrics["val"]["spike_rate"],
            "test_pr_auc":     split_metrics["test"]["pr_auc"],
            "test_f1_at_tau":  split_metrics["test"]["f1_at_tau"],
            "test_spike_rate": split_metrics["test"]["spike_rate"],
        }
        meta_path = ARTIFACTS / "metadata.json"
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)
        mlflow.log_artifact(str(meta_path), artifact_path="artifacts")

        # Predictions artifact (test set)
        pred_df = test[["timestamp"]].copy()
        pred_df["y_true"] = y_te
        pred_df["y_prob"] = pipe.predict_proba(X_te)[:, 1]
        pred_df["y_pred"] = (pred_df["y_prob"] >= tau).astype(int)
        tmp = ARTIFACTS / "lr_predictions.csv"
        pred_df.to_csv(tmp, index=False)
        mlflow.log_artifact(str(tmp), artifact_path="predictions")

        # Newer MLflow Python clients can call endpoints that older tracking
        # servers do not expose. Keep training successful by treating server
        # model logging as best-effort; the portable pickle artifact above is
        # still the source of truth used by infer.py and the FastAPI service.
        try:
            mlflow.sklearn.log_model(pipe, artifact_path="model")
        except MlflowException as exc:
            log.warning("Skipping MLflow model log because the tracking server is incompatible: %s", exc)

        print(f"  Model saved → {pkl_path}")
        print(f"  MLflow run_id: {run.info.run_id}")
        return run.info.run_id


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Train volatility spike models")
    parser.add_argument("--features", default="data/processed/features.parquet",
                        help="Path to features Parquet file")
    parser.add_argument("--tau", type=float, default=None,
                        help="Classification threshold (default: auto from validation best-F1)")
    parser.add_argument("--tracking-uri", default=None,
                        help="MLflow tracking URI (default: config.yaml mlflow.tracking_uri)")
    parser.add_argument("--config", default="config.yaml",
                        help="Project config file used for MLflow defaults")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    tracking_uri = args.tracking_uri or cfg["mlflow"]["tracking_uri"]
    experiment_name = cfg["mlflow"].get("experiment_name", "btc-volatility")

    mlflow.set_tracking_uri(tracking_uri)
    experiment_id = mlflow.set_experiment(experiment_name).experiment_id

    df           = load_data(Path(args.features))
    train, val, test = time_split(df)

    print(f"\nData: {len(df):,} rows  |  "
          f"train={len(train):,}  val={len(val):,}  test={len(test):,}")
    print(f"Spike rate — train: {train[TARGET].mean()*100:.1f}%  "
          f"val: {val[TARGET].mean()*100:.1f}%  "
          f"test: {test[TARGET].mean()*100:.1f}%\n")

    # Write test split so infer.py can be called with features_test.parquet
    test_path = Path(args.features).parent / "features_test.parquet"
    test.to_parquet(test_path, index=False)
    print(f"Test split saved → {test_path}")

    print("=== Run 1: Z-score baseline ===")
    run_zscore(train, val, test, experiment_id)

    print("\n=== Run 2: Logistic Regression ===")
    run_logistic(train, val, test, experiment_id, tau=args.tau)

    print("\nDone. Open the MLflow UI at:")
    print("  http://localhost:5001")


if __name__ == "__main__":
    main()
