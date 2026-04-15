"""
BTC Volatility Spike Detector — FastAPI Service (Week 4 thin slice).

Loads the trained Logistic Regression pipeline bundle and serves predictions
via a REST API exposing /health, /predict, /version, and /metrics.
"""

# Standard library imports used for env lookup, model loading, and timing
import os
import pickle
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

# Numerical + web framework deps
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Prometheus client for /metrics endpoint
from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Config — model path + version are overridable via environment variables
# ---------------------------------------------------------------------------
MODEL_PATH = os.getenv("MODEL_PATH", "models/artifacts/lr_pipeline.pkl")
MODEL_VERSION = os.getenv("MODEL_VERSION", "v1.0")

# ---------------------------------------------------------------------------
# Load model once at startup so /predict stays hot
# ---------------------------------------------------------------------------
_model_path = Path(MODEL_PATH)  # resolve path against CWD
if not _model_path.exists():
    # Fail fast so container restart surfaces a missing artifact
    raise FileNotFoundError(f"Model not found at {MODEL_PATH}")

with open(_model_path, "rb") as f:
    _bundle = pickle.load(f)  # bundle keys: pipeline, feature_cols, tau

PIPELINE = _bundle["pipeline"]          # sklearn Pipeline (scaler + LR)
FEATURE_COLS = _bundle["feature_cols"]  # ordered list of 7 feature names
TAU = _bundle["tau"]                    # decision threshold from training

# ---------------------------------------------------------------------------
# Git SHA resolved once at startup for traceability in /version
# ---------------------------------------------------------------------------
try:
    GIT_SHA = (
        subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        )
        .decode()
        .strip()
    )
except Exception:
    # Inside docker we may not have git; degrade gracefully
    GIT_SHA = "unknown"

# ---------------------------------------------------------------------------
# Prometheus metrics registered at module import time
# ---------------------------------------------------------------------------
REQUEST_COUNT = Counter(
    "predict_requests_total",
    "Total prediction requests",
)
REQUEST_ERRORS = Counter(
    "predict_errors_total",
    "Total failed prediction requests",
)
REQUEST_LATENCY = Histogram(
    "predict_latency_seconds",
    "Prediction request latency in seconds",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.8, 1.0],
)

# ---------------------------------------------------------------------------
# Pydantic request / response schemas — enforce 7 features per row
# ---------------------------------------------------------------------------
class TickRow(BaseModel):
    """A single observation with the 7 required features."""
    log_return: float
    spread_bps: float
    vol_60s: float
    mean_return_60s: float
    trade_intensity_60s: float
    n_ticks_60s: float
    spread_mean_60s: float


class PredictRequest(BaseModel):
    # Batch endpoint: caller supplies one or more TickRows
    rows: list[TickRow]


class PredictResponse(BaseModel):
    scores: list[float]
    model_variant: str
    version: str
    ts: str


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="BTC Volatility Spike Detector")


@app.get("/health")
def health():
    # Simple liveness probe; model is already loaded at import time
    return {"status": "ok"}


@app.get("/version")
def version():
    # Expose model identity, git sha, decision threshold, feature order
    return {
        "model": "lr_pipeline",
        "version": MODEL_VERSION,
        "sha": GIT_SHA,
        "tau": TAU,
        "features": FEATURE_COLS,
    }


@app.get("/metrics")
def metrics():
    # Prometheus scrape endpoint — text exposition format
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    # Count every incoming request for throughput monitoring
    REQUEST_COUNT.inc()
    start = time.perf_counter()

    try:
        # Build feature matrix in the exact column order the model expects
        X = np.array(
            [[getattr(row, col) for col in FEATURE_COLS] for row in req.rows]
        )

        # Probability of class 1 (volatility spike)
        y_prob = PIPELINE.predict_proba(X)[:, 1]

        # Round scores so the API response stays human-readable
        scores = [round(float(p), 6) for p in y_prob]

        return PredictResponse(
            scores=scores,
            model_variant="ml",
            version=MODEL_VERSION,
            ts=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:
        # Count the error and return 500 with the exception message
        REQUEST_ERRORS.inc()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        # Always record latency — success or failure
        REQUEST_LATENCY.observe(time.perf_counter() - start)
