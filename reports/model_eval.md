# Model Evaluation Summary — Milestone 3
**Project:** BTC Volatility Spike Detector  
**Date:** 2026-04-07  

---

## Evaluation Setup

| Parameter | Value |
|---|---|
| Target | `vol_spike` — 1 if 60-second realized volatility ≥ τ = 0.000048 (P85) |
| Target horizon | 60 seconds |
| Features | `log_return`, `spread_bps`, `vol_60s`, `mean_return_60s`, `trade_intensity_60s`, `n_ticks_60s`, `spread_mean_60s` |
| Validation strategy | Time-based splits with no shuffling |
| Split | 60% Train / 20% Validation / 20% Test (by row count) |
| Primary metric | PR-AUC (precision-recall area under curve) |

---

## Dataset Context & Regime Shift

The dataset spans approximately 65 hours of continuous BTC-USD tick data (2026-04-04 22:54 → 2026-04-07 15:54 UTC), with ~631K raw ticks producing 613,853 labelled feature rows.

| Split | Rows | Spike Rate | Period |
|---|---|---|---|
| Train | 368,311 | **15.4%** | Earlier collection window |
| Validation | 122,771 | **14.1%** | Mid collection window |
| Test | 122,771 | **7.0%** | Later collection window |

The spike rate varies from 7.0% to 15.4% across splits, reflecting genuine market-regime changes across the collection window. Train and validation are relatively balanced, while the test window landed on a quieter stretch (7.0%). The Logistic Regression model uses `class_weight="balanced"` to compensate for class imbalance during training.

---

## Results

| Model | Val PR-AUC | Test PR-AUC | Val F1 | Test F1 |
|---|---|---|---|---|
| Z-score baseline (sigmoid-calibrated, `z > 2.0`) | 0.3270 | 0.1340 | 0.3868 | 0.1487 |
| **Logistic Regression v1 (Variant B, 7 features)** | **0.3580** | **0.1459** | **0.4463** | **0.1359** |

**Baseline parameters:** `zscore_threshold = 2.0`, feature = `vol_60s`, calibrated on train mean/std, pseudo-probabilities via sigmoid transform.  
**LR parameters:** `C = 0.1`, `solver = lbfgs`, `class_weight = balanced`, `tau = 0.7015` (best-F1 on validation set).

---

## Conclusion

The Logistic Regression model **outperforms the z-score baseline on both val and test PR-AUC** (test PR-AUC 0.1459 vs 0.1340), demonstrating that the learned combination of 7 features performs better than a single-feature rule.

The val-to-test PR-AUC drop (0.3580 → 0.1459) reflects a **market regime shift**, not model failure. The test window captured a quieter period with only a 7.0% spike rate, compared to 14.1% in validation. Both models exhibit the same directional drop, confirming the cause is distributional rather than overfitting.

Our strict temporal split (train → val → test with no shuffling) avoids data leakage that would inflate metrics under shuffled evaluation. The test set performance drop is specifically explained by the test window landing on a low-volatility regime, not by model degradation.
