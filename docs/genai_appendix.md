# GenAI Appendix — BTC Volatility Spike Detector

This document logs every instance where Generative AI (Claude) was used to
assist in building this project, including the prompt given, the file(s)
affected, and how the output was verified.

---

**Prompt:** "How can I solve the spike rate inconsistency following the instructors directions to Use time-based train → validation → test splits"
Used in: `models/train.py`
Verification: I implemented the tests that were offered in the instructions as well as the Quick Commands (Example: docker compose up -d, python scripts/ws_ingest.py --pair BTC-USD --minutes 15, python scripts/kafka_consume_check.py --topic ticks.raw --min 100, python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features, python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet, python models/train.py --features data/processed/features.parquet, python models/infer.py --features data/processed/features_test.parquet) to verify the code executed successfully and produced the required outputs.

---

**Prompt:** "In your EDA Notebook (eda.ipynb): Create a plot showing the future_vol_60s for the first half of your data vs. the second half. Say: 'I chose τ=0.000046 because it represents the 90th percentile of the total dataset. I acknowledge that the training period was calmer (4% spikes) than the testing period (19% spikes), which represents a real-world volatility regime shift.' this is to show how percentile plots of future_vol_60s, justify my τ choice. Consider Keep class_weight='balanced' in your code. This tells the AI: 'Hey, spikes are rare in the training data, so pay extra attention to them when you see them!' Is this necessary?"
Used in: `notebooks/eda.ipynb`
Verification: I reviewed and edited the response.

---

**Prompt:** "Make sure this has happened: Log your parameters, metrics, and model artifacts to MLflow. Metrics must include: PR-AUC (required)"
Used in: `models/train.py`
Verification: I implemented the tests that were offered in the instructions as well as the Quick Commands (Example: docker compose up -d, python scripts/ws_ingest.py --pair BTC-USD --minutes 15, python scripts/kafka_consume_check.py --topic ticks.raw --min 100, python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features, python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet, python models/train.py --features data/processed/features.parquet, python models/infer.py --features data/processed/features_test.parquet) to verify the code executed successfully and produced the required outputs.

---

**Prompt:** "Write a one-page Scoping Brief: use case, 60-second prediction goal, success metric, and risk assumptions."
Used in: `docs/scoping_brief.md`
Verification: I reviewed and edited the response.

---

**Prompt:** 'Build scripts/ws_ingest.py — a WebSocket ingestor using asyncio and websockets library with two concurrent tasks: one for the ticker channel and one for heartbeats. Include reconnect loop with exponential backoff, heartbeat counter to detect dropped messages, Kafka producer via confluent_kafka, optional NDJSON file mirror, and graceful shutdown via SIGINT/SIGTERM.'
Used in: `scripts/ws_ingest.py`
Verification: I implemented the tests that were offered in the instructions as well as the Quick Commands (Example: docker compose up -d, python scripts/ws_ingest.py --pair BTC-USD --minutes 15, python scripts/kafka_consume_check.py --topic ticks.raw --min 100, python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features, python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet, python models/train.py --features data/processed/features.parquet, python models/infer.py --features data/processed/features_test.parquet) to verify the code executed successfully and produced the required outputs.

---

**Prompt:** 'Fix the Pylance import errors for confluent_kafka and websockets that could not be resolved.'
Used in: `.vscode/settings.json`
Verification: I implemented the tests that were offered in the instructions as well as the Quick Commands (Example: docker compose up -d, python scripts/ws_ingest.py --pair BTC-USD --minutes 15, python scripts/kafka_consume_check.py --topic ticks.raw --min 100, python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features, python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet, python models/train.py --features data/processed/features.parquet, python models/infer.py --features data/processed/features_test.parquet) to verify the code executed successfully and produced the required outputs.

---

**Prompt:** 'Do we have features/featurizer.py (Kafka consumer) to compute windowed features like midprice returns, bid-ask spread, trade intensity, and order-book imbalance?'
Used in: `features/featurizer.py`
Verification: I implemented the tests that were offered in the instructions as well as the Quick Commands (Example: docker compose up -d, python scripts/ws_ingest.py --pair BTC-USD --minutes 15, python scripts/kafka_consume_check.py --topic ticks.raw --min 100, python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features, python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet, python models/train.py --features data/processed/features.parquet, python models/infer.py --features data/processed/features_test.parquet) to verify the code executed successfully and produced the required outputs.

---

