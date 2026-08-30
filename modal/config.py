"""Modal App + Image definition.

All Modal service classes (CaptionBurner, AIReframe, AudioTranscriber) share
the same `app` and `image` defined here.
"""

from __future__ import annotations

import logging

import modal

# --- Logging ---
# Configure structured logging for all services. Modal captures stdout/stderr
# per-container, so we use a simple format that's easy to parse.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("makemyclip")

# --- Modal App ---
app = modal.App("makemyclip-ai-rendering")

_LOCAL_SOURCES = (
    "config",
    "models",
    "colors",
    "fonts",
    "presets",
    "ass_builder",
    "r2_storage",
    "ytdlp_helper",
    "burner",
    "reframer",
    "transcriber",
    "analyzer",
    "utils",
    "errors",
    "camera_engine",
    "layout_classifier",
    "video_utils",
    "content_classifier",
    "render_strategies",
    "silence_remover",
)

# --- Image ---
image = (
    modal.Image.from_registry("nvidia/cuda:12.4.0-devel-ubuntu22.04", add_python="3.12")
    .apt_install(
        [
            "ffmpeg",
            "libgl1-mesa-glx",
            "libglib2.0-0",
            "wget",
            "curl",
            "unzip",
            "libcudnn8",
            "libcudnn8-dev",
            "fonts-liberation",
            "fontconfig",
            "git",
        ]
    )
    .run_commands(
        "curl -fsSL https://deno.land/install.sh | sh",
        "ln -s /root/.deno/bin/deno /usr/local/bin/deno",
    )
    .pip_install_from_requirements("requirements.txt")
    .pip_install(
        "setuptools", "boto3", "pysubs2", "requests", "assemblyai", "fastapi"
    )
    # Upgrade yt-dlp to nightly for SABR protocol support (required for YouTube HD)
    .run_commands("pip install -U --pre 'yt-dlp[default]'")
    .run_commands(
        "yt-dlp --remote-components ejs:github -o /dev/null --skip-download 'https://www.youtube.com/watch?v=jNQXAC9IVRw' || true",
    )
    .add_local_dir("asd", "/root/asd", copy=True)
    # Pre-download S3FD face detector model weight using wget directly to bypass gdown/pkg_resources issues
    .run_commands(
        "mkdir -p /root/asd/model/faceDetector/s3fd && wget --no-check-certificate 'https://docs.google.com/uc?export=download&id=1KafnHz7ccT-3IyddBsL5yi2xGtxAKypt' -O /root/asd/model/faceDetector/s3fd/sfd_face.pth || curl -L 'https://drive.google.com/uc?id=1KafnHz7ccT-3IyddBsL5yi2xGtxAKypt' -o /root/asd/model/faceDetector/s3fd/sfd_face.pth"
    )
    .run_commands("mkdir -p /usr/share/fonts/truetype/custom")
    .add_local_dir("../fonts", "/usr/share/fonts/truetype/custom", copy=True)
    .run_commands("fc-cache -f -v")
    .add_local_file("watermark.svg", "/root/watermark.svg", copy=True)
    .add_local_file("watermark.png", "/root/watermark.png", copy=True)
    .add_local_python_source(*_LOCAL_SOURCES)
)

# --- Shared Modal secrets ---
ai_secret = modal.Secret.from_name("ai-podcast-clipper-secret")
youtube_cookies_secret = modal.Secret.from_name("youtube-cookies")

# --- GPU recommendation ---
# L4 (Ada Lovelace) offers ~1.8x the throughput of T4 at only ~30% more cost.
# It has a significantly faster NVENC encoder and higher memory bandwidth,
# making it the sweet spot for AI reframing workloads.
RECOMMENDED_GPU = "L4"
