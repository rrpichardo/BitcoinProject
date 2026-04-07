import importlib.util
import json
import sys
import types
from pathlib import Path


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "features"))

import replay


def _write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("".join(lines))


def _tick(timestamp: str, price: str) -> str:
    return json.dumps({
        "product_id": "BTC-USD",
        "timestamp": timestamp,
        "price": price,
        "best_bid": "66999.0",
        "best_ask": "67001.0",
        "volume_24_h": "1000.0",
    }) + "\n"


def test_iter_ticks_streams_sorted_and_dedupes(tmp_path):
    file_a = tmp_path / "a.ndjson"
    file_b = tmp_path / "b.ndjson"

    shared = _tick("2026-04-05T00:00:01.000000Z", "67000.0")
    _write_lines(file_a, [
        _tick("2026-04-05T00:00:00.000000Z", "66999.0"),
        shared,
    ])
    _write_lines(file_b, [
        shared,
        _tick("2026-04-05T00:00:02.000000Z", "67002.0"),
    ])

    rows = list(replay.iter_ticks([str(tmp_path / "*.ndjson")]))
    assert [row[1]["timestamp"] for row in rows] == [
        "2026-04-05T00:00:00.000000Z",
        "2026-04-05T00:00:01.000000Z",
        "2026-04-05T00:00:02.000000Z",
    ]


def test_iter_ticks_skips_malformed_tail_line(tmp_path):
    path = tmp_path / "broken.ndjson"
    _write_lines(path, [
        _tick("2026-04-05T00:00:00.000000Z", "67000.0"),
        '{"product_id":"BTC-USD"',
    ])

    rows = list(replay.iter_ticks([str(path)]))
    assert len(rows) == 1


def test_mirror_writer_creates_atomic_segment(tmp_path, monkeypatch):
    stub = types.ModuleType("confluent_kafka")
    stub.Producer = object
    sys.modules.setdefault("confluent_kafka", stub)

    spec = importlib.util.spec_from_file_location(
        "ws_ingest_test", ROOT / "scripts" / "ws_ingest.py"
    )
    ws_ingest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ws_ingest)

    monkeypatch.chdir(tmp_path)
    writer = ws_ingest.MirrorWriter("BTC-USD")
    writer.write('{"a":1}')
    writer.flush()

    files = sorted((tmp_path / "data" / "raw").glob("*.ndjson"))
    assert len(files) == 1
    assert files[0].read_text() == '{"a":1}\n'
    assert list((tmp_path / "data" / "raw").glob("*.tmp")) == []
