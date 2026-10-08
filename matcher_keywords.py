"""
Keyword-based matcher used for every job, both stages of the pipeline
(see main.py) -- no LLM involved. Scores a candidate job posting against the
desired profile (any junior technical role -- development, QA, or IT --
center of Israel) using simple substring keyword matching across three
categories: role, level, location.

"role" itself has two tiers: unambiguous words (developer, programmer,
backend, ...) score directly, while ambiguous words ("engineer", Hebrew
"מפתח"/"מהנדס") only count when paired with a software-context qualifier
(see KEYWORDS["role_software_qualifier"] in config.py) -- otherwise they
equally match hardware/mechanical/systems engineering titles, which are
common at defense/hardware companies.

role and location are the main signal (most postings never mention a level
at all). "level" only adds a small bonus when the posting explicitly says
junior/entry-level. If a posting explicitly says senior/mid-level instead,
that's an outright disqualifier ("senior_conflict"), regardless of score.

Likewise, a posting that names a non-Israel location (and no Israeli one)
is an outright disqualifier ("foreign_conflict") -- missing location info
is treated as "unknown, don't penalize", but an explicit foreign location
is a real conflict, not just an absence of a positive signal.

The candidate only wants center-Israel or remote roles, so the same
treatment applies to a posting that names a non-center Israeli city (Haifa,
Beer Sheva, Jerusalem, etc.) without also naming a center/remote location
("periphery_conflict") -- a real commute-distance disqualifier, not just an
absence of a positive signal.

Score = sum of weights for matched categories (0-100).
A job is "compatible" if score >= COMPATIBILITY_THRESHOLD and there's no
senior_conflict, foreign_conflict, or periphery_conflict.
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

    # "role" alone (developer/programmer/backend/...) is unambiguous. Bare
    # "engineer" (English) or "מפתח"/"מהנדס" (Hebrew) is not -- those are used
    # just as often for hardware/mechanical/systems roles, so they only count
    # toward role when paired with a software-context qualifier word.
    role_match = _matches(combined, KEYWORDS["role"]) or (
        _matches(combined, KEYWORDS["role_ambiguous"])
        and _matches(combined, KEYWORDS["role_software_qualifier"])
    )
    if role_match:
        matched.append("role")
        score += WEIGHTS["role"]

    if _matches(combined, KEYWORDS["location"]):
        matched.append("location")
        score += WEIGHTS["location"]

    senior_conflict = _matches(combined, KEYWORDS["level_senior"])
    if not senior_conflict and _matches(combined, KEYWORDS["level_junior"]):
        matched.append("level")
        score += WEIGHTS["level"]

    # Only a disqualifier when there's no actual Israeli place name also
    # mentioned -- trust the positive signal over the negative one if both
    # are present. Deliberately checks location_israel_named rather than
    # "location" in matched: bare "remote" doesn't say remote-from-WHERE,
    # so "US, CA, Remote" must not clear this the way "Tel Aviv" would.
    foreign_conflict = (
        not _matches(combined, KEYWORDS["location_israel_named"])
        and _matches(combined, KEYWORDS["location_foreign"])
    )

    # Israel but not center/remote (Haifa, Beer Sheva, Jerusalem, ...) -- only
    # a disqualifier when no center-specific/remote keyword is also mentioned.
    # Deliberately gated on location_center_specific rather than "location" in
    # matched: a bare "israel"/"מרכז" mention doesn't say WHICH city, so it
    # shouldn't be enough to clear an explicit periphery-city mention.
    periphery_conflict = (
        not _matches(combined, KEYWORDS["location_center_specific"])
        and _matches(combined, KEYWORDS["location_non_center_israel"])
    )

    # bare "engineer" in the role list also matches non-software engineering
    # disciplines (hardware/mechanical/electrical/...) -- a real disqualifier
    non_software_conflict = _matches(combined, KEYWORDS["role_non_software"])

    compatible = (
        score >= COMPATIBILITY_THRESHOLD
        and not senior_conflict
        and not foreign_conflict
        and not periphery_conflict
        and not non_software_conflict
    )

    return {
        "score": score,
        "compatible": compatible,
        "matched": matched,
        "senior_conflict": senior_conflict,
        "foreign_conflict": foreign_conflict,
        "periphery_conflict": periphery_conflict,
        "non_software_conflict": non_software_conflict,
    }
