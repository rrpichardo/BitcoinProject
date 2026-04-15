# Runbook

## Purpose

This runbook describes the current operating flow for the Bitcoin volatility service: startup, live streaming, replay fallback, validation, and recovery.

## Scope

This runbook covers the setup and working pipeline that exists now:

- Kafka startup
- MLflow startup
- FastAPI startup and endpoint checks
- live ingest
- live feature generation
- replay
- training and inference

This runbook does not claim that later-week deliverables are complete yet. In particular, CI, Grafana dashboards, formal SLO docs, rollback controls, and final demo packaging are outside the current scope.

## Primary Mode

Use live streaming as the primary operating mode. Use replay for deterministic verification, debugging, and backup demos.

## Startup

1. Start infrastructure and the API:

```bash
docker compose up -d
docker compose ps
```

2. Start the live feature consumer in a separate terminal:

```bash
python features/featurizer.py \
  --topic_in ticks.raw \
  --topic_out ticks.features \
  --output_parquet data/processed/features_live.parquet
```

3. Start the raw-stream validator in a separate terminal:

```bash
python scripts/kafka_consume_check.py --topic ticks.raw --min 100
```

4. Start live ingest in a separate terminal:

```bash
python scripts/ws_ingest.py --pair BTC-USD --minutes 15
```

5. After ingest stops, stop the featurizer with `Ctrl-C` so it flushes and commits `data/processed/features_live.parquet`.

## Replay And Training

After a live capture completes, rebuild the canonical training parquet and retrain:

```bash
python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet
python models/train.py --features data/processed/features.parquet
python models/infer.py --features data/processed/features_test.parquet
```

## API Checks

Use these checks after startup or before a local verification run:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/version
curl http://localhost:8000/metrics
curl -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"rows":[{"log_return":0.0001,"spread_bps":1.5,"vol_60s":0.00005,"mean_return_60s":0.0,"trade_intensity_60s":10.0,"n_ticks_60s":50,"spread_mean_60s":1.2}]}'
```

## Why This Order

- Kafka, MLflow, and the API come up before any streaming work starts.
- The featurizer is already listening before raw ticks arrive.
- The validator is already listening before raw ticks arrive.
- The ingest job starts last, so downstream consumers observe the live stream in real time.
- Replay and training happen after the raw slice is fully captured.

## Replay Fallback

If live ingest is unavailable or you need a deterministic verification path, use replay mode:

```bash
docker compose up -d
python scripts/replay.py --raw data/raw/20260404.ndjson --out data/processed/features_10min.parquet --minutes 10
python models/infer.py --features data/processed/features_10min.parquet --batch
```

## Troubleshooting

### Validator sees no messages

- If ingest already started before the validator, rerun:

```bash
python scripts/kafka_consume_check.py --topic ticks.raw --min 100 --from-beginning
```

### Duplicate ingest

- Plain `docker compose up -d` is safe for the assignment flow.
- The containerized `ingestor` service is now opt-in via the `live-ingest` profile, so it does not start by default.
- If you intentionally want the containerized ingestor instead of the local script, use:

```bash
docker compose --profile live-ingest up -d
```

### MLflow training issues

- `config.yaml` is set to use the running MLflow server at `http://localhost:5001`.
- This repo includes a compatibility fallback for newer local MLflow clients talking to the Docker MLflow server.
- If training logs metrics but skips MLflow model logging, the saved model bundle in `models/artifacts/lr_pipeline.pkl` is still the source of truth for `infer.py` and the API.

### Monitoring expectations

- The API exposes `/metrics` in Prometheus format.
- Full Prometheus scraping, Grafana dashboards, alerting, and SLO documentation are planned later and are not part of the current runbook.

### Featurizer did not write the final parquet

- Stop it cleanly with `Ctrl-C`.
- The featurizer commits Parquet on shutdown.
- Temporary files appear as `.features_live.parquet.*.tmp` until commit.

### Replay warnings about malformed lines

- `scripts/replay.py` is designed to skip malformed NDJSON lines and continue.
- Review the warning count, but a small number of skipped lines does not automatically invalidate the replay.

## Recovery

### Restart infrastructure

```bash
docker compose down
docker compose up -d
```

### Rebuild training data from raw capture

```bash
python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet
```

### Refresh model artifacts

```bash
python models/train.py --features data/processed/features.parquet
python models/infer.py --features data/processed/features_test.parquet
```

## Suggested Verification Flow

1. Start infrastructure.
2. Start featurizer.
3. Start validator.
4. Start ingest.
5. Show `/health`, `/version`, and `/predict`.
6. Stop featurizer and show `features_live.parquet`.
7. Run replay/train/infer if a deterministic evaluation step is needed.
