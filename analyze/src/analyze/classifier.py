"""NLP-based issue classifier using spaCy linguistic features.

Uses dependency parsing, POS tags, and sentence structure to understand
what's being discussed and classify based on linguistic patterns.
"""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML
from spacy.language import Language

from analyze.entities import load_nlp
from analyze.models import Classification


@dataclass
class LinguisticFeatures:
    """Linguistic features extracted from text."""

    has_modal: bool  # would, could, should
    has_negation: bool  # not, n't, no
    has_question: bool  # ends with ?, wh-words
    has_imperative: bool  # command form
    all_lemmas: list[str]  # All lemmas (for keyword matching)
    verb_lemmas: list[str]  # All verb lemmas
    root_verbs: list[str]  # Root verbs of sentences
    subjects: list[str]  # Subject nouns
    objects: list[str]  # Object nouns
    entities: dict[str, list[str]]  # Entity type -> entity texts


def extract_linguistic_features(nlp: Language, text: str) -> LinguisticFeatures:
    """Extract linguistic features using spaCy dependency parsing."""
    doc = nlp(text)

    # Detect modals
    has_modal = any(token.tag_ == "MD" for token in doc)

    # Detect negation
    has_negation = any(token.dep_ == "neg" for token in doc)

    # Detect questions by punctuation
    has_question = "?" in text

    # Extract all lemmas (excluding punctuation and whitespace)
    all_lemmas = [
        token.lemma_.lower()
        for token in doc
        if not token.is_punct and not token.is_space
    ]

    # Extract verbs
    verb_lemmas = [
        token.lemma_.lower() for token in doc if token.pos_ in ("VERB", "AUX")
    ]

    # Extract root verbs (main action of each sentence)
    root_verbs = [
        sent.root.lemma_.lower()
        for sent in doc.sents
        if sent.root.pos_ in ("VERB", "AUX")
    ]

    # Extract subjects and objects using dependency relations
    subjects = []
    objects = []
    for token in doc:
        if token.dep_ in ("nsubj", "nsubjpass"):
            subjects.append(token.lemma_.lower())
        elif token.dep_ in ("dobj", "pobj", "attr"):
            objects.append(token.lemma_.lower())

    # Extract entities by type
    entities: dict[str, list[str]] = {}
    for ent in doc.ents:
        if ent.label_ not in entities:
            entities[ent.label_] = []
        # Preserve original case for entity names (important for filtering)
        entities[ent.label_].append(ent.text)

    return LinguisticFeatures(
        has_modal=has_modal,
        has_negation=has_negation,
        has_question=has_question,
        has_imperative=False,  # TODO: detect imperatives
        all_lemmas=all_lemmas,
        verb_lemmas=verb_lemmas,
        root_verbs=root_verbs,
        subjects=subjects,
        objects=objects,
        entities=entities,
    )


def load_semantic_rules(rules_path: Path | None = None) -> dict:
    """Load semantic classification rules from YAML."""
    if rules_path is None:
        rules_path = Path(__file__).parent.parent.parent / "classify_rules.yaml"

    yaml_loader = YAML(typ="safe")
    with open(rules_path) as f:
        return yaml_loader.load(f)


def classify_by_linguistic_features(
    features: LinguisticFeatures, rules: dict, text: str
) -> dict[str, float]:
    """Classify based on linguistic features and learned rules."""
    scores: dict[str, float] = {
        "outage": 0.0,
        "defect": 0.0,
        "enhancement": 0.0,
        "clarification": 0.0,
        "inquiry": 0.0,
        "routing_issue": 0.0,
    }

    text_lower = text.lower()

    # Load keyword patterns from rules (for bootstrapping)
    for category, config in rules.items():
        if category not in scores:
            continue

        keywords = config.get("keywords", [])
        weight = config.get("weight", 1.0)

        for keyword in keywords:
            kw_lower = keyword.lower()
            # Check multi-word phrases in original text
            if " " in kw_lower:
                if kw_lower in text_lower:
                    scores[category] += weight
            else:
                # Check single-word keywords against lemmas
                kw_normalized = kw_lower.replace(" ", "_")
                if kw_normalized in features.all_lemmas:
                    scores[category] += weight

    # Boost feature requests if modal present (only if no strong matches elsewhere)
    if features.has_modal and max(scores.values()) < 2.0:
        scores["enhancement"] += 1.5

    # Boost questions if question markers present
    if features.has_question:
        scores["inquiry"] += 1.5
        scores["clarification"] += 1.0

    # Negation + action verbs often indicate bugs (only if no strong routing_issue signal)
    if features.has_negation and features.verb_lemmas and scores["routing_issue"] < 1.0:
        scores["defect"] += 1.0

    return scores


