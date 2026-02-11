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
    """Load semantic classification rules from YAML.

    Also loads custom rules from classify_rules.custom.yaml if it exists,
    which allows for team-specific overrides and domain terminology.
    """
    if rules_path is None:
        rules_path = Path(__file__).parent.parent.parent / "classify_rules.yaml"

    yaml_loader = YAML(typ="safe")
    with open(rules_path) as f:
        rules = yaml_loader.load(f)

    # Extract config section (e.g., similarity_threshold)
    config = rules.pop("config", {})
    rules["_config"] = config

    # Try to load custom rules overlay
    custom_path = rules_path.parent / "classify_rules.custom.yaml"
    if custom_path.exists():
        with open(custom_path) as f:
            custom_rules = yaml_loader.load(f) or {}

        # Store custom sections separately
        rules["_contexts"] = custom_rules.get("contexts", {})
        rules["_overrides"] = custom_rules.get("overrides", {})
        rules["_keyword_overrides"] = custom_rules.get("keyword_overrides", {})
        rules["_corrections"] = custom_rules.get("corrections", {})

        # Merge custom config if present
        if "config" in custom_rules:
            rules["_config"].update(custom_rules["config"])

    return rules


def classify_by_linguistic_features(
    features: LinguisticFeatures,
    rules: dict,
    text: str,
    context: str | None = None,
    nlp: Language | None = None,
    similarity_threshold: float = 0.5,
) -> dict[str, float]:
    """Classify based on linguistic features and learned rules with semantic similarity.

    Args:
        features: Extracted linguistic features
        rules: Classification rules (including custom overrides)
        text: Full text to classify
        context: Optional context name (e.g., source name) for context-specific rules
        nlp: Optional spaCy model with word vectors for similarity matching
        similarity_threshold: Minimum similarity score for fuzzy keyword matching (default 0.7)
    """
    scores: dict[str, float] = {
        "outage": 0.0,
        "defect": 0.0,
        "enhancement": 0.0,
        "inquiry": 0.0,
        "routing_issue": 0.0,
        "action": 0.0,
    }

    text_lower = text.lower()

    # Build merged rule set: base + context + overrides
    merged_rules = {}

    # Start with base rules
    for category in scores.keys():
        if category in rules:
            merged_rules[category] = {
                "keywords": rules[category].get("keywords", []),
                "weight": rules[category].get("weight", 1.0),
            }

    # Apply context-specific rules if context provided
    if context and "_contexts" in rules:
        contexts = rules["_contexts"]
        if context in contexts:
            for category, config in contexts[context].items():
                if category in merged_rules:
                    # Merge keywords and use context weight if higher
                    merged_rules[category]["keywords"].extend(config.get("keywords", []))
                    merged_rules[category]["weight"] = max(
                        merged_rules[category]["weight"],
                        config.get("weight", 1.0)
                    )

    # Apply global overrides (highest priority)
    if "_overrides" in rules:
        for category, config in rules["_overrides"].items():
            if category in merged_rules:
                merged_rules[category]["keywords"].extend(config.get("keywords", []))
                if "weight" in config:
                    merged_rules[category]["weight"] = config["weight"]

    # Check if we have word vectors available for similarity matching
    has_vectors = nlp is not None and nlp.vocab.vectors_length > 0

    # Build token cache for similarity checks (if vectors available)
    text_tokens = {}
    if has_vectors:
        doc = nlp(text.lower())
        text_tokens = {token.lemma_: token for token in doc if token.has_vector}

    # Score based on merged rules
    for category, config in merged_rules.items():
        keywords = config["keywords"]
        weight = config["weight"]

        for keyword in keywords:
            kw_lower = keyword.lower()
            matched = False

            # EXACT MATCH (existing logic)
            if " " in kw_lower:
                # Multi-word phrase
                if kw_lower in text_lower:
                    scores[category] += weight
                    matched = True
            else:
                # Check single-word keywords against lemmas
                kw_normalized = kw_lower.replace(" ", "_")
                if kw_normalized in features.all_lemmas:
                    scores[category] += weight
                    matched = True

            # SIMILARITY MATCH (only if exact match failed and vectors available)
            if not matched and has_vectors and " " not in kw_lower:
                try:
                    kw_token = nlp(kw_lower)[0]
                    if kw_token.has_vector:
                        # Check similarity against all text tokens
                        for text_lemma, text_token in text_tokens.items():
                            similarity = kw_token.similarity(text_token)
                            if similarity >= similarity_threshold:
                                # Partial score based on similarity
                                scores[category] += weight * similarity
                                break  # Only count best match per keyword
                except (IndexError, KeyError):
                    pass  # Skip if token can't be processed

    # Boost feature requests if modal present (only if no strong matches elsewhere)
    if features.has_modal and max(scores.values()) < 2.0:
        scores["enhancement"] += 1.5

    # Boost questions if question markers present (documentation failure)
    if features.has_question:
        scores["inquiry"] += 2.0

    # Negation + action verbs often indicate bugs (only if no strong routing_issue signal)
    if features.has_negation and features.verb_lemmas and scores["routing_issue"] < 1.0:
        scores["defect"] += 1.0

    return scores


