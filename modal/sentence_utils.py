"""Sentence-level utilities for viral clip extraction.

Sentence segmentation, filler pruning, quote matching, content-mode detection,
hook/conclusion scoring, signal extraction, and clip word building.
"""

from __future__ import annotations

import logging
import re

from viral_constants import (
    CONCLUSION_INDICATORS,
    FILLER_WORDS,
    HOOK_INDICATORS,
    LEADING_CONNECTORS,
    WEAK_ENDING_WORDS,
)

logger = logging.getLogger("makemyclip.sentence_utils")


# ═══════════════════════════════════════════════════════════════════════════════
# SENTENCE SEGMENTATION & FILLER PRUNING
# ═══════════════════════════════════════════════════════════════════════════════


def build_sentence_stream(words: list[dict]) -> list[dict]:
    """Segment words into grammatical sentence units with timing and speaker metadata."""
    if not words:
        return []

    sentences: list[dict] = []
    current_words: list[dict] = []

    for i, w in enumerate(words):
        current_words.append(w)
        text = w["word"].rstrip().rstrip("\"')}]")
        is_punct = text.endswith((".", "?", "!"))

        is_long_pause = False
        is_speaker_turn = False
        if i < len(words) - 1:
            gap = words[i + 1]["start"] - w["end"]
            if gap > 0.65:
                is_long_pause = True
            if (
                w.get("speaker") is not None
                and words[i + 1].get("speaker") is not None
                and w.get("speaker") != words[i + 1].get("speaker")
            ):
                is_speaker_turn = True

        # Split sentence on punctuation, speaker turn, pause gap, or length safeguard
        is_clause_split = len(current_words) >= 25 and (text.endswith((",", ";", ":")) or is_long_pause)
        is_runaway_split = len(current_words) >= 38

        if (
            is_punct
            or (is_speaker_turn and len(current_words) >= 3)
            or (is_long_pause and len(current_words) >= 4)
            or is_clause_split
            or is_runaway_split
        ):
            s_text = " ".join(cw["word"] for cw in current_words).strip()
            if s_text:
                sentences.append({
                    "index": len(sentences),
                    "text": s_text,
                    "start": current_words[0]["start"],
                    "end": current_words[-1]["end"],
                    "start_ms": int(round(current_words[0]["start"] * 1000)),
                    "end_ms": int(round(current_words[-1]["end"] * 1000)),
                    "speaker": current_words[0].get("speaker"),
                    "words": current_words,
                })
            current_words = []

    if current_words:
        s_text = " ".join(cw["word"] for cw in current_words).strip()
        if s_text:
            sentences.append({
                "index": len(sentences),
                "text": s_text,
                "start": current_words[0]["start"],
                "end": current_words[-1]["end"],
                "start_ms": int(round(current_words[0]["start"] * 1000)),
                "end_ms": int(round(current_words[-1]["end"] * 1000)),
                "speaker": current_words[0].get("speaker"),
                "words": current_words,
            })

    return sentences


def normalize_common_stt_homophones(text: str) -> str:
    """Normalize common speech-to-text capitalization/homophone errors in transcript text."""
    if not text:
        return text
    # Fix "PI" -> "pie" in economic/metaphorical contexts
    text = re.sub(
        r"\b(economic|the|more|fixed|their|our|of|a|lot\s+of|grow(?:ing)?\s+the|grow(?:ing)?\s+that|slice\s+of|someone\s+else(?:'s)?)\s+PI\b",
        r"\1 pie",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bPI\s+(is\s+not\s+fixed|has\s+grown|myth|grows|size)\b",
        r"pie \1",
        text,
        flags=re.IGNORECASE,
    )
    return text



def prune_leading_fillers(clip_words: list[dict]) -> tuple[float, list[dict]]:
    """Prune conversational filler words and leading transition connectors from the start of a clip."""
    if not clip_words or len(clip_words) <= 5:
        return (clip_words[0]["start"] if clip_words else 0.0, clip_words)

    start_idx = 0
    # Pass 1: Prune individual filler words
    while start_idx < min(4, len(clip_words) - 5):
        clean_word = clip_words[start_idx]["word"].strip().lower().rstrip(".,!?")
        if clean_word in FILLER_WORDS:
            start_idx += 1
        else:
            break

    # Pass 2: Check for multi-word leading connectors (e.g. "more important,", "on top of that,")
    remaining = clip_words[start_idx:]
    if len(remaining) >= 6:
        for n_words in (4, 3, 2):
            if len(remaining) > n_words + 3:
                phrase = " ".join(w["word"].strip().lower().rstrip(".,!?") for w in remaining[:n_words])
                if phrase in LEADING_CONNECTORS:
                    start_idx += n_words
                    # Prune any trailing filler immediately following the connector (e.g. "More important, um, when...")
                    while start_idx < min(start_idx + 3, len(clip_words) - 4):
                        cw = clip_words[start_idx]["word"].strip().lower().rstrip(".,!?")
                        if cw in FILLER_WORDS:
                            start_idx += 1
                        else:
                            break
                    break

    pruned = clip_words[start_idx:]
    return (pruned[0]["start"], pruned)


