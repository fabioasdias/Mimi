"""Tests for the rule-based classifier."""

from analyze.classifier import classify_issue


def test_classify_outage():
    """Test outage classification."""
    classification = classify_issue(
        "Service is down",
        "We're experiencing a 503 error. The service is unavailable.",
    )
    assert classification.type == "outage"
    assert classification.confidence > 0.5


def test_classify_bug():
    """Test bug classification."""
    classification = classify_issue(
        "Error in checkout",
        "The checkout button doesn't work. Getting an unexpected exception.",
    )
    assert classification.type == "bug"
    assert classification.confidence > 0.5


def test_classify_new_feature():
    """Test feature request classification."""
    classification = classify_issue(
        "Feature request: Dark mode",
        "Would be nice if we could add dark mode support. This is an enhancement.",
    )
    assert classification.type == "new_feature"
    assert classification.confidence > 0.5


def test_classify_user_error():
    """Test user error/question classification."""
    classification = classify_issue(
        "How do I export data?",
        "I'm confused about how to use the export feature. Help me understand.",
    )
    assert classification.type == "user_error"
    assert classification.confidence > 0.5


def test_classify_wrong_team():
    """Test wrong team classification."""
    classification = classify_issue(
        "Redirect to Platform team",
        "This should go to the platform team. Not our responsibility.",
    )
    assert classification.type == "wrong_team"
    assert classification.confidence > 0.5


def test_classify_question():
    """Test question classification."""
    classification = classify_issue(
        "Quick question about API",
        "Anyone know how the rate limiting works?",
    )
    assert classification.type == "question"
    assert classification.confidence > 0.3


def test_classify_no_match():
    """Test default classification when no patterns match."""
    classification = classify_issue(
        "Random title",
        "Some content without any keywords.",
    )
    assert classification.type == "question"
    assert classification.confidence == 0.3


def test_classify_multiple_categories():
    """Test that the highest scoring category wins."""
    classification = classify_issue(
        "Outage and bug",
        "Service is down. We have a bug causing timeouts and errors.",
    )
    # Should classify as outage (higher weight) over bug
    assert classification.type == "outage"


def test_summary_truncation():
    """Test that summary is truncated to 200 chars."""
    long_title = "x" * 300
    classification = classify_issue(long_title, "Some content")
    assert len(classification.summary) == 200
    assert classification.summary == long_title[:200]
