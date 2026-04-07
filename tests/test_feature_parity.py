"""
Tests that replay.ProductState and featurizer.ProductState produce
numerically identical feature vectors and labels for the same tick stream.
"""

import math
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Both modules live in sibling directories — add them to the path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "features"))
sys.path.insert(0, str(ROOT / "scripts"))

import replay as replay_mod
import importlib.util, types

# featurizer.py imports confluent_kafka at module level; stub it out so the
# test suite doesn't require a running Kafka broker.
_stub = types.ModuleType("confluent_kafka")
_stub.Consumer = _stub.Producer = _stub.KafkaError = object
sys.modules.setdefault("confluent_kafka", _stub)

spec = importlib.util.spec_from_file_location(
    "featurizer", ROOT / "features" / "featurizer.py"
)
featurizer_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(featurizer_mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WINDOW_SEC    = 60.0
HORIZON_SEC   = 60.0
VOL_THRESHOLD = 0.000041


def _ts(offset_sec: float) -> str:
    """Return an ISO-8601 timestamp offset_sec after a fixed epoch."""
    base = datetime(2026, 4, 5, 0, 0, 0, tzinfo=timezone.utc).timestamp()
    # Use timezone-aware constructor — utcfromtimestamp is deprecated in 3.12+
    t    = datetime.fromtimestamp(base + offset_sec, tz=timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def _tick(offset_sec: float, price: float, bid_offset: float = 0.01) -> dict:
    return {
        "product_id": "BTC-USD",
        "timestamp":  _ts(offset_sec),
        "price":      str(price),
        "best_bid":   str(price - bid_offset),
        "best_ask":   str(price + bid_offset),
    }


def _run_state(StateClass, ticks: list[dict]) -> list[dict]:
    state = StateClass(WINDOW_SEC, HORIZON_SEC, VOL_THRESHOLD)
    rows  = []
    for tick in ticks:
        rows.extend(state.ingest(tick))
    rows.extend(state.drain_remaining())
    return rows


# ---------------------------------------------------------------------------
# Tick stream fixture — 130 seconds, realistic price walk
# ---------------------------------------------------------------------------

@pytest.fixture()
def tick_stream():
    import random
    rng    = random.Random(42)
    price  = 67_000.0
    ticks  = []
    for i in range(130):
        price += rng.gauss(0, 1.5)
        ticks.append(_tick(i, price))
    return ticks


# ---------------------------------------------------------------------------
# Test 1: identical row count
# ---------------------------------------------------------------------------

def test_parity_row_count(tick_stream):
    rows_r = _run_state(replay_mod.ProductState,     tick_stream)
    rows_f = _run_state(featurizer_mod.ProductState, tick_stream)
    assert len(rows_r) == len(rows_f), (
        f"Row count mismatch: replay={len(rows_r)}, featurizer={len(rows_f)}"
    )


# ---------------------------------------------------------------------------
# Test 2: identical timestamps (same rows in same order)
# ---------------------------------------------------------------------------

def test_parity_timestamps(tick_stream):
    rows_r = _run_state(replay_mod.ProductState,     tick_stream)
    rows_f = _run_state(featurizer_mod.ProductState, tick_stream)
    for i, (r, f) in enumerate(zip(rows_r, rows_f)):
        assert r["timestamp"] == f["timestamp"], (
            f"Row {i}: timestamp mismatch {r['timestamp']} != {f['timestamp']}"
        )


# ---------------------------------------------------------------------------
# Test 3: all numeric features agree to floating-point precision
# ---------------------------------------------------------------------------

NUMERIC_COLS = [
    "price", "midprice", "log_return",
    "spread_abs", "spread_bps",
    "vol_60s", "mean_return_60s", "trade_intensity_60s",
    "spread_mean_60s",
    "price_range_60s",
    "future_vol_60s",
]

def test_parity_numeric_features(tick_stream):
    rows_r = _run_state(replay_mod.ProductState,     tick_stream)
    rows_f = _run_state(featurizer_mod.ProductState, tick_stream)
    for i, (r, f) in enumerate(zip(rows_r, rows_f)):
        for col in NUMERIC_COLS:
            rv, fv = r[col], f[col]
            if math.isnan(rv) and math.isnan(fv):
                continue
            assert math.isclose(rv, fv, rel_tol=1e-9), (
                f"Row {i} col '{col}': replay={rv} featurizer={fv}"
            )


# ---------------------------------------------------------------------------
# Test 4: integer features agree exactly
# ---------------------------------------------------------------------------

def test_parity_integer_features(tick_stream):
    rows_r = _run_state(replay_mod.ProductState,     tick_stream)
    rows_f = _run_state(featurizer_mod.ProductState, tick_stream)
    for i, (r, f) in enumerate(zip(rows_r, rows_f)):
        assert r["n_ticks_60s"] == f["n_ticks_60s"], (
            f"Row {i} n_ticks_60s: replay={r['n_ticks_60s']} featurizer={f['n_ticks_60s']}"
        )
        assert r["vol_spike"] == f["vol_spike"], (
            f"Row {i} vol_spike: replay={r['vol_spike']} featurizer={f['vol_spike']}"
        )


# ---------------------------------------------------------------------------
# Test 5: spike rate is plausible (~0–100%)
# ---------------------------------------------------------------------------

def test_spike_rate_plausible(tick_stream):
    rows = _run_state(replay_mod.ProductState, tick_stream)
    rate = sum(r["vol_spike"] for r in rows) / len(rows)
    assert 0.0 <= rate <= 1.0


# ---------------------------------------------------------------------------
# Test 6: empty tick stream produces no rows (no crash)
# ---------------------------------------------------------------------------

def test_empty_stream():
    rows_r = _run_state(replay_mod.ProductState,     [])
    rows_f = _run_state(featurizer_mod.ProductState, [])
    assert rows_r == [] and rows_f == []


# ---------------------------------------------------------------------------
# Test 7: single tick produces no labelled rows (horizon can't close)
# ---------------------------------------------------------------------------

def test_single_tick_no_label():
    ticks  = [_tick(0, 67_000.0)]
    rows_r = _run_state(replay_mod.ProductState,     ticks)
    rows_f = _run_state(featurizer_mod.ProductState, ticks)
    assert rows_r == []
    assert rows_f == []


def test_force_drain_does_not_emit_partial_labels(tick_stream):
    rows_r = _run_state(replay_mod.ProductState, tick_stream)
    rows_f = _run_state(featurizer_mod.ProductState, tick_stream)
    assert all(not math.isnan(row["future_vol_60s"]) for row in rows_r)
    assert all(not math.isnan(row["future_vol_60s"]) for row in rows_f)
