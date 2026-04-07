"""
Score a features Parquet file with the trained LR pipeline.

Output: CSV with columns [timestamp, y_true, y_prob, y_pred]

Two inference modes:
  --benchmark  Row-by-row loop measuring per-tick latency (default for individual grading)
  --batch      Vectorized batch prediction for production/FastAPI use (~100-1000x faster)

Usage
-----
    # Benchmark mode (per-tick latency measurement)
    python models/infer.py

    # Batch mode (production / FastAPI endpoint)
    python models/infer.py --batch

    python models/infer.py --features data/processed/features.parquet \\
                           --model    models/artifacts/lr_pipeline.pkl \\
                           --output   data/processed/predictions.csv \\
                           --batch
"""

import argparse
import hashlib
import pickle
import time
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_MODEL  = Path(__file__).parent / "artifacts" / "lr_pipeline.pkl"
DEFAULT_OUTPUT = Path("data/processed/predictions.csv")


def _sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_model(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Model artifact not found: {path}")

    # Verify artifact integrity before deserializing
    checksum_path = path.with_suffix(".sha256")
    if checksum_path.exists():
        expected = checksum_path.read_text().strip().split()[0]
        actual = _sha256(path)
        if actual != expected:
            raise RuntimeError(
                f"Artifact integrity check failed for {path}: "
                f"expected sha256={expected}, got {actual}"
            )
    else:
        import warnings
        warnings.warn(
            f"No checksum file found at {checksum_path}; "
            "skipping integrity check. Run train.py to regenerate.",
            stacklevel=2,
        )

    with open(path, "rb") as f:
        bundle = pickle.load(f)
    required = {"pipeline", "feature_cols", "tau"}
    missing = required - set(bundle)
    if missing:
        raise ValueError(f"Model bundle is missing keys: {sorted(missing)}")
    return bundle


def run_inference(features_path: Path, model_path: Path, output_path: Path,
                  batch_mode: bool = False):
    # Load model bundle (pipeline + feature_cols + tau threshold)
    bundle       = load_model(model_path)
    pipe         = bundle["pipeline"]
    feature_cols = bundle["feature_cols"]
    tau          = bundle["tau"]

    # Load and validate features parquet
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

    if batch_mode:
        # ── BATCH MODE ────────────────────────────────────────────────────────
        # Vectorized prediction: passes all rows to sklearn in one call.
        # ~100-1000x faster than row-by-row — use this for FastAPI /predict
        # endpoint and any production pipeline to stay within p95 ≤ 800ms SLO.
        t0      = time.perf_counter()
        y_probs = pipe.predict_proba(X)[:, 1]  # single vectorized call
        elapsed = time.perf_counter() - t0

        # Compute summary latency stats to match benchmark output format
        mean_ms     = (elapsed / len(X)) * 1000   # average ms per row
        p99_ms      = mean_ms                      # batch has no per-row variance
        total_ms    = elapsed * 1000
        print(f"Mode             : BATCH (vectorized)")
        print(f"Total time       : {total_ms:.2f} ms for {len(X):,} rows")

    else:
        # ── BENCHMARK MODE ────────────────────────────────────────────────────
        # Row-by-row loop: measures realistic per-tick latency as the model
        # would experience in a live streaming context (one tick at a time).
        # Intentionally O(n) — do NOT use this path inside FastAPI.
        y_probs   = np.empty(len(X))
        latencies = np.empty(len(X))

        for i in range(len(X)):
            t0           = time.perf_counter()
            y_probs[i]   = pipe.predict_proba(X[i].reshape(1, -1))[0, 1]
            latencies[i] = time.perf_counter() - t0

        mean_ms = latencies.mean() * 1000
        p99_ms  = np.percentile(latencies, 99) * 1000
        print(f"Mode             : BENCHMARK (row-by-row)")

    # Apply classification threshold to convert probabilities → binary labels
    y_preds = (y_probs >= tau).astype(int)

    # Build output DataFrame with predictions
    out = df[["timestamp"]].copy()
    if "vol_spike" in df.columns:
        # Include ground truth labels if available (for PR-AUC calculation)
        out["y_true"] = df["vol_spike"].values
    else:
        out["y_true"] = np.nan
    out["y_prob"] = y_probs
    out["y_pred"] = y_preds

    # Write predictions to CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    # Print latency and performance summary
    print(f"Rows scored      : {len(X):,}")
    print(f"Mean latency     : {mean_ms:.4f} ms/tick")
    print(f"P99  latency     : {p99_ms:.4f} ms/tick")
    print(f"Tau              : {tau}")

    # Compute PR-AUC if ground truth labels are present
    if "y_true" in out.columns and out["y_true"].notna().any():
        from sklearn.metrics import average_precision_score
        pr_auc = average_precision_score(out["y_true"].dropna(),
                                         out.loc[out["y_true"].notna(), "y_prob"])
        print(f"PR-AUC           : {pr_auc:.4f}")

    # Enforce the 2s/tick latency ceiling (benchmark mode only — meaningful check)
    if not batch_mode and mean_ms > 2000:
        raise RuntimeError(
            f"Mean latency {mean_ms:.1f} ms exceeds 2s/tick limit"
        )

    print(f"\nPredictions saved → {output_path}")
    return out


def main():
    parser = argparse.ArgumentParser(description="Score features with trained LR model")
    parser.add_argument("--features",  default="data/processed/features.parquet")
    parser.add_argument("--model",     default=str(DEFAULT_MODEL))
    parser.add_argument("--output",    default=str(DEFAULT_OUTPUT))
    # --batch: vectorized prediction for FastAPI / production pipelines
    # default is benchmark mode (row-by-row) to preserve per-tick latency measurement
    parser.add_argument("--batch",     action="store_true",
                        help="Use vectorized batch prediction (production/FastAPI mode). "
                             "Default is row-by-row benchmark mode.")
    args = parser.parse_args()

    run_inference(
        features_path=Path(args.features),
        model_path=Path(args.model),
        output_path=Path(args.output),
        batch_mode=args.batch,
    )


if __name__ == "__main__":
    main()
