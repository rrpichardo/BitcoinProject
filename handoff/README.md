# BTC Volatility Spike Detector — Handoff Package

## Model Selection: Selected-Base

The deployed model is the **Logistic Regression pipeline** (`models/artifacts/lr_pipeline.pkl`), chosen as the selected-base model. It outperforms the z-score baseline on unseen test data (Test PR-AUC 0.1459 vs 0.1340) using a time-based evaluation split with no data leakage.

---

## How to Run

### 1. Install Requirements

```bash
pip install -r requirements.txt
```

### 2. Set Up the .env File

Copy the example and fill in your values:

```bash
cp docker/.env.example .env
```

Open `.env` and set `KAFKA_BOOTSTRAP_SERVERS` (default `localhost:9092`). The Coinbase API keys are optional — only needed for authenticated WebSocket channels.

### 3. Run Docker Compose

Start Kafka and MLflow:

```bash
docker compose -f docker/compose.yaml up -d
```

Wait for the Kafka healthcheck to pass (~20 seconds), then verify topics were created:

```bash
docker logs kafka-init
```

### 4. Load the Model and Run Inference

The model uses a **probability threshold of 0.7015** — a tick is predicted as a volatility spike when `y_prob >= 0.7015`.

```python
import pickle
import pandas as pd

with open("models/artifacts/lr_pipeline.pkl", "rb") as f:
    bundle = pickle.load(f)

pipeline     = bundle["pipeline"]      # sklearn Pipeline (StandardScaler + LogisticRegression)
feature_cols = bundle["feature_cols"]  # list of 7 feature column names
tau          = bundle["tau"]            # probability threshold (auto-selected from validation best-F1)

df      = pd.read_parquet("data_sample/features_slice.parquet")  # or your own features file
X       = df[feature_cols].values
y_prob  = pipeline.predict_proba(X)[:, 1]
y_pred  = (y_prob >= tau).astype(int)

print(f"Spike rate: {y_pred.mean()*100:.1f}%")
```

Or use the inference script directly:

```bash
python models/infer.py \
  --features data_sample/features_slice.csv \
  --model    models/artifacts/lr_pipeline.pkl \
  --output   predictions.csv
```

---

## Package Contents

```
handoff/
├── docker/
│   ├── compose.yaml          Kafka + MLflow services
│   ├── Dockerfile.ingestor   WebSocket ingestor container
│   └── .env.example          Environment variable template
├── docs/
│   ├── feature_spec.md       Feature definitions and label schema
│   └── model_card_v1.md      Model card
├── models/
│   └── artifacts/
│       └── lr_pipeline.pkl   Trained sklearn pipeline (tau = 0.7015)
├── data_sample/
│   ├── raw_slice.parquet     First 10 minutes of raw tick data
│   └── features_slice.csv    Corresponding labelled feature rows
├── reports/
│   ├── model_eval.pdf        Evaluation summary (Milestone 3)
│   ├── train_vs_test.html    Evidently drift report
│   └── predictions.csv       Full inference output [timestamp, y_true, y_prob, y_pred]
├── requirements.txt
└── README.md                 This file
```
