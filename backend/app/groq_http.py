"""Shared Groq HTTP helper: one retry policy for every Groq call.

Groq's free tier rate-limits aggressively and answers 429 with a ``Retry-After``
header. Both Groq callers (ASR and the LLM answer generator) go through
``post_with_retry`` so a rate limit is waited out instead of surfacing as a
failed job or a silently degraded answer.
"""

from __future__ import annotations

import logging
import random
import time

import httpx

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
BASE_BACKOFF = 2.0
MAX_BACKOFF = 60.0  # keep a rate-limited demo responsive rather than hanging


def _retry_after_seconds(response: httpx.Response, fallback: float) -> float:
    """Seconds to wait per the ``Retry-After`` header, else ``fallback``.

    Groq sends a numeric value, but it has been seen with a unit suffix
    ("7.66s"), which a bare float()/int() would choke on.
    """
    raw = response.headers.get("Retry-After", "").strip().rstrip("s")
    try:
        return min(max(float(raw), 0.0), MAX_BACKOFF)
    except ValueError:
        return fallback


def post_with_retry(
    url: str,
    *,
    headers: dict | None = None,
    json: dict | None = None,
    data: dict | None = None,
    files: dict | None = None,
    timeout: float = 60.0,
    max_retries: int = MAX_RETRIES,
) -> httpx.Response:
    """POST to Groq, retrying on 429, 5xx and network errors.

    Any ``files`` payload must hold bytes, not an open file object: a retry
    re-sends the same body and a consumed stream would upload empty.
    Raises the last error (``HTTPStatusError`` or ``RequestError``) if every
    attempt fails.
    """
    backoff = BASE_BACKOFF
    for attempt in range(1, max_retries + 1):
        last = attempt == max_retries
        try:
            response = httpx.post(
                url, headers=headers, json=json, data=data, files=files, timeout=timeout
            )
        except httpx.RequestError as exc:
            if last:
                raise
            logger.warning(
                "Groq request error %s: %s - retry %s/%s in %.1fs",
                type(exc).__name__, exc, attempt, max_retries, backoff,
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)
            continue

        if response.status_code == 429 or response.status_code >= 500:
            if last:
                response.raise_for_status()
                return response
            wait = _retry_after_seconds(response, backoff)
            # Jitter so concurrent jobs do not all come back in the same instant.
            wait += random.uniform(0, 0.5)
            logger.warning(
                "Groq %s - sleeping %.1fs (attempt %s/%s)",
                response.status_code, wait, attempt, max_retries,
            )
            time.sleep(wait)
            backoff = min(backoff * 2, MAX_BACKOFF)
            continue

        response.raise_for_status()
        return response

    raise AssertionError("unreachable")  # loop always returns or raises
