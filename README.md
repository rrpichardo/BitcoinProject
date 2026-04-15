# Bitcoin Volatility Detection Pipeline

Real-time BTC-USD volatility spike detection using Coinbase WebSocket, Kafka, FastAPI, MLflow, and Evidently.

## Week 4 Thin Slice

This repo includes the Week 4 system setup deliverables:

- `docker-compose.yaml` and [`docker/compose.yaml`](/Users/ricopichardo/Library/Mobile%20Documents/com~apple~CloudDocs/CMU/CMU/Classes/Mini%204/Operationalizing%20AI/BitcoinProject/docker/compose.yaml) to launch Kafka (KRaft), MLflow, and the FastAPI service
- FastAPI endpoints in [`api/main.py`](/Users/ricopichardo/Library/Mobile%20Documents/com~apple~CloudDocs/CMU/CMU/Classes/Mini%204/Operationalizing%20AI/BitcoinProject/api/main.py): `/health`, `/predict`, `/version`, `/metrics`
- Architecture diagram in [`docs/architecture.svg`](/Users/ricopichardo/Library/Mobile%20Documents/com~apple~CloudDocs/CMU/CMU/Classes/Mini%204/Operationalizing%20AI/BitcoinProject/docs/architecture.svg)
- Team roles and model choice docs in [`docs/team_charter.md`](/Users/ricopichardo/Library/Mobile%20Documents/com~apple~CloudDocs/CMU/CMU/Classes/Mini%204/Operationalizing%20AI/BitcoinProject/docs/team_charter.md) and [`docs/selection_rationale.md`](/Users/ricopichardo/Library/Mobile%20Documents/com~apple~CloudDocs/CMU/CMU/Classes/Mini%204/Operationalizing%20AI/BitcoinProject/docs/selection_rationale.md)

### Thin Slice Runbook

```bash
# Start the Week 4 services from the project root
docker compose -f docker-compose.yaml up -d kafka mlflow api

# API health/version checks
curl http://localhost:8000/health
curl http://localhost:8000/version

# Replay the first 10 minutes of a raw mirror file into features
python3 scripts/replay.py \
  --raw data/raw/20260404.ndjson \
  --out data/processed/features_10min.parquet \
  --minutes 10
```

### Sample `/predict` Request

```bash
curl -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"rows":[{"log_return":0.0001,"spread_bps":1.5,"vol_60s":0.00005,"mean_return_60s":0.0,"trade_intensity_60s":10.0,"n_ticks_60s":50,"spread_mean_60s":1.2}]}'
```

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
