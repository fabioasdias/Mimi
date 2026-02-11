"""Test script for semantic similarity matching.

Run after installing en_core_web_lg:
    python -m spacy download en_core_web_lg
"""

import spacy

try:
    nlp = spacy.load("en_core_web_lg")
    print(f"Loaded en_core_web_lg")
    print(f"  Vectors: {nlp.vocab.vectors_length}")
    print()

    # Test pairs that should be similar
    pairs = [
        ("broken", "failing"),
        ("outage", "downtime"),
        ("bug", "defect"),
        ("feature", "enhancement"),
        ("down", "offline"),
        ("error", "exception"),
        ("crash", "fail"),
    ]

    print("Semantic similarity scores:")
    print("-" * 45)
    for word1, word2 in pairs:
        token1 = nlp(word1)[0]
        token2 = nlp(word2)[0]
        similarity = token1.similarity(token2)
        match_status = "PASS" if similarity >= 0.7 else "FAIL"
        print(f"{match_status:4s} {word1:12s} <-> {word2:12s}: {similarity:.3f}")

    print()
    print("Threshold: 0.7 (scores >= 0.7 will match)")

except OSError as e:
    print(f"ERROR: Model not found: {e}")
    print()
    print("Install with:")
    print("  python -m spacy download en_core_web_lg")
