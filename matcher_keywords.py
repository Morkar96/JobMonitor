"""
Keyword-based fallback matcher, used by matcher.py whenever the LLM matcher
(matcher_llm.py) isn't available. Scores a candidate job posting against the
desired profile (junior software developer, center of Israel) using simple
substring keyword matching across three categories: role, level, location.

role and location are the main signal (most postings never mention a level
at all). "level" only adds a small bonus when the posting explicitly says
junior/entry-level. If a posting explicitly says senior/mid-level instead,
that's an outright disqualifier ("senior_conflict"), regardless of score.

Likewise, a posting that names a non-Israel location (and no Israeli one)
is an outright disqualifier ("foreign_conflict") -- missing location info
is treated as "unknown, don't penalize", but an explicit foreign location
is a real conflict, not just an absence of a positive signal.

Score = sum of weights for matched categories (0-100).
A job is "compatible" if score >= COMPATIBILITY_THRESHOLD and there's no
senior_conflict or foreign_conflict.
"""

from config import KEYWORDS, WEIGHTS, COMPATIBILITY_THRESHOLD


def _matches(text: str, keywords: list[str]) -> bool:
    text = text.lower()
    return any(kw.lower() in text for kw in keywords)


def score_job_keywords(title: str, extra_text: str = "") -> dict:
    """
    title: the link text / job title we scraped
    extra_text: optional extra context (e.g. surrounding snippet), improves
                recall for location/level info that isn't in the title itself
    Returns {"score": int, "compatible": bool, "matched": [categories],
              "senior_conflict": bool, "foreign_conflict": bool}
    """
    combined = f"{title} {extra_text}"
    matched = []
    score = 0

    for category in ("role", "location"):
        if _matches(combined, KEYWORDS[category]):
            matched.append(category)
            score += WEIGHTS[category]

    senior_conflict = _matches(combined, KEYWORDS["level_senior"])
    if not senior_conflict and _matches(combined, KEYWORDS["level_junior"]):
        matched.append("level")
        score += WEIGHTS["level"]

    # only a disqualifier when there's no Israeli location also mentioned --
    # trust the positive signal over the negative one if both are present
    foreign_conflict = "location" not in matched and _matches(combined, KEYWORDS["location_foreign"])

    compatible = (
        score >= COMPATIBILITY_THRESHOLD
        and not senior_conflict
        and not foreign_conflict
    )

    return {
        "score": score,
        "compatible": compatible,
        "matched": matched,
        "senior_conflict": senior_conflict,
        "foreign_conflict": foreign_conflict,
        # keyword matching has no way to tell a blog post from a real
        # posting -- only the LLM path (matcher_llm.py) can set this True.
        "non_job_content": False,
    }
