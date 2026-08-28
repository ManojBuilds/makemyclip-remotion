"""Render Strategies for AI Reframer.

Modularized rendering logic for various video formats:
- ReframeStrategy: Single speaker face-locking pan and adaptive zoom.
- SplitStrategy: 2-speaker split-screen with active speaker highlight / listener dimming.
- LetterboxStrategy: Blurred background letterbox card with central framing.
- ScreencastStrategy: Saliency / edge centroid smart zoom letterbox with blurred background.
- PresentationStrategy: Slide as main content + speaker face picture-in-picture (PiP) overlay.
- PanelStrategy: Multi-speaker 2x2 grid layout with active speaker highlight.
- PassthroughStrategy: Vertical native (9:16) video pass-through with scale/pad to 1080x1920.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import math
from typing import Any, Dict, List, Optional, Tuple

try:
    import cv2
except ImportError:
    cv2 = None
import numpy as np

from camera_engine import CAMERA_PROFILES, CameraProfile, calculate_adaptive_pan_alpha
from video_utils import make_blurred_bg


class RenderStrategy(ABC):
    """Abstract base class for vertical render strategies."""

    def __init__(self, target_w: int = 1080, target_h: int = 1920):
        self.target_w = target_w
        self.target_h = target_h

    @abstractmethod
    def render_frame(
        self,
        img: np.ndarray,
        fidx: int,
        faces_fidx: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> np.ndarray:
        """Render a single video frame to (target_h, target_w, 3)."""
        pass


class ReframeStrategy(RenderStrategy):
    """Single speaker dynamic face-locking and camera easing."""

    def render_frame(
        self,
        img: np.ndarray,
        fidx: int,
        faces_fidx: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> np.ndarray:
        scale = self.target_h / img.shape[0]
        virtual_w = img.shape[1] * scale
        virtual_h = img.shape[0] * scale

        target_cx = state.get("target_cx")
        current_cx = state.get("current_cx")
        current_target_cx = state.get("current_target_cx")
        current_cy = state.get("current_cy_reframe")
        current_target_cy = state.get("current_target_cy_reframe")
        prev_target_cx = state.get("prev_target_cx")
        scene_median_s = state.get("scene_median_s")
        held_speaker_y = state.get("held_speaker_y")
        held_speaker_s = state.get("held_speaker_s")
        is_scene_start = fidx in state.get("scene_starts", set())
        speaker_switched = state.get("speaker_switched", False)

        if target_cx is None and current_cx is None:
            # Fallback center crop
            res = cv2.resize(img, None, fx=scale, fy=scale)
            tx = max(min(res.shape[1] // 2 - self.target_w // 2, res.shape[1] - self.target_w), 0)
            return res[0:self.target_h, tx : tx + self.target_w]

        if target_cx is None:
            target_cx = current_cx
            target_cy = current_cy if current_cy is not None else virtual_h / 2.0
            target_s = scene_median_s if scene_median_s is not None else virtual_w * 0.08
        else:
            target_cy = (held_speaker_y * scale) if held_speaker_y is not None else virtual_h / 2.0
            target_s = scene_median_s if scene_median_s is not None else ((held_speaker_s or 50.0) * scale)

        if current_cx is None or is_scene_start or current_target_cx is None:
            current_cx = float(target_cx)
            current_target_cx = float(target_cx)
            current_cy = float(target_cy)
            current_target_cy = float(target_cy)
        elif speaker_switched:
            current_target_cx = float(target_cx)
            current_target_cy = float(target_cy)

        # Dead zones
        DEAD_ZONE_PX = 15.0
        if target_cx - current_target_cx > DEAD_ZONE_PX:
            current_target_cx = float(target_cx - DEAD_ZONE_PX)
        elif current_target_cx - target_cx > DEAD_ZONE_PX:
            current_target_cx = float(target_cx + DEAD_ZONE_PX)

        DEAD_ZONE_Y = 15.0
        if abs(target_cy - current_target_cy) > DEAD_ZONE_Y:
            current_target_cy = float(target_cy)

        # Adaptive pan easing
        dist_x = abs(current_target_cx - current_cx)
        if dist_x < 15.0:
            adaptive_alpha = 0.0
        else:
            sigmoid_factor = 1.0 / (1.0 + math.exp(-0.025 * (dist_x - 150.0)))
            velocity = abs(current_target_cx - (prev_target_cx or current_target_cx)) if prev_target_cx is not None else 0.0
            velocity_boost = min(0.12, velocity / 500.0)
            adaptive_alpha = 0.05 + (0.35 + velocity_boost) * sigmoid_factor

        if adaptive_alpha > 0.0:
            current_cx += (current_target_cx - current_cx) * adaptive_alpha
            current_cy += (current_target_cy - current_cy) * (adaptive_alpha * 0.5)

        # Framing calculations: Keep the full vertical shot with head and body intact
        # Standard 16:9 to 9:16 reframe uses full vertical height (1.0x to 1.12x subtle framing)
        zoom = 1.05
        img_h, img_w = img.shape[:2]
        crop_h = float(img_h) / zoom
        crop_w = crop_h * (float(self.target_w) / float(self.target_h))

        # Ensure crop fits within source image
        crop_h = min(crop_h, float(img_h))
        crop_w = min(crop_w, float(img_w))

        # Convert virtual center X back to source pixel coordinates
        src_cx = current_cx / scale
        src_cy = current_cy / scale if current_cy is not None else img_h * 0.35

        # Center horizontally on active speaker with bounds clamping
        x1 = max(0.0, min(src_cx - crop_w / 2.0, float(img_w) - crop_w))

        # Vertically align: anchor with 15% headroom above face center, clamp to [0, img_h - crop_h]
        y1 = max(0.0, min(src_cy - crop_h * 0.28, float(img_h) - crop_h))

        crop = img[int(y1) : int(y1 + crop_h), int(x1) : int(x1 + crop_w)]
        if crop.shape[0] > 0 and crop.shape[1] > 0:
            res = cv2.resize(crop, (self.target_w, self.target_h), interpolation=cv2.INTER_AREA)
        else:
            res = cv2.resize(img, None, fx=scale, fy=scale)
            tx = max(min(res.shape[1] // 2 - self.target_w // 2, res.shape[1] - self.target_w), 0)
            res = res[0:self.target_h, tx : tx + self.target_w]

        # Update state references
        state["current_cx"] = current_cx
        state["current_target_cx"] = current_target_cx
        state["current_cy_reframe"] = current_cy
        state["current_target_cy_reframe"] = current_target_cy
        state["prev_target_cx"] = float(target_cx)

        return res


class SplitStrategy(RenderStrategy):
    """Dynamic 2-speaker split-screen layout with active speaker highlight."""

    def render_frame(
        self,
        img: np.ndarray,
        fidx: int,
        faces_fidx: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> np.ndarray:
        scale = self.target_h / img.shape[0]
        face_top = None
        face_bottom = None

        if faces_fidx:
            if len(faces_fidx) >= 2:
                sorted_lr = sorted(faces_fidx, key=lambda f: f.get("x", 0))
                face_top = sorted_lr[0]
                face_bottom = sorted_lr[-1]
            elif len(faces_fidx) == 1:
                single_face = faces_fidx[0]
                mid_x = (img.shape[1] * scale) / 2.0
                if single_face.get("x", 0) < mid_x:
                    face_top = single_face
                else:
                    face_bottom = single_face

        if face_top and face_bottom and abs(face_top.get("x", 0) - face_bottom.get("x", 0)) < 100.0:
            face_bottom = None

        # Safety Fallback: If only 1 person exists and no 2nd person track has ever been established
        if (face_top is None or face_bottom is None) and (state.get("split_cx_top") is None or state.get("split_cx_bottom") is None):
            reframe_strat = ReframeStrategy(self.target_w, self.target_h)
            return reframe_strat.render_frame(img, fidx, faces_fidx, state)

        # Tracking state
        SPLIT_DEAD_ZONE = 25.0
        SPLIT_ALPHA = 0.04

        for is_top, f_obj in [(True, face_top), (False, face_bottom)]:
            p_prefix = "top" if is_top else "bottom"
            cx_key, cy_key, s_key = f"split_cx_{p_prefix}", f"split_cy_{p_prefix}", f"split_s_{p_prefix}"
            tcx_key, tcy_key, ts_key = f"split_target_cx_{p_prefix}", f"split_target_cy_{p_prefix}", f"split_target_s_{p_prefix}"

            if f_obj is not None:
                fx, fy, fs = float(f_obj.get("x", 0)), float(f_obj.get("y", 0)), float(f_obj.get("s", 50))
                if state.get(cx_key) is None:
                    state[cx_key] = state[tcx_key] = fx
                    state[cy_key] = state[tcy_key] = fy
                    state[s_key] = state[ts_key] = fs
                else:
                    if abs(fx - state[tcx_key]) > SPLIT_DEAD_ZONE:
                        state[tcx_key] = fx
                    if abs(fy - state[tcy_key]) > SPLIT_DEAD_ZONE:
                        state[tcy_key] = fy
                    if abs(fs - state[ts_key]) > (state[ts_key] * 0.10):
                        state[ts_key] = fs

                    state[cx_key] += (state[tcx_key] - state[cx_key]) * SPLIT_ALPHA
                    state[cy_key] += (state[tcy_key] - state[cy_key]) * SPLIT_ALPHA
                    state[s_key] += (state[ts_key] - state[s_key]) * SPLIT_ALPHA

        final_frame = np.zeros((self.target_h, self.target_w, 3), dtype=np.uint8)
        score_top = face_top.get("score", 0.0) if face_top else 0.0
        score_bottom = face_bottom.get("score", 0.0) if face_bottom else 0.0
        active_th = 0.5

        for is_top, y_start in [(True, 0), (False, 960)]:
            p_prefix = "top" if is_top else "bottom"
            cx = state.get(f"split_cx_{p_prefix}")
            cy = state.get(f"split_cy_{p_prefix}")

            if is_top:
                is_active = (score_top > active_th and score_top >= score_bottom)
            else:
                is_active = (score_bottom > active_th and score_bottom > score_top)

            sub_h, sub_w = img.shape[:2]
            if cx is None:
                cx_rel = sub_w * 0.28 if is_top else sub_w * 0.72
                cy_rel = sub_h * 0.25
            else:
                cx_rel = max(0.0, min(float(cx), float(sub_w)))
                cy_rel = max(0.0, min(float(cy) if cy is not None else sub_h * 0.25, float(sub_h)))

            crop_w = float(sub_w) * 0.44
            crop_h = crop_w / 1.125
            crop_w = min(crop_w, float(sub_w))
            crop_h = min(crop_h, float(sub_h))

            x1 = max(0.0, min(cx_rel - crop_w / 2.0, sub_w - crop_w))
            y1 = max(0.0, min(cy_rel - crop_h * 0.22, sub_h - crop_h))

            crop = img[int(y1) : int(y1 + crop_h), int(x1) : int(x1 + crop_w)]
            if crop.shape[0] > 0 and crop.shape[1] > 0:
                resized = cv2.resize(crop, (1080, 960), interpolation=cv2.INTER_AREA)
                if not is_active and (score_top > active_th or score_bottom > active_th):
                    resized = cv2.convertScaleAbs(resized, alpha=0.88, beta=0)
                final_frame[y_start : y_start + 960, 0:1080] = resized

        final_frame[958:962, :] = (40, 40, 40)
        return final_frame


class LetterboxStrategy(RenderStrategy):
    """Blurred background letterbox card."""

    def render_frame(
        self,
        img: np.ndarray,
        fidx: int,
        faces_fidx: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> np.ndarray:
        bg = make_blurred_bg(img, target_w=self.target_w, target_h=self.target_h)
        CARD_W = self.target_w
        CARD_H = int(self.target_h * 0.68)
        scale = (CARD_H * 1.10) / img.shape[0]

        scaled_h = int(CARD_H * 1.10)
        scaled_w = int(img.shape[1] * scale)
        res_scaled = cv2.resize(img, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)

        target_cx = state.get("target_cx")
        if target_cx is None:
            target_cx = int((img.shape[1] * scale) / 2)

        cx_card = (target_cx / (img.shape[1] * (self.target_h / img.shape[0]))) * scaled_w if img.shape[1] > 0 else scaled_w // 2
        tx = max(min(int(cx_card) - CARD_W // 2, scaled_w - CARD_W), 0)
        res = res_scaled[0:CARD_H, tx : tx + CARD_W]

        start_y = 310
        bg[start_y : start_y + res.shape[0], 0 : res.shape[1]] = res
        return bg


class ScreencastStrategy(RenderStrategy):
    """Smart Zoom Letterbox with Active Mouse Cursor & Saliency Tracking."""

    def render_frame(
        self,
        img: np.ndarray,
        fidx: int,
        faces_fidx: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> np.ndarray:
        bg = make_blurred_bg(img, target_w=self.target_w, target_h=self.target_h)
        CARD_W = self.target_w
        CARD_H = int(self.target_h * 0.70)
        img_h, img_w = img.shape[:2]

        small_w, small_h = 320, 180
        gray_small = cv2.cvtColor(cv2.resize(img, (small_w, small_h)), cv2.COLOR_BGR2GRAY)

        # 1. Detect Intentional Highlight Actions (Cursor Motion / Active Typing)
        prev_gray = state.get("screencast_prev_gray")
        has_highlight_action = False
        action_x_pct = 0.5
        action_y_pct = 0.4

        if prev_gray is not None and prev_gray.shape == gray_small.shape:
            try:
                frame_diff = cv2.absdiff(gray_small, prev_gray)
                _, thresh = cv2.threshold(frame_diff, 25, 255, cv2.THRESH_BINARY)
                motion_pixels = cv2.countNonZero(thresh)

                # Intentional action signature (mouse pointing / code typing)
                if 15 < motion_pixels < 3500:
                    moments = cv2.moments(thresh)
                    if moments["m00"] > 0:
                        action_x_pct = float(moments["m10"] / moments["m00"]) / float(small_w)
                        action_y_pct = float(moments["m01"] / moments["m00"]) / float(small_h)
                        has_highlight_action = True
            except Exception:
                has_highlight_action = False

        state["screencast_prev_gray"] = gray_small

        # 2. Editor Highlight Zoom Controller (Lock & Snappy Punch-In Zoom)
        # Base state: 1.0x (Rock-solid stationary overview)
        # Highlight state: 1.35x (Snappy punch-in directly on highlighted code)
        zoom_hold_timer = state.get("screencast_zoom_timer", 0)

        if has_highlight_action:
            # Trigger a 2-second (60 frames) highlight zoom event
            state["screencast_zoom_timer"] = 60
            state["screencast_zoom_target_x"] = action_x_pct
            state["screencast_zoom_target_y"] = action_y_pct
            target_zoom = 1.35
            target_cx_pct = action_x_pct
            target_cy_pct = action_y_pct
        elif zoom_hold_timer > 0:
            state["screencast_zoom_timer"] = zoom_hold_timer - 1
            target_zoom = 1.35
            target_cx_pct = state.get("screencast_zoom_target_x", 0.5)
            target_cy_pct = state.get("screencast_zoom_target_y", 0.4)
        else:
            # Stationary locked full overview (no drifting!)
            target_zoom = 1.0
            target_cx_pct = 0.5
            target_cy_pct = 0.5

        # 3. Smooth Camera & Zoom Easing
        curr_zoom = state.get("screencast_curr_zoom", 1.0)
        curr_cx_pct = state.get("screencast_curr_cx", 0.5)
        curr_cy_pct = state.get("screencast_curr_cy", 0.5)

        # Smooth easing curves
        ZOOM_ALPHA = 0.08
        PAN_ALPHA = 0.06

        curr_zoom += (target_zoom - curr_zoom) * ZOOM_ALPHA
        curr_cx_pct += (target_cx_pct - curr_cx_pct) * PAN_ALPHA
        curr_cy_pct += (target_cy_pct - curr_cy_pct) * PAN_ALPHA

        state["screencast_curr_zoom"] = curr_zoom
        state["screencast_curr_cx"] = curr_cx_pct
        state["screencast_curr_cy"] = curr_cy_pct

        # 4. Render Zoomed Content onto Centered Card
        scale = (CARD_H * curr_zoom) / float(max(img_h, 1))
        scaled_h = int(CARD_H * curr_zoom)
        scaled_w = int(img_w * scale)
        res_scaled = cv2.resize(img, (max(scaled_w, 1), max(scaled_h, 1)), interpolation=cv2.INTER_AREA)

        cx_px = curr_cx_pct * scaled_w
        cy_px = curr_cy_pct * scaled_h

        tx = max(0, min(int(cx_px - CARD_W // 2), max(0, scaled_w - CARD_W)))
        ty = max(0, min(int(cy_px - CARD_H // 2), max(0, scaled_h - CARD_H)))
        card_content = res_scaled[ty : min(ty + CARD_H, res_scaled.shape[0]), tx : min(tx + CARD_W, res_scaled.shape[1])]

        start_y = max(0, (self.target_h - card_content.shape[0]) // 2)
        bg[start_y : start_y + card_content.shape[0], 0 : card_content.shape[1]] = card_content

        # 5. Instructor / Gamer Facecam Picture-in-Picture (PiP)
        # Use state memory so PiP stays persistent and smooth even if face detection drops momentarily
        if faces_fidx:
            best_face = max(faces_fidx, key=lambda f: f.get("s", 0))
            fx, fy, fs = float(best_face.get("x", 0)), float(best_face.get("y", 0)), float(best_face.get("s", 0))
            if fs > 5:
                state["pip_last_fx"] = fx
                state["pip_last_fy"] = fy
                state["pip_last_fs"] = fs

        last_fx = state.get("pip_last_fx")
        last_fy = state.get("pip_last_fy")
        last_fs = state.get("pip_last_fs")

        if last_fs is not None and last_fs > 5:
            fw = min(int(last_fs * 3.0), img_w)
            fh = min(int(last_fs * 3.0), img_h)
            x1 = max(0, min(int(last_fx - fw // 2), max(0, img_w - fw)))
            y1 = max(0, min(int(last_fy - fh // 2), max(0, img_h - fh)))
            face_crop = img[y1 : min(y1 + fh, img_h), x1 : min(x1 + fw, img_w)]
            if face_crop.shape[0] > 10 and face_crop.shape[1] > 10:
                pip_size = 260
                pip_resized = cv2.resize(face_crop, (pip_size, pip_size), interpolation=cv2.INTER_AREA)
                # Premium rounded border / clean edge
                cv2.rectangle(pip_resized, (0, 0), (pip_size - 1, pip_size - 1), (255, 255, 255), 4)
                pip_y = min(start_y + card_content.shape[0] - pip_size - 30, self.target_h - pip_size - 30)
                pip_x = min(self.target_w - pip_size - 30, self.target_w - pip_size - 30)
                if pip_y >= 0 and pip_x >= 0:
                    bg[pip_y : pip_y + pip_size, pip_x : pip_x + pip_size] = pip_resized

        return bg


class GamingStrategy(RenderStrategy):
    """Pro Gaming Layout (Focused Gameplay + Corner Streamer Facecam).

    1. Renders 16:9 gameplay in a centered 1080x1200 card with ambient blurred background.
    2. Overlays the gamer's corner webcam box as a crisp, dedicated Picture-in-Picture (PiP).
    """

    def render_frame(
        self,
        img: np.ndarray,
        fidx: int,
        faces_fidx: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> np.ndarray:
        img_h, img_w = img.shape[:2]
        bg = make_blurred_bg(img)

        # 1. Main Centered Gameplay Card (1080x1200)
        CARD_H = 1200
        CARD_W = 1080
        scale = CARD_H / float(max(img_h, 1))
        scaled_w = int(img_w * scale)
        res_scaled = cv2.resize(img, (max(scaled_w, 1), CARD_H), interpolation=cv2.INTER_AREA)

        # Center horizontally on gameplay crosshair/action
        tx = max(0, min(int((scaled_w - CARD_W) // 2), max(0, scaled_w - CARD_W)))
        card_content = res_scaled[0 : CARD_H, tx : min(tx + CARD_W, scaled_w)]

        start_y = (self.target_h - CARD_H) // 2
        bg[start_y : start_y + CARD_H, 0 : card_content.shape[1]] = card_content

        # 2. Corner Streamer Facecam Box Anchor
        # Extract the streamer's camera window from the bottom-right quadrant
        cam_w = int(img_w * 0.28)
        cam_h = int(img_h * 0.35)
        cx1 = max(0, img_w - cam_w)
        cy1 = max(0, img_h - cam_h)
        streamer_crop = img[cy1 : min(cy1 + cam_h, img_h), cx1 : min(cx1 + cam_w, img_w)]

        if streamer_crop.shape[0] > 10 and streamer_crop.shape[1] > 10:
            pip_w = 340
            pip_h = 240
            pip_resized = cv2.resize(streamer_crop, (pip_w, pip_h), interpolation=cv2.INTER_AREA)
            # Clean white broadcast border
            cv2.rectangle(pip_resized, (0, 0), (pip_w - 1, pip_h - 1), (255, 255, 255), 3)

            # Place PiP in the lower right of the vertical frame (above bottom padding)
            pip_y = min(start_y + CARD_H - pip_h - 20, self.target_h - pip_h - 20)
            pip_x = min(self.target_w - pip_w - 20, self.target_w - pip_w - 20)
            if pip_y >= 0 and pip_x >= 0:
                bg[pip_y : pip_y + pip_h, pip_x : pip_x + pip_w] = pip_resized

        return bg


class PresentationStrategy(RenderStrategy):
    """Slide deck presentation layout with speaker face Picture-in-Picture."""

    def render_frame(
        self,
        img: np.ndarray,
        fidx: int,
        faces_fidx: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> np.ndarray:
        # Presentation renders slide in main card + face PiP
        return ScreencastStrategy(self.target_w, self.target_h).render_frame(img, fidx, faces_fidx, state)


class PanelStrategy(RenderStrategy):
    """Broadcast-Grade Multi-Speaker T-Layout.

    Top Half (1080x960): Active speaker (large hero focus with smooth camera easing).
    Bottom Half (1080x960): Other panelists in stable columns (reactions / context).
    """

    def render_frame(
        self,
        img: np.ndarray,
        fidx: int,
        faces_fidx: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> np.ndarray:
        # Fallback to SplitStrategy if fewer than 2 faces
        if len(faces_fidx) < 2:
            return SplitStrategy(self.target_w, self.target_h).render_frame(img, fidx, faces_fidx, state)

        final_frame = np.zeros((self.target_h, self.target_w, 3), dtype=np.uint8)
        img_h, img_w = img.shape[:2]

        PANEL_ALPHA = 0.04  # Extra smooth camera motion
        PANEL_DEAD_ZONE = 15.0

        # Sort all available faces left-to-right across the studio frame
        sorted_faces = sorted(faces_fidx, key=lambda f: f.get("x", 0))

        # --- Active Speaker Arbitration with Hysteresis Hold ---
        # Find face with highest ASD speaking score
        best_speaker_idx = max(range(len(sorted_faces)), key=lambda i: sorted_faces[i].get("score", 0.0))
        best_score = sorted_faces[best_speaker_idx].get("score", 0.0)

        held_speaker_col = state.get("panel_held_top_col", 0)
        frames_on_speaker = state.get("panel_frames_on_speaker", 0)

        # Require 1.2s (30 frames) minimum stability hold before switching the large top camera
        MIN_SPEAKER_HOLD_FRAMES = 30
        if best_score > 0.48:
            if best_speaker_idx != held_speaker_col and frames_on_speaker >= MIN_SPEAKER_HOLD_FRAMES:
                held_speaker_col = best_speaker_idx
                frames_on_speaker = 0
            else:
                frames_on_speaker += 1
        else:
            frames_on_speaker += 1

        state["panel_held_top_col"] = held_speaker_col
        state["panel_frames_on_speaker"] = frames_on_speaker

        # Clamp held_speaker_col if face count changed
        held_speaker_col = min(held_speaker_col, len(sorted_faces) - 1)
        top_hero_face = sorted_faces[held_speaker_col]

        # Other panelists for bottom row
        other_faces = [f for i, f in enumerate(sorted_faces) if i != held_speaker_col]
        num_bottom = min(3, len(other_faces))
        other_faces = other_faces[:num_bottom]

        # --- Top Slot (Hero Active Speaker: 1080x960) ---
        # Slot 0 = Top Hero
        top_slots = [(0, 0, 1080, 960, top_hero_face, "hero_top")]

        # --- Bottom Row Slots (Remaining Panelists) ---
        bottom_slots = []
        if num_bottom == 1:
            bottom_slots.append((0, 960, 1080, 960, other_faces[0], "bottom_col_0"))
        elif num_bottom == 2:
            bottom_slots.append((0, 960, 540, 960, other_faces[0], "bottom_col_0"))
            bottom_slots.append((540, 960, 540, 960, other_faces[1], "bottom_col_1"))
        elif num_bottom >= 3:
            col_w = 360
            bottom_slots.append((0, 960, col_w, 960, other_faces[0], "bottom_col_0"))
            bottom_slots.append((360, 960, col_w, 960, other_faces[1], "bottom_col_1"))
            bottom_slots.append((720, 960, col_w, 960, other_faces[2], "bottom_col_2"))

        all_slots = top_slots + bottom_slots

        # --- Render Each Slot with Rock-Solid Spatial Smoothing & Aspect Ratio ---
        for x_pos, y_pos, pw, ph, face, slot_key in all_slots:
            if face is None:
                continue

            raw_fx = float(face.get("x", img_w / 2.0))
            raw_fy = float(face.get("y", img_h / 2.0))
            raw_fs = float(face.get("s", 60.0))
            score = float(face.get("score", 0.0))

            cx_key = f"tlayout_cx_{slot_key}"
            cy_key = f"tlayout_cy_{slot_key}"
            s_key = f"tlayout_s_{slot_key}"

            if state.get(cx_key) is None:
                state[cx_key] = raw_fx
                state[cy_key] = raw_fy
                state[s_key] = raw_fs
            else:
                if abs(raw_fx - state[cx_key]) > PANEL_DEAD_ZONE:
                    state[cx_key] += (raw_fx - state[cx_key]) * PANEL_ALPHA
                if abs(raw_fy - state[cy_key]) > PANEL_DEAD_ZONE:
                    state[cy_key] += (raw_fy - state[cy_key]) * PANEL_ALPHA
                state[s_key] += (raw_fs - state[s_key]) * PANEL_ALPHA

            cx = state[cx_key]
            cy = state[cy_key]
            fs = state[s_key]

            # Distortion-free crop calculation matching slot aspect ratio
            aspect = float(pw) / float(ph)
            is_hero = (slot_key == "hero_top")
            zoom_multiplier = 2.4 if is_hero else 2.6
            crop_h = max(fs * zoom_multiplier, float(ph * 0.7))
            crop_h = min(crop_h, float(img_h))
            crop_w = crop_h * aspect

            if crop_w > float(img_w):
                crop_w = float(img_w)
                crop_h = crop_w / aspect

            # Golden ratio headroom (22% for hero, 20% for bottom)
            headroom_pct = 0.22 if is_hero else 0.20
            x1 = max(0.0, min(cx - crop_w / 2.0, float(img_w) - crop_w))
            y1 = max(0.0, min(cy - crop_h * headroom_pct, float(img_h) - crop_h))

            crop = img[int(y1) : int(y1 + crop_h), int(x1) : int(x1 + crop_w)]
            if crop.shape[0] > 0 and crop.shape[1] > 0:
                panel = cv2.resize(crop, (pw, ph), interpolation=cv2.INTER_AREA)

                # Active speaker dimming for inactive bottom panelists
                is_speaking = is_hero or (score > 0.40)
                if not is_speaking:
                    panel = cv2.convertScaleAbs(panel, alpha=0.88, beta=0)

                final_frame[y_pos : y_pos + ph, x_pos : x_pos + pw] = panel

                # Subtle broadcast accent on active hero speaker
                if is_hero and score > 0.35:
                    cv2.rectangle(final_frame, (x_pos + 2, y_pos + 2), (x_pos + pw - 2, y_pos + ph - 2), (230, 230, 230), 3)

        # Elegant divider lines
        cv2.line(final_frame, (0, 960), (1080, 960), (35, 35, 35), 4)
        if num_bottom == 2:
            cv2.line(final_frame, (540, 960), (540, 1920), (35, 35, 35), 4)
        elif num_bottom >= 3:
            cv2.line(final_frame, (360, 960), (360, 1920), (35, 35, 35), 4)
            cv2.line(final_frame, (720, 960), (720, 1920), (35, 35, 35), 4)

        return final_frame


class PassthroughStrategy(RenderStrategy):
    """Already vertical native video (9:16) scaling / padding to 1080x1920."""

    def render_frame(
        self,
        img: np.ndarray,
        fidx: int,
        faces_fidx: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> np.ndarray:
        if img.shape[0] == self.target_h and img.shape[1] == self.target_w:
            return img
        return cv2.resize(img, (self.target_w, self.target_h), interpolation=cv2.INTER_AREA)


def get_strategy(crop_mode: str, target_w: int = 1080, target_h: int = 1920) -> RenderStrategy:
    """Factory resolver to get corresponding render strategy by crop_mode."""
    mode = (crop_mode or "auto").lower()

    # Aliases
    if mode in ("course", "tutorial"):
        mode = "screencast"
    elif mode in ("game", "action"):
        mode = "gaming"

    strategies = {
        "reframe": ReframeStrategy,
        "single": ReframeStrategy,
        "split": SplitStrategy,
        "letterbox": LetterboxStrategy,
        "screencast": ScreencastStrategy,
        "gaming": GamingStrategy,
        "presentation": PresentationStrategy,
        "panel": PanelStrategy,
        "passthrough": PassthroughStrategy,
    }

    cls = strategies.get(mode, LetterboxStrategy)
    return cls(target_w=target_w, target_h=target_h)
