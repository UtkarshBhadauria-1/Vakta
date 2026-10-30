"""Small, transparent lexicon sentiment signal for response tone and triage.

This is a heuristic, not a trained or validated sentiment model. It never
persists input text or matched terms.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[a-z]+(?:'[a-z]+)?")
_POSITIVE = {
    "appreciate", "awesome", "clear", "excellent", "glad", "good", "great",
    "happy", "helpful", "love", "resolved", "satisfied", "thanks", "thank",
}
_NEGATIVE = {
    "angry", "anxious", "bad", "broken", "confused", "complaint", "disappointed",
    "frustrated", "harassed", "harassment", "hate", "issue", "lost", "painful",
    "problem", "sad", "stress", "stressed", "terrible", "unfair", "unhappy",
    "upset", "unsafe", "worried",
}
_NEGATORS = {"barely", "can't", "cannot", "hardly", "never", "no", "not", "without"}


@dataclass(frozen=True)
class SentimentResult:
    label: str
    score: float


def analyze_sentiment(text: str) -> SentimentResult:
    """Return positive/neutral/negative with a bounded heuristic score [-1, 1]."""
    tokens = _TOKEN_RE.findall(text.casefold())
    weighted: list[float] = []
    for index, token in enumerate(tokens):
        if token in _POSITIVE:
            value = 1.0
        elif token in _NEGATIVE:
            value = -1.0
        else:
            continue
        preceding = tokens[max(0, index - 3):index]
        if any(word in _NEGATORS for word in preceding):
            value *= -1.0
        weighted.append(value)

    if not weighted:
        return SentimentResult(label="neutral", score=0.0)
    score = round(max(-1.0, min(1.0, sum(weighted) / len(weighted))), 3)
    label = "negative" if score <= -0.2 else "positive" if score >= 0.2 else "neutral"
    return SentimentResult(label=label, score=score)