**Prompt:** 'Remove ob_imbalance since it is optional — the Coinbase ticker channel does not provide bid/ask size fields.'
Used in: `features/featurizer.py`
Verification: I implemented the tests that were offered in the instructions as well as the Quick Commands (Example: docker compose up -d, python scripts/ws_ingest.py --pair BTC-USD --minutes 15, python scripts/kafka_consume_check.py --topic ticks.raw --min 100, python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features, python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet, python models/train.py --features data/processed/features.parquet, python models/infer.py --features data/processed/features_test.parquet) to verify the code executed successfully and produced the required outputs.

---

**Prompt:** 'Now that I have the replay script, what should I do with it?'
Used in: `scripts/replay.py`
Verification: I implemented the tests that were offered in the instructions as well as the Quick Commands (Example: docker compose up -d, python scripts/ws_ingest.py --pair BTC-USD --minutes 15, python scripts/kafka_consume_check.py --topic ticks.raw --min 100, python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features, python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet, python models/train.py --features data/processed/features.parquet, python models/infer.py --features data/processed/features_test.parquet) to verify the code executed successfully and produced the required outputs.

---

**Prompt:** 'Conduct EDA in a notebook. Use percentile plots with the goal to set a spike threshold. Create this notebook notebooks/eda.ipynb — plot sigma_future from smallest to largest to see how volatility is distributed.'
Used in: `notebooks/eda.ipynb`
Verification: I reviewed and edited the response.

---

**Prompt:** 'Implement the variables from docs/feature_spec.md including: Target horizon 60s, Volatility proxy rolling std of midprice returns over the next horizon, Label definition 1 if sigma_future >= tau else 0, Chosen threshold tau 0.000046.'
Used in: `docs/feature_spec.md`
Verification: I reviewed and edited the response.

---

**Prompt:** 'Create an Evidently report comparing early and late windows of data.'
Used in: `notebooks/evidently_drift.ipynb`
Verification: I reviewed and edited the response.

---

**Prompt:** 'Test: Replay and live consumer should yield identical features. Evidently report includes drift and data quality.'
Used in: `tests/test_feature_parity.py`
Verification: I implemented the tests that were offered in the instructions as well as the Quick Commands (Example: docker compose up -d, python scripts/ws_ingest.py --pair BTC-USD --minutes 15, python scripts/kafka_consume_check.py --topic ticks.raw --min 100, python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features, python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet, python models/train.py --features data/processed/features.parquet, python models/infer.py --features data/processed/features_test.parquet) to verify the code executed successfully and produced the required outputs.

---

**Prompt:** 'Test: Replay and live consumer should yield identical features. Evidently report includes drift and data quality.'
Used in: `tests/test_evidently_report.py`
Verification: I implemented the tests that were offered in the instructions as well as the Quick Commands (Example: docker compose up -d, python scripts/ws_ingest.py --pair BTC-USD --minutes 15, python scripts/kafka_consume_check.py --topic ticks.raw --min 100, python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features, python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet, python models/train.py --features data/processed/features.parquet, python models/infer.py --features data/processed/features_test.parquet) to verify the code executed successfully and produced the required outputs.

---

**Prompt:** 'Train one baseline model (z-score rule) and one ML model (Logistic Regression). Use time-based train/validation/test splits. Log parameters, metrics, and model artifacts to MLflow. Metrics must include PR-AUC and optionally F1@threshold.'
Used in: `models/train.py`
Verification: I implemented the tests that were offered in the instructions as well as the Quick Commands (Example: docker compose up -d, python scripts/ws_ingest.py --pair BTC-USD --minutes 15, python scripts/kafka_consume_check.py --topic ticks.raw --min 100, python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features, python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet, python models/train.py --features data/processed/features.parquet, python models/infer.py --features data/processed/features_test.parquet) to verify the code executed successfully and produced the required outputs.

---

**Prompt:** 'Build models/infer.py — load model from models/artifacts/, score a features parquet file, output CSV with timestamp, y_true, y_prob, y_pred, print mean inference latency which must be less than 2x real-time.'
Used in: `models/infer.py`
Verification: I implemented the tests that were offered in the instructions as well as the Quick Commands (Example: docker compose up -d, python scripts/ws_ingest.py --pair BTC-USD --minutes 15, python scripts/kafka_consume_check.py --topic ticks.raw --min 100, python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features, python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet, python models/train.py --features data/processed/features.parquet, python models/infer.py --features data/processed/features_test.parquet) to verify the code executed successfully and produced the required outputs.

---

