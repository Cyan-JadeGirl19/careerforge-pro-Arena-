"""Caption (WebVTT) generation from the candidate's own text.

Honest by design: this is NOT speech recognition. Cues are split from
the transcript/script the candidate provides (or edited) and timed
proportionally across the measured video duration. The UI says so and
the candidate reviews the cue list before exporting - no invented
transcriptions, no fake "AI transcript" claims.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Cue:
    start: float
    end: float
    text: str


def _chunk_words(words: list[str], max_words: int) -> list[list[str]]:
    """Group words into readable cues, preferring punctuation breaks."""
    chunks: list[list[str]] = []
    cur: list[str] = []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words or (
            len(cur) >= 5 and w.rstrip().endswith((".", "!", "?", ";", ","))
        ):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def transcript_to_cues(text: str, duration: float, max_words: int = 11) -> list[Cue]:
    """Split a transcript into cues timed proportionally over `duration`.

    Cue length is proportional to its share of the words, with a small
    gap between cues. The last cue is clamped to the video length.
    """
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        raise ValueError("Empty transcript - paste what you say in the video.")
    if not duration or duration <= 0:
        raise ValueError("No video duration to time captions against.")
    words = text.split()
    total = len(words)
    chunks = _chunk_words(words, max_words)
    gap = 0.12
    usable = max(0.5, duration - gap * max(0, len(chunks) - 1))
    cues: list[Cue] = []
    t = 0.0
    for ch in chunks:
        span = usable * len(ch) / total
        end = t + span
        if t >= duration:
            break
        end = min(end, duration)
        cues.append(Cue(t, end, " ".join(ch)))
        t = end + gap
    if not cues:
        raise ValueError("Could not build cues from that text.")
    return cues


def _fmt(ts: float) -> str:
    h = int(ts // 3600)
    m = int((ts % 3600) // 60)
    s = ts % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def cues_to_vtt(cues: list[Cue]) -> str:
    lines = ["WEBVTT", ""]
    for i, c in enumerate(cues, 1):
        lines.extend([str(i), f"{_fmt(c.start)} --> {_fmt(c.end)}", c.text, ""])
    return "\n".join(lines)
