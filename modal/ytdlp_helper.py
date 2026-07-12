"""Shared YouTube download helper.

Both ``AudioTranscriber`` and ``AIReframe`` need to download YouTube videos.
This module centralizes the cookies handling and the multi-strategy fallback
logic so they don't drift apart.

We use ``subprocess`` for hard-killable timeouts (Python threads cannot be
killed reliably; subprocess.run + timeout will SIGKILL a stuck yt-dlp).
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger("makemyclip.ytdlp")

# Seconds of padding added to each side of a segment download range.
# Shared with reframer.py so the ffmpeg seek offset stays in sync.
SEGMENT_DOWNLOAD_PAD_S = 10.0


def write_cookies_file(tmpdir: str) -> str | None:
    """Write the ``COOKIES_TXT`` env var to a 0600 file.

    Returns the path or ``None`` if no cookies are configured.
    """
    cookie_data = os.environ.get("COOKIES_TXT", "")
    if not cookie_data:
        return None
    cookies_path = os.path.join(tmpdir, "cookies.txt")
    with open(cookies_path, "w") as f:
        f.write(cookie_data)
    # Restrict permissions immediately to limit blast radius if the tmpdir leaks.
    os.chmod(cookies_path, 0o600)
    logger.info("Cookies loaded (%d bytes)", len(cookie_data))
    return cookies_path


def remove_bgutil_pot_provider() -> None:
    """Uninstall the bgutil PO Token provider plugin.

    The plugin auto-registers with yt-dlp and infinitely retries integrity-token
    generation, which is impossible in headless containers. Removing it
    prevents 4+ minute hangs at extraction time.
    """
    try:
        subprocess.run(
            ["pip", "uninstall", "-y", "bgutil-ytdlp-pot-provider"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        logger.info("Removed bgutil PO Token plugin (prevents infinite retries)")
    except Exception as e:  # noqa: BLE001 — startup hook, must not crash container
        logger.warning("Could not remove bgutil plugin: %s", e)


def download_youtube_audio(vurl: str, tmpdir: str) -> str:
    """Download YouTube audio as MP3 with multi-strategy fallback.

    Returns the absolute path to the downloaded audio file.
    Raises ``RuntimeError`` if every strategy fails.
    """
    cookies_path = write_cookies_file(tmpdir)
    if cookies_path is None:
        logger.warning("No COOKIES_TXT env var — YouTube may block downloads")

    base_args = [
        "yt-dlp",
        "-f",
        "bestaudio/best",
        "-x",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",
        "-o",
        f"{tmpdir}/audio.%(ext)s",
        "--socket-timeout",
        "30",
        "--retries",
        "3",
        "--fragment-retries",
        "3",
        "--no-warnings",
        "--remote-components",
        "ejs:github",
    ]
    if cookies_path:
        base_args += ["--cookies", cookies_path]

    strategies = [
        {
            "name": "mweb client (no PO Token needed)",
            "extra_args": ["--extractor-args", "youtube:player_client=mweb"],
            "timeout": 120,
        },
        {
            "name": "web client + cookies",
            "extra_args": ["--extractor-args", "youtube:player_client=web"],
            "timeout": 120,
        },
        {
            "name": "default client (last resort)",
            "extra_args": [],
            "timeout": 120,
        },
    ]

    last_error: Exception | None = None

    for strategy in strategies:
        logger.info("Trying strategy: %s...", strategy["name"])

        # Clean up leftover files from previous failed attempts
        for old_file in Path(tmpdir).glob("audio.*"):
            try:
                old_file.unlink()
            except Exception:
                pass

        cmd = base_args + strategy["extra_args"] + [vurl]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=strategy["timeout"],
            )

            if result.returncode != 0:
                stderr_tail = (result.stderr or "")[-500:]
                raise RuntimeError(
                    f"yt-dlp exited with code {result.returncode}: {stderr_tail}"
                )

            # Find the output file
            mp3_files = list(Path(tmpdir).glob("audio*.mp3"))
            if not mp3_files:
                mp3_files = list(Path(tmpdir).glob("*.mp3"))
            if not mp3_files:
                # yt-dlp might have kept the original format
                mp3_files = [f for f in Path(tmpdir).glob("audio*") if f.is_file()]

            if not mp3_files:
                raise FileNotFoundError(
                    f"No audio file found in {tmpdir} after download"
                )

            local_media = str(mp3_files[0])
            file_size = os.path.getsize(local_media)

            if file_size < 1000:
                raise RuntimeError(
                    f"Downloaded file too small ({file_size} bytes) — likely corrupted"
                )

            logger.info(
                "✅ Strategy '%s' succeeded: %s (%s bytes)",
                strategy["name"],
                local_media,
                f"{file_size:,}",
            )

            # Best-effort cleanup of cookie file once we have the audio
            if cookies_path and os.path.exists(cookies_path):
                try:
                    os.remove(cookies_path)
                except OSError:
                    pass

            return local_media

        except subprocess.TimeoutExpired:
            last_error = TimeoutError(
                f"yt-dlp timed out after {strategy['timeout']}s"
            )
            logger.warning(
                "❌ Strategy '%s' timed out after %ds — process killed",
                strategy["name"],
                strategy["timeout"],
            )
            continue

        except Exception as e:  # noqa: BLE001 — fall through to next strategy
            last_error = e
            logger.warning(
                "❌ Strategy '%s' failed: %s: %s",
                strategy["name"],
                type(e).__name__,
                e,
            )
            continue

    # Cleanup cookie file before raising
    if cookies_path and os.path.exists(cookies_path):
        try:
            os.remove(cookies_path)
        except OSError:
            pass

    raise RuntimeError(
        f"All YouTube download strategies failed. Last error: {last_error}"
    )


def download_youtube_video(
    vurl: str,
    tmpdir: str,
    start_time: float | None = None,
    end_time: float | None = None,
    max_height: int = 1080,
    skip_probe: bool = False,
) -> str:
    """Download a YouTube video (with audio) as a remuxed MP4.

    Uses the Python yt-dlp API because we need ``extract_info`` to surface format
    diagnostics for debugging.  When *start_time* and *end_time* are supplied the
    download is limited to that segment via ``--download-sections``, which uses
    YouTube's HTTP-range support to fetch only the bytes needed (dramatically
    cutting download time and bandwidth for short clips from long videos).

    A 10-second padding is added on each side of the requested range so that
    keyframe-accurate cuts never lose frames at the boundaries.

    Parameters
    ----------
    max_height : int
        Maximum video height to download (e.g. 720 for preview, 1080 for export).
    skip_probe : bool
        If True, skip the Phase 1 format probe to save ~4s.

    Returns the absolute path to the downloaded file.
    """
    import time as _t

    import yt_dlp
    from yt_dlp.utils import download_range_func

    cookies_path = write_cookies_file(tmpdir)
    if cookies_path is None:
        logger.warning(
            "No COOKIES_TXT env var found — YouTube may throttle or block the download"
        )

    # If a segment is requested, check the video duration first.
    # If the video is under 3 hours (<= 10800s), it is MUCH faster to download the full video natively
    # using parallel HTTP streams than to download a segment using yt-dlp's ffmpeg-range-downloader
    # (which gets heavily throttled by YouTube to ~120KB/s).
    if start_time is not None and end_time is not None:
        try:
            probe_opts = {
                "cookiefile": cookies_path,
                "quiet": True,
                "no_warnings": True,
                "js_runtimes": {"deno": {"path": "/usr/local/bin/deno"}},
            }
            with yt_dlp.YoutubeDL(probe_opts) as ydl_probe:
                probe_info = ydl_probe.extract_info(vurl, download=False)
                vid_duration = probe_info.get("duration")
                if vid_duration and vid_duration <= 10800:
                    logger.info(
                        "Video duration is under 3 hours (%.1fs <= 10800s) — downloading FULL video natively to bypass YouTube speed throttles...",
                        vid_duration,
                    )
                    start_time = None
                    end_time = None
        except Exception as e:
            logger.warning("Could not probe video duration: %s", e)

    # mweb (mobile web) client provides HD formats without requiring PO Tokens.
    ydl_opts = {
        "outtmpl": f"{tmpdir}/%(title)s.%(ext)s",
        "cookiefile": cookies_path,
        "quiet": False,
        "no_warnings": False,
        "verbose": True,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "js_runtimes": {"deno": {"path": "/usr/local/bin/deno"}},
        "remote_components": ["ejs:github"],
        "format": f"bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]/best",
        "merge_output_format": "mp4",
        "format_sort": ["res", "vcodec:h264", "ext:mp4:m4a", "acodec:aac"],
        "postprocessors": [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}],
    }

    # Segment download: fetch only the needed portion instead of the full video.
    # 10s padding on each side ensures the segment extends past the nearest
    # keyframes.  We intentionally do NOT set force_keyframes_at_cuts because
    # that triggers a full libx264 re-encode of the segment (43s+ observed in
    # production).  Stream-copy is near-instant; downstream ffmpeg -ss handles
    # precise seeking within the padded segment.
    if start_time is not None and end_time is not None:
        seg_start = max(0.0, start_time - SEGMENT_DOWNLOAD_PAD_S)
        seg_end = end_time + SEGMENT_DOWNLOAD_PAD_S
        ydl_opts["download_ranges"] = download_range_func(
            None, [(seg_start, seg_end)]
        )
        logger.info(
            "Segment download enabled: %.1f–%.1f (padded from %.1f–%.1f)",
            seg_start,
            seg_end,
            start_time,
            end_time,
        )

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Phase 1: probe formats for diagnostics (non-fatal on failure)
            # Skipped in preview mode — saves ~4s by avoiding a redundant API call.
            if not skip_probe:
                try:
                    probe_info = ydl.extract_info(vurl, download=False)
                    _log_format_diagnostics(probe_info)
                except Exception as probe_err:  # noqa: BLE001
                    logger.warning(
                        "Phase 1 probe failed (non-fatal, continuing): %s",
                        probe_err,
                    )

            # Phase 2: actual download
            logger.info("── Phase 2: Downloading video ──")
            info = ydl.extract_info(vurl, download=True)
            local_path = ydl.prepare_filename(info)

            _log_download_result(info, local_path)

            # If the prepared filename is wrong (e.g. remuxed extension changed),
            # fall back to scanning for the largest .mp4 file in tmpdir.
            if not os.path.exists(local_path):
                base_path = os.path.splitext(local_path)[0]
                if os.path.exists(base_path + ".mp4"):
                    local_path = base_path + ".mp4"
                else:
                    files = []
                    for _attempt in range(3):
                        files = [
                            f
                            for f in Path(tmpdir).glob("*.mp4")
                            if f.stat().st_size > 0
                        ]
                        if files:
                            break
                        logger.info(
                            "yt-dlp fallback: no mp4 yet, retrying (%d/3)...",
                            _attempt + 1,
                        )
                        _t.sleep(1)
                    if not files:
                        raise RuntimeError(
                            "[ytdlp] yt-dlp download failed: no usable mp4 found "
                            "in tmpdir after retries"
                        )
                    local_path = str(max(files, key=lambda f: f.stat().st_size))

        return local_path
    finally:
        if cookies_path and os.path.exists(cookies_path):
            try:
                os.remove(cookies_path)
                logger.info("Cookie file deleted after download")
            except OSError:
                pass


def _log_format_diagnostics(probe_info: dict) -> None:
    formats = probe_info.get("formats", [])
    logger.info("Video title: %s", probe_info.get("title", "N/A"))
    logger.info("Total available formats: %d", len(formats))

    video_formats = [f for f in formats if f.get("vcodec", "none") != "none"]
    logger.info("Video-only/combined formats (%d):", len(video_formats))
    for fmt in video_formats:
        height = fmt.get("height", "?")
        width = fmt.get("width", "?")
        vcodec = fmt.get("vcodec", "?")
        ext = fmt.get("ext", "?")
        fmt_id = fmt.get("format_id", "?")
        filesize = fmt.get("filesize") or fmt.get("filesize_approx") or 0
        filesize_mb = filesize / (1024 * 1024) if filesize else 0
        fps_val = fmt.get("fps", "?")
        logger.info(
            "  [%s] %sx%s %s .%s ~%.1fMB @%sfps",
            fmt_id, width, height, vcodec, ext, filesize_mb, fps_val,
        )

    selected_height = probe_info.get("height", "?")
    logger.info(
        "yt-dlp selected: format=%s format_id=%s resolution=%s (%sx%s) "
        "vcodec=%s acodec=%s",
        probe_info.get("format", "N/A"),
        probe_info.get("format_id", "N/A"),
        probe_info.get("resolution", "N/A"),
        probe_info.get("width", "?"),
        selected_height,
        probe_info.get("vcodec", "?"),
        probe_info.get("acodec", "?"),
    )

    has_1080p = any(f.get("height") == 1080 for f in video_formats)
    has_720p = any(f.get("height") == 720 for f in video_formats)
    logger.info("1080p available: %s, 720p available: %s", has_1080p, has_720p)
    if (
        selected_height
        and selected_height != "?"
        and isinstance(selected_height, (int, str))
    ):
        try:
            if int(selected_height) < 1080 and has_1080p:
                logger.warning(
                    "1080p IS available but yt-dlp selected %sp!", selected_height,
                )
        except (TypeError, ValueError):
            pass


def _log_download_result(info: dict, local_path: str) -> None:
    logger.info(
        "Download result: format=%s format_id=%s resolution=%sx%s "
        "vcodec=%s acodec=%s ext=%s expected_file=%s",
        info.get("format", "N/A"),
        info.get("format_id", "N/A"),
        info.get("width", "?"),
        info.get("height", "?"),
        info.get("vcodec", "?"),
        info.get("acodec", "?"),
        info.get("ext", "?"),
        local_path,
    )
