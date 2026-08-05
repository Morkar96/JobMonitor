"""
Top-level job-matching entry point used by main.py.

Tries the LLM matcher (matcher_llm.py) first -- it reads the actual
semantics of a posting rather than just keyword substrings, so it catches
things keyword matching can't (e.g. a role that's clearly senior without
using the word "senior"). Falls back to the keyword matcher
(matcher_keywords.py) whenever the LLM can't be used for this call: no API
key configured, rate-limited, hit the per-run call cap, network error, or
an unexpected response shape. The keyword matcher never fails this way, so
every job always gets scored one way or the other.
"""

from matcher_keywords import score_job_keywords
from matcher_llm import score_job_llm, LLMMatcherUnavailable


def score_job(title: str, extra_text: str = "") -> dict:
    """
    Returns {"score": int, "compatible": bool, "matched": [categories],
              "senior_conflict": bool, "foreign_conflict": bool,
              "engine": "llm" | "keywords", ...}
    """
    try:
        result = score_job_llm(title, extra_text)
        result["engine"] = "llm"
        return result
    except LLMMatcherUnavailable:
        result = score_job_keywords(title, extra_text)
        result["engine"] = "keywords"
        return result
