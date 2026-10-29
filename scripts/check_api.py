#!/usr/bin/env python3
"""Simple API endpoint smoke test for LectureFlow backend.

Run ``python -m scripts.check_api`` after starting the backend (e.g. via
``docker compose up backend``). The script performs a minimal health check and
demonstrates a basic upload‑initiation flow using the in‑memory repository.
"""

import os
import json
import sys
from urllib.parse import urljoin

import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
HEADERS = {"Authorization": "Bearer dummy-token"}

def simple_get(path: str):
    url = urljoin(BASE_URL, path)
    try:
        r = requests.get(url, headers=HEADERS, timeout=5)
        print(f"GET {path}: {r.status_code}")
        print(r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)
    except Exception as e:
        print(f"GET {path} failed: {e}")

def simple_post(path: str, json_body: dict):
    url = urljoin(BASE_URL, path)
    try:
        r = requests.post(url, headers={**HEADERS, "Content-Type": "application/json"}, json=json_body, timeout=5)
        print(f"POST {path}: {r.status_code}")
        print(r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)
        return r
    except Exception as e:
        print(f"POST {path} failed: {e}")
        return None

def main():
    # 1. Health check
    simple_get("/api/health")

    # 2. Initiate a lecture upload (requires a JSON payload)
    payload = {
        "title": "Demo Lecture",
        "declared_type": "audio/wav",
        "declared_size_bytes": 12345,
    }
    resp = simple_post("/api/lectures/uploads", payload)
    if not resp or resp.status_code != 200:
        print("Upload initiation failed – aborting further checks.")
        sys.exit(1)

    data = resp.json()
    lecture_id = data.get("lecture_id")
    signed_upload_url = data.get("signed_upload_url")
    if not lecture_id or not signed_upload_url:
        print("Unexpected response from upload initiation.")
        sys.exit(1)

    # 3. Perform a signed upload (PUT) with a tiny payload
    upload_url = urljoin(BASE_URL, signed_upload_url)
    try:
        r = requests.put(upload_url, data=b"demo", headers={"Content-Type": "audio/wav"}, timeout=5)
        print(f"PUT {signed_upload_url}: {r.status_code}")
        print(r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)
    except Exception as e:
        print(f"PUT {signed_upload_url} failed: {e}")
        sys.exit(1)

    # 4. Mark the upload complete
    complete_payload = {"storage_path": data.get("storage_path")}
    simple_post(f"/api/lectures/{lecture_id}/upload-complete", complete_payload)

    # 5. Retrieve lecture metadata
    simple_get(f"/api/lectures/{lecture_id}")

if __name__ == "__main__":
    main()
