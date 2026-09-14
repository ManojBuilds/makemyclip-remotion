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


def sanitize_source_url(vurl: str) -> tuple[str, str]:
    """Normalize video URL and return (cleaned_url, platform_name)."""
    import re
    from utils import detect_video_source
    cleaned = (vurl or "").strip()
    platform = detect_video_source(cleaned)
    if platform == "google_drive":
        match = re.search(r"/file/d/([a-zA-Z0-9_-]+)", cleaned) or re.search(r"[?&]id=([a-zA-Z0-9_-]+)", cleaned)
        if match:
            file_id = match.group(1)
            cleaned = f"https://drive.google.com/file/d/{file_id}/view"
    return cleaned, platform


def _check_and_raise_specific_error(error_msg: str, platform: str) -> None:
    """Check stderr or exception messages for common user-actionable error states."""
    err_lower = (error_msg or "").lower()
    if "quotaexceeded" in err_lower or "download quota" in err_lower:
        raise RuntimeError(
            "Google Drive download quota exceeded for this file. Please make a copy to your own Google Drive or upload the video directly."
        )
    if (
        "private video" in err_lower
        or "requires authentication" in err_lower
        or "this video is private" in err_lower
        or "sign in" in err_lower
        or "login" in err_lower
    ):
        if platform == "loom":
            raise RuntimeError(
                "This Loom video is private or restricted to a workspace. Please set sharing to 'Anyone with the link can view'."
            )
        elif platform == "vimeo":
            raise RuntimeError(
                "This Vimeo video is private, password-protected, or restricted from external downloads."
            )
        elif platform == "google_drive":
            raise RuntimeError(
                "This Google Drive file is private. Please set sharing permissions to 'Anyone with the link can view'."
            )
        elif platform == "twitch":
            raise RuntimeError(
                "This Twitch VOD/clip is subscriber-only or requires authentication."
            )
        raise RuntimeError(f"The {platform} video is private or requires authentication.")


