"""Pydantic models for Modal endpoint request/response payloads."""

from typing import List, Optional
from pydantic import BaseModel


class CaptionStyle(BaseModel):
    preset: Optional[str] = None
    font_family: Optional[str] = None
    font_size: Optional[float] = None
    font_color: Optional[str] = None
    highlight_color: Optional[str] = None
    stroke_color: Optional[str] = None
    stroke_width: Optional[float] = None
    background: Optional[bool] = None
    background_color: Optional[str] = None
    animation: Optional[str] = None
    shadow: Optional[bool] = None
    position_y: Optional[float] = None
    uppercase: Optional[bool] = None

    # Optional advanced fields
    speaker_colors: Optional[dict] = None
    letter_spacing: Optional[float] = None
    highlight_scale: Optional[float] = None
    power_color: Optional[str] = None
    max_words: Optional[int] = None
    shadow_depth: Optional[float] = None
    shadow_alpha: Optional[int] = None
    future_dim: Optional[bool] = None


class ReframeRequest(BaseModel):
    video_url: str
    start_time: float
    end_time: float
    fps: int = 25
    styling: Optional[CaptionStyle] = None
    transcript: Optional[List[dict]] = None
    show_watermark: bool = False
    crop_mode: str = "reframe"
    quality: str = "preview"  # "preview" (fast, 540p, smaller file) or "export" (full 1080p)
    analysis_url: Optional[str] = None


class BurnCaptionsRequest(BaseModel):
    video_url: str
    transcript: List[dict]
    styling: CaptionStyle
    show_watermark: bool = False
    crop_mode: Optional[str] = "reframe"
    quality: str = "export"  # "preview" (fast, 540p) or "export" (full 1080p)
    plan: str = "free"  # "free", "creator", or "power" — controls export resolution


class BatchClipItem(BaseModel):
    """A single clip within a batch reframe request."""
    clip_id: str
    start_time: float
    end_time: float
    crop_mode: str = "auto"
    transcript: Optional[List[dict]] = None
    styling: Optional[CaptionStyle] = None
    show_watermark: bool = False


class BatchReframeRequest(BaseModel):
    """Batch reframe request — processes all clips from a single source decode."""
    video_url: str
    clips: List[BatchClipItem]
    quality: str = "preview"
    analysis_url: Optional[str] = None


class TranscribeRequest(BaseModel):
    video_url: str
    transcribe_language: Optional[str] = "auto"
    translate_language: Optional[str] = "none"
    prompt: Optional[str] = None
    keyterms: Optional[List[str]] = None


class AnalyzeVideoRequest(BaseModel):
    video_url: str
    project_id: str
    duration: float
    detect_skip: int = 5
    chunk_duration: float = 600.0  # 10 minutes per chunk


class AnalyzeVideoResponse(BaseModel):
    success: bool
    project_id: str
    analysis_url: str
    total_frames: int
    num_tracks: int
    duration_secs: float
    error: Optional[str] = None