def extract_keywords_and_products(features: LinguisticFeatures) -> list[str]:
    """Extract keyword and product names using spaCy NER.

    Relies on spaCy's trained model to identify ORG and PRODUCT entities,
    then filters out obvious non-keywords (code snippets, fragments, etc.).
    """
    keywords: set[str] = set()

    # Collect ORG and PRODUCT entities from spaCy NER
    for ent_type in ("ORG", "PRODUCT"):
        if ent_type in features.entities:
            keywords.update(features.entities[ent_type])

    # Filter out obvious garbage that spaCy incorrectly tagged
    filtered = set()
    for keyword in keywords:

        # Skip if contains newlines, tabs, or other control characters
        if any(ord(c) < 32 for c in keyword if c != ' '):
            continue

        # Skip if contains code-like characters
        code_chars = ["(", ")", "{", "}", "[", "]", "<", ">", ".", "/", "\\", "&", "+", "*", "="]
        if any(char in keyword for char in code_chars):
            continue

        # Skip if contains URL fragments
        if "http" in keyword.lower() or "://" in keyword:
            continue

        # Skip if starts/ends with quotes or special punctuation
        if keyword and (keyword[0] in ["'", '"', "`", "#"] or keyword[-1] in ["'", '"', "`"]):
            continue

        # Skip if it's mostly non-alphabetic (code/variables tend to have numbers/symbols)
        alpha_count = sum(c.isalpha() or c.isspace() for c in keyword)
        if len(keyword) > 0 and alpha_count / len(keyword) < 0.75:
            continue

        # Skip obvious variable names (all lowercase single word)
        if " " not in keyword and keyword.islower():
            continue

        # Skip camelCase variable names (has lowercase then uppercase in middle)
        if " " not in keyword and len(keyword) > 1:
            has_camel = any(
                keyword[i].islower() and keyword[i + 1].isupper()
                for i in range(len(keyword) - 1)
            )
            if has_camel:
                continue

        filtered.add(keyword)

    return sorted(filtered)[:10]


def classify_issue(
    title: str,
    conversation_text: str,
    nlp: Language | None = None,
) -> Classification:
    """Classify an issue using NLP linguistic features.

    Args:
        title: Issue title
        conversation_text: Full conversation content
        nlp: Optional spaCy model (will load if not provided)

    Returns:
        Classification with type, confidence, and extracted keywords
    """
    if nlp is None:
        nlp = load_nlp()

    full_text = f"{title}\n{conversation_text}"

    # Extract linguistic features
    features = extract_linguistic_features(nlp, full_text)

    # Load rules and classify
    rules = load_semantic_rules()
    scores = classify_by_linguistic_features(features, rules, full_text)

    # If no clear pattern, default to inquiry with low confidence
    if max(scores.values()) == 0:
        return Classification(
            type="inquiry",
            confidence=0.3,
            keywords=[],
            summary=title[:200],
        )

    # Find best category
    best_category = max(scores, key=lambda k: scores[k])
    total_score = sum(scores.values())
    confidence = min(scores[best_category] / total_score, 0.99)

    # Extract keywords
    keywords = extract_keywords_and_products(features)

    return Classification(
        type=best_category,
        confidence=round(confidence, 2),
        keywords=keywords,
        summary=title[:200],
    )
