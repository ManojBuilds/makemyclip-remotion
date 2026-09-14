"""Constants for viral clip detection and scoring.

Hook indicators, conclusion phrases, filler words, and weak-ending signals
used by both the Gemini discovery and heuristic fallback engines.
"""

FILLER_WORDS = {
    "um", "uh", "like", "so", "yeah", "yes", "right", "well", "and",
    "basically", "actually", "you know", "i mean", "okay", "ok",
    "anyway", "anyways", "literally", "honestly", "obviously",
}

HOOK_INDICATORS = [
    # ── Questions & curiosity ──
    "why do", "how to", "what if", "did you know", "have you noticed",
    "do you think", "can you imagine", "have you ever", "what would happen",
    "want to know", "guess what", "you know what",
    # ── Problem / mistake framing ──
    "the biggest mistake", "the problem is", "the secret to", "nobody talks about",
    "worst mistake", "stop doing", "don't ever", "never do", "the number one mistake",
    "the fatal flaw", "the trap is", "most people get wrong",
    # ── Revelation / truth bombs ──
    "unpopular opinion", "the truth about", "shocking truth", "mind-blowing",
    "the crazy thing is", "the real truth", "what nobody tells you", "the flip side",
    "here's what they don't", "the dirty secret", "the hidden",
    # ── Advice / wisdom ──
    "best advice", "always remember", "if you want", "here's why", "the reason why",
    "the key is", "the trick is", "the hack is", "pro tip", "golden rule",
    # ── Story / confession / vulnerability ──
    "i realized", "insane story", "this changed my", "i was wrong", "i failed",
    "i lost everything", "i almost", "nobody knows this", "true story",
    "i couldn't believe", "i was shocked", "it broke my heart", "that moment when",
    "so there i was", "picture this", "let me paint", "when i was",
    # ── Direct address / urgency ──
    "you need to", "listen to me", "pay attention", "trust me", "let me tell you",
    "hear me out", "mark my words", "i'm telling you", "write this down",
    # ── Superlatives ──
    "the biggest", "the worst", "the best", "the craziest", "the most important",
    "the hardest", "the easiest", "the single most", "the only way",
    # ── Numbered lists / structure ──
    "three things", "five reasons", "the one thing", "number one", "first of all",
    "two words", "one word", "rule number", "step one",
    # ── Contrast / pivot ──
    "but here's the thing", "most people don't", "but actually", "the difference between",
    "on one hand", "what people think vs", "contrary to",
    # ── Emotional triggers ──
    "this is insane", "this is crazy", "i can't believe", "oh my god",
    "are you kidding", "wait wait wait", "hold on", "that's wild",
]

CONCLUSION_INDICATORS = [
    # ── Punchlines & summaries ──
    "and that's why", "that's the secret", "that's the difference", "that's the lesson",
    "that's the point", "that's what matters", "that's the key", "that's the truth",
    "that's what it comes down to", "that's the bottom line",
    "and that is why", "that is the secret", "that is the difference", "that is the lesson",
    "that is the point", "that is what matters", "that is the key", "that is the truth",
    "that is what it comes down to", "that is the bottom line",

    # ── Callbacks & takeaways ──
    "so remember", "bottom line", "the takeaway", "moral of the story",
    "long story short", "point being", "in a nutshell", "at the end of the day",
    "the lesson here", "the message is", "what i learned",
    # ── Emphatic closers ──
    "period", "full stop", "end of story", "done", "mic drop",
    "simple as that", "that's it", "there you go", "case closed",
    "no question about it", "without a doubt", "hands down",
    # ── Reflective closers ──
    "and i'll never forget that", "changed my life", "changed everything",
    "never looked back", "and that was it", "and it worked",
    "and i'm so glad", "best decision i ever made",
]

# Words that signal an incomplete thought when ending a clip
WEAK_ENDING_WORDS = {
    "and", "but", "so", "because", "or", "like", "which", "that", "when",
    "where", "while", "if", "then", "also", "plus", "with", "for", "the",
    "a", "an", "to", "of", "in", "on", "is", "was", "are", "were",
}

# Transitional phrases that make a clip opening sound like a mid-conversation continuation
LEADING_CONNECTORS = [
    "more importantly",
    "more important",
    "on top of that",
    "in addition to that",
    "in addition",
    "furthermore",
    "not only that",
    "like i said",
    "as i said",
    "as mentioned",
    "by the way",
    "at the same time",
    "having said that",
    "that being said",
]

