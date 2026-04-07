# Composite Model Strategy

## Base Pipeline
**rrpichardo's** end-to-end pipeline serves as the foundation:
- WebSocket ingestor → Kafka → Featurizer → Parquet sink
- Logistic Regression with `class_weight="balanced"`, temporal train/val/test split
- Threshold (tau) auto-selected on validation best-F1
- MLflow experiment tracking, Evidently drift reporting

## Team Member Contributions

| Member | Contribution | Integration |
|---|---|---|
| **rrpichardo** | Full pipeline (ingest → featurize → train → infer), 7-feature LR model (Variant B), Docker infrastructure, drift monitoring | Base — used as-is |
| **streakh** | `ob_imbalance` feature (order-book imbalance) | Experimental feature candidate |
| **Irene** | `spread_mean_60s` (rolling mean spread), `price_range_60s` (rolling price range), `ob_imbalance` | `spread_mean_60s` already in Variant B; `price_range_60s` tested in ablation Variant C |

## Feature Selection Strategy

The final feature set is determined by **validation PR-AUC ablation**, not by hand-picking.
Four variants were tested (see `reports/ablation_results.json`):

| Variant | Features | Rationale |
|---|---|---|
| A | 6 baseline features | Control |
| B | A + `spread_mean_60s` | Irene's liquidity signal |
| C | B + `price_range_60s` | Full candidate set (Irene) |
| D | C − `spread_abs` − `n_ticks_60s` | Drop correlated features |

**Winner: Variant B** (7 features) — selected by highest validation PR-AUC.
`ob_imbalance` (streakh/Irene) is available in the featurizer for future integration
but was not included in the current ablation because the Coinbase Advanced Trade
WebSocket does not provide order-book depth (bid_size/ask_size) in the ticker channel.

## Composite Summary

> Selected-composite base: rrpichardo's pipeline and LR model, extended with
> `ob_imbalance` (streakh/Irene), `spread_mean` (Irene), and `price_range` (Irene)
> as experimental features, with the final feature set determined by validation
> PR-AUC ablation.
