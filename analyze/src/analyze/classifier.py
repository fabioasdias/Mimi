"""Rule-based ticket classifier.

Bootstrap implementation using keyword patterns.
Can be replaced with a trained spaCy TextCategorizer later.
"""

import re

from analyze.models import Classification

# Category patterns: (category, keywords/phrases, weight)
RULES: list[tuple[str, list[str], float]] = [
    (
        "outage",
        [
            "down",
            "outage",
            "unavailable",
            "500",
            "503",
            "timeout",
            "not responding",
            "can't access",
            "cannot access",
            "service is down",
            "incident",
            "degraded",
            "p1",
            "p0",
            "sev1",
            "sev0",
            "emergency",
        ],
        1.0,
    ),
    (
        "bug",
        [
            "bug",
            "error",
            "crash",
            "broken",
            "doesn't work",
            "does not work",
            "unexpected",
            "regression",
            "defect",
            "issue",
            "failing",
            "failed",
            "exception",
            "stacktrace",
            "stack trace",
        ],
        0.8,
    ),
    (
        "new_feature",
        [
            "feature request",
            "new feature",
            "enhancement",
            "would be nice",
            "could we add",
            "can we add",
            "requesting",
            "proposal",
            "rfc",
            "roadmap",
            "improvement",
        ],
        0.9,
    ),
    (
        "user_error",
        [
            "how do i",
            "how to",
            "help me",
            "confused",
            "don't understand",
            "where is",
            "can't find",
            "documentation",
            "what does",
            "is it possible",
            "tutorial",
        ],
        0.7,
    ),
    (
        "wrong_team",
        [
            "wrong team",
            "not our",
            "not my team",
            "redirect",
            "reassign",
            "belongs to",
            "should go to",
            "moved to",
            "transferred",
            "not responsible",
        ],
        0.9,
    ),
    (
        "question",
        [
            "question",
            "asking",
            "clarification",
            "wondering",
            "anyone know",
            "does anyone",
            "quick question",
        ],
        0.6,
    ),
]

# Pre-compile patterns
_COMPILED_RULES = [
    (
        category,
        [re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE) for kw in keywords],
        weight,
    )
    for category, keywords, weight in RULES
]


def classify_ticket(title: str, conversation_text: str) -> Classification:
    """Classify a ticket based on its title and conversation content.

    Returns the best-matching classification with confidence score.
    """
    full_text = f"{title}\n{conversation_text}"

    scores: dict[str, float] = {}
    match_details: dict[str, list[str]] = {}

    for category, patterns, weight in _COMPILED_RULES:
        matches = []
        for pattern in patterns:
            found = pattern.findall(full_text)
            if found:
                matches.extend(found)

        if matches:
            # Score based on number of matching keywords, weighted
            scores[category] = len(matches) * weight
            match_details[category] = matches

    if not scores:
        return Classification(
            type="question",
            confidence=0.3,
            services=[],
            summary=title[:200],
        )

    # Normalize scores
    total = sum(scores.values())
    best_category = max(scores, key=scores.get)  # type: ignore[arg-type]
    confidence = min(scores[best_category] / total, 0.99) if total > 0 else 0.5

    return Classification(
        type=best_category,
        confidence=round(confidence, 2),
        services=[],  # Filled by entities module
        summary=title[:200],
    )
