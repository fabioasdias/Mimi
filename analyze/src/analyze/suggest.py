"""Suggest new classification rules based on gathered data."""

import json
from collections import Counter
from pathlib import Path

from analyze.entities import load_nlp


def extract_keywords(texts: list[str], top_n: int = 20) -> list[tuple[str, int]]:
    """Extract common keywords from texts using spaCy."""
    nlp = load_nlp()

    # Collect lemmas, filtering for meaningful words
    lemmas: list[str] = []
    for text in texts:
        doc = nlp(text)
        for token in doc:
            # Skip stop words, punctuation, numbers, short words
            if (
                not token.is_stop
                and not token.is_punct
                and not token.like_num
                and len(token.text) > 2
                and token.pos_ in ("NOUN", "VERB", "ADJ")
            ):
                lemmas.append(token.lemma_.lower())

    # Count and return top N
    counter = Counter(lemmas)
    return counter.most_common(top_n)


def analyze_sentiment(texts: list[str]) -> dict[str, int]:
    """Basic sentiment analysis using spaCy."""
    nlp = load_nlp()

    sentiments = {"positive": 0, "neutral": 0, "negative": 0}

    # Simple heuristic based on common sentiment words
    positive_words = {
        "good",
        "great",
        "excellent",
        "thanks",
        "helpful",
        "works",
        "perfect",
        "love",
    }
    negative_words = {
        "bad",
        "broken",
        "fail",
        "error",
        "problem",
        "issue",
        "wrong",
        "bug",
        "crash",
    }

    for text in texts:
        doc = nlp(text)
        lemmas = {token.lemma_.lower() for token in doc if not token.is_punct}

        pos_count = len(lemmas & positive_words)
        neg_count = len(lemmas & negative_words)

        if neg_count > pos_count:
            sentiments["negative"] += 1
        elif pos_count > neg_count:
            sentiments["positive"] += 1
        else:
            sentiments["neutral"] += 1

    return sentiments


def suggest_rules(
    gathered_path: Path, category: str | None = None
) -> dict[str, list[tuple[str, int]]]:
    """Suggest new classification keywords based on gathered data.

    Args:
        gathered_path: Path to gathered.json
        category: Optional category to filter by (e.g., "bug", "question")

    Returns:
        Dict mapping categories to suggested keywords with frequency counts
    """
    with open(gathered_path) as f:
        data = json.load(f)

    # Support both "issues" (new) and "tickets" (legacy) for backwards compatibility
    issues = data.get("issues") or data.get("tickets", [])

    # Group issues by title patterns
    all_texts: list[str] = []
    for issue in issues:
        title = issue.get("title", "")
        conversation = issue.get("conversation", [])
        text = f"{title}\n" + "\n".join(
            m.get("content", "") for m in conversation[:3]  # First 3 messages
        )
        all_texts.append(text)

    if not all_texts:
        return {}

    # Extract keywords
    keywords = extract_keywords(all_texts, top_n=30)

    # Analyze sentiment
    sentiment = analyze_sentiment(all_texts)

    return {
        "suggested_keywords": keywords,
        "sentiment_distribution": sentiment,
        "total_issues": len(issues),
    }