def download_media_audio(vurl: str, tmpdir: str) -> str:
    """Download audio as MP3 for YouTube (multi-strategy) or other platforms (clean yt-dlp).

    Returns the absolute path to the downloaded audio file.
    Raises ``RuntimeError`` if every strategy fails.
    """
    cleaned_url, platform = sanitize_source_url(vurl)

    if platform != "youtube":
        logger.info("Downloading audio via native yt-dlp extractor for '%s'...", platform)
        for old_file in Path(tmpdir).glob("audio.*"):
            try:
                old_file.unlink()
            except Exception:
                pass

        cmd = [
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
            "60",
            "--retries",
            "3",
            "--no-warnings",
            cleaned_url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            stderr = result.stderr or ""
            _check_and_raise_specific_error(stderr, platform)
            raise RuntimeError(f"yt-dlp audio download failed for {platform}: {stderr[-500:]}")

        mp3_files = list(Path(tmpdir).glob("audio*.mp3"))
        if not mp3_files:
            mp3_files = list(Path(tmpdir).glob("*.mp3"))
        if not mp3_files:
            mp3_files = [f for f in Path(tmpdir).glob("audio*") if f.is_file()]

        if not mp3_files:
            raise FileNotFoundError(f"No audio file found in {tmpdir} after {platform} download")

        local_media = str(mp3_files[0])
        file_size = os.path.getsize(local_media)
        if file_size < 1000:
            raise RuntimeError(f"Downloaded file too small ({file_size} bytes) — likely corrupted")

        logger.info(
            "✅ Native %s audio download succeeded: %s (%s bytes)",
            platform,
            local_media,
            f"{file_size:,}",
        )
        return local_media

    # --- YouTube download with multi-strategy fallback ---
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
        "--concurrent-fragments",
        "8",
        "--no-warnings",
        "--remote-components",
        "ejs:github",
    ]
    if cookies_path:
        base_args += ["--cookies", cookies_path]

    strategies = [
        {
            "name": "tv + web_safari + web client",
            "extra_args": ["--extractor-args", "youtube:player_client=tv,web_safari,mweb,web"],
            "timeout": 120,
        },
        {
            "name": "android_vr + mweb + web client",
            "extra_args": ["--extractor-args", "youtube:player_client=android_vr,mweb,web"],
            "timeout": 120,
        },
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


download_youtube_audio = download_media_audio


def download_youtube_video(
    vurl: str,
    tmpdir: str,
    start_time: float | None = None,
    end_time: float | None = None,
    max_height: int | None = 720,
    skip_probe: bool = False,
) -> tuple[str, float]:
    """Download a YouTube video (with audio) as a remuxed MP4 with multi-strategy fallback.

    Parameters
    ----------
    max_height : int | None
        Maximum video height to download (e.g. 720 for preview/default, 1080
        for HD export). Pass ``None`` to fetch the highest resolution
        actually available for this video — no height ceiling is applied to
        format selection. In this mode a strategy that already reaches 1080p+
        is accepted immediately (diminishing returns beyond that for most
        content), but if the first strategy that succeeds tops out below
        1080p, the remaining strategies are still tried in case a different
        client exposes a higher-resolution stream (HLS-serving clients in
        particular can structurally cap lower than DASH-serving ones).
    skip_probe : bool
        If True, skip the Phase 1 format probe to save ~4s.

    Returns (local_file_path, actual_segment_offset_seconds).
    """
    import shutil
    import time as _t

    import yt_dlp
    from yt_dlp.utils import download_range_func

    cookies_path = write_cookies_file(tmpdir)
    if cookies_path is None:
        logger.warning(
            "No COOKIES_TXT env var found — YouTube may throttle or block the download"
        )

    # NOTE: we used to force a full-video download whenever max_height >= 720,
    # on the theory that Modal's bandwidth made a full download "free" (~3s)
    # and that range-limited requests got silently downgraded to 360p. Neither
    # holds up right now: under YouTube's current PO-Token/SABR restrictions,
    # the client combo that actually reaches 720p+ (see strategies below) does
    # so over HLS via a JS-challenge-solved web_safari session, not a raw DASH
    # byte-range request — so segment-limited downloads don't trigger that old
    # downgrade behavior. Forcing a full download here means fetching an
    # entire 60-90 minute source video just to cut a 10s clip out of it, which
    # is where most of the wall-clock time was going. We keep honoring
    # start_time/end_time at every quality tier now; the existing
    # resolution-check loop below still falls back to the next strategy (or
    # the best available candidate) if a given client can't hit the target
    # height, so quality is still protected.

    if max_height is None:
        # "Highest available" mode: 4320 (8K) is just a sanity ceiling for the
        # format filter below — no real YouTube upload exceeds it, so this is
        # effectively "no cap" without needing a second code path for the
        # format string. We do, however, want a higher bar than the normal
        # 720p floor before we're willing to stop trying more strategies (see
        # quality_floor below).
        target_res = 4320
        quality_floor = 1080
    else:
        target_res = (
            max_height
            if max_height in (360, 480, 720, 1080, 1440, 2160)
            else max(144, min(max_height, 4320))
        )
        quality_floor = 720
    quality_label = "highest available" if max_height is None else f"{target_res}p"
    # Nudge yt-dlp toward HLS (m3u8) formats when resolutions tie: that's the
    # protocol that's actually working under current YouTube restrictions, and
    # unlike raw DASH byte-range formats it downloads discrete fragments, so
    # it plays nicely with time-ranged (--download-sections style) downloads.
    format_sort = [f"res:{target_res}", "res:720", "proto:m3u8_native", "vcodec:h264", "quality"]

    actual_segment_offset = 0.0
    seg_start = 0.0
    seg_end = 0.0
    if start_time is not None and end_time is not None:
        seg_start = max(0.0, start_time - SEGMENT_DOWNLOAD_PAD_S)
        seg_end = end_time + SEGMENT_DOWNLOAD_PAD_S
        actual_segment_offset = seg_start
        logger.info(
            "Segment download enabled: %.1f–%.1f (padded from %.1f–%.1f)",
            seg_start,
            seg_end,
            start_time,
            end_time,
        )

    cleaned_url, platform = sanitize_source_url(vurl)

    if platform == "youtube":
        strategies = [
            {
                "name": "tv + web_safari + web",
                "use_cookies": True,
                "player_client": ["tv", "web_safari", "mweb", "web"],
            },
            {
                "name": "android_vr + mweb + web (cookies)",
                "use_cookies": True,
                "player_client": ["android_vr", "mweb", "web"],
            },
            {
                "name": "android_vr + android + ios + web (no cookies)",
                "use_cookies": False,
                "player_client": ["android_vr", "android", "ios", "web"],
            },
            {
                "name": "default yt-dlp client",
                "use_cookies": True,
                "player_client": None,
            },
        ]
    else:
        strategies = [
            {
                "name": f"native {platform} extractor",
                "use_cookies": False,
                "player_client": None,
            },
        ]
        skip_probe = True

    last_error: Exception | None = None
    fallback_candidate: tuple[str, int] | None = None  # (local_path, height)

    try:
        for strat_idx, strategy in enumerate(strategies):
            sname = strategy["name"]
            logger.info(
                "Attempting video download strategy [%d/%d]: %s (target=%s)...",
                strat_idx + 1,
                len(strategies),
                sname,
                quality_label,
            )

            # Clean up leftover files from previous failed/low-res attempts
            for old_file in Path(tmpdir).glob("*.mp4"):
                try:
                    old_file.unlink()
                except Exception:
                    pass

            use_cookie = cookies_path if (strategy["use_cookies"] and cookies_path) else None
            ydl_opts = {
                "outtmpl": f"{tmpdir}/%(title)s.%(ext)s",
                "cookiefile": use_cookie,
                "quiet": False,
                "no_warnings": False,
                "verbose": True,
                "socket_timeout": 60,
                "retries": 3,
                "fragment_retries": 3,
                "concurrent_fragment_downloads": 8,
                "js_runtimes": {"deno": {"path": "/usr/local/bin/deno"}},
                "remote_components": ["ejs:github"],
                "format": f"bestvideo[height<={target_res}]+bestaudio/best[height<={target_res}]/bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "format_sort": format_sort,
                "postprocessors": [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}],
            }

            if strategy["player_client"]:
                ydl_opts["extractor_args"] = {
                    "youtube": {
                        "player_client": strategy["player_client"],
                    }
                }

            if start_time is not None and end_time is not None:
                ydl_opts["download_ranges"] = download_range_func(
                    None, [(seg_start, seg_end)]
                )

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Phase 1: probe formats for diagnostics (YouTube only)
                    if not skip_probe and platform == "youtube":
                        try:
                            probe_info = ydl.extract_info(cleaned_url, download=False)
                            _log_format_diagnostics(probe_info)
                        except Exception as probe_err:  # noqa: BLE001
                            logger.warning(
                                "Phase 1 probe failed (non-fatal, continuing): %s",
                                probe_err,
                            )

                    # Phase 2: actual download
                    logger.info("── Phase 2: Downloading video with '%s' ──", sname)
                    try:
                        info = ydl.extract_info(cleaned_url, download=True)
                    except Exception as dl_err:
                        # For progressive downloads (e.g. Google Drive), if download_ranges fails, retry full download
                        if "download_ranges" in ydl_opts:
                            logger.warning(
                                "Segment download failed for %s (%s). Retrying full download...",
                                platform,
                                dl_err,
                            )
                            ydl_opts_full = dict(ydl_opts)
                            ydl_opts_full.pop("download_ranges", None)
                            with yt_dlp.YoutubeDL(ydl_opts_full) as ydl_retry:
                                info = ydl_retry.extract_info(cleaned_url, download=True)
                                actual_segment_offset = 0.0
                        else:
                            raise dl_err

                    local_path = ydl.prepare_filename(info)

                    _log_download_result(info, local_path)

                    # If the prepared filename is wrong, scan for the largest .mp4 in tmpdir
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
                                    f"[ytdlp] yt-dlp download failed with '{sname}': no usable mp4 found"
                                )
                            local_path = str(max(files, key=lambda f: f.stat().st_size))

                    file_size = os.path.getsize(local_path)
                    if file_size < 1000:
                        raise RuntimeError(
                            f"Downloaded file too small ({file_size} bytes) — likely corrupted"
                        )

                    dl_height = info.get("height") or 0
                    logger.info(
                        "✅ Strategy '%s' succeeded: %s (%s bytes, %sp)",
                        sname,
                        local_path,
                        f"{file_size:,}",
                        dl_height,
                    )

                    # Check if resolution meets requirement
                    min_acceptable = min(target_res, quality_floor)
                    if dl_height >= min_acceptable or strat_idx == len(strategies) - 1:
                        return local_path, actual_segment_offset
                    else:
                        logger.warning(
                            "Strategy '%s' downloaded %sp which is below target (%s, min %sp). Retrying with next strategy...",
                            sname,
                            dl_height,
                            quality_label,
                            min_acceptable,
                        )
                        # Save fallback candidate in tmpdir
                        fallback_path = os.path.join(tmpdir, f"fallback_{strat_idx}_{dl_height}p.mp4")
                        try:
                            shutil.copy2(local_path, fallback_path)
                            if fallback_candidate is None or dl_height > fallback_candidate[1]:
                                fallback_candidate = (fallback_path, dl_height)
                        except Exception:
                            pass
                        continue

            except Exception as e:  # noqa: BLE001
                _check_and_raise_specific_error(str(e), platform)
                last_error = e
                logger.warning("❌ Strategy '%s' failed: %s: %s", sname, type(e).__name__, e)
                continue

        if fallback_candidate is not None:
            logger.warning(
                "All strategies completed. Returning best available resolution %sp: %s",
                fallback_candidate[1],
                fallback_candidate[0],
            )
            return fallback_candidate[0], actual_segment_offset

        raise RuntimeError(
            f"All video download strategies failed for {platform}. Last error: {last_error}"
        )

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


download_media_video = download_youtube_video


def get_media_info(vurl: str) -> dict:
    """Extract metadata (duration, fps, width, height, title) without downloading the video."""
    import tempfile
    import yt_dlp

    cleaned_url, platform = sanitize_source_url(vurl)

    with tempfile.TemporaryDirectory() as tmpdir:
        cookies_path = write_cookies_file(tmpdir)
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        if platform == "youtube":
            ydl_opts["extractor_args"] = {
                "youtube": {
                    "player_client": ["android_vr", "mweb", "web"],
                }
            }
            if cookies_path:
                ydl_opts["cookiefile"] = cookies_path

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(cleaned_url, download=False)
                return {
                    "duration": info.get("duration"),
                    "fps": info.get("fps") or 25.0,
                    "width": info.get("width") or 1280,
                    "height": info.get("height") or 720,
                    "title": info.get("title") or f"{platform.replace('_', ' ').title()} Video",
                    "platform": platform,
                }
        except Exception as e:
            logger.warning("Failed to extract media info via yt_dlp for %s: %s", platform, e)
            _check_and_raise_specific_error(str(e), platform)
            return {"fps": 25.0, "width": 1280, "height": 720, "platform": platform}


get_youtube_info = get_media_info