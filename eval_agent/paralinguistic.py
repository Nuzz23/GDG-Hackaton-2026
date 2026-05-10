"""Paralinguistic feature extraction.

Operates on a `TranscriptionResult` from `eval_agent.asr` (which uses
`word_timestamps=True`). Extracts process-level signals that text alone
does not carry: filler density, self-corrections, thinking pauses,
reformulation attempts.

These features are passed to the `judge_open` prompt and primarily
affect the `elaborazione` dimension. The cognitive thesis: a verbatim
response TYPED is "riportata"; the same response SPOKEN with hesitations
and self-corrections is "rielaborata" — process is observable in audio
in ways it isn't in text.

All heuristics are intentionally simple (regex + counts + thresholds).
This is v1 — embeddings or LLM-assisted reformulation detection are out
of scope. The brief is explicit: don't over-engineer.
"""

from __future__ import annotations

import re
import statistics
from typing import Any


# ---------------------------------------------------------------------------
# Vocabularies
# ---------------------------------------------------------------------------


# Pure disfluency fillers — high count = cognitive load OR not understanding.
# Whisper transcribes most of these as standalone tokens.
IT_FILLERS = {"ehm", "uhm", "mh", "mmh", "uh", "boh", "eh", "ah", "mmm"}
EN_FILLERS = {"um", "uh", "er", "ah", "hmm", "uhh", "umm"}

# Hedge markers — informal restructuring; positive signal for `rielaborata`.
# Multi-word hedges go through substring matching, single-word through
# token matching.
IT_HEDGES = {"tipo", "cioè", "praticamente", "essenzialmente", "diciamo", "in pratica", "in sostanza"}
EN_HEDGES = {"like", "you know", "kind of", "sort of", "i mean", "basically", "essentially"}

# Self-correction patterns — strong metacognitive signal.
IT_SELF_CORRECT_PATTERNS = [
    r"\bno\s+aspett[ao]\b",
    r"\bno\s+scusa\b",
    r"\bscusa,?\s+intend[ioe]\b",
    r"\bintend[ioe]\s+dire\b",
    r"\bvoglio\s+dire\b",
    r"\bmi\s+correggo\b",
    r"\bcioè\s+no\b",
    r"\baspetta,?\s+volevo\s+dire\b",
    r"\b—\s*no,?\s+\b",
]
EN_SELF_CORRECT_PATTERNS = [
    r"\bwait,?\s*no\b",
    r"\bactually,?\s*no\b",
    r"\bi\s+mean,?\s+(?!\.)",
    r"\bscratch\s+that\b",
    r"\blet\s+me\s+rephrase\b",
    r"\bno,?\s+sorry\b",
    r"\bsorry,?\s+i\s+mean\b",
    r"\bcorrection,?\s+\b",
]


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------


# Inter-word gap above this counts as a "thinking pause".
THINKING_PAUSE_S = 0.8

# Adjacent-segment keyword overlap above this counts as reformulation.
# Cap at 0.95 to avoid counting verbatim repeats.
REFORM_OVERLAP_LO = 0.45
REFORM_OVERLAP_HI = 0.95

# Minimum content-word length (chars) to count for overlap.
MIN_CONTENT_WORD_LEN = 4

