import json
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

base = Path(r"C:\Users\Leon\Documents\Github\finalproject_cpe027\kaggle\results")
df = pd.read_csv(base / "tier2_m3av_results.csv")

# Figure 1 - mean WER by condition
means = df.groupby("condition", sort=True)["wer"].mean().sort_index()
fig, ax = plt.subplots(figsize=(9, 5))
ax.bar(means.index, 100 * means.values, color="#4c78a8")
ax.set_title("Tier 2 mean WER by DSP condition (300 clips)")
ax.set_ylabel("WER (%)")
ax.set_xticks(range(len(means.index)))
ax.set_xticklabels(means.index, rotation=30, ha="right")
fig.tight_layout()
fig.savefig(base / "tier2_wer_by_condition.png", dpi=150)
plt.close(fig)

# Figure 2 - WER by condition x bucket
bucket_means = df.groupby(["duration_bucket", "condition"], sort=True)["wer"].mean().unstack("condition")
fig, ax = plt.subplots(figsize=(9, 5))
bucket_means.plot.bar(ax=ax)
ax.set_title("Tier 2 WER by duration bucket and condition")
ax.set_ylabel("WER (%)")
fig.tight_layout()
fig.savefig(base / "tier2_wer_by_bucket.png", dpi=150)
plt.close(fig)

# Figure 3 - relative gain vs arm_a
fig, ax = plt.subplots(figsize=(10, 5))
for bucket, sub in df.groupby("duration_bucket"):
    arm_a = sub.loc[sub.condition == "arm_a", "wer"].mean()
    gain = (sub.groupby("condition", sort=True)["wer"].mean() - arm_a) / arm_a * 100.0
    ax.plot(gain.index, gain.values, marker="o", label=bucket)
ax.axhline(0, color="k", linewidth=0.8, linestyle="--")
ax.set_title("Relative WER gain vs arm_a by duration bucket")
ax.set_ylabel("Relative WER change (%)")
ax.set_xticks(range(len(gain.index)))
ax.set_xticklabels(gain.index, rotation=30, ha="right")
ax.legend(title="Bucket")
fig.tight_layout()
fig.savefig(base / "tier2_rel_wer_vs_arm_a.png", dpi=150)
plt.close(fig)

print("Wrote figures:", base / "tier2_wer_by_condition.png", base / "tier2_wer_by_bucket.png", base / "tier2_rel_wer_vs_arm_a.png")
