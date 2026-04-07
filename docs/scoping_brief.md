# Scoping Brief — BTC Volatility Spike Detector

## Use Case

Cryptocurrency trading desks and automated market makers need advance warning
before periods of unusually high price volatility. A sudden spike in BTC-USD
volatility can adjust positions, hedges or other financial decisions. Today, most participants react *after* the spike has alreadybegun. This project builds a real-time system that ingests the Coinbase BTC-USD WebSocket feed, engineers tick-level features via Kafka, and classifies whether
a volatility spike is imminent. 

## 60-Second Prediction Goal

The model predicts, at every incoming tick, whether the realized volatility of
BTC-USD midprice log-returns over the **next 60 seconds** will exceed a
threshold τ = 0.000048 (the 85th percentile of observed `future_vol_60s`).

- **Label**: `vol_spike = 1` if σ_future(60s) ≥ 0.000048; else `0`.
- **Positive rate**: ~15% of ticks overall, though this varies across
  volatility regimes (as low as ~8% in calm periods, up to ~25% in volatile
  periods).
- **Horizon justification**: 60 seconds is long enough for a trading system to
   filter out random, high frequency tick noise, but short enough that the signal remains correlated to the current market position. 

## Success Metric

| Metric | Target | Rationale |
|--------|--------|-----------|
| **PR-AUC** (primary) | > 0.40 on test set | PR-AUC is the appropriate metric for imbalanced binary classification. A random classifier scores ~0.10 (the base spike rate), so 0.40 represents meaningful skill. |
| Latency (inference) | < 50 ms per tick | The prediction must be available before the next tick arrives to be operationally useful. |


## Risk Assumptions


1. **Regime shift**:  Training data is more volatile (15.4% spikes) than the test period (7.0% spikes). The model may over-predict in calm regimes or under-predict in volatile ones.  Model performance degrades when deployed into a different volatility regime than it trained on.
2. **Label leakage** : Features computed from overlapping or forward-looking windows could leak future information into the model. Artificially inflated metrics that do not generalize.  Strict time-based train → val → test splits (60/20/20, no shuffle).
3. **Feed disruption**: Coinbase WebSocket disconnections create gaps in the tick stream, producing stale or missing features. False negatives (missed spikes) or NaN feature rows during outages.
4. **Threshold sensitivity**:  τ = 0.000048 was calibrated on the observed dataset. A structurally different market (e.g., macro shock) may shift the volatility distribution. The 85th percentile of future data may no longer correspond to the same τ, changing the effective spike rate.
|5. **Single-asset scope**: The model only ingests BTC-USD order book data. Cross-asset contagion (e.g., ETH crash spilling into BTC) is invisible. Spikes driven by external circumstances can make the model not accurate without any warning features. 