"""Multi-signal sentence-aware heuristic engine for viral clip discovery.

Acts as a reliable, fast fallback when Gemini is unavailable or rate-limited.
Uses sentence boundary alignment, filler pruning, speech velocity spikes,
acoustic events (applause, laughter), sentiment analysis, and conclusion scoring.
"""

from __future__ import annotations

import logging

from sentence_utils import (
    build_clip_words,
    calculate_sweet_spot_clip_count,
    clips_overlap_too_much,
    detect_content_mode,
    prune_leading_fillers,
    score_sentence_conclusion,
    score_sentence_hook,
)
from viral_constants import WEAK_ENDING_WORDS

logger = logging.getLogger("makemyclip.viral_heuristics")


def generate_sentence_candidates(
    sentences: list[dict],
    words: list[dict],
    sentiments: list,
    acoustic_events: list,
    highlights: list,
    velocity_timeline: list,
    chapters: list | None = None,
) -> list[dict]:
    """Generate candidates from multi-sentence windows strictly aligned to sentence boundaries.

    Content-mode-aware: scoring adapts to solo vs dialogue vs panel content.
    """
    if not sentences:
        return []

    candidates: list[dict] = []
    avg_wpm = (
        sum(v["wpm"] for v in velocity_timeline) / len(velocity_timeline)
        if velocity_timeline else 160.0
    )

    content_mode = detect_content_mode(sentences)
    logger.info("Heuristic engine content mode: %s", content_mode)

    n_sentences = len(sentences)

    for i in range(n_sentences):
        cur_start_sent = sentences[i]
        start_sec = cur_start_sent["start"]

        # Check multi-sentence windows of 18 to 65 seconds (up to 28 sentences for snappy dialogue)
        for j in range(i + 1, min(i + 28, n_sentences)):
            cur_end_sent = sentences[j]
            raw_dur = cur_end_sent["end"] - start_sec

            if raw_dur < 18.0:
                continue
            if raw_dur > 65.0:
                break

            # Prune fillers from start
            sub_words = [
                w for w in words
                if w["start"] >= start_sec - 0.05 and w["end"] <= cur_end_sent["end"] + 0.05
            ]
            pruned_start, pruned_words = prune_leading_fillers(sub_words)
            dur = cur_end_sent["end"] - pruned_start

            if not (18.0 <= dur <= 65.0):
                continue

            c_s_ms = int(round(pruned_start * 1000))
            c_e_ms = int(round(cur_end_sent["end"] * 1000))

            # --- Scoring signals ---
            base_score = 7.2

            # 1. Opening hook score (universal — all modes benefit from strong hooks)
            hook_score = score_sentence_hook(cur_start_sent["text"])
            base_score += hook_score

            # 2. Content-mode-specific scoring
            window_speakers = set(
                sentences[k].get("speaker") for k in range(i, j + 1)
                if sentences[k].get("speaker") is not None
            )
            turns = sum(
                1 for k in range(i, j)
                if sentences[k].get("speaker") != sentences[k + 1].get("speaker")
            )

            if content_mode == "solo":
                # ── Solo mode: reward emotional intensity, pacing shifts, and story arcs ──

                # 2a. Emotional intensity from sentiments (replaces speaker-turn bonus)
                w_sent = [
                    s for s in sentiments
                    if int(s["start"] * 1000) >= c_s_ms and int(s["end"] * 1000) <= c_e_ms
                ]
                non_neutral = [s for s in w_sent if s.get("sentiment") != "NEUTRAL"]
                high_conf = [s for s in non_neutral if s.get("confidence", 0) > 0.7]
                if high_conf:
                    base_score += min(0.8, len(high_conf) * 0.2)
                elif non_neutral:
                    base_score += min(0.5, len(non_neutral) * 0.15)

                # 2b. Pacing shift (speech velocity spike = excitement/emphasis)
                w_vel = [
                    v for v in velocity_timeline
                    if v["window_start_ms"] >= c_s_ms and v["window_end_ms"] <= c_e_ms
                ]
                if w_vel:
                    max_wpm = max(v["wpm"] for v in w_vel)
                    min_wpm = min(v["wpm"] for v in w_vel)
                    if max_wpm > avg_wpm * 1.4:
                        base_score += 0.4  # Strong excitement indicator
                    elif max_wpm > avg_wpm * 1.2:
                        base_score += 0.2
                    # Velocity contrast within the clip (dynamic delivery)
                    if min_wpm > 0 and max_wpm / min_wpm > 1.6:
                        base_score += 0.3

                # 2c. Story arc detection (hook phrase at start + conclusion at end)
                has_hook = hook_score > 0.5
                conclusion_score = score_sentence_conclusion(cur_end_sent["text"])
                if has_hook and conclusion_score > 0.4:
                    base_score += 0.5  # Complete narrative arc bonus

                # 2d. Rhetorical patterns (questions followed by answers — self-Q&A)
                window_texts = [sentences[k]["text"] for k in range(i, j + 1)]
                has_question = any(t.strip().endswith("?") for t in window_texts[:3])
                has_answer_after = any(not t.strip().endswith("?") for t in window_texts[1:4])
                if has_question and has_answer_after:
                    base_score += 0.3

            else:
                # ── Dialogue/Panel mode: keep speaker-turn scoring ──
                if len(window_speakers) > 1:
                    base_score += min(0.8, 0.3 + turns * 0.15)

                # Sentiments for dialogue/panel
                w_sent = [
                    s for s in sentiments
                    if int(s["start"] * 1000) >= c_s_ms and int(s["end"] * 1000) <= c_e_ms
                ]
                non_neutral = [s for s in w_sent if s.get("sentiment") != "NEUTRAL"]
                if non_neutral:
                    base_score += min(0.6, len(non_neutral) * 0.15)
                labels = {s.get("sentiment") for s in non_neutral}
                if "POSITIVE" in labels and "NEGATIVE" in labels:
                    base_score += 0.4  # Sentiment contrast = debate/tension

                # Pacing for dialogue/panel
                w_vel = [
                    v for v in velocity_timeline
                    if v["window_start_ms"] >= c_s_ms and v["window_end_ms"] <= c_e_ms
                ]
                if w_vel:
                    max_wpm = max(v["wpm"] for v in w_vel)
                    if max_wpm > avg_wpm * 1.3:
                        base_score += 0.3

            # 3. Acoustic events (laughter, applause) — universal signal
            w_acst = [
                e for e in acoustic_events
                if e["start_ms"] >= c_s_ms and e["end_ms"] <= c_e_ms
            ]
            if w_acst:
                base_score += min(0.6, len(w_acst) * 0.3)

            # 4. Highlights — universal signal
            w_hl = [
                h for h in highlights
                if any(
                    int(t["start"] * 1000) >= c_s_ms and int(t["end"] * 1000) <= c_e_ms
                    for t in h.get("timestamps", [])
                )
            ]
            if w_hl:
                base_score += min(0.5, len(w_hl) * 0.15)

            # 5. Ending quality score (penalize weak endings, reward strong ones)
            conclusion_quality = score_sentence_conclusion(cur_end_sent["text"])
            if conclusion_quality >= 0.6:
                base_score += 0.4  # Strong satisfying ending
            elif conclusion_quality >= 0.3:
                base_score += 0.15  # Decent ending
            elif conclusion_quality == 0.0:
                last_word = cur_end_sent["text"].split()[-1].strip().lower().rstrip(".,!?;:") if cur_end_sent["text"].split() else ""
                if last_word in WEAK_ENDING_WORDS:
                    base_score -= 0.3  # Penalize trailing conjunction/preposition endings

            final_score = round(max(1.0, min(9.9, base_score)), 1)

            first_words = [w["word"].strip() for w in pruned_words[:6]] if pruned_words else cur_start_sent["text"].split()[:6]
            headline = " ".join(first_words) if first_words else "Viral Highlight"

            candidates.append({
                "start_sec": pruned_start,
                "end_sec": cur_end_sent["end"],
                "start_ms": c_s_ms,
                "end_ms": c_e_ms,
                "duration_seconds": round(dur, 2),
                "headline": headline,
                "summary": cur_start_sent["text"],
                "gist": headline,
                "hook_quote": "WATCH THIS",
                "viral_score": final_score,
                "speakers_count": len(window_speakers),
                "turns_count": turns,
                "conclusion_quality": conclusion_quality,
            })

    return candidates


