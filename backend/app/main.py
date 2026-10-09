from fastapi import FastAPI

app = FastAPI(
    title="LectureFlow API",
    description="Backend API scaffold for the LectureFlow prototype.",
    version="0.1.0",
)


@app.get("/api/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "lectureflow-backend"}
