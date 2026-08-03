"""
Scores a candidate job posting against the desired profile
(junior software developer, center of Israel) using simple
substring keyword matching across three categories: role, level, location.

Score = sum of weights for matched categories (0-100).
A job is "compatible" if score >= COMPATIBILITY_THRESHOLD.
"""

from config import KEYWORDS, WEIGHTS, COMPATIBILITY_THRESHOLD


def _matches(text: str, keywords: list[str]) -> bool:
    text = text.lower()
    return any(kw.lower() in text for kw in keywords)


def score_job(title: str, extra_text: str = "") -> dict:
    """
    title: the link text / job title we scraped
    extra_text: optional extra context (e.g. surrounding snippet), improves
                recall for location/level info that isn't in the title itself
    Returns {"score": int, "compatible": bool, "matched": [categories]}
    """
    combined = f"{title} {extra_text}"
    matched = []
    score = 0

    for category, keywords in KEYWORDS.items():
        if _matches(combined, keywords):
            matched.append(category)
            score += WEIGHTS[category]

    return {
        "score": score,
        "compatible": score >= COMPATIBILITY_THRESHOLD,
        "matched": matched,
    }
