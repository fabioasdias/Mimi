"""Tests for service entity extraction."""

from analyze.entities import extract_services, load_nlp


def test_extract_service_names():
    """Test extraction of service names with pattern matching."""
    text = "The auth-service is failing to connect to payment-api and user-db."
    services = extract_services(text)
    assert "auth-service" in services
    assert "payment-api" in services
    assert "user-db" in services
    assert len(services) == 3


def test_extract_worker_and_queue():
    """Test extraction of worker and queue patterns."""
    text = "The notification-worker is stuck. Check email-queue."
    services = extract_services(text)
    assert "notification-worker" in services
    assert "email-queue" in services


def test_extract_gateway_and_cache():
    """Test extraction of gateway and cache patterns."""
    text = "api-gateway timeout, redis-cache is down."
    services = extract_services(text)
    assert "api-gateway" in services
    assert "redis-cache" in services


def test_stopword_filtering():
    """Test that stopword services are filtered out."""
    text = "The the-service is failing. Contact customer-service."
    services = extract_services(text)
    assert "the-service" not in services
    assert "customer-service" not in services


def test_known_services_matching():
    """Test matching against a known service list."""
    text = "We have an issue with Kubernetes and PostgreSQL."
    known = {"kubernetes", "postgresql", "redis"}
    services = extract_services(text, known_services=known)
    assert "kubernetes" in services
    assert "postgresql" in services
    assert "redis" not in services  # Not mentioned in text


def test_case_insensitive():
    """Test that service matching is case-insensitive."""
    text = "AUTH-SERVICE and Payment-Api are down."
    services = extract_services(text)
    assert "auth-service" in services
    assert "payment-api" in services


def test_empty_text():
    """Test with empty text."""
    services = extract_services("")
    assert services == []


def test_no_services():
    """Test text with no service names."""
    text = "This is just a random message without any services."
    services = extract_services(text)
    assert services == []


def test_duplicate_services():
    """Test that duplicate services are deduplicated."""
    text = "auth-service failed. Restart auth-service."
    services = extract_services(text)
    assert services.count("auth-service") == 1


def test_sorted_output():
    """Test that output is sorted alphabetically."""
    text = "zebra-api, apple-service, banana-worker"
    services = extract_services(text)
    assert services == ["apple-service", "banana-worker", "zebra-api"]
