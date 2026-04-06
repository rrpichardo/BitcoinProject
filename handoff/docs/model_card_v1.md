# Model Card — BTC Volatility Spike Detector v1

## Model Details

| Field | Value |
|---|---|
| Name | BTC Volatility Spike Detector |
| Version | v1 |
| Type | Binary classifier — Logistic Regression |
| Framework | scikit-learn 1.4+ |
| Artifact | `models/artifacts/lr_pipeline.pkl` |
| MLflow experiment | `btc-volatility` |
| Date | 2026-04-05 |

**Architecture:** `StandardScaler → LogisticRegression(C=0.1, class_weight='balanced')`

---

## Intended Use

Predicts whether BTC-USD price volatility will **spike** over the next 60 seconds given the current tick-level state. Intended for use as a real-time signal in a trading alerting system.

---

## Data

| Field | Value |
|---|---|
| Source | Coinbase Advanced Trade WebSocket (`wss://advanced-trade-ws.coinbase.com`) |
| Pair | BTC-USD |
| Collection period | 2026-04-04 22:54 UTC → 2026-04-05 17:10 UTC (~18 hours) |
| Raw ticks | 115,161 |
| Labelled rows | 110,964 |
| Null labels (edge drain) | 174 rows dropped |

**Label definition:** `vol_spike = 1` if the realised log-return standard deviation over the next 60 seconds exceeds `σ_threshold = 0.000046` (P90 of observed `future_vol_60s`; equivalent to ~$2.75 price movement on a $60k BTC price).

**Class distribution (full dataset):** 9.8% positive (vol spike), 90.2% negative.

---

## Features

| Feature | Description |
|---|---|
| `vol_60s` | Rolling std of log-returns over 60s window |
| `mean_return_60s` | Rolling mean log-return over 60s window |
| `n_ticks_60s` | Tick count in 60s window |
| `trade_intensity_60s` | Trades per second over 60s window |
| `log_return` | Instantaneous log-return vs previous tick |
| `spread_abs` | Absolute bid-ask spread |
| `spread_bps` | Bid-ask spread in basis points |
| `price` | Last trade price |
| `midprice` | (bid + ask) / 2 |

**Feature pipeline:** All features standardised with `StandardScaler` fitted on the training split only.

---

## Training

**Split strategy:** Time-ordered sequential split (no shuffling — preserves temporal structure).

| Split | Rows | Spike rate |
|---|---|---|
| Train (0–60%) | 66,578 | 4.3% |
| Validation (60–80%) | 22,193 | 19.9% |
| Test (80–100%) | 22,193 | 16.3% |

The spike rate increase across splits reflects real market-regime variation over the 18-hour collection window.
---

## Performance

### Test set (held-out, time-ordered)

| Metric | Value |
|---|---|
| PR-AUC | **0.417** |
| Accuracy | 0.822 |
| Precision (spike) | 0.448 |
| Recall (spike) | 0.394 |
| F1 (spike) | 0.420 |
| Decision threshold (τ) | 0.637 (best-F1, saved) |

### Baseline comparison

| Model | Val PR-AUC | Test PR-AUC |
|---|---|---|
| Z-score baseline | 0.334 | 0.261 |
| **Logistic Regression v1** | **0.252** | **0.417** |

The LR model generalises better to unseen future data (test > val) despite lower val PR-AUC. This could suggest that the z-score baseline overfitted to the market regime of the validation window.

---

## Feature Importance (Logistic Regression Coefficients)

| Feature | Coefficient | Direction |
|---|---|---|
| `vol_60s` | +0.3383 | Higher rolling vol → more likely spike |
| `n_ticks_60s` | −0.1143 | More ticks → less likely spike |
| `trade_intensity_60s` | −0.1143 | Higher intensity → less likely spike |
| `mean_return_60s` | +0.0621 | Positive drift → more likely spike |
| `spread_bps` | +0.0283 | Wider spread → more likely spike |
| `log_return` | −0.0164 | Negative instantaneous return → more likely spike |

`price`, `midprice`, and `spread_abs` showed near-zero coefficients and do not materially contribute.

---

## Drift Monitoring

Drift detected on the **target label (`vol_spike`)** between early and late windows:

| Metric | Value |
|---|---|
| Detection method | Jensen-Shannon distance |
| Drift score | **0.127** |
| Drift detected | Yes |

This reflects the spike rate shifting from ~4% (early collection) to ~16–20% (later collection). This consistent with a genuine change in market volatility regime during the collection period.
Evidently HTML reports: `reports/evidently/feature_drift.html`, `reports/evidently/target_drift.html`

---

## Limitations

- **Short training window (~18 hours).** The model has seen only one market session. Performance during high-volatility regimes is unknown.
- **Single pair.** Trained on BTC-USD only and not validated on other pairs.
- **No order-book depth.** `ob_imbalance` is unavailable from the Coinbase basic ticker feed; adding bid/ask sizes could improve recall.
- **Class imbalance.** At 9.8% positive rate in training, we see low precision at high recall. `class_weight='balanced'` partially compensates but precision remains low (~45%).

---

## Ethical Considerations

This model outputs a probabilistic signal for a financial instrument. It should not be used as the sole basis for automated trade execution without human oversight.

---

## Versioning and Retraining Triggers

Retrain when any of the following occur:

1. Target drift score (Jensen-Shannon) exceeds **0.15**
2. Test PR-AUC drops below **0.30** on a rolling 7-day evaluation window
3. New feature sources become available (e.g., order-book depth)
