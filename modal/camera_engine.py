"""Camera Engine for AI Reframer.

Encapsulates camera movement calculations, including:
- CameraProfile presets (default, podcast, interview, presentation)
- Sigmoid adaptive easing with target velocity acceleration
- Audio-driven Zoom Punch state machine
- Ken Burns static scene slow zoom & lateral drift
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class CameraProfile:
    """Tunable camera behavior preset.

    Groups framing ratios, pan speeds, dead zones, and zoom parameters into a
    single swappable profile object.
    """

    # --- Framing ---
    face_crop_ratio: float = 0.106        # Face fills this fraction of 1920px height
    face_vertical_anchor: float = 0.22    # Face positioned at this % from top
    split_face_anchor: float = 0.38       # Face at this % from top in split panels

    # --- Pan speed ---
    pan_alpha_min: float = 0.05           # Minimum pan speed (sigmoid baseline)
    pan_alpha_max: float = 0.35           # Maximum pan speed at large distances
    pan_sigmoid_center: float = 150.0     # Distance (px) at sigmoid midpoint
    pan_sigmoid_steepness: float = 0.025  # Sigmoid steepness factor

    # --- Dead zones ---
    dead_zone_px: float = 40.0            # Pixel dead zone on X before pan starts
    dead_zone_y_px: float = 15.0          # Pixel dead zone on Y
    dead_zone_scale_pct: float = 0.10     # 10% dead zone on scale shifts

    # --- Speaker switching ---
    speaker_hold_s: float = 1.5           # Seconds to hold speaker after silence
    min_cut_s: float = 0.8               # Minimum time before speaker switch
    look_ahead_frames: int = 8            # Interjection filter look-ahead

    # --- Zoom punch ---
    zoom_punch_magnitude: float = 0.07    # Emphasis zoom intensity
    zoom_punch_spike_threshold: float = 1.8
    zoom_punch_cooldown: int = 20

    # --- Smoothing ---
    vertical_dampen: float = 0.5          # Dampen vertical pan by this factor
    scale_smooth_alpha: float = 0.15      # EMA alpha for scale changes
    split_smooth_alpha: float = 0.04      # Split-screen tracking alpha
    split_dead_zone: float = 25.0         # Split-screen dead zone (px)

    # --- Edge handling ---
    edge_widen_threshold: float = 0.25    # Distance from edge (fraction) to trigger widening
    edge_widen_factor: float = 0.88       # Widen crop by this factor near edges


CAMERA_PROFILES = {
    "default": CameraProfile(),
    "podcast": CameraProfile(
        pan_alpha_max=0.20,
        min_cut_s=1.2,
        dead_zone_px=50.0,
        zoom_punch_magnitude=0.05,
    ),
    "interview": CameraProfile(
        pan_alpha_max=0.40,
        face_crop_ratio=0.12,
        min_cut_s=0.6,
        zoom_punch_magnitude=0.08,
    ),
    "presentation": CameraProfile(
        pan_alpha_max=0.15,
        dead_zone_px=60.0,
        face_crop_ratio=0.09,
        zoom_punch_spike_threshold=2.0,
    ),
}


def calculate_adaptive_pan_alpha(
    current_cx: float,
    target_cx: float,
    prev_target_cx: float | None = None,
    profile: CameraProfile | None = None,
) -> float:
    """Calculate adaptive pan alpha using sigmoid easing + velocity acceleration.

    Returns alpha value in range [0.0, profile.pan_alpha_max + velocity_boost].
    """
    if profile is None:
        profile = CAMERA_PROFILES["default"]

    dist_x = abs(target_cx - current_cx)
    if dist_x < 15.0:
        return 0.0

    sigmoid_factor = 1.0 / (1.0 + math.exp(-profile.pan_sigmoid_steepness * (dist_x - profile.pan_sigmoid_center)))
    velocity = abs(target_cx - (prev_target_cx or target_cx)) if prev_target_cx is not None else 0.0
    velocity_boost = min(0.12, velocity / 500.0)

    adaptive_alpha = profile.pan_alpha_min + (profile.pan_alpha_max + velocity_boost) * sigmoid_factor
    return adaptive_alpha
