from pathlib import Path
p = Path("app/worker.py")
for i, line in enumerate(p.read_text().splitlines(), 1):
    if any(token in line for token in ("job.dsp", "_save_artifact", "update_job_state", "timings[")):
        print(i, line)