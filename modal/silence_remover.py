"""Silence Remover — detect and cut dead-air gaps from clips.

Uses word-level timestamps from transcription to identify silent gaps,
then uses FFmpeg to physically remove them while keeping a short natural
pause at each cut point.

Industry-standard thresholds (matches OpusClip / Vizard / Descript):
  - MIN_GAP_S = 0.4s  — only gaps > 0.4s are considered "silence"
  - KEEP_PAUSE_S = 0.12s — brief breath pause kept at each cut

Usage
-----
    from silence_remover import (
        detect_silent_gaps,
        build_silence_removed_segments,
        remove_silence_ffmpeg,
        remap_word_timestamps,
        remap_transcript_blocks,
    )
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass

logger = logging.getLogger("makemyclip.silence_remover")

# ── Tuning constants ──────────────────────────────────────────────────
MIN_GAP_S = 0.40      # Minimum gap duration to classify as "silence"
KEEP_PAUSE_S = 0.12   # Natural breath pause kept at each cut point
_FFMPEG_TIMEOUT_S = 600


@dataclass
class SilentGap:
    """A detected silent gap between words."""
    start: float   # seconds — end of previous word
    end: float     # seconds — start of next word
    duration: float

    def __repr__(self) -> str:
        return f"SilentGap({self.start:.2f}s–{self.end:.2f}s, {self.duration:.2f}s)"


def detect_silent_gaps(
    words: list[dict],
    min_gap_s: float = MIN_GAP_S,
) -> list[SilentGap]:
    """Scan word timestamps and return gaps exceeding *min_gap_s*.

    Parameters
    ----------
    words : list[dict]
        Word-level timestamps with ``start`` and ``end`` keys (in seconds).
    min_gap_s : float
        Minimum gap duration to report as silence.

    Returns
    -------
    list[SilentGap]
    """
    if not words or len(words) < 2:
        return []

    gaps: list[SilentGap] = []
    for i in range(len(words) - 1):
        gap_start = words[i]["end"]
        gap_end = words[i + 1]["start"]
        gap_dur = gap_end - gap_start
        if gap_dur > min_gap_s:
            gaps.append(SilentGap(start=gap_start, end=gap_end, duration=gap_dur))

    return gaps


@dataclass
class KeepSegment:
    """A contiguous time segment to keep in the output."""
    src_start: float
    src_end: float

    @property
    def duration(self) -> float:
        return self.src_end - self.src_start


def build_silence_removed_segments(
    words: list[dict],
    total_duration: float,
    min_gap_s: float = MIN_GAP_S,
    keep_pause_s: float = KEEP_PAUSE_S,
) -> list[KeepSegment]:
    """Build time segments to keep after removing silent gaps.

    Each silent gap is replaced by a short *keep_pause_s* pause.  The
    returned segments describe which source-timeline regions map into
    the output.

    Returns
    -------
    list[KeepSegment]
        Ordered list of segments from the source timeline to keep.
        An empty list means no silence was found (use original video).
    """
    gaps = detect_silent_gaps(words, min_gap_s=min_gap_s)
    if not gaps:
        return []

    segments: list[KeepSegment] = []
    cursor = 0.0

    for gap in gaps:
        # Keep everything from cursor to gap start + half the breath pause
        seg_end = gap.start + keep_pause_s / 2.0
        if seg_end > cursor:
            segments.append(KeepSegment(src_start=cursor, src_end=seg_end))
        # Jump over the gap, leaving a small pause before the next word
        cursor = gap.end - keep_pause_s / 2.0

    # Keep the tail (from last gap end to video end)
    if cursor < total_duration:
        segments.append(KeepSegment(src_start=cursor, src_end=total_duration))

    # Sanity: if we'd only save < 1s, skip removal entirely
    total_kept = sum(s.duration for s in segments)
    if total_kept < 1.0:
        logger.warning("Silence removal would leave < 1s of content. Skipping.")
        return []

    total_removed = total_duration - total_kept
    logger.info(
        "Silence removal: %d gaps found, removing %.1fs of %.1fs (%.0f%% reduction)",
        len(gaps),
        total_removed,
        total_duration,
        (total_removed / total_duration) * 100 if total_duration > 0 else 0,
    )

    return segments


def remove_silence_ffmpeg(
    input_video: str,
    output_video: str,
    segments: list[KeepSegment],
    fps: float = 25.0,
) -> bool:
    """Cut silent segments from *input_video* using FFmpeg concat demuxer.

    Creates individual trimmed segment files, then concatenates them into
    *output_video*.  This approach is the most reliable for frame-accurate
    cuts with proper audio sync.

    Returns True on success, False on failure (caller should fall back to
    the original video).
    """
    if not segments:
        return False

    tmpdir = tempfile.mkdtemp(prefix="silence_rm_")

    try:
        segment_files: list[str] = []

        # 1. Trim each segment into a separate file
        for i, seg in enumerate(segments):
            seg_path = os.path.join(tmpdir, f"seg_{i:04d}.mp4")
            segment_files.append(seg_path)

            cmd = [
                "ffmpeg", "-y",
                "-ss", f"{seg.src_start:.4f}",
                "-i", input_video,
                "-t", f"{seg.duration:.4f}",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-avoid_negative_ts", "make_zero",
                "-r", str(fps),
                seg_path,
                "-loglevel", "warning",
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=_FFMPEG_TIMEOUT_S
            )
            if result.returncode != 0:
                logger.error(
                    "Failed to trim segment %d (%.2f–%.2f): %s",
                    i, seg.src_start, seg.src_end, result.stderr[-500:]
                )
                return False

        # 2. Build concat file list
        concat_list = os.path.join(tmpdir, "concat.txt")
        with open(concat_list, "w") as f:
            for seg_path in segment_files:
                f.write(f"file '{seg_path}'\n")

        # 3. Concatenate
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-r", str(fps),
            output_video,
            "-loglevel", "warning",
        ]
        result = subprocess.run(
            concat_cmd, capture_output=True, text=True, timeout=_FFMPEG_TIMEOUT_S
        )
        if result.returncode != 0:
            logger.error("FFmpeg concat failed: %s", result.stderr[-500:])
            return False

        if not os.path.exists(output_video) or os.path.getsize(output_video) == 0:
            logger.error("Silence-removed output is empty or missing")
            return False

        logger.info(
            "Silence removal complete: %s (%.1f KB)",
            output_video,
            os.path.getsize(output_video) / 1024,
        )
        return True

    except subprocess.TimeoutExpired:
        logger.error("FFmpeg silence removal timed out after %ds", _FFMPEG_TIMEOUT_S)
        return False
    except Exception as e:
        logger.error("Silence removal failed: %s", e, exc_info=True)
        return False
    finally:
        # Clean up temp segment files
        import shutil
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


def remap_word_timestamps(
    words: list[dict],
    segments: list[KeepSegment],
) -> list[dict]:
    """Remap word timestamps from original timeline → silence-removed timeline.

    Words that fall inside a kept segment are shifted to their new position.
    Words that fall inside a removed gap are dropped (shouldn't happen in
    practice since gaps are between words, not during them).

    Parameters
    ----------
    words : list[dict]
        Original word-level timestamps with ``start``, ``end``, ``word`` keys.
    segments : list[KeepSegment]
        Segments from :func:`build_silence_removed_segments`.

    Returns
    -------
    list[dict]
        New word list with adjusted timestamps.
    """
    if not segments or not words:
        return words

    remapped: list[dict] = []
    output_cursor = 0.0  # running position in output timeline

    for seg in segments:
        seg_start = seg.src_start
        seg_end = seg.src_end

        for w in words:
            w_start = w["start"]
            w_end = w["end"]

            # Word must overlap with this segment
            if w_end <= seg_start or w_start >= seg_end:
                continue

            # Clamp word boundaries to segment
            clamped_start = max(w_start, seg_start)
            clamped_end = min(w_end, seg_end)

            # Map to output timeline
            new_start = output_cursor + (clamped_start - seg_start)
            new_end = output_cursor + (clamped_end - seg_start)

            remapped.append({
                **w,
                "start": round(new_start, 4),
                "end": round(new_end, 4),
            })

        output_cursor += seg.duration

    return remapped


def remap_transcript_blocks(
    transcript: list[dict],
    segments: list[KeepSegment],
) -> list[dict]:
    """Remap an entire transcript (caption blocks with nested words).

    Each block has ``start``, ``end``, and ``words`` (list of word dicts).
    This remaps both the block-level and word-level timestamps.

    Parameters
    ----------
    transcript : list[dict]
        Caption blocks (``ClipCaption`` format).
    segments : list[KeepSegment]
        Kept segments from :func:`build_silence_removed_segments`.

    Returns
    -------
    list[dict]
        Remapped transcript blocks.
    """
    if not segments or not transcript:
        return transcript

    remapped_blocks: list[dict] = []

    for block in transcript:
        block_words = block.get("words", [])
        if not block_words:
            remapped_blocks.append(block)
            continue

        # Remap individual words
        new_words = remap_word_timestamps(block_words, segments)
        if not new_words:
            continue

        # Recompute block start/end from remapped words
        new_block = {
            **block,
            "start": new_words[0]["start"],
            "end": new_words[-1]["end"],
            "words": new_words,
            "transcript": " ".join(w.get("punctuated_word", w.get("word", "")) for w in new_words),
        }
        remapped_blocks.append(new_block)

    return remapped_blocks
