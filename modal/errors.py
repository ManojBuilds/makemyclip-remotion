"""Custom exception hierarchy for MakeMyClip Modal services.

Distinguishing transient from permanent errors lets callers decide
whether to retry or surface the error immediately.
"""

from __future__ import annotations


class MakeMyClipError(Exception):
    """Base exception for all MakeMyClip backend errors."""


# --- Transient (retryable) errors ---

class TransientError(MakeMyClipError):
    """An error that may succeed on retry (network, rate-limit, etc.)."""


class DownloadError(TransientError):
    """Failed to download a remote resource."""


class UploadError(TransientError):
    """Failed to upload to cloud storage (R2 / S3)."""


class TranscriptionError(TransientError):
    """External transcription service returned a transient error."""


# --- Permanent (non-retryable) errors ---

class PermanentError(MakeMyClipError):
    """An error that will not succeed on retry."""


class InvalidInputError(PermanentError):
    """The request payload is invalid or missing required fields."""


class RenderError(PermanentError):
    """FFmpeg or the render pipeline failed due to bad input/state."""


class VideoProbeError(PermanentError):
    """Could not determine video metadata (resolution, fps, etc.)."""