# ═══════════════════════════════════════════════════════════════════════════════
# QUOTE MATCHING & CLIP OVERLAP
# ═══════════════════════════════════════════════════════════════════════════════


def _clean_text_for_matching(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", "", (text or "").lower()).strip()


def find_matching_sentence(
    quote: str,
    target_time: float,
    sentences: list[dict],
    is_start: bool = True,
    search_window_sec: float = 60.0,
) -> int:
    """Find the best sentence index matching a quote near target_time, with global fallback."""
    if not sentences:
        return 0

    clean_quote = _clean_text_for_matching(quote)
    quote_tokens = set(clean_quote.split()) if clean_quote else set()

    # 1. Proximity-window search (within search_window_sec)
    candidates = []
    for idx, s in enumerate(sentences):
        t = s["start"] if is_start else s["end"]
        diff = abs(t - target_time)
        if diff <= search_window_sec:
            s_clean = _clean_text_for_matching(s["text"])
            score = 0.0
            if clean_quote and clean_quote in s_clean:
                score = 4.0
            elif quote_tokens:
                s_tokens = set(s_clean.split())
                overlap = len(quote_tokens & s_tokens)
                if overlap > 0:
                    score = (overlap / max(1, len(quote_tokens))) * 2.0
            candidates.append((score, -diff, idx))

    if candidates:
        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        if candidates[0][0] > 0.4:
            return candidates[0][2]

    # 2. Global quote substring search across all sentences if quote is substantial
    if clean_quote and len(clean_quote.split()) >= 3:
        for idx, s in enumerate(sentences):
            s_clean = _clean_text_for_matching(s["text"])
            if clean_quote in s_clean:
                return idx

    # 3. Proximity fallback
    best_idx = 0
    best_dist = float("inf")
    for idx, s in enumerate(sentences):
        t = s["start"] if is_start else s["end"]
        dist = abs(t - target_time)
        if dist < best_dist:
            best_dist = dist
            best_idx = idx

    return best_idx


def clips_overlap_too_much(
    s1: float, e1: float, s2: float, e2: float, max_overlap_ratio: float = 0.35
) -> bool:
    """Check if two clip intervals overlap by more than max_overlap_ratio of the shorter clip."""
    overlap_start = max(s1, s2)
    overlap_end = min(e1, e2)
    overlap = max(0.0, overlap_end - overlap_start)
    if overlap <= 0:
        return False
    min_dur = min(e1 - s1, e2 - s2)
    if min_dur <= 0:
        return True
    return (overlap / min_dur) > max_overlap_ratio


# ═══════════════════════════════════════════════════════════════════════════════
# CONTENT MODE & SCORING
# ═══════════════════════════════════════════════════════════════════════════════


def detect_content_mode(sentences: list[dict]) -> str:
    """Detect whether content is solo, dialogue, or panel based on speaker distribution.

    Returns:
        "solo"     – >=85% of sentences from one speaker (vlogs, monologues, tutorials)
        "dialogue" – 2 speakers (interviews, podcasts)
        "panel"    – 3+ speakers (roundtable, group discussions)
    """
    if not sentences:
        return "solo"

    speaker_counts: dict[int | None, int] = {}
    for s in sentences:
        spk = s.get("speaker")
        speaker_counts[spk] = speaker_counts.get(spk, 0) + 1

    # Exclude None speakers from counting
    known_speakers = {k: v for k, v in speaker_counts.items() if k is not None}
    if not known_speakers:
        return "solo"

    total = sum(known_speakers.values())
    max_count = max(known_speakers.values())
    num_speakers = len(known_speakers)

    if num_speakers >= 3:
        return "panel"
    if num_speakers == 2 and (max_count / total) < 0.85:
        return "dialogue"
    return "solo"


def score_sentence_conclusion(text: str) -> float:
    """Evaluate how satisfying a sentence is as a clip ending (0.0 to 1.0).

    High scores for punchlines, summary statements, emphatic closers.
    Low/negative scores for trailing conjunctions and incomplete thoughts.
    """
    clean = text.lower().strip().rstrip("\"')}]")
    score = 0.0

    # Check for conclusion indicator phrases
    for phrase in CONCLUSION_INDICATORS:
        if phrase in clean:
            score += 0.7
            break

    # Exclamation marks suggest emphatic closure
    if clean.endswith("!"):
        score += 0.3

    # Question marks can be strong endings (rhetorical) or weak (unanswered)
    # Treat as mildly positive — the context decides
    if clean.endswith("?"):
        score += 0.1

    # Check if final word is a weak/incomplete signal
    last_word = clean.split()[-1].rstrip(".,!?;:") if clean.split() else ""
    if last_word in WEAK_ENDING_WORDS:
        score -= 0.5

    # Sentences ending with strong nouns/adjectives tend to feel conclusive
    # (heuristic: longer last word = more likely a content word, not a function word)
    if len(last_word) >= 6 and last_word not in WEAK_ENDING_WORDS:
        score += 0.15

    return max(0.0, min(1.0, score))


def score_sentence_hook(text: str) -> float:
    """Evaluate hook power of an opening sentence (0.0 to 1.5 pts)."""
    clean = text.lower().strip()
    score = 0.0

    # Question mark indicates curiosity hook
    if clean.endswith("?"):
        score += 0.8

    # Check for hook phrases
    for hook in HOOK_INDICATORS:
        if hook in clean:
            score += 0.7
            break

    # Contrast word at start (e.g. "But the real reason...")
    first_word = clean.split()[0] if clean.split() else ""
    if first_word in {"but", "however", "actually", "honestly", "listen"}:
        score += 0.3

    return min(1.5, score)


# ═══════════════════════════════════════════════════════════════════════════════
# SIGNAL EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════


def calculate_speech_velocity(words: list, window_seconds: float = 5.0) -> list[dict]:
    if not words:
        return []
    min_time = words[0]["start"]
    max_time = words[-1]["end"]
    timeline = []
    current_time = min_time
    step = 2.5
    while current_time < max_time:
        win_start = current_time
        win_end = current_time + window_seconds
        win_words = [w for w in words if w["start"] >= win_start and w["end"] <= win_end]
        count = len(win_words)
        wpm = (count / window_seconds) * 60.0
        timeline.append({
            "window_start_ms": int(win_start * 1000),
            "window_end_ms": int(win_end * 1000),
            "word_count": count,
            "wpm": round(wpm, 1),
        })
        current_time += step
    return timeline


def extract_acoustic_events(words: list, full_text: str) -> list[dict]:
    pattern = re.compile(r"\[(laughter|cheering|gasp|applause|sigh)\]", re.IGNORECASE)
    events = []
    for w in words:
        match = pattern.search(w["word"])
        if match:
            events.append({
                "event": match.group(1).lower(),
                "text": w["word"],
                "start_ms": int(w["start"] * 1000),
                "end_ms": int(w["end"] * 1000),
                "speaker": w.get("speaker"),
            })
    return events


def build_clip_words(words: list, start_ms: int, end_ms: int) -> list[dict]:
    """Extract words within a clip range, rebase timestamps to clip-relative, and normalize common STT errors."""
    start_sec = start_ms / 1000.0
    sub_words = [w for w in words if start_ms <= int(w["start"] * 1000) <= end_ms]
    out = []
    for idx, w in enumerate(sub_words):
        raw_word = w["word"].strip()
        p_word = raw_word
        # Contextual normalization: "PI" -> "pie" when following economic / fixed / more / the / a / of
        if raw_word.rstrip(".,!?;:").upper() == "PI":
            prev_raw = sub_words[idx - 1]["word"].strip().lower().rstrip(".,!?;:") if idx > 0 else ""
            if prev_raw in {"economic", "the", "more", "fixed", "their", "of", "a", "lot"}:
                suffix = ""
                for char in reversed(raw_word):
                    if char in ".,!?;:'\"":
                        suffix = char + suffix
                    else:
                        break
                p_word = "pie" + suffix
                raw_word = "pie" + suffix

        out.append({
            "word": raw_word.lower(),
            "punctuated_word": p_word,
            "start": round(max(0.0, w["start"] - start_sec), 3),
            "end": round(max(0.05, w["end"] - start_sec), 3),
            "confidence": round(w.get("confidence", 0.99), 3),
            "speaker": str(w.get("speaker", 0)),
        })
    return out



def calculate_sweet_spot_clip_count(total_duration_sec: float) -> int:
    """Target clip count — generous pool so users have plenty of options."""
    duration_min = total_duration_sec / 60.0
    if duration_min <= 5:
        return 5
    elif duration_min <= 15:
        return 8
    elif duration_min <= 30:
        return 10
    elif duration_min <= 60:
        return 14
    elif duration_min <= 120:
        return 16
    else:
        return 18