**Prompt:** 'Generate a fresh Evidently report comparing test vs training distribution.'
Used in: `scripts/build_drift_report.py`
Verification: I implemented the tests that were offered in the instructions as well as the Quick Commands (Example: docker compose up -d, python scripts/ws_ingest.py --pair BTC-USD --minutes 15, python scripts/kafka_consume_check.py --topic ticks.raw --min 100, python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features, python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet, python models/train.py --features data/processed/features.parquet, python models/infer.py --features data/processed/features_test.parquet) to verify the code executed successfully and produced the required outputs.

---

**Prompt:** 'Generate a fresh Evidently report comparing test vs training distribution.'
Used in: `reports/evidently/train_vs_test.html`
Verification: I reviewed and edited the response.

---

**Prompt:** 'I need to create a 1-page model evaluation summary for Milestone 3. Extract exact spike rates for train, validation, and test splits and PR-AUC scores for both the z-score baseline and Logistic Regression from MLflow logs. Write a professional markdown document with Evaluation Setup, Dataset Context and Regime Shift, Results table, and Conclusion sections.'
Used in: `reports/model_eval.md`
Verification: I reviewed and edited the response.

---

**Prompt:** 'We need to edit the EDA document to fix overlapping labels in the percentile plot, remove "Choose your threshold at the bend" from the title, replace the decision summary cell with my own text about choosing tau = 0.000046 at the 90th percentile, and remove the regime shift section since it belongs in the Evidently report.'
Used in: `notebooks/eda.ipynb`
Verification: I reviewed the changes.

---

**Prompt:** 'I need to prepare a handoff folder for my team project. Create a top-level directory named handoff with subdirectories: docker, docs, models/artifacts, reports, and data_sample. Include docker/compose.yaml, Dockerfile.ingestor, .env.example, docs/feature_spec.md, docs/model_card_v1.md, models/artifacts/, and requirements.txt.'
Used in: `handoff/`
Verification: I implemented the tests that were offered in the instructions as well as the Quick Commands (Example: docker compose up -d, python scripts/ws_ingest.py --pair BTC-USD --minutes 15, python scripts/kafka_consume_check.py --topic ticks.raw --min 100, python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features, python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet, python models/train.py --features data/processed/features.parquet, python models/infer.py --features data/processed/features_test.parquet) to verify the code executed successfully and produced the required outputs.

---

**Prompt:** 'Save a 10-minute raw slice of market data and its corresponding features. Take the first 10 minutes of the raw dataframe and save it as handoff/data_sample/raw_slice.parquet. Then take those same rows from the processed feature dataframe and save them as handoff/data_sample/features_slice.csv.'
Used in: `handoff/data_sample/raw_slice.parquet`
Verification: I reviewed the folder content. 

---
---

**Prompt:** 'Include reports/model_eval.pdf, Evidently report, and one predictions file in the handoff folder. For the note, state that this is a Selected-base model. Include exact steps on how a teammate can run this: 1. Install requirements, 2. Set up the .env file, 3. Run the docker-compose, and 4. Load the model from the artifacts folder using the 0.30 probability threshold for prediction.'
Used in: `handoff/reports/model_eval.pdf`
Verification: I reviewed  the folder content. 

---

**Prompt:** 'Include reports/model_eval.pdf, Evidently report, and one predictions file in the handoff folder. For the note, state that this is a Selected-base model. Include exact steps on how a teammate can run this: 1. Install requirements, 2. Set up the .env file, 3. Run the docker-compose, and 4. Load the model from the artifacts folder using the 0.30 probability threshold for prediction.'
Used in: `handoff/README.md`
Verification: I reviewed the response.

---

Prompt: 'make sure the project is ok by running all of these commands ensuring they wokr and evertyhing follows the prooject instructions: commmands to veirfy  # 0) Start Kafka + MLflow $ docker compose up -d # 1) Ingest 15 minutes of ticks $ python scripts/ws_ingest.py --pair BTC-USD --minutes 15 # 2) Check messages in Kafka $ python scripts/kafka_consume_check.py --topic ticks.raw --min 100 # 3) Build features $ python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features # 4) Replay raw to verify feature consistency $ python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet # 5) Train and evaluate $ python models/train.py --features data/processed/features.parquet $ python models/infer.py --features data/processed/features_test.parquet'
Used in: compose.yaml
Verification: I implemented the tests that were offered in the instructions as well as the Quick Commands (Example: docker compose up -d, python scripts/ws_ingest.py --pair BTC-USD --minutes 15, python scripts/kafka_consume_check.py --topic ticks.raw --min 100, python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features, python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet, python models/train.py --features data/processed/features.parquet, python models/infer.py --features data/processed/features_test.parquet) to verify the code executed successfully and produced the required outputs.

