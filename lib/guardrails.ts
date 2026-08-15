// ─── Generic Boundary Guardrails (replaces "Level 1000" hardcoded overrides) ──
//
// These rules detect STRUCTURAL PATTERNS in the transcript, not content from
// any specific video. They run on every clip, for every video, automatically.
//
// Pattern 1: "Stalled restart" — speaker derails / loses train of thought,
//            asker has to repeat their question verbatim (or near-verbatim)
//            before getting a real answer. Common in live, low-edit recordings.
// Pattern 2: "Unanswered prompt" — clip starts on a question/prompt that gets
//            deflected, cut off, or redirected instead of answered, and the
//            model (incorrectly) used the prompt itself as the hook.
// Pattern 3: "Weak trailing button" — clip ends on a low-content filler line
//            ("okay", "yeah", "or something") while a stronger payoff sentence
//            sits within a few seconds afterward, still on-topic.
//
// All three are detected from `sentences` shape/content, not from timestamps
// or indices specific to one transcript.

// ─── Shared helpers ─────────────────────────────────────────────────────────

const FILLER_ONLY_RE =
  /^[\s.,!?]*(yeah|yep|yup|okay|ok|right|um+|uh+|hmm+|so|well|like|or something|i mean)[\s.,!?]*$/i

const DEFLECTION_RE =
  /\b(can i switch|can i grab|hold on|cut that|let's not|i don't want to answer|can we not|next question|switch (the )?(camera|character|persona))\b/i

