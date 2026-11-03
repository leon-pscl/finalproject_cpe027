from pathlib import Path

p = Path("app/repositories.py")
s = p.read_text()

# Abstract signature.
old = '''    def create_job(
        self,
        owner_id: str,
        lecture_id: str,
        job_id: str,
        processing_version: str,
        *,
        stage: JobStage = JobStage.QUEUED,
        state: str = "queued",
        attempts: int = 0,
        lease_until: datetime | None = None,
        worker_id: str | None = None,
        safe_error_code: ErrorCode | None = None,
        timings: dict[str, Any] | None = None,
    ) -> JobDocument:
        raise NotImplementedError
'''
new = '''    def create_job(
        self,
        owner_id: str,
        lecture_id: str,
        job_id: str,
        processing_version: str,
        *,
        stage: JobStage = JobStage.QUEUED,
        state: str = "queued",
        attempts: int = 0,
        lease_until: datetime | None = None,
        worker_id: str | None = None,
        safe_error_code: ErrorCode | None = None,
        timings: dict[str, Any] | None = None,
        processing_options: dict[str, Any] | None = None,
    ) -> JobDocument:
        raise NotImplementedError
'''
assert old in s
s = s.replace(old, new, 1)

# _job_from_dict
old2 = '''        timings=data.get("timings", {}),
    )
'''
new2 = '''        timings=data.get("timings", {}),
        processing_options=data.get("processing_options"),
    )
'''
assert old2 in s
s = s.replace(old2, new2, 1)

# Abstract row base _ensure_job signature
old3 = '''    def create_job(
        self,
        owner_id: str,
        lecture_id: str,
        job_id: str,
        processing_version: str,
        *,
        stage: JobStage = JobStage.QUEUED,
        state: str = "queued",
        attempts: int = 0,
        lease_until: datetime | None = None,
        worker_id: str | None = None,
        safe_error_code: ErrorCode | None = None,
        timings: dict[str, Any] | None = None,
    ) -> JobDocument:
'''
# this marker occurs abstract and maybe only one; work around by replacing impl block instead.
p.write_text(s)
print("partial")