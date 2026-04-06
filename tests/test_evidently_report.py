"""
Tests that the Evidently report pipeline:
- runs without error on real or synthetic data
- includes DataDriftPreset (feature drift)
- includes DataQualityPreset (null / type checks)
- produces a non-empty HTML artefact
"""

import math
import random
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from evidently.report import Report
from evidently.metric_preset import DataDriftPreset, DataQualityPreset, TargetDriftPreset
from evidently.pipeline.column_mapping import ColumnMapping

FEATURE_COLS = [
    "price", "midprice", "log_return",
    "spread_abs", "spread_bps",
    "vol_60s", "mean_return_60s", "n_ticks_60s", "trade_intensity_60s",
]
TARGET_COL = "vol_spike"


# ---------------------------------------------------------------------------
# Fixture — synthetic reference / current DataFrames
# ---------------------------------------------------------------------------

def _make_df(n: int, price_base: float, spike_rate: float, seed: int) -> pd.DataFrame:
    rng   = random.Random(seed)
    rows  = []
    price = price_base
    for _ in range(n):
        price  += rng.gauss(0, 1.5)
        spread  = abs(rng.gauss(0.01, 0.002))
        mid     = price
        rows.append({
            "price":               price,
            "midprice":            mid,
            "log_return":          rng.gauss(0, 0.00003),
            "spread_abs":          spread,
            "spread_bps":          spread / mid * 10_000,
            "vol_60s":             abs(rng.gauss(0.00002, 0.000005)),
            "mean_return_60s":     rng.gauss(0, 0.000005),
            "n_ticks_60s":         rng.randint(100, 300),
            "trade_intensity_60s": rng.uniform(1.5, 5.0),
            "vol_spike":           1 if rng.random() < spike_rate else 0,
        })
    return pd.DataFrame(rows)


@pytest.fixture()
def reference():
    return _make_df(n=500, price_base=67_000, spike_rate=0.10, seed=1)


@pytest.fixture()
def current():
    return _make_df(n=500, price_base=67_100, spike_rate=0.12, seed=2)


# ---------------------------------------------------------------------------
# Test 1: DataDriftPreset runs without error
# ---------------------------------------------------------------------------

def test_data_drift_runs(reference, current):
    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=reference[FEATURE_COLS],
               current_data=current[FEATURE_COLS])
    result = report.as_dict()
    assert "metrics" in result
    assert len(result["metrics"]) > 0


# ---------------------------------------------------------------------------
# Test 2: DataQualityPreset runs without error
# ---------------------------------------------------------------------------

def test_data_quality_runs(reference, current):
    report = Report(metrics=[DataQualityPreset()])
    report.run(reference_data=reference[FEATURE_COLS],
               current_data=current[FEATURE_COLS])
    result = report.as_dict()
    assert "metrics" in result


# ---------------------------------------------------------------------------
# Test 3: combined report includes both drift and quality metrics
# ---------------------------------------------------------------------------

def test_combined_report_metric_types(reference, current):
    report = Report(metrics=[DataQualityPreset(), DataDriftPreset()])
    report.run(reference_data=reference[FEATURE_COLS],
               current_data=current[FEATURE_COLS])
    result     = report.as_dict()
    metric_ids = {m["metric"] for m in result["metrics"]}
    # DataDriftPreset expands into these metric types
    assert any("Drift" in mid for mid in metric_ids), (
        f"No drift metric found in: {metric_ids}"
    )
    assert any("Quality" in mid or "Summary" in mid for mid in metric_ids), (
        f"No quality metric found in: {metric_ids}"
    )


# ---------------------------------------------------------------------------
# Test 4: TargetDriftPreset runs on labelled data
# ---------------------------------------------------------------------------

def test_target_drift_runs(reference, current):
    col_map = ColumnMapping(target=TARGET_COL, prediction=None)
    report  = Report(metrics=[TargetDriftPreset()])
    report.run(
        reference_data=reference[FEATURE_COLS + [TARGET_COL]],
        current_data=current[FEATURE_COLS + [TARGET_COL]],
        column_mapping=col_map,
    )
    result = report.as_dict()
    assert "metrics" in result and len(result["metrics"]) > 0


# ---------------------------------------------------------------------------
# Test 5: HTML output is non-empty and well-formed
# ---------------------------------------------------------------------------

def test_html_output_non_empty(reference, current, tmp_path):
    report = Report(metrics=[DataQualityPreset(), DataDriftPreset()])
    report.run(reference_data=reference[FEATURE_COLS],
               current_data=current[FEATURE_COLS])
    out = tmp_path / "drift.html"
    report.save_html(str(out))
    assert out.exists()
    content = out.read_text()
    assert len(content) > 1_000, "HTML file suspiciously small"
    assert "<html" in content.lower()


# ---------------------------------------------------------------------------
# Test 6: drift score is a float in [0, 1] for each feature column
# ---------------------------------------------------------------------------

def test_drift_scores_in_range(reference, current):
    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=reference[FEATURE_COLS],
               current_data=current[FEATURE_COLS])
    result = report.as_dict()
    for m in result["metrics"]:
        if m["metric"] == "ColumnDriftMetric":
            score = m["result"]["drift_score"]
            assert 0.0 <= score <= 1.0, (
                f"drift_score={score} out of range for {m['result']['column_name']}"
            )


# ---------------------------------------------------------------------------
# Test 7: report on identical DataFrames detects no drift
# ---------------------------------------------------------------------------

def test_no_drift_on_identical_data(reference):
    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=reference[FEATURE_COLS],
               current_data=reference[FEATURE_COLS])
    result  = report.as_dict()
    drifted = [
        m["result"]["column_name"]
        for m in result["metrics"]
        if m["metric"] == "ColumnDriftMetric"
        and m["result"]["drift_detected"]
    ]
    assert drifted == [], f"Unexpected drift on identical data: {drifted}"
