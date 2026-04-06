# Feature Specification — BTC Volatility Spike Detector

## Label

| Parameter         | Value                                                        |
|-------------------|--------------------------------------------------------------|
| Target horizon    | 60 seconds                                                   |
| Volatility proxy  | Rolling std of midprice log-returns over the next 60s        |
| Label definition  | `vol_spike = 1` if `σ_future >= τ`; else `0`                |
| Chosen threshold τ | **0.000046**                                                |
| Spike rate at τ   | ~10% of labelled ticks                                       |
| ≈ $1σ move @ $60k | $2.75                                                       |
| Percentile        | P90 — elbow of the σ_future distribution                     |

Threshold was chosen at P90 of the observed `future_vol_60s` distribution.
At this point the percentile curve visibly steepens, giving the visually most accurate
separation between baseline noise and genuine spike events. 

---

## Features

All features are computed per tick from a lookback window of `window_seconds = 60`.

| Feature               | Formula / description                                            | Unit            |
|-----------------------|------------------------------------------------------------------|-----------------|
| `price`               | Last traded price                                                | USD             |
| `midprice`            | `(best_bid + best_ask) / 2`                                      | USD             |
| `log_return`          | `ln(price_t / price_{t-1})`                                      | dimensionless   |
| `spread_abs`          | `best_ask − best_bid`                                            | USD             |
| `spread_bps`          | `spread_abs / midprice × 10,000`                                 | basis points    |
| `vol_60s`             | Std of log-returns over past 60s                                 | dimensionless   |
| `mean_return_60s`     | Mean log-return over past 60s                                    | dimensionless   |
| `n_ticks_60s`         | Count of ticks in the past 60s                                   | integer         |
| `trade_intensity_60s` | `n_ticks_60s / 60`  (ticks per second)                          | ticks/sec       |

---

## Parquet schema (`data/processed/features.parquet`)

| Column                | Type      | Description                              |
|-----------------------|-----------|------------------------------------------|
| `product_id`          | string    | e.g. `BTC-USD`                           |
| `timestamp`           | string    | ISO-8601 source timestamp                |
| `price`               | float64   |                                          |
| `midprice`            | float64   |                                          |
| `log_return`          | float64   |                                          |
| `spread_abs`          | float64   |                                          |
| `spread_bps`          | float64   |                                          |
| `vol_60s`             | float64   |                                          |
| `mean_return_60s`     | float64   |                                          |
| `n_ticks_60s`         | int64     |                                          |
| `trade_intensity_60s` | float64   |                                          |
| `future_vol_60s`      | float64   | σ over next 60s; NaN if horizon not closed |
| `vol_spike`           | int64     | 1 if `future_vol_60s >= 0.000046` else 0 |