const FALSE_START_RE =
  /\b(i (said|did) (that|it|this) (backwards|wrong)|that('s| was) wrong|wait,? (no|let me)|hold on,? (let me|wait)|scratch that|i lost (my|the) (train of thought|question)|what was the question|i don't know why i('m| am) saying)\b/i

/** Normalizes text for fuzzy repeat-detection: lowercase, strip punctuation/filler words. */
function normalizeForRepeatCheck(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, "")
    .replace(/\b(um|uh|like|you know|i mean)\b/g, "")
    .replace(/\s+/g, " ")
    .trim()
}

/** Cheap similarity: word-overlap ratio. Good enough to catch "near-verbatim repeat". */
function similarity(a: string, b: string): number {
  const wa = new Set(normalizeForRepeatCheck(a).split(" ").filter(Boolean))
  const wb = new Set(normalizeForRepeatCheck(b).split(" ").filter(Boolean))
  if (wa.size === 0 || wb.size === 0) return 0
  let overlap = 0
  for (const w of wa) if (wb.has(w)) overlap++
  return overlap / Math.max(wa.size, wb.size)
}

// ─── Pattern 1: Stalled restart ─────────────────────────────────────────────
//
// Looks for: [askerSentence] ... [false-start/derail by responder] ...
// [askerSentence repeated, similarity above threshold]. If the clip's start
// index is the FIRST occurrence of the asker's line, and a near-duplicate of
// that same line exists later (before any real answer began), snap the clip
// to start at the near-duplicate instead — this drops the dead derail.
function fixStalledRestart(
  sentences: Sentence[],
  startIdx: number, // 0-based index into `sentences`
  endIdx: number
): { startIdx: number; note?: string } {
  const opener = sentences[startIdx]
  if (!opener) return { startIdx }

  // Look ahead within the clip's own window for a near-duplicate of the opener,
  // spoken by the same speaker as the opener, with a false-start/derail marker
  // from the OTHER speaker in between.
  let sawDerailMarker = false
  for (let i = startIdx + 1; i <= endIdx && i < sentences.length; i++) {
    const s = sentences[i]
    if (FALSE_START_RE.test(s.text)) {
      sawDerailMarker = true
      continue
    }
    if (
      sawDerailMarker &&
      s.speaker === opener.speaker &&
      similarity(s.text, opener.text) >= 0.7
    ) {
      // Found the clean restart — snap start here, drop the dead derail.
      return {
        startIdx: i,
        note: `Stalled restart detected: original opener (#${opener.index}) was followed by a derail/false-start, then repeated near-verbatim at #${s.index}. Clip now starts at the clean repeat.`,
      }
    }
  }
  return { startIdx }
}

// ─── Pattern 2: Unanswered prompt ───────────────────────────────────────────
//
// If the clip's opening sentence is itself a question/prompt (heuristically:
// from a different speaker than sentence[startIdx+1], ends in "?", or matches
// a deflection pattern in the very next line), and the next line deflects
// instead of answering, advance the start to the deflection/switch line.
function fixUnansweredPrompt(
  sentences: Sentence[],
  startIdx: number
): { startIdx: number; note?: string } {
  const opener = sentences[startIdx]
  const next = sentences[startIdx + 1]
  if (!opener || !next) return { startIdx }

  const openerIsPrompt = /\?\s*$/.test(opener.text.trim())
  const nextIsDeflection = DEFLECTION_RE.test(next.text)

  if (openerIsPrompt && nextIsDeflection && next.speaker !== opener.speaker) {
    return {
      startIdx: startIdx + 1,
      note: `Unanswered prompt detected: opener (#${opener.index}) was a question that got deflected/redirected rather than answered. Clip now starts on the deflection itself (#${next.index}).`,
    }
  }
  return { startIdx }
}

// ─── Pattern 3: Weak trailing button ────────────────────────────────────────
//
// If the clip's last sentence is filler-only (or very short, < 4 content words)
// AND a stronger, longer, on-topic sentence from the main speaker exists within
// a small lookahead window (same speaker continuing, or a short reaction then
// the main speaker resuming), extend the end to include it.
function fixWeakTrailingButton(
  sentences: Sentence[],
  startIdx: number,
  endIdx: number,
  maxLookahead = 4,
  maxExtraSeconds = 20,
  maxTrimBack = 4
): { endIdx: number; note?: string } {
  const closer = sentences[endIdx]
  const opener = sentences[startIdx]
  if (!closer || !opener) return { endIdx }

  const isWeak = (s: Sentence) => {
    const wc = s.text.trim().split(/\s+/).length
    return FILLER_ONLY_RE.test(s.text.trim()) || wc <= 4
  }

  if (!isWeak(closer)) return { endIdx }

  // The clip's "main speaker" is whichever speaker said the most inside the
  // current window — payoffs belong to them, not to whoever asks the next
  // unrelated question.
  const speakerWordCounts = new Map<number | null, number>()
  for (let i = startIdx; i <= endIdx && i < sentences.length; i++) {
    const s = sentences[i]
    const wc = s.text.trim().split(/\s+/).length
    speakerWordCounts.set(
      s.speaker,
      (speakerWordCounts.get(s.speaker) ?? 0) + wc
    )
  }
  let mainSpeaker: number | null = closer.speaker
  let maxWords = -1
  for (const [spk, wc] of speakerWordCounts) {
    if (wc > maxWords) {
      maxWords = wc
      mainSpeaker = spk
    }
  }

  // Pass A — TRIM BACK: a run of trailing weak/filler lines may be sitting
  // on top of a perfectly good payoff that's already inside the clip. Walk
  // backward from the closer; if we find a substantial main-speaker line
  // within a short distance, that's the real ending — use it instead of
  // reaching forward for new content.
  for (
    let i = endIdx - 1, steps = 0;
    i > startIdx && steps < maxTrimBack;
    i--, steps++
  ) {
    const candidate = sentences[i]
    if (isWeak(candidate)) continue // keep walking back past more filler
    if (candidate.speaker === mainSpeaker) {
      return {
        endIdx: i,
        note: `Weak trailing button detected: closer (#${closer.index}, "${closer.text.trim()}") and ${steps} preceding line(s) were filler. Trimmed end back to #${candidate.index}, the last substantive line from the main speaker, which was already inside the original clip.`,
      }
    }
    break // hit a substantial line from the OTHER speaker — stop, don't trim past it
  }

  // Pass B — EXTEND FORWARD: no good payoff was already inside the clip,
  // so look just past the current end for one, same rules as before.
  for (
    let i = endIdx + 1;
    i < sentences.length && i <= endIdx + maxLookahead;
    i++
  ) {
    const candidate = sentences[i]
    if (candidate.start - closer.end > maxExtraSeconds) break // too far away, stop looking

    const looksLikeNewQuestion = /\?\s*$/.test(candidate.text.trim())
    if (candidate.speaker !== mainSpeaker && looksLikeNewQuestion) break

    if (!isWeak(candidate) && candidate.speaker === mainSpeaker) {
      return {
        endIdx: i,
        note: `Weak trailing button detected: original closer (#${closer.index}) was filler-only ("${closer.text.trim()}"), and no stronger line was found earlier in the clip. Extended end to #${candidate.index}, a substantive follow-up from the clip's main speaker within ${(candidate.end - closer.end).toFixed(1)}s.`,
      }
    }
  }
  return { endIdx }
}

// ─── Pattern 4: Reasoning mismatch ──────────────────────────────────────────
//
// Detects if the AI's written reasoning (resolution or boundary validation)
// describes or quotes a sentence slightly ahead of the returned end index,
// and extends the boundary to match the intended payoff.
function fixReasoningMismatches(
  sentences: Sentence[],
  endIdx: number,
  resolutionText?: string,
  endValidationText?: string
): { endIdx: number; note?: string } {
  const originalEnd = endIdx

  // Method 1: Semantic quote/text matching
  if (resolutionText) {
    const cleanResolution = resolutionText.toLowerCase()
    for (let i = endIdx + 1; i <= endIdx + 5 && i < sentences.length; i++) {
      const s = sentences[i]
      const cleanSent = s.text
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, "")
        .trim()
      if (cleanSent.length > 3 && cleanResolution.includes(cleanSent)) {
        endIdx = i
      }
    }
  }

  // Method 2: Regex index matching (e.g. "sentence 166")
  if (endIdx === originalEnd && endValidationText) {
    const rx = /sentence\s+#?(\d+)/gi
    let match
    while ((match = rx.exec(endValidationText)) !== null) {
      const num = parseInt(match[1], 10)
      if (!isNaN(num)) {
        const targetIdx = num - 1
        if (
          targetIdx > endIdx &&
          targetIdx <= endIdx + 5 &&
          targetIdx < sentences.length
        ) {
          endIdx = targetIdx
        }
      }
    }
  }

  if (endIdx !== originalEnd) {
    const oldSent = sentences[originalEnd]
    const newSent = sentences[endIdx]
    return {
      endIdx,
      note: `Reasoning mismatch fixed: reasoning text referenced or quoted sentence #${newSent.index} ("${newSent.text.trim()}"), extending end from #${oldSent.index} to #${newSent.index}.`,
    }
  }

  return { endIdx }
}

// ─── Pattern 5: Leading filler header trimmer ─────────────────────────────────
//
// If the clip's starting sentence is a low-value intro filler ("so basically",
// "like I said", "you know", "well", "now"), and sentence[startIdx + 1] is a
// stronger, self-contained statement, snap startIdx to startIdx + 1 to drop
// throat-clearing fillers.
const LEADING_FILLER_HEADER_RE =
  /^[\s.,!?]*(so|well|like|you know|i mean|so basically|like i said|now|right|anyway|um+|uh+|look|listen)[\s.,!?]*/i

function fixLeadingFillerHeader(
  sentences: Sentence[],
  startIdx: number,
  endIdx: number
): { startIdx: number; note?: string } {
  if (startIdx >= endIdx || startIdx >= sentences.length - 1) return { startIdx }

  const opener = sentences[startIdx]
  const next = sentences[startIdx + 1]
  if (!opener || !next) return { startIdx }

  const openerWordCount = opener.text.trim().split(/\s+/).length
  const openerIsFiller =
    FILLER_ONLY_RE.test(opener.text.trim()) ||
    (openerWordCount <= 5 && LEADING_FILLER_HEADER_RE.test(opener.text.trim()))

  const nextIsSubstantive = next.text.trim().split(/\s+/).length >= 4

  if (openerIsFiller && nextIsSubstantive) {
    return {
      startIdx: startIdx + 1,
      note: `Leading filler header trimmed: opener (#${opener.index}, "${opener.text.trim()}") was low-value throat-clearing filler. Clip now starts directly on clean hook (#${next.index}).`,
    }
  }

  return { startIdx }
}

// ─── Pattern 6: High-energy speaker switch payoff alignment ─────────────
//
// If clip ends on a setup or question by Speaker A, and Speaker B reacts or
// gives a punchy mic-drop line within 3 seconds right after, extend endIdx to
// include Speaker B's payoff line.
function fixSpeakerSwitchPayoff(
  sentences: Sentence[],
  startIdx: number,
  endIdx: number
): { endIdx: number; note?: string } {
  if (endIdx >= sentences.length - 1) return { endIdx }

  const closer = sentences[endIdx]
  const next = sentences[endIdx + 1]
  if (!closer || !next) return { endIdx }

  const endsWithQuestion = /\?\s*$/.test(closer.text.trim())
  const speakerSwitched = next.speaker !== null && closer.speaker !== null && next.speaker !== closer.speaker
  const timingGap = next.start - closer.end
  const nextWordCount = next.text.trim().split(/\s+/).length

  const isEligible =
    timingGap <= 3.0 &&
    ((endsWithQuestion && nextWordCount >= 3 && nextWordCount <= 25) ||
      (speakerSwitched && timingGap <= 2.0 && nextWordCount >= 2 && nextWordCount <= 12))

  if (isEligible) {
    return {
      endIdx: endIdx + 1,
      note: `Speaker switch payoff aligned: extended clip end to include reaction/answer (#${next.index}, "${next.text.trim()}") from Speaker ${next.speaker ?? "0"}.`,
    }
  }

  return { endIdx }
}

// ─── Public entry point ─────────────────────────────────────────────────────

export interface GuardrailResult {
  startIdx: number
  endIdx: number
  notes: string[]
}

/**
 * Applies all structural guardrails to a clip's sentence-index range.
 * Pure function of (sentences, startIdx, endIdx) — works identically on
 * ANY transcript, since detection is based on linguistic patterns
 * (false starts, repeats, filler, deflection), never on hardcoded content,
 * sentence numbers, or timestamps from a specific video.
 */
export function applyBoundaryGuardrails(
  sentences: Sentence[],
  startIdx: number,
  endIdx: number,
  resolutionText = "",
  endValidationText = ""
): GuardrailResult {
  const notes: string[] = []

  const { startIdx: s0, note: n0 } = fixLeadingFillerHeader(sentences, startIdx, endIdx)
  if (n0) notes.push(n0)

  const { startIdx: s1, note: n1 } = fixUnansweredPrompt(sentences, s0)
  if (n1) notes.push(n1)

  const { startIdx: s2, note: n2 } = fixStalledRestart(sentences, s1, endIdx)
  if (n2) notes.push(n2)

  const { endIdx: e1, note: n3 } = fixWeakTrailingButton(sentences, s2, endIdx)
  if (n3) notes.push(n3)

  const { endIdx: e2, note: n4 } = fixReasoningMismatches(
    sentences,
    e1,
    resolutionText,
    endValidationText
  )
  if (n4) notes.push(n4)

  const { endIdx: e3, note: n5 } = fixSpeakerSwitchPayoff(sentences, s2, e2)
  if (n5) notes.push(n5)

  // Safety: never let start cross end after adjustments.
  const finalStart = Math.min(s2, e3)
  const finalEnd = Math.max(s2, e3)

  return { startIdx: finalStart, endIdx: finalEnd, notes }
}

import type { Sentence } from "./gemini"

