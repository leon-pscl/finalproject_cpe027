from pathlib import Path

p = Path("app/repositories.py")
s = p.read_text()

old = """def _ensure_job_row(
    owner_id: str,
    lecture_id: str,
    job_id: str,
    processing_version: str,
    stage: JobStage = JobStage.QUEUED,
    state: str = "queued",
    attempts: int = 0,
    lease_until: datetime | None = None,
    worker_id: str | None = None,
    safe_error_code: ErrorCode | None = None,
    timings: dict[str, Any] | None = None,
) -> dict[str, Any]:
"""
new = """def _ensure_job_row(
    owner_id: str,
    lecture_id: str,
    job_id: str,
    processing_version: str,
    stage: JobStage = JobStage.QUEUED,
    state: str = "queued",
    attempts: int = 0,
    lease_until: datetime | None = None,
    worker_id: str | None = None,
    safe_error_code: ErrorCode | None = None,
    timings: dict[str, Any] | None = None,
    processing_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
"""
assert old in s
s = s.replace(old, new, 1)

old2 = '''        "timings": timings or {},
        "created_at": timestamp,
'''
new2 = '''        "timings": timings or {},
        "processing_options": processing_options,
        "created_at": timestamp,
'''
assert old2 in s
s = s.replace(old2, new2, 1)

# In-memory create_job signature.
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
        with self._lock:
            existing = self._jobs.get(job_id)
            if existing is not None:
                if (
                    existing.get("owner_id") != owner_id
                    or existing.get("lecture_id") != lecture_id
                ):
                    raise ValueError("Job is not accessible")
                return _job_from_dict(job_id, data["lecture_id"], existing)
'''
# There are two create_job blocks (abstract and in-memory); replacement should only apply if unique.
count = s.count(old3)
assert count == 1, count
s = s.replace(old3, '''    def create_job(
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
        with self._lock:
            existing = self._jobs.get(job_id)
            if existing is not None:
                if (
                    existing.get("owner_id") != owner_id
                    or existing.get("lecture_id") != lecture_id
                ):
                    raise ValueError("Job is not accessible")
                return _job_from_dict(job_id, data["lecture_id"], existing)
''', 1)

old4 = '''            data = _ensure_job_row(
                owner_id,
                lecture_id,
                job_id,
                processing_version,
                stage,
                state,
                attempts,
                lease_until,
                worker_id,
                safe_error_code,
                timings,
            )
'''
count4 = s.count(old4)
assert count4 == 1, count4
s = s.replace(old4, '''            data = _ensure_job_row(
                owner_id,
                lecture_id,
                job_id,
                processing_version,
                stage,
                state,
                attempts,
                lease_until,
                worker_id,
                safe_error_code,
                timings,
                processing_options,
            )
''', 1)

p.write_text(s)
print("patched repository", flush=True)