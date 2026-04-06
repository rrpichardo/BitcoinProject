# Model Evaluation Summary — Milestone 3
**Project:** BTC Volatility Spike Detector  
**Date:** 2026-04-05  

---

## Evaluation Setup

| Parameter | Value |
|---|---|
| Target | `vol_spike` — 1 if 60-second realized volatility ≥ τ = 0.000046 |
| Target horizon | 60 seconds |
| Features | `log_return`, `spread_bps`, `vol_60s`, `mean_return_60s`, `trade_intensity_60s`, `n_ticks_60s` |
| Validation strategy | Time-based splits with no shuffling |
| Split | 60% Train / 20% Validation / 20% Test (by row count) |
| Primary metric | PR-AUC (precision-recall area under curve) |

---

## Dataset Context & Regime Shift

The dataset spans approximately 18 hours of continuous BTC-USD tick data (2026-04-04 22:54 → 2026-04-05 17:10). Something to notice is that the overnight session was significantly calmer than the morning session that followed.

| Split | Rows | Spike Rate | Period |
|---|---|---|---|
| Train | 66,578 | **4.3%** | Overnight (low-volatility regime) |
| Validation | 22,193 | **19.9%** | Morning session open |
| Test | 22,193 | **16.3%** | Morning session continuation |

The spike rate jumped from 4.3% in training to ~16–20% in evaluation.This **4× increase** is driven entirely by real-world intraday trading patterns. This is consistent with the Evidently drift report, which detected statistically significant drift in between the training and test windows.

To handle the rare positive class in trainin, the Logistic Regression model used `class_weight="balanced"`, which up-weights the 4.3% spike minority during training so the model still learns to detect them.

---

## Results

| Model | Val PR-AUC | Test PR-AUC | Val F1 (best) | Test F1 (best) |
|---|---|---|---|---|
| Z-score baseline (`z > 2.0` on `vol_60s`) | 0.3341 | 0.2611 | 0.4313 | 0.3567 |
| Logistic Regression (`C=0.1`, balanced) | 0.2523 | **0.4163** | 0.3534 | **0.4195** |

**Baseline parameters:** `zscore_threshold = 2.0`, feature = `vol_60s`, calibrated on train mean/std.  
**LR parameters:** `C = 0.1`, `solver = lbfgs`, `class_weight = balanced`, `tau = 0.6373` (auto-selected best-F1).

---

## Conclusion

The Logistic Regression model **outperforms the z-score baseline on unseen test data** (PR-AUC 0.4163 vs 0.2611), demonstrating that the learned combination of features performes better than using a single feature.  

However, both models face a genuine challenge. They were trained on a 4.3% spike rate and evaluated showcasing a 16–19% spike rate. Collecting data across multiple full days could help stabilize the training distribution and possibly improve both PR-AUC scores.
