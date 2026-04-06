# Bitcoin Volatility Detection Pipeline

Real-time BTC-USD volatility spike detection using Coinbase WebSocket, Kafka, MLflow, and Evidently.

## Quick Start

```bash
# 0) Start Kafka + MLflow
docker compose up -d

# 1) Ingest 15 minutes of ticks
python scripts/ws_ingest.py --pair BTC-USD --minutes 15

# 2) Check messages in Kafka
python scripts/kafka_consume_check.py --topic ticks.raw --min 100

# 3) Build features (live consumer)
python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features

# 4) Replay raw files to verify feature consistency
python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet

# 5) Train and evaluate
python models/train.py --features data/processed/features.parquet
python models/infer.py --features data/processed/features_test.parquet
```

## Repository Layout

```
data/raw/               Captured raw tick data (NDJSON)
data/processed/         Featurized Parquet files
features/               Feature engineering (live + replay)
models/                 Training, inference, artifacts
notebooks/              EDA
reports/                Evidently drift + model evaluation
scripts/                Ingest, replay, Kafka sanity check
docker/                 Compose + Dockerfile
docs/                   Scoping brief, feature spec, model card, GenAI log
handoff/                Files passed to team
mlruns/                 MLflow store (file backend)
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| Kafka (KRaft) | 9092 | Message broker |
| MLflow | 5001 | Experiment tracking |

## Environment

Copy `.env.example` to `.env` and adjust if needed. Never commit `.env`.
