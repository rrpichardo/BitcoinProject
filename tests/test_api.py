"""Smoke tests for the FastAPI prediction service.

These tests run the app in-process via FastAPI's TestClient, so they verify
the actual endpoint behavior without depending on Docker or an open localhost
port in the execution environment.
"""

from fastapi.testclient import TestClient

from api.main import app

# A plausible single-row feature payload matching the trained feature order
SAMPLE_ROW = {
    "log_return": 0.0001,
    "spread_bps": 1.5,
    "vol_60s": 0.00005,
    "mean_return_60s": 0.0,
    "trade_intensity_60s": 10.0,
    "n_ticks_60s": 50,
    "spread_mean_60s": 1.2,
}

client = TestClient(app)


def test_health():
    # /health should return 200 with a fixed ok payload
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_version():
    # /version exposes model identity + threshold + feature list
    r = client.get("/version")
    assert r.status_code == 200
    body = r.json()
    assert "model" in body
    assert "sha" in body
    assert "tau" in body
    assert len(body["features"]) == 7


def test_predict_single():
    # Single-row prediction should return a probability in [0, 1]
    r = client.post("/predict", json={"rows": [SAMPLE_ROW]})
    assert r.status_code == 200
    body = r.json()
    assert len(body["scores"]) == 1
    assert 0.0 <= body["scores"][0] <= 1.0
    assert body["model_variant"] == "ml"


def test_predict_batch():
    # Batch of 5 rows should produce 5 scores
    r = client.post("/predict", json={"rows": [SAMPLE_ROW] * 5})
    assert r.status_code == 200
    assert len(r.json()["scores"]) == 5


def test_predict_missing_field():
    # Missing required features should fail Pydantic validation with a 422
    bad_row = {"log_return": 0.0001}
    r = client.post("/predict", json={"rows": [bad_row]})
    assert r.status_code == 422


def test_metrics():
    # /metrics must expose the prometheus counter so scrapers can ingest it
    client.post("/predict", json={"rows": [SAMPLE_ROW]})
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "predict_requests_total" in r.text


if __name__ == "__main__":
    # Allow running as a plain script for a quick human-readable report
    tests = [
        test_health,
        test_version,
        test_predict_single,
        test_predict_batch,
        test_predict_missing_field,
        test_metrics,
    ]
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
