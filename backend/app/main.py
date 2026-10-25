from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.contracts import ErrorCode
from app.routers import lectures, storage

app = FastAPI(
    title="LectureFlow API",
    description="Backend API scaffold for the LectureFlow prototype.",
    version="0.1.0",
)


@app.get("/api/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "lectureflow-backend"}


app.include_router(lectures.router, prefix="/api")
app.include_router(storage.router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    messages = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error.get("loc", []))
        if location:
            messages.append(f"{location}: {error.get('msg', 'invalid value')}")
        else:
            messages.append(str(error.get("msg", "invalid request")))
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "error_code": ErrorCode.INVALID_REQUEST.value,
                "message": "; ".join(messages),
            }
        },
    )
