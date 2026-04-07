from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "features"))

from parquet_sink import AtomicParquetSink
from featurizer import FLUSH_ROWS, PARQUET_SCHEMA


def _sample_row() -> dict:
    return {
        "product_id": "BTC-USD",
        "timestamp": "2026-04-05T00:00:00.000000Z",
        "price": 67_000.0,
        "midprice": 67_000.0,
        "log_return": 0.0,
        "spread_abs": 0.02,
        "spread_bps": 0.0029850746268656717,
        "vol_60s": 0.0,
        "mean_return_60s": 0.0,
        "n_ticks_60s": 1,
        "trade_intensity_60s": 0.1,
        "spread_mean_60s": 0.02,
        "price_range_60s": 0.0,
        "future_vol_60s": 0.0,
        "vol_spike": 0,
    }


def test_close_without_writes_preserves_existing_file(tmp_path):
    out_path = tmp_path / "features.parquet"
    sentinel = b"keep-me"
    out_path.write_bytes(sentinel)

    sink = AtomicParquetSink(out_path, schema=PARQUET_SCHEMA, flush_rows=FLUSH_ROWS)
    sink.close()

    assert out_path.read_bytes() == sentinel


def test_close_after_write_replaces_target_with_valid_parquet(tmp_path):
    out_path = tmp_path / "features.parquet"
    out_path.write_text("stale")

    sink = AtomicParquetSink(out_path, schema=PARQUET_SCHEMA, flush_rows=FLUSH_ROWS)
    sink.write(_sample_row())
    sink.close()

    df = pd.read_parquet(out_path)
    assert len(df) == 1
    assert df.iloc[0]["product_id"] == "BTC-USD"