---

Prompt: 'make sure the project is ok by running all of these commands ensuring they wokr and evertyhing follows the prooject instructions: commmands to veirfy  # 0) Start Kafka + MLflow $ docker compose up -d # 1) Ingest 15 minutes of ticks $ python scripts/ws_ingest.py --pair BTC-USD --minutes 15 # 2) Check messages in Kafka $ python scripts/kafka_consume_check.py --topic ticks.raw --min 100 # 3) Build features $ python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features # 4) Replay raw to verify feature consistency $ python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet # 5) Train and evaluate $ python models/train.py --features data/processed/features.parquet $ python models/infer.py --features data/processed/features_test.parquet'
Used in: scripts/ws_ingest.py
Verification: I implemented the tests that were offered in the instructions as well as the Quick Commands (Example: docker compose up -d, python scripts/ws_ingest.py --pair BTC-USD --minutes 15, python scripts/kafka_consume_check.py --topic ticks.raw --min 100, python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features, python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet, python models/train.py --features data/processed/features.parquet, python models/infer.py --features data/processed/features_test.parquet) to verify the code executed successfully and produced the required outputs.

---

Prompt: 'make sure the project is ok by running all of these commands ensuring they wokr and evertyhing follows the prooject instructions: commmands to veirfy  # 0) Start Kafka + MLflow $ docker compose up -d # 1) Ingest 15 minutes of ticks $ python scripts/ws_ingest.py --pair BTC-USD --minutes 15 # 2) Check messages in Kafka $ python scripts/kafka_consume_check.py --topic ticks.raw --min 100 # 3) Build features $ python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features # 4) Replay raw to verify feature consistency $ python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet # 5) Train and evaluate $ python models/train.py --features data/processed/features.parquet $ python models/infer.py --features data/processed/features_test.parquet'
Used in: scripts/kafka_consume_check.py
Verification: I implemented the tests that were offered in the instructions as well as the Quick Commands (Example: docker compose up -d, python scripts/ws_ingest.py --pair BTC-USD --minutes 15, python scripts/kafka_consume_check.py --topic ticks.raw --min 100, python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features, python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet, python models/train.py --features data/processed/features.parquet, python models/infer.py --features data/processed/features_test.parquet) to verify the code executed successfully and produced the required outputs.

---

Prompt: 'make sure the project is ok by running all of these commands ensuring they wokr and evertyhing follows the prooject instructions: commmands to veirfy  # 0) Start Kafka + MLflow $ docker compose up -d # 1) Ingest 15 minutes of ticks $ python scripts/ws_ingest.py --pair BTC-USD --minutes 15 # 2) Check messages in Kafka $ python scripts/kafka_consume_check.py --topic ticks.raw --min 100 # 3) Build features $ python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features # 4) Replay raw to verify feature consistency $ python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet # 5) Train and evaluate $ python models/train.py --features data/processed/features.parquet $ python models/infer.py --features data/processed/features_test.parquet'
Used in: scripts/replay.py
Verification: I implemented the tests that were offered in the instructions as well as the Quick Commands (Example: docker compose up -d, python scripts/ws_ingest.py --pair BTC-USD --minutes 15, python scripts/kafka_consume_check.py --topic ticks.raw --min 100, python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features, python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet, python models/train.py --features data/processed/features.parquet, python models/infer.py --features data/processed/features_test.parquet) to verify the code executed successfully and produced the required outputs.

---

Prompt: 'make sure the project is ok by running all of these commands ensuring they wokr and evertyhing follows the prooject instructions: commmands to veirfy  # 0) Start Kafka + MLflow $ docker compose up -d # 1) Ingest 15 minutes of ticks $ python scripts/ws_ingest.py --pair BTC-USD --minutes 15 # 2) Check messages in Kafka $ python scripts/kafka_consume_check.py --topic ticks.raw --min 100 # 3) Build features $ python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features # 4) Replay raw to verify feature consistency $ python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet # 5) Train and evaluate $ python models/train.py --features data/processed/features.parquet $ python models/infer.py --features data/processed/features_test.parquet'
Used in: models/train.py
Verification: I implemented the tests that were offered in the instructions as well as the Quick Commands (Example: docker compose up -d, python scripts/ws_ingest.py --pair BTC-USD --minutes 15, python scripts/kafka_consume_check.py --topic ticks.raw --min 100, python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features, python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet, python models/train.py --features data/processed/features.parquet, python models/infer.py --features data/processed/features_test.parquet) to verify the code executed successfully and produced the required outputs.
