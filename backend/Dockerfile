# Multi‑stage Dockerfile for the backend service
# --------------------------------------------
# Builder stage – installs compilers and all Python dependencies (including dev packages when needed)
FROM python:3.12-slim AS builder

# Ensure deterministic builds and longer pip timeout for large wheels
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=300

WORKDIR /app

# Install system packages required for building wheels and runtime ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ build-essential ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Install runtime Python dependencies. Torch comes first, from the CPU-only index: the
# PyPI wheel is the CUDA build (~2.5GB with its nvidia deps) and nothing here needs a GPU.
# Installing it after requirements.txt is a no-op, as sentence-transformers already pulled it in.
COPY requirements.txt ./
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.0,<3" \
    && pip install -r requirements.txt

# --------------------------------------------
# Runtime stage – contains only the runtime dependencies (no compilers)
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy the installed site‑packages and binaries from the builder stage
COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin

# Install only the ffmpeg runtime (no compilers) – keep the image lean
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Copy application code (the code does not need to be re‑installed)
COPY app ./app
COPY dsp.py ./dsp.py

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# --------------------------------------------
# Test stage – builds on the builder image and adds dev‑only dependencies and tests
FROM builder AS test

# Install development‑only Python packages (pytest, ruff, etc.)
COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

# Copy test suite
COPY tests ./tests

# Default command runs the test suite; can be overridden in Docker‑Compose
CMD ["pytest"]
