"""Keyword and component entity extraction.

Uses spaCy NER plus custom pattern matching for known keyword names.
"""

import re

import spacy
from spacy.language import Language

# Common infrastructure/keyword patterns
KEYWORD_PATTERNS = [
    re.compile(r"\b(\w+-service)\b", re.IGNORECASE),
    re.compile(r"\b(\w+-api)\b", re.IGNORECASE),
    re.compile(r"\b(\w+-gateway)\b", re.IGNORECASE),
    re.compile(r"\b(\w+-worker)\b", re.IGNORECASE),
    re.compile(r"\b(\w+-queue)\b", re.IGNORECASE),
    re.compile(r"\b(\w+-db)\b", re.IGNORECASE),
    re.compile(r"\b(\w+-cache)\b", re.IGNORECASE),
]

# Stopwords to filter out false positive keyword matches
STOP_KEYWORDS = {
    "the-service",
    "a-service",
    "this-service",
    "our-service",
    "my-service",
    "your-service",
    "customer-service",
}


def load_nlp() -> Language:
    """Load spaCy model with word vectors for similarity matching.

    Requires en_core_web_lg (500k vectors) for semantic similarity.
    Install with: python -m spacy download en_core_web_lg
    """
    try:
        return spacy.load("en_core_web_lg")
    except OSError:
        from spacy.cli import download
        download("en_core_web_lg")
        return spacy.load("en_core_web_lg")


def extract_keywords(
    text: str, known_keywords: set[str] | None = None
) -> list[str]:
    """Extract keyword/component names from text.

    Combines regex pattern matching with optional known keyword list.
    """
    keywords: set[str] = set()

    # Pattern-based extraction
    for pattern in KEYWORD_PATTERNS:
        for match in pattern.finditer(text):
            name = match.group(1).lower()
            if name not in STOP_KEYWORDS:
                keywords.add(name)

    # Match against known keywords if provided
    if known_keywords:
        text_lower = text.lower()
        for kw in known_keywords:
            if kw.lower() in text_lower:
                keywords.add(kw.lower())

    return sorted(keywords)


def extract_keywords_spacy(nlp: Language, text: str) -> list[str]:
    """Use spaCy NER to find organization/product entities as potential keywords."""
    doc = nlp(text)
    entities: set[str] = set()

    for ent in doc.ents:
        if ent.label_ in ("ORG", "PRODUCT"):
            entities.add(ent.text.lower())

    return sorted(entities)