def extract_keywords_and_products(
    features: LinguisticFeatures, rules: dict | None = None
) -> list[str]:
    """Extract keyword and product names using spaCy NER.

    Relies on spaCy's trained model to identify ORG and PRODUCT entities,
    then filters out obvious non-keywords (code snippets, fragments, etc.).

    Args:
        features: Linguistic features with NER entities
        rules: Optional rules dict with keyword overrides
    """
    keywords: set[str] = set()

    # Collect ORG and PRODUCT entities from spaCy NER
    for ent_type in ("ORG", "PRODUCT"):
        if ent_type in features.entities:
            keywords.update(features.entities[ent_type])

    # Apply keyword overrides if available
    if rules and "_keyword_overrides" in rules:
        overrides = rules["_keyword_overrides"]

        # Always include specified keywords
        if "always_include" in overrides:
            keywords.update(overrides["always_include"])

        # Always exclude specified keywords
        if "always_exclude" in overrides:
            exclude_set = set(overrides["always_exclude"])
            keywords = keywords - exclude_set

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
    issue_id: str | None = None,
    context: str | None = None,
) -> Classification:
    """Classify an issue using NLP linguistic features.

    Args:
        title: Issue title
        conversation_text: Full conversation content
        nlp: Optional spaCy model (will load if not provided)
        issue_id: Optional issue ID to check for manual corrections
        context: Optional context name (e.g., source) for context-specific rules

    Returns:
        Classification with type, confidence, and extracted keywords
    """
    if nlp is None:
        nlp = load_nlp()

    # Load rules (including custom rules if they exist)
    rules = load_semantic_rules()

    # Check if this issue has a manual correction
    if issue_id and "_corrections" in rules:
        corrections = rules["_corrections"]
        if issue_id in corrections:
            corrected_type = corrections[issue_id]
            # Return corrected classification with max confidence
            return Classification(
                type=corrected_type,
                confidence=0.99,  # High confidence for manual corrections
                keywords=[],  # Will be extracted below
                summary=title[:200],
            )

    full_text = f"{title}\n{conversation_text}"

    # Extract linguistic features
    features = extract_linguistic_features(nlp, full_text)

    # Get similarity threshold from config if available
    similarity_threshold = 0.5  # default
    if "_config" in rules:
        similarity_threshold = rules["_config"].get("similarity_threshold", 0.5)

    # Classify using context-aware rules with semantic similarity
    scores = classify_by_linguistic_features(
        features, rules, full_text, context=context, nlp=nlp, similarity_threshold=similarity_threshold
    )

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

    # Extract keywords with overrides applied
    keywords = extract_keywords_and_products(features, rules)

    return Classification(
        type=best_category,
        confidence=round(confidence, 2),
        keywords=keywords,
        summary=title[:200],
    )