# Filler rate above this (per minute) flags possible cognitive overload.
HIGH_FILLER_RATE_PER_MIN = 20


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_features(result: Any) -> dict:
    """Compute paralinguistic features from a `TranscriptionResult`.

    `result` is intentionally typed as `Any` so callers can pass either the
    real dataclass from `eval_agent.asr` OR a dict-like substitute (used in
    tests / programmatic feature injection).

    Returns a dict with numeric counts AND an `evidence_summary` string the
    judge can read directly without parsing.
    """
    segments = _segments_of(result)
    if not segments:
        return {}

    language = _language_of(result)
    duration = float(_duration_of(result) or 1.0)
    duration_min = max(duration / 60.0, 1e-6)

    fillers = IT_FILLERS if language == "it" else EN_FILLERS
    hedges = IT_HEDGES if language == "it" else EN_HEDGES
    correction_patterns = (
        IT_SELF_CORRECT_PATTERNS if language == "it" else EN_SELF_CORRECT_PATTERNS
    )

    full_text = " ".join(s["text"] for s in segments)
    full_text_lower = full_text.lower()

    # Word-level: required for filler counting + pause stats. faster-whisper
    # populates this when word_timestamps=True.
    all_words = []
    for seg in segments:
        for w in seg.get("words", []):
            all_words.append(w)

    filler_count = _count_token_membership(all_words, fillers)
    hedge_count = _count_hedges(full_text_lower, all_words, hedges)
    self_correction_count, self_correction_examples = _count_self_corrections(
        full_text_lower, correction_patterns
    )
    long_pause_count, long_pause_durations = _count_long_pauses(all_words)
    reformulation_count = _count_reformulations(segments)

    median_pause = (
        round(statistics.median(long_pause_durations), 2)
        if long_pause_durations else 0.0
    )
    filler_per_min = round(filler_count / duration_min, 1)

    return {
        "duration_seconds": round(duration, 2),
        "filler_count": filler_count,
        "filler_per_min": filler_per_min,
        "hedge_count": hedge_count,
        "self_correction_count": self_correction_count,
        "self_correction_examples": self_correction_examples[:5],
        "long_pause_count": long_pause_count,
        "long_pause_median_s": median_pause,
        "reformulation_count": reformulation_count,
        "evidence_summary": _summarize(
            filler_count, filler_per_min, hedge_count,
            self_correction_count, long_pause_count, reformulation_count, duration,
        ),
    }


# ---------------------------------------------------------------------------
# Adapters: accept dataclass-shaped or dict-shaped input
# ---------------------------------------------------------------------------


def _segments_of(result) -> list[dict]:
    """Normalize segments into a list of dicts with `text` + `words` keys.

    Words inside each segment are also normalized to dicts with
    `start`, `end`, `word`.
    """
    segs = getattr(result, "segments", None)
    if segs is None and isinstance(result, dict):
        segs = result.get("segments", [])
    out: list[dict] = []
    for s in segs or []:
        if isinstance(s, dict):
            text = s.get("text", "")
            words = s.get("words", []) or []
            out.append({
                "text": text,
                "words": [
                    {
                        "start": float(getattr(w, "start", w["start"]) if not isinstance(w, dict) else w["start"]),
                        "end": float(getattr(w, "end", w["end"]) if not isinstance(w, dict) else w["end"]),
                        "word": (getattr(w, "word", None) if not isinstance(w, dict) else w.get("word", "")) or "",
                    }
                    for w in words
                ],
            })
        else:
            words = getattr(s, "words", None) or []
            out.append({
                "text": getattr(s, "text", ""),
                "words": [
                    {"start": float(w.start), "end": float(w.end), "word": w.word}
                    for w in words
                ],
            })
    return out


def _language_of(result) -> str:
    lang = getattr(result, "language", None)
    if lang is None and isinstance(result, dict):
        lang = result.get("language")
    return (lang or "it").split("-")[0].lower()


def _duration_of(result) -> float | None:
    d = getattr(result, "duration_seconds", None)
    if d is None and isinstance(result, dict):
        d = result.get("duration_seconds")
    return d


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------


_PUNCT_STRIP_RE = re.compile(r"[^\w\s]+")


def _count_token_membership(words: list[dict], vocab: set[str]) -> int:
    return sum(
        1 for w in words
        if _normalize_token(w["word"]) in vocab
    )


def _normalize_token(s: str) -> str:
    return _PUNCT_STRIP_RE.sub("", s.strip().lower())


