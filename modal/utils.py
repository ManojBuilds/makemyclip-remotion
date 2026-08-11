"""Shared utilities for Modal services.

Small helpers used across multiple services that don't belong in any
single domain module.
"""

from __future__ import annotations

import functools
import logging
import time
from typing import TypeVar

logger = logging.getLogger("makemyclip")

T = TypeVar("T")


def normalize_url(url: str | None) -> str:
    """Ensure ``url`` has an http:// or https:// scheme if missing."""
    if not url or not isinstance(url, str):
        return ""
    u = url.strip()
    if u and not u.startswith(("http://", "https://")):
        return f"https://{u}"
    return u


def is_youtube_url(url: str) -> bool:
    """Return True if ``url`` points to a YouTube video."""
    normalized = normalize_url(url)
    return "youtube.com" in normalized or "youtu.be" in normalized


def validate_url(url: str, *, label: str = "url") -> str:
    """Validate and return normalized URL (starting with http:// or https://).

    Catches the most common misconfigurations *before* expensive GPU work
    begins — a malformed URL would otherwise only surface after downloading
    frames, running face detection, etc.
    """
    if not url or not isinstance(url, str):
        raise ValueError(f"{label} must be a non-empty string")
    normalized = normalize_url(url)
    if not normalized.startswith(("http://", "https://")):
        raise ValueError(
            f"{label} must start with http:// or https://, got: {url[:80]!r}"
        )
    return normalized


def retry(
    max_attempts: int = 3,
    backoff_base: float = 1.0,
    retryable: tuple[type[Exception], ...] = (Exception,),
):
    """Decorator: retry a function with exponential backoff.

    Only retries exceptions whose type is in ``retryable``.
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except retryable as exc:
                    last_exc = exc
                    if attempt < max_attempts:
                        wait = backoff_base * (2 ** (attempt - 1))
                        logger.warning(
                            "[retry] %s attempt %d/%d failed: %s — retrying in %.1fs",
                            fn.__name__,
                            attempt,
                            max_attempts,
                            exc,
                            wait,
                        )
                        time.sleep(wait)
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


class StageTimer:
    """Lightweight context manager for timing pipeline stages.

    Usage::

        with StageTimer("face_detection") as t:
            detect_faces(...)
        # logs: [timer] face_detection completed in 4.2s
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.elapsed: float = 0.0

    def __enter__(self) -> "StageTimer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_exc) -> None:
        self.elapsed = time.perf_counter() - self._start
        logger.info(
            "[timer] %s completed in %.1fs", self.name, self.elapsed
        )
