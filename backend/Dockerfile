# Multi-stage Dockerfile for the backend service
# --------------------------------------------
# Builder stage – installs compilers and all Python dependencies (including dev packages when needed)
FROM python:3.12-slim AS builder

# Ensure deterministic builds and longer pip timeout for large wheels
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=300

WORKDIR /app

# Install system packages required for building wheels and runtime ffmpeg.
# BuildKit caches apt downloads so rebuilds are fast; keeping build tools only in this stage.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ build-essential ffmpeg

# Install runtime Python dependencies. Torch comes first, from the CPU-only index: the
# PyPI wheel is the CUDA build (~2.5GB with its nvidia deps) and nothing here needs a GPU.
# Installing it after requirements.txt is a no-op, as sentence-transformers already pulled it in.
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --prefer-binary --index-url https://download.pytorch.org/whl/cpu "torch>=2.0,<3" \
    && pip install --prefer-binary -r requirements.txt

# --------------------------------------------
# Runtime stage – contains only the runtime dependencies (no compilers)
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Copy the installed site-packages and binaries from the builder stage
COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin

# Install only the ffmpeg runtime (no compilers) – keep the image lean
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends ffmpeg

# Copy application code (the code does not need to be re-installed)
COPY app ./app
COPY dsp.py ./dsp.py

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=6 --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# --------------------------------------------
# Test stage – builds on the builder image and adds dev-only dependencies and tests
FROM builder AS test

# Install development-only Python packages (pytest, ruff, etc.)
COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

# Copy application code and test suite
COPY app ./app
COPY dsp.py ./dsp.py
COPY tests ./tests

# Default command runs the test suite; can be overridden in Docker-Compose
CMD ["pytest"]