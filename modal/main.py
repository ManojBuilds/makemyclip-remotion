"""Modal deploy entrypoint for makemyclip-ai-rendering.

This file used to contain ~1300 lines of Modal app + image config + Pydantic
models + caption rendering + face tracking + reframer + transcriber all
mixed together. It has been refactored into focused modules:

  config.py          – Modal app + image + shared secrets
  models.py          – Pydantic request/response schemas
  colors.py          – ASS subtitle color helpers
  fonts.py           – font-name resolution map
  presets.py         – caption preset normalization + per-preset base styles
  ass_builder.py     – ASS subtitle file generator
  r2_storage.py      – Cloudflare R2 upload helper (shared)
  ytdlp_helper.py    – YouTube downloader with multi-strategy fallback (shared)
  burner.py          – CaptionBurner Modal class
  reframer.py        – AIReframe Modal class (face tracking + ASD + render)
  transcriber.py     – AudioTranscriber Modal class

Deployment:
    modal deploy main.py

The endpoints exposed are unchanged:
    POST  /reframe    → AIReframe.reframe        (MODAL_REFRAME_ENDPOINT)
    POST  /endpoint   → CaptionBurner.endpoint   (MODAL_BURNER_ENDPOINT)
    POST  /transcribe → AudioTranscriber.transcribe (MODAL_TRANSCRIBE_ENDPOINT)
"""

from config import app  # noqa: F401  – Modal CLI discovers the app via this import

# Importing each service module registers its Modal class with the shared `app`.
# `noqa: F401` keeps the linter quiet about "unused" imports.
from burner import CaptionBurner  # noqa: F401
from reframer import AIReframe  # noqa: F401
from transcriber import AudioTranscriber  # noqa: F401
