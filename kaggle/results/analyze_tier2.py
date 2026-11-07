import json
from pathlib import Path
import pandas as pd

base = Path(r"C:\Users\Leon\Documents\Github\finalproject_cpe027\kaggle\results")
df = pd.read_csv(base / "tier2_m3av_results.csv")
df["WER_pct"] = 100 * df["wer"]
df["CER_pct"] = 100 * df["cer"]

overall = (df.groupby("condition", dropna=False)
           .agg(n=("clip_id", "count"),
                clip_pct_of_total=("clip_id", lambda s: 100 * len(s) / len(df)),
                duration_s=("audio_duration_s", "mean"),
                wer_pct=("WER_pct", "mean"),
                cer_pct=("CER_pct", "mean"),
                term_presence=("term_presence_recall", "mean"),
                nshr=("nshr", "mean"),
                rtf=("rtf", "mean"),
                seconds=("seconds", "mean"))
           .round(3))

per_bucket = (df.groupby(["duration_bucket", "condition"], dropna=False)
              .agg(n=("clip_id", "count"),
                   duration_s=("audio_duration_s", "mean"),
                   wer_pct=("WER_pct", "mean"),
                   cer_pct=("CER_pct", "mean"),
                   nshr=("nshr", "mean"),
                   rtf=("rtf", "mean"),
                   seconds=("seconds", "mean"))
              .round(3))

relative = []
for bucket, sub in df.groupby("duration_bucket"):
    arm_a = sub.loc[sub["condition"] == "arm_a", "wer"].mean()
    for c, g in sub.groupby("condition"):
        rel = (g["wer"].mean() - arm_a) / arm_a * 100 if (arm_a is not None and arm_a > 0) else float("nan")
        relative.append({
            "duration_bucket": bucket,
            "condition": c,
            "n": len(g),
            "mean_wer_pct": round(100 * g["wer"].mean(), 2),
            "arm_a_wer_pct": round(100 * arm_a, 2),
            "rel_change_vs_arm_a_pct": round(rel, 2),
        })
relative_df = pd.DataFrame(relative).set_index(["duration_bucket", "condition"]).sort_index()

overall.reset_index().to_csv(base / "tier2_overall_by_condition.csv", index=False)
per_bucket.reset_index().to_csv(base / "tier2_wer_by_bucket.csv", index=False)
relative_df.reset_index().to_csv(base / "tier2_rel_wer_vs_arm_a.csv", index=False)

print("=== Overall (n and mean per condition, 300 clips / 6 conditions) ===")
print(overall.to_string())
print("\n=== Per bucket x condition (WER/CER) ===")
print(per_bucket[[ "n", "wer_pct", "cer_pct", "nshr", "rtf", "seconds"]].to_string())
print("\n=== Relative WER change vs arm_a by bucket (arm_a column = 0.0%) ===")
print(relative_df[[ "n", "mean_wer_pct", "arm_a_wer_pct", "rel_change_vs_arm_a_pct"]].to_string())

worst = (df.sort_values("wer", ascending=False)
        .groupby("condition", dropna=False)
        .head(2)[["clip_id", "condition", "audio_duration_s", "wer", "cer", "nshr"]])
best = (df.sort_values("wer", ascending=True)
        .groupby("condition", observed=False)
        .head(2)[["clip_id", "condition", "audio_duration_s", "wer", "cer", "nshr"]])
print("\n=== 2 worst transcripts per condition ===")
print(worst.round(3).to_string(index=False))
print("\n=== 2 best transcripts per condition ===")
print(best.round(3).to_string(index=False))
print("\nSaved: tier2_overall_by_condition.csv, tier2_wer_by_bucket.csv, tier2_rel_wer_vs_arm_a.csv")
