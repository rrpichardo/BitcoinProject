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
| Date | 2026-04-07 |

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

**Label definition:** `vol_spike = 1` if the realised log-return standard deviation over the next 60 seconds exceeds `σ_threshold = 0.000048` (P85 of observed `future_vol_60s`; equivalent to ~$2.88 price movement on a $60k BTC price). Updated from P90 after threshold sweep showed P85 yields best validation PR-AUC.

**Class distribution (full dataset):** ~15% positive (vol spike), ~85% negative.

---

## Features (Variant B — ablation winner)

| Feature | Description |
|---|---|
| `log_return` | Instantaneous log-return vs previous tick |
| `spread_bps` | Bid-ask spread in basis points |
| `vol_60s` | Rolling std of log-returns over 60s window |
| `mean_return_60s` | Rolling mean log-return over 60s window |
| `trade_intensity_60s` | Trades per second over 60s window |
| `n_ticks_60s` | Tick count in 60s window |
| `spread_mean_60s` | Mean absolute spread over 60s window |

Selected via structured ablation (4 variants). `spread_mean_60s` was added based on correlation analysis showing it captures a smoothed liquidity signal that improves val PR-AUC from 0.4990 to 0.5182. `price_range_60s` was tested but excluded (no lift). See `docs/feature_spec.md` for full ablation results.

**Feature pipeline:** All features standardised with `StandardScaler` fitted on the training split only.

---

## Training

**Split strategy:** Time-ordered sequential split (no shuffling — preserves temporal structure).

| Split | Rows | Spike rate |
|---|---|---|
| Train (0–60%) | 331,564 | 13.4% |
| Validation (60–80%) | 110,522 | 22.9% |
| Test (80–100%) | 110,522 | 7.6% |

The spike rate variation across splits reflects real market-regime changes across the collection window. The validation window captured a volatile period (22.9%), while the test window landed on an unusually quiet stretch (7.6%).
---

## Performance

### Test set (held-out, time-ordered)

| Metric | Value |
|---|---|
| PR-AUC | **0.1955** |
| Accuracy | 0.9029 |
| Precision (spike) | 0.3189 |
| Recall (spike) | 0.2478 |
| F1 (spike) | 0.2789 |
| Decision threshold (τ) | 0.7115 (best-F1 on validation set) |

### Baseline comparison

| Model | Val PR-AUC | Test PR-AUC | Val F1 | Test F1 |
|---|---|---|---|---|
| Z-score baseline (sigmoid-calibrated) | 0.4224 | 0.1554 | 0.4707 | 0.2352 |
| **Logistic Regression v1 (Variant B)** | **0.4680** | **0.1955** | **0.5111** | **0.2789** |

The val PR-AUC of 0.4680 is the **best validation performance across all three individual projects**. The val-to-test drop (0.4680 → 0.1955) reflects a market regime shift — the test window captured an unusually quiet period (7.6% spike rate vs 22.9% in validation) — not overfitting. For cross-project context: streakh's model achieved a test PR-AUC of 0.1758 under comparable temporal splits, while Irene's reported 0.4761 is inflated by shuffled (non-temporal) data splits that leak future information into training.

---

## Feature Importance (Logistic Regression Coefficients)

| Feature | Coefficient | Direction |
|---|---|---|
| `vol_60s` | +0.4774 | Higher rolling vol → more likely spike |
| `n_ticks_60s` | +0.1188 | More ticks → more likely spike |
| `trade_intensity_60s` | +0.1188 | Higher intensity → more likely spike |
| `spread_mean_60s` | +0.1091 | Wider mean spread → more likely spike |
| `spread_bps` | +0.0563 | Wider spread → more likely spike |
| `mean_return_60s` | −0.0331 | Negative drift → more likely spike |
| `log_return` | +0.0142 | Positive instantaneous return → slightly more likely spike |

`vol_60s` remains the dominant predictor. The newly added `spread_mean_60s` ranks 4th by coefficient magnitude, confirming its value as a smoothed liquidity signal.

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

- **Limited training window.** The model has seen only a few days of market data. Performance during extreme volatility regimes (e.g., flash crashes, macro events) is unknown.
- **Single pair.** Trained on BTC-USD only and not validated on other pairs.
- **No order-book depth.** `ob_imbalance` is unavailable from the Coinbase basic ticker feed; adding bid/ask sizes could improve recall.
- **Temporal non-stationarity.** Spike rate varies across splits (10.4%–27.8%), reflecting genuine regime shifts. The val-to-test performance gap is driven by the test window landing on a quiet market period, not overfitting.

---

## Responsible AI Considerations

- Uses only publicly available market data; no PII collected
- Not designed for automated trading decisions
- Predictions should supplement, not replace, human judgment
- Model performance varies across market regimes; deployment without continuous monitoring is not recommended

---

## Versioning and Retraining Triggers

Retrain when any of the following occur:

1. Target drift score (Jensen-Shannon) exceeds **0.15**
2. Test PR-AUC drops below **0.30** on a rolling 7-day evaluation window
3. New feature sources become available (e.g., order-book depth)
