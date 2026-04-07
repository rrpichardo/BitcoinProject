"""
Score a features Parquet file with the trained LR pipeline.

Output: CSV with columns [timestamp, y_true, y_prob, y_pred]
Prints mean per-row inference latency; raises if > 2s/tick.

Usage
-----
    python models/infer.py
    python models/infer.py --features data/processed/features.parquet \\
                           --model    models/artifacts/lr_pipeline.pkl \\
                           --output   data/processed/predictions.csv
"""

import argparse
import pickle
import time
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_MODEL  = Path(__file__).parent / "artifacts" / "lr_pipeline.pkl"
DEFAULT_OUTPUT = Path("data/processed/predictions.csv")


def load_model(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Model artifact not found: {path}")
    with open(path, "rb") as f:
        bundle = pickle.load(f)
    required = {"pipeline", "feature_cols", "tau"}
    missing = required - set(bundle)
    if missing:
        raise ValueError(f"Model bundle is missing keys: {sorted(missing)}")
    return bundle


def run_inference(features_path: Path, model_path: Path, output_path: Path):
    # Load model bundle
    bundle       = load_model(model_path)
    pipe         = bundle["pipeline"]
    feature_cols = bundle["feature_cols"]
    tau          = bundle["tau"]

    # Load features
    if not features_path.exists():
        raise FileNotFoundError(f"Features parquet not found: {features_path}")
    df = pd.read_parquet(features_path).sort_values("timestamp").reset_index(drop=True)
    missing = {"timestamp", *feature_cols} - set(df.columns)
    if missing:
        raise ValueError(f"Features parquet is missing required columns: {sorted(missing)}")
    df = df.dropna(subset=feature_cols)
    if df.empty:
        raise ValueError(f"No rows remain after dropping null feature rows from {features_path}")

    X = df[feature_cols].values

    # Score row-by-row to measure per-tick latency
    y_probs   = np.empty(len(X))
    latencies = np.empty(len(X))

    for i in range(len(X)):
        t0          = time.perf_counter()
        y_probs[i]  = pipe.predict_proba(X[i].reshape(1, -1))[0, 1]
        latencies[i] = time.perf_counter() - t0

    y_preds = (y_probs >= tau).astype(int)

    # Build output
    out = df[["timestamp"]].copy()
    if "vol_spike" in df.columns:
        out["y_true"] = df["vol_spike"].values
    else:
        out["y_true"] = np.nan
    out["y_prob"] = y_probs
    out["y_pred"] = y_preds

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    # Latency report
    mean_ms = latencies.mean() * 1000
    p99_ms  = np.percentile(latencies, 99) * 1000
    print(f"Rows scored      : {len(X):,}")
    print(f"Mean latency     : {mean_ms:.4f} ms/tick")
    print(f"P99  latency     : {p99_ms:.4f} ms/tick")
    print(f"Tau              : {tau}")
    if "y_true" in out.columns and out["y_true"].notna().any():
        from sklearn.metrics import average_precision_score
        pr_auc = average_precision_score(out["y_true"].dropna(),
                                         out.loc[out["y_true"].notna(), "y_prob"])
        print(f"PR-AUC           : {pr_auc:.4f}")

    if mean_ms > 2000:
        raise RuntimeError(
            f"Mean latency {mean_ms:.1f} ms exceeds 2s/tick limit"
        )

    print(f"\nPredictions saved → {output_path}")
    return out


def main():
    parser = argparse.ArgumentParser(description="Score features with trained LR model")
    parser.add_argument("--features", default="data/processed/features.parquet")
    parser.add_argument("--model",    default=str(DEFAULT_MODEL))
    parser.add_argument("--output",   default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    run_inference(
        features_path=Path(args.features),
        model_path=Path(args.model),
        output_path=Path(args.output),
    )


if __name__ == "__main__":
    main()
