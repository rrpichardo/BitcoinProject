# Bitcoin Volatility Detection Pipeline

Real-time BTC-USD volatility spike detection with Kafka, FastAPI, MLflow, and replay support.

## Current Scope

This repo is currently set up through the system/API stage. The live ingest, feature pipeline, replay flow, training flow, FastAPI endpoints, and MLflow integration are in place.

The following later-week items are not documented here as completed yet:

- CI / GitHub Actions hardening
- load testing and latency reporting
- Prometheus + Grafana dashboards
- SLO docs and alerting
- rollback toggles
- final demo and release handoff

## Setup

```bash
docker compose up -d kafka mlflow api kafka-init
python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features --output_parquet data/processed/features_live.parquet
python scripts/kafka_consume_check.py --topic ticks.raw --min 100
python scripts/ws_ingest.py --pair BTC-USD --minutes 15
python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet
python models/train.py --features data/processed/features.parquet
python models/infer.py --features data/processed/features_test.parquet
curl -X POST http://localhost:8000/predict -H 'Content-Type: application/json' -d '{"rows":[{"log_return":0.0001,"spread_bps":1.5,"vol_60s":0.00005,"mean_return_60s":0.0,"trade_intensity_60s":10.0,"n_ticks_60s":50,"spread_mean_60s":1.2}]}'
```

If the validator starts after ingest has already begun, use `python scripts/kafka_consume_check.py --topic ticks.raw --min 100 --from-beginning`.

## Docs

- Operations: [docs/runbook.md](/Users/ricopichardo/Library/Mobile%20Documents/com~apple~CloudDocs/CMU/CMU/Classes/Mini%204/Operationalizing%20AI/BitcoinProject/docs/runbook.md)
- Architecture: [docs/architecture.svg](/Users/ricopichardo/Library/Mobile%20Documents/com~apple~CloudDocs/CMU/CMU/Classes/Mini%204/Operationalizing%20AI/BitcoinProject/docs/architecture.svg)
- Feature spec: [docs/feature_spec.md](/Users/ricopichardo/Library/Mobile%20Documents/com~apple~CloudDocs/CMU/CMU/Classes/Mini%204/Operationalizing%20AI/BitcoinProject/docs/feature_spec.md)
- Model card: [docs/model_card_v1.md](/Users/ricopichardo/Library/Mobile%20Documents/com~apple~CloudDocs/CMU/CMU/Classes/Mini%204/Operationalizing%20AI/BitcoinProject/docs/model_card_v1.md)
- Team docs: [docs/team_charter.md](/Users/ricopichardo/Library/Mobile%20Documents/com~apple~CloudDocs/CMU/CMU/Classes/Mini%204/Operationalizing%20AI/BitcoinProject/docs/team_charter.md), [docs/selection_rationale.md](/Users/ricopichardo/Library/Mobile%20Documents/com~apple~CloudDocs/CMU/CMU/Classes/Mini%204/Operationalizing%20AI/BitcoinProject/docs/selection_rationale.md)

Only the documents listed above are intended to exist at this stage.
