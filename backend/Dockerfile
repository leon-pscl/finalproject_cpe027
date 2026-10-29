FROM python:3.12-slim

# Add a longer pip timeout to avoid large wheel failures
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=300

WORKDIR /app

RUN mkdir -p /models

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt --verbose

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