def _count_hedges(full_text_lower: str, words: list[dict], hedges: set[str]) -> int:
    count = 0
    for hedge in hedges:
        if " " in hedge:
            count += full_text_lower.count(hedge)
        else:
            count += sum(1 for w in words if _normalize_token(w["word"]) == hedge)
    return count


def _count_self_corrections(full_text_lower: str, patterns: list[str]) -> tuple[int, list[str]]:
    count = 0
    examples: list[str] = []
    for pat in patterns:
        for m in re.finditer(pat, full_text_lower, flags=re.IGNORECASE):
            count += 1
            examples.append(m.group(0))
    return count, examples


def _count_long_pauses(words: list[dict]) -> tuple[int, list[float]]:
    """Count inter-word gaps > THINKING_PAUSE_S."""
    if len(words) < 2:
        return 0, []
    gaps: list[float] = []
    for i in range(len(words) - 1):
        gap = words[i + 1]["start"] - words[i]["end"]
        if gap > THINKING_PAUSE_S:
            gaps.append(gap)
    return len(gaps), gaps


# ---------------------------------------------------------------------------
# Reformulation detection (keyword overlap heuristic)
# ---------------------------------------------------------------------------


_STOPWORDS_IT = {
    "il","la","i","le","un","una","è","e","di","a","da","in","con","su","per",
    "tra","fra","che","non","mi","ti","si","ci","vi","loro","del","della","dei",
    "delle","al","alla","ai","alle","sul","sulla","quel","quello","quella",
    "questo","questa","questi","queste","ma","o","se","perché","perche","come",
    "essere","avere","ha","sono","era","stato","stata",
}
_STOPWORDS_EN = {
    "the","a","an","is","are","was","were","be","been","being","of","to","in",
    "on","at","with","by","for","from","and","or","but","if","not","this",
    "that","these","those","i","you","he","she","it","we","they","what",
    "when","where","why","how","do","does","did",
}


def _count_reformulations(segments: list[dict]) -> int:
    """Adjacent segments with > REFORM_OVERLAP_LO content-word overlap (capped
    below REFORM_OVERLAP_HI to skip verbatim repeats) count as reformulations.
    """
    if len(segments) < 2:
        return 0
    count = 0
    for i in range(len(segments) - 1):
        kw1 = _content_words(segments[i]["text"])
        kw2 = _content_words(segments[i + 1]["text"])
        if not kw1 or not kw2:
            continue
        overlap = len(kw1 & kw2) / min(len(kw1), len(kw2))
        if REFORM_OVERLAP_LO < overlap < REFORM_OVERLAP_HI:
            count += 1
    return count


def _content_words(text: str) -> set[str]:
    words = re.findall(r"\b[\w]+\b", text.lower())
    return {
        w for w in words
        if len(w) >= MIN_CONTENT_WORD_LEN
        and w not in _STOPWORDS_IT
        and w not in _STOPWORDS_EN
    }


# ---------------------------------------------------------------------------
# Evidence summary — short prose for the judge
# ---------------------------------------------------------------------------


def _summarize(
    fillers: int, filler_per_min: float, hedges: int,
    self_corrects: int, pauses: int, reforms: int, duration: float,
) -> str:
    parts: list[str] = []
    if duration < 5:
        parts.append("response very short (<5s)")
    if self_corrects > 0:
        parts.append(f"{self_corrects} self-correction(s)")
    if reforms > 0:
        parts.append(f"{reforms} apparent reformulation(s) between adjacent segments")
    if pauses > 0:
        parts.append(f"{pauses} long thinking pause(s)")
    if hedges > 0:
        parts.append(f"{hedges} informal hedge(s)")
    if filler_per_min > HIGH_FILLER_RATE_PER_MIN:
        parts.append(
            f"high filler density ({filler_per_min:.0f}/min) — possible cognitive load"
        )
    elif fillers > 0:
        parts.append(f"{fillers} filler(s)")
    return "; ".join(parts) if parts else "no significant paralinguistic signals"
