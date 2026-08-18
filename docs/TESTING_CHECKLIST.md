# 📋 AI Reframer & Analyzer Testing Guide & Verification Checklist

This document provides a step-by-step verification checklist and CLI commands to test all AI Video Reframer, TalkNCE Active Speaker Detection (ASD), and VideoAnalyzer features deployed on Modal.

---

## 🌐 Deployed Production Endpoints

| Service / Function | HTTP Method | Live Endpoint URL |
|---|---|---|
| **AIReframe — Single Reframe** | `POST` | `https://ms8460149--makemyclip-ai-rendering-aireframe-reframe.modal.run` |
| **AIReframe — Batch Reframe** | `POST` | `https://ms8460149--makemyclip-ai-rendering-aireframe-batch-reframe.modal.run` |
| **AIReframe — Eval Clip** | `POST` | `https://ms8460149--makemyclip-ai-rendering-aireframe-eval-clip.modal.run` |
| **VideoAnalyzer — Analyze** | `POST` | `https://ms8460149--makemyclip-ai-rendering-videoanalyzer-analyze.modal.run` |
| **CaptionBurner — Endpoint** | `POST` | `https://ms8460149--makemyclip-ai-rendering-captionburner-endpoint.modal.run` |
| **AudioTranscriber — Transcribe** | `POST` | `https://ms8460149--makemyclip-ai-rendering-audiotranscriber-transcribe.modal.run` |

---

## 🧪 Phase 1: Local Code Syntax & Import Verification

Run this single-line verification script from your terminal to confirm that all Python files, module exports, and syntax parse cleanly:

```bash
python3 -c "
import ast, glob, sys
files = glob.glob('modal/**/*.py', recursive=True)
for f in files:
    ast.parse(open(f).read())
print(f'✅ All {len(files)} Python files parsed cleanly!')

sys.path.insert(0, 'modal')
from camera_engine import CAMERA_PROFILES, CameraProfile, calculate_adaptive_pan_alpha
from layout_classifier import classify_layout, is_valid_face_track
from video_utils import compute_audio_rms_energy, make_blurred_bg, mux_audio_video
from talknce import create_talknce_engine
print('✅ All decomposed modules imported successfully!')
"
```

---

## 🎬 Phase 2: Testing Single Clip Reframing (`/reframe`) (✅ VERIFIED & COMPLETED)

### 1. Test Command (via Modal CLI)

```bash
modal run modal/reframer.py::AIReframe.reframe \
  --video-url "https://www.youtube.com/watch?v=GH3eWEkCNnA" \
  --crop-mode "auto"
```

### 2. Test Command (via cURL HTTP POST)

```bash
curl -X POST "https://ms8460149--makemyclip-ai-rendering-aireframe-reframe.modal.run" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=GH3eWEkCNnA",
    "crop_mode": "auto",
    "camera_profile": "podcast",
    "start_time": 0,
    "end_time": 20
  }'
```

### 3. Single Clip Verification Checklist

- [x] **Fast Camera Panning (~0.6s)**: Confirm camera locks onto a new speaker in ~15 frames (0.6s) without lagging behind audio.
- [x] **Audio Emphasis "Zoom Punch"**: Confirm camera applies a subtle 7% zoom-in during loud audio spikes / punchlines.
- [x] **Ken Burns Motion Drift**: Confirm static scenes (>3s still) apply a subtle slow 0.08%/frame zoom and lateral drift instead of freezing statically.
- [x] **Screen-Share / Slide Saliency**: Confirm crop centers on text/graphics when no faces are detected.
- [x] **Quality Telemetry**: Confirm response contains the `quality_metrics` JSON payload.

---

## 👥 Phase 3: Testing Split-Screen Layouts (`crop_mode="split"`) (✅ VERIFIED & COMPLETED)

Test on a 2-person podcast or interview video (e.g., Joe Rogan, Lex Fridman, or Huberman Lab):

```bash
curl -X POST "https://ms8460149--makemyclip-ai-rendering-aireframe-reframe.modal.run" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=GOqEl4ADyVk",
    "crop_mode": "split",
    "start_time": 695,
    "end_time": 705
  }'
```

