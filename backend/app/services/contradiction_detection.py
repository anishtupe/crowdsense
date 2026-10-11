"""
Contradiction detection — core research component.

Given two (or more) reports believed to describe the same incident,
flag whether they disagree in ways that should lower confidence rather
than reinforce it — e.g. one report says "fire contained", another says
"fire spreading"; one says minor injuries, another says fatalities.

This ships as a keyword/heuristic-based placeholder so it runs with zero
extra dependencies. Swap in a real NLI model for the "Multilingual NLI"
approach described in your architecture doc:

    pip install transformers torch
    (load e.g. a cross-lingual NLI checkpoint and classify entailment/
    contradiction/neutral between each pair of report texts)

Keep the function signature the same so `fusion_engine.py` and the
pipeline don't need to change when you swap the implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


_NLI_MODEL = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
_nli_pipeline = None
_nli_unavailable = False

_SEVERITY_WORDS_HIGH = ["fatal", "died", "dead", "collapsed", "trapped", "severe"]
_SEVERITY_WORDS_LOW = ["minor", "contained", "under control", "safe", "resolved"]


@dataclass
class ContradictionResult:
    report_a_id: str
    report_b_id: str
    contradicts: bool
    reason: Optional[str] = None


def _severity_signal(text: Optional[str]) -> int:
    """Returns +1 for high-severity language, -1 for low-severity language,
    0 if neither/ambiguous."""
    if not text:
        return 0
    lowered = text.lower()
    has_high = any(w in lowered for w in _SEVERITY_WORDS_HIGH)
    has_low = any(w in lowered for w in _SEVERITY_WORDS_LOW)
    if has_high and not has_low:
        return 1
    if has_low and not has_high:
        return -1
    return 0


def _get_nli_pipeline():
    """Load the multilingual NLI pipeline on first use; None if unavailable."""
    global _nli_pipeline, _nli_unavailable
    if _nli_unavailable:
        return None
    if _nli_pipeline is None:
        try:
            from transformers import pipeline

            _nli_pipeline = pipeline(
                "text-classification",
                model=_NLI_MODEL,
            )
        except Exception:
            _nli_unavailable = True
            return None
    return _nli_pipeline


def _label_is_contradiction(output) -> bool:
    if isinstance(output, list):
        output = output[0]
    label = str(output.get("label", "")).lower()
    return "contradiction" in label


def _nli_contradicts(nli, text_a: str, text_b: str) -> bool:
    ab = nli({"text": text_a, "text_pair": text_b}, truncation=True)
    ba = nli({"text": text_b, "text_pair": text_a}, truncation=True)
    return _label_is_contradiction(ab) or _label_is_contradiction(ba)


def _heuristic_contradiction(text_a: Optional[str], text_b: Optional[str]) -> bool:
    sig_a = _severity_signal(text_a)
    sig_b = _severity_signal(text_b)
    return sig_a != 0 and sig_b != 0 and sig_a != sig_b


def detect_contradiction(
    report_a_id: str, text_a: Optional[str],
    report_b_id: str, text_b: Optional[str],
) -> ContradictionResult:
    """NLI contradiction check with keyword/severity heuristic fallback."""
    nli = _get_nli_pipeline()
    contradicts = False
    reason = None

    if nli is not None and text_a and text_b:
        try:
            contradicts = _nli_contradicts(nli, text_a, text_b)
            reason = "nli contradiction" if contradicts else None
        except Exception:
            nli = None

    if nli is None:
        contradicts = _heuristic_contradiction(text_a, text_b)
        reason = "conflicting severity language" if contradicts else None

    return ContradictionResult(
        report_a_id=report_a_id,
        report_b_id=report_b_id,
        contradicts=contradicts,
        reason=reason,
    )


def any_contradictions(reports: List[tuple[str, Optional[str]]]) -> bool:
    """reports: list of (report_id, text) tuples believed to be about the
    same incident. Returns True if any pair contradicts."""
    for i in range(len(reports)):
        for j in range(i + 1, len(reports)):
            result = detect_contradiction(
                reports[i][0], reports[i][1], reports[j][0], reports[j][1]
            )
            if result.contradicts:
                return True
    return False
