"""Service and component entity extraction.

Uses spaCy NER plus custom pattern matching for known service names.
"""

import re

import spacy
from spacy.language import Language

# Common infrastructure/service patterns
SERVICE_PATTERNS = [
    re.compile(r"\b(\w+-service)\b", re.IGNORECASE),
    re.compile(r"\b(\w+-api)\b", re.IGNORECASE),
    re.compile(r"\b(\w+-gateway)\b", re.IGNORECASE),
    re.compile(r"\b(\w+-worker)\b", re.IGNORECASE),
    re.compile(r"\b(\w+-queue)\b", re.IGNORECASE),
    re.compile(r"\b(\w+-db)\b", re.IGNORECASE),
    re.compile(r"\b(\w+-cache)\b", re.IGNORECASE),
]

# Stopwords to filter out false positive service matches
STOP_SERVICES = {
    "the-service",
    "a-service",
    "this-service",
    "our-service",
    "my-service",
    "your-service",
    "customer-service",
}


def load_nlp() -> Language:
    """Load spaCy model, downloading if needed."""
    try:
        return spacy.load("en_core_web_sm")
    except OSError:
        from spacy.cli import download

        download("en_core_web_sm")
        return spacy.load("en_core_web_sm")


def extract_services(
    text: str, known_services: set[str] | None = None
) -> list[str]:
    """Extract service/component names from text.

    Combines regex pattern matching with optional known service list.
    """
    services: set[str] = set()

    # Pattern-based extraction
    for pattern in SERVICE_PATTERNS:
        for match in pattern.finditer(text):
            name = match.group(1).lower()
            if name not in STOP_SERVICES:
                services.add(name)

    # Match against known services if provided
    if known_services:
        text_lower = text.lower()
        for svc in known_services:
            if svc.lower() in text_lower:
                services.add(svc.lower())

    return sorted(services)


def extract_services_spacy(nlp: Language, text: str) -> list[str]:
    """Use spaCy NER to find organization/product entities as potential services."""
    doc = nlp(text)
    entities: set[str] = set()

    for ent in doc.ents:
        if ent.label_ in ("ORG", "PRODUCT"):
            entities.add(ent.text.lower())

    return sorted(entities)