### Split-Screen Verification Checklist

- [x] **Active Speaker Zoom Boost**: Confirm the speaking person's panel receives a 5% zoom boost (`SPLIT_SPEAKER_ZOOM_BOOST = 1.05`).
- [x] **Passive Listener Panel Dimming**: Confirm the listener panel is dimmed to 88% brightness (`SPLIT_LISTENER_DIM = 0.88`).
- [x] **TalkNCE Mic Bleed Filtering**: Confirm studio background chatter does not trigger false camera switches.
- [x] **OpusClip Framing & 165px+ Headroom**: Confirm fixed 44% width and 0.22 upper-third headroom anchor prevents head cutoffs.

---

## 📊 Phase 4: Testing Full Video Analysis (`/analyze`) (✅ VERIFIED & COMPLETED)

Test the `VideoAnalyzer` service on a sub-segment or full video:

```bash
curl -X POST "https://ms8460149--makemyclip-ai-rendering-videoanalyzer-analyze.modal.run" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=GOqEl4ADyVk",
    "project_id": "test_phase4_clip_1130_1330",
    "start_time": 690,
    "end_time": 810
  }'
```

### VideoAnalyzer Verification Checklist

- [x] **Sub-Segment Range Bounding**: Confirm `start_time` and `end_time` limits processing strictly to the requested clip without processing full video.
- [x] **Fast Parallel GPU Processing**: Confirm 3,000 frames (120s) analyze in ~106s across TalkNCE GPUs.
- [x] **Scene Boundary & Track Serialization**: Confirm response outputs `analysis.json` to R2 with face tracks, TalkNCE scores, and scene bounds.
- [x] **Pre-Calculated `scene_layouts`**: Confirm `analysis.json` contains recommended layout modes per scene.

---

## 🎨 Phase 5: Testing Caption Burning & Subtitle Styling (`/burn`) (✅ VERIFIED & COMPLETED)

Test the `CaptionBurner` endpoint to burn animated captions (e.g., Hormozi style, karaoke highlighting) onto a reframed video:

```bash
curl -X POST "https://ms8460149--makemyclip-ai-rendering-captionburner-endpoint.modal.run" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://pub-dab84dec13074258806f788a00943c46.r2.dev/reframes/orig_79eae122-506c-49bf-a12d-5a0f893f404d.mp4",
    "transcript": [
      {"word": "Welcome", "start": 0.0, "end": 0.5},
      {"word": "to", "start": 0.5, "end": 0.8},
      {"word": "the", "start": 0.8, "end": 1.0},
      {"word": "show", "start": 1.0, "end": 1.5}
    ],
    "styling": {
      "preset": "hormozi",
      "font_family": "Montserrat",
      "font_size": 48
    },
    "show_watermark": false,
    "quality": "export"
  }'
```

### CaptionBurner Verification Checklist

- [x] **ASS Subtitle Render Speed**: Confirm ASS subtitles bake onto video in **~6 seconds** (Status 200 OK).
- [x] **Word-by-Word Active Highlighting**: Confirm active word is animated during playback.
- [x] **Watermark Baking**: Confirm optional watermark renders cleanly when `show_watermark: true`.

---

## 📐 Phase 6: Quality Metrics Telemetry Schema

The API response payload includes a `quality_metrics` telemetry object:

```json
{
  "success": true,
  "video_url": "https://pub-xxx.r2.dev/rendered/xxx.mp4",
  "quality_metrics": {
    "face_detection_coverage": 0.984,
    "asd_confidence": 0.912,
    "layout_switches": 2,
    "speaker_switches": 5,
    "camera_stability_score": 0.942
  }
}
```

### Metric Definitions:
- `face_detection_coverage`: Fraction of frames where valid face tracks were active (0.0 to 1.0).
- `asd_confidence`: Mean TalkNCE confidence score for the active speaker (0.0 to 1.0).
- `layout_switches`: Number of layout mode transitions (`single` ↔ `split` ↔ `letterbox`).
- `speaker_switches`: Total number of active speaker camera switches.
- `camera_stability_score`: Smoothness metric measuring frame-to-frame pan velocity stability (higher is smoother).