def score_and_rank_short_clips(
    sentiments: list,
    acoustic_events: list,
    highlights: list,
    velocity_timeline: list,
    words: list,
    sentences: list[dict],
    total_duration_sec: float,
    chapters: list | None = None,
) -> list[dict]:
    """Multi-signal sentence-aware engine (Fallback if Gemini is unavailable)."""
    target_count = calculate_sweet_spot_clip_count(total_duration_sec)

    candidates = generate_sentence_candidates(
        sentences=sentences,
        words=words,
        sentiments=sentiments,
        acoustic_events=acoustic_events,
        highlights=highlights,
        velocity_timeline=velocity_timeline,
        chapters=chapters,
    )

    if not candidates:
        return []

    # Greedy diversity selection with proximity penalty
    pool = sorted(candidates, key=lambda c: c["viral_score"], reverse=True)
    min_gap_sec = max(30.0, total_duration_sec / (target_count * 1.5))
    selected: list[dict] = []

    for _ in range(target_count):
        if not pool:
            break

        best_idx, best_eff = -1, -1.0
        for idx, cand in enumerate(pool):
            # Check overlap with already selected
            if any(clips_overlap_too_much(cand["start_sec"], cand["end_sec"], sel["start_sec"], sel["end_sec"]) for sel in selected):
                continue

            eff = cand["viral_score"]
            for sel in selected:
                dist = abs(cand["start_sec"] - sel["start_sec"])
                if dist < min_gap_sec:
                    eff -= 1.5 * (1.0 - dist / min_gap_sec)

            if eff > best_eff:
                best_eff = eff
                best_idx = idx

        if best_idx >= 0:
            selected.append(pool.pop(best_idx))

    selected.sort(key=lambda c: c["start_sec"])

    out: list[dict] = []
    for i, c in enumerate(selected):
        c_id = f"short_clip_{i + 1}"
        out.append({
            "id": c_id,
            "type": "short",
            "headline": c["headline"],
            "title": c["headline"],
            "gist": c["gist"],
            "summary": c["summary"],
            "description": c["summary"],
            "hook_quote": c["hook_quote"],
            "hookText": c["hook_quote"],
            "start_ms": c["start_ms"],
            "end_ms": c["end_ms"],
            "start_sec": c["start_sec"],
            "end_sec": c["end_sec"],
            "startTime": c["start_sec"],
            "endTime": c["end_sec"],
            "duration_seconds": c["duration_seconds"],
            "viral_score": c["viral_score"],
            "viralScore": c["viral_score"],
            "viralReason": "Multi-signal audio intelligence peak (sentence-aligned)",
            "hashtags": "#shorts #viral #podcast",
            "clipType": "hot_take",
            "is_shorts_ready": True,
            "words": build_clip_words(words, c["start_ms"], c["end_ms"]),
            "signals": {
                "source": "multi_signal_fallback",
                "pacing_note": "Multi-signal scored (sentence-aligned)",
            },
        })

    return out
