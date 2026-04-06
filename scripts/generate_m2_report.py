"""
Milestone 2 — Evidently report: early vs late window.

Loads data/processed/features.parquet, splits chronologically in half,
and runs DataDriftPreset + DataQualityPreset comparing the early window
(reference) against the late window (current).

Output: reports/evidently/early_vs_late.html
"""

import pandas as pd
from pathlib import Path
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset, DataQualityPreset

# ── Load ──────────────────────────────────────────────────────────────────────
df = pd.read_parquet("data/processed/features.parquet")
df = df.sort_values("timestamp").reset_index(drop=True)

# ── Split exactly in half ─────────────────────────────────────────────────────
mid = len(df) // 2
# Sample up to 5 000 rows per half — Evidently is slow on >50k rows
reference = df.iloc[:mid].sample(n=min(5000, mid), random_state=42).copy()
current   = df.iloc[mid:].sample(n=min(5000, len(df) - mid), random_state=42).copy()

print(f"Total rows     : {len(df):,}")
print(f"Reference (early): rows={len(reference):,}  "
      f"{reference['timestamp'].iloc[0][:19]} → {reference['timestamp'].iloc[-1][:19]}")
print(f"Current   (late) : rows={len(current):,}  "
      f"{current['timestamp'].iloc[0][:19]} → {current['timestamp'].iloc[-1][:19]}")
print(f"Spike rate — early: {reference['vol_spike'].mean()*100:.1f}%  "
      f"late: {current['vol_spike'].mean()*100:.1f}%")

# ── Run report ────────────────────────────────────────────────────────────────
report = Report(metrics=[
    DataQualityPreset(),
    DataDriftPreset(),
])
report.run(reference_data=reference, current_data=current)

# ── Save ──────────────────────────────────────────────────────────────────────
out = Path("reports/evidently/early_vs_late.html")
out.parent.mkdir(parents=True, exist_ok=True)
report.save_html(str(out))
print(f"\nSaved → {out.resolve()}")
