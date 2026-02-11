"""Classification improvement through active learning."""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from ruamel.yaml import YAML


def analyze_classification_quality(
    analyzed_path: Path, confidence_threshold: float = 0.5
) -> dict:
    """Analyze classification results and identify improvement opportunities.

    Args:
        analyzed_path: Path to analyzed.json file
        confidence_threshold: Flag classifications below this confidence

    Returns:
        Dictionary with analysis results including:
        - by_type: Issues grouped by classification type
        - low_confidence: Issues below confidence threshold
        - keyword_by_type: Keyword frequency per type
        - suggestions: Recommended keywords per type
    """
    analyzed_data = json.loads(analyzed_path.read_text())
    issues = analyzed_data.get("issues", [])

    if not issues:
        return {"issues": [], "by_type": {}, "low_confidence": [], "suggestions": {}}

    low_confidence = []
    by_type = defaultdict(list)
    keyword_by_type = defaultdict(lambda: defaultdict(int))

    for issue in issues:
        classification = issue.get("classification", {})
        conf = classification.get("confidence", 0)
        issue_type = classification.get("type", "unknown")
        keywords = classification.get("keywords", [])

        by_type[issue_type].append(issue)

        if conf < confidence_threshold:
            low_confidence.append(
                {
                    "id": issue.get("id"),
                    "type": issue_type,
                    "confidence": conf,
                    "summary": classification.get("summary", "")[:60],
                }
            )

        # Track keywords per type
        for kw in keywords:
            keyword_by_type[issue_type][kw] += 1

    # Generate suggestions - top keywords per type
    suggestions = {}
    for issue_type in by_type.keys():
        top_keywords = sorted(
            keyword_by_type[issue_type].items(), key=lambda x: -x[1]
        )[:5]
        if top_keywords:
            suggestions[issue_type] = [kw for kw, _ in top_keywords]

    return {
        "issues": issues,
        "by_type": dict(by_type),
        "low_confidence": low_confidence,
        "keyword_by_type": dict(keyword_by_type),
        "suggestions": suggestions,
    }


def learn_from_correction(
    issue: dict, correct_type: str, gathered_path: Path
) -> dict[str, list[str]]:
    """Learn classification patterns from a corrected issue.

    Analyzes the issue text to extract keywords and patterns that should
    signal the correct type.

    Args:
        issue: The issue data
        correct_type: The correct classification type
        gathered_path: Path to gathered.json to get full text

    Returns:
        Dict with suggested rule additions for the correct type
    """
    # Load full issue data to get complete text
    gathered_data = json.loads(gathered_path.read_text())
    gathered_issues = gathered_data.get("issues", [])

    # Find the full issue
    issue_id = issue.get("id")
    full_issue = next((i for i in gathered_issues if i.get("id") == issue_id), None)

    if not full_issue:
        return {"keywords": []}

    # Extract text
    title = full_issue.get("title", "")
    conversation = full_issue.get("conversation", [])
    full_text = f"{title}\n" + "\n".join(
        msg.get("content", "") for msg in conversation
    )

    # Extract potential signal words (simple heuristic)
    # Look for distinctive words that appear in the text
    words = re.findall(r"\b[a-z]{3,}\b", full_text.lower())
    word_counts = Counter(words)

    # Filter out common words (basic stop words)
    stop_words = {
        "the",
        "and",
        "for",
        "that",
        "this",
        "with",
        "from",
        "have",
        "are",
        "was",
        "been",
        "will",
        "can",
        "has",
        "but",
        "not",
        "you",
        "all",
        "were",
        "when",
        "there",
        "what",
        "which",
        "their",
        "said",
        "each",
        "she",
        "how",
        "may",
        "other",
        "than",
        "then",
        "now",
        "only",
        "could",
        "our",
        "also",
    }

    candidate_keywords = [
        word
        for word, count in word_counts.most_common(20)
        if word not in stop_words and count >= 2
    ]

    return {"keywords": candidate_keywords[:5]}


def apply_learned_patterns(
    corrections: list[dict], rules_path: Path, context: str | None = None
) -> None:
    """Apply learned patterns from user corrections to custom rules.

    Args:
        corrections: List of corrections with learned keywords
        rules_path: Path to classify_rules.custom.yaml
        context: Optional context name for context-specific rules
    """
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=2, offset=2)

    # Load or create custom rules
    if rules_path.exists():
        with open(rules_path) as f:
            custom_rules = yaml.load(f) or {}
    else:
        custom_rules = {}

    # Group corrections by type
    by_type = defaultdict(list)
    for correction in corrections:
        by_type[correction["correct_type"]].extend(correction["learned_keywords"])

    # If context is provided, add to context-specific rules
    if context:
        if "contexts" not in custom_rules:
            custom_rules["contexts"] = {}
        if context not in custom_rules["contexts"]:
            custom_rules["contexts"][context] = {}

        for issue_type, keywords in by_type.items():
            if issue_type not in custom_rules["contexts"][context]:
                custom_rules["contexts"][context][issue_type] = {
                    "weight": 1.5,  # Higher weight for learned patterns
                    "keywords": [],
                }

            existing = custom_rules["contexts"][context][issue_type]["keywords"]
            new_keywords = [kw for kw in keywords if kw not in existing]
            if new_keywords:
                custom_rules["contexts"][context][issue_type]["keywords"].extend(
                    new_keywords[:5]
                )  # Add top 5
    else:
        # Add to global overrides
        if "overrides" not in custom_rules:
            custom_rules["overrides"] = {}

        for issue_type, keywords in by_type.items():
            if issue_type not in custom_rules["overrides"]:
                custom_rules["overrides"][issue_type] = {
                    "weight": 1.5,
                    "keywords": [],
                }

            existing = custom_rules["overrides"][issue_type]["keywords"]
            new_keywords = [kw for kw in keywords if kw not in existing]
            if new_keywords:
                custom_rules["overrides"][issue_type]["keywords"].extend(
                    new_keywords[:5]
                )

    # Also store corrections for direct lookup
    if "corrections" not in custom_rules:
        custom_rules["corrections"] = {}

    for correction in corrections:
        custom_rules["corrections"][correction["issue_id"]] = correction[
            "correct_type"
        ]

    # Write back
    with open(rules_path, "w") as f:
        yaml.dump(custom_rules, f)
