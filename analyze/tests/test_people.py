"""Tests for people identity resolution."""

from analyze.models import IssueAnalysis, Classification
from analyze.people import resolve_identities, build_service_graph


def test_resolve_single_person():
    """Test identity resolution with a single person."""
    tickets = [
        {
            "id": "ticket-1",
            "people": [
                {
                    "source": "github",
                    "source_id": "123",
                    "name": "Alice",
                    "email": "alice@example.com",
                }
            ],
        }
    ]

    graph, mapping = resolve_identities(tickets)
    assert len(graph.nodes) == 1
    assert graph.nodes[0].label == "Alice"
    assert len(graph.nodes[0].identities) == 1
    assert len(graph.edges) == 1
    assert graph.edges[0].role == "participant"


def test_resolve_same_email():
    """Test that people with same email are merged."""
    tickets = [
        {
            "id": "ticket-1",
            "people": [
                {
                    "source": "github",
                    "source_id": "123",
                    "name": "Alice",
                    "email": "alice@example.com",
                }
            ],
        },
        {
            "id": "ticket-2",
            "people": [
                {
                    "source": "jira",
                    "source_id": "alice",
                    "name": "Alice Smith",
                    "email": "alice@example.com",
                }
            ],
        },
    ]

    graph, mapping = resolve_identities(tickets)
    assert len(graph.nodes) == 1
    assert len(graph.nodes[0].identities) == 2
    assert graph.nodes[0].label == "Alice"  # Prefers first with email
    assert len(graph.edges) == 2  # One edge per ticket


def test_resolve_fuzzy_name_match():
    """Test fuzzy name matching across sources with similar names."""
    # Use names that are similar enough to match (>85% similarity)
    # "Alice M Johnson" vs "Alice Johnson" = 93% match
    tickets = [
        {
            "id": "ticket-1",
            "people": [
                {"source": "github", "source_id": "123", "name": "Alice M Johnson"}
            ],
        },
        {
            "id": "ticket-2",
            "people": [
                {"source": "slack", "source_id": "U456", "name": "Alice Johnson"}
            ],
        },
    ]

    graph, mapping = resolve_identities(tickets)
    assert len(graph.nodes) == 1
    assert len(graph.nodes[0].identities) == 2


def test_resolve_different_people():
    """Test that different people stay separate."""
    tickets = [
        {
            "id": "ticket-1",
            "people": [
                {
                    "source": "github",
                    "source_id": "123",
                    "name": "Alice",
                    "email": "alice@example.com",
                }
            ],
        },
        {
            "id": "ticket-2",
            "people": [
                {
                    "source": "github",
                    "source_id": "456",
                    "name": "Bob",
                    "email": "bob@example.com",
                }
            ],
        },
    ]

    graph, mapping = resolve_identities(tickets)
    assert len(graph.nodes) == 2
    assert {n.label for n in graph.nodes} == {"Alice", "Bob"}


def test_resolve_no_cross_source_same_name():
    """Test that same name in same source doesn't merge."""
    tickets = [
        {
            "id": "ticket-1",
            "people": [
                {"source": "github", "source_id": "123", "name": "Alice"}
            ],
        },
        {
            "id": "ticket-2",
            "people": [
                {"source": "github", "source_id": "456", "name": "Alice"}
            ],
        },
    ]

    graph, mapping = resolve_identities(tickets)
    # Same source, different source_id -> different people even with same name
    assert len(graph.nodes) == 2


def test_resolve_case_insensitive_email():
    """Test that email matching is case-insensitive."""
    tickets = [
        {
            "id": "ticket-1",
            "people": [
                {
                    "source": "github",
                    "source_id": "123",
                    "name": "Alice",
                    "email": "Alice@Example.COM",
                }
            ],
        },
        {
            "id": "ticket-2",
            "people": [
                {
                    "source": "jira",
                    "source_id": "alice",
                    "name": "Alice",
                    "email": "alice@example.com",
                }
            ],
        },
    ]

    graph, mapping = resolve_identities(tickets)
    assert len(graph.nodes) == 1
    assert len(graph.nodes[0].identities) == 2


def test_resolve_person_roles():
    """Test that person roles are preserved in edges."""
    tickets = [
        {
            "id": "ticket-1",
            "people": [
                {
                    "source": "github",
                    "source_id": "123",
                    "name": "Alice",
                    "role": "reporter",
                }
            ],
        }
    ]

    graph, mapping = resolve_identities(tickets)
    assert len(graph.edges) == 1
    assert graph.edges[0].role == "reporter"


def test_build_service_graph_empty():
    """Test service graph with no services."""
    analyses = [
        IssueAnalysis(
            id="ticket-1",
            classification=Classification(
                type="bug", confidence=0.9, services=[], summary="Test"
            ),
        )
    ]

    graph = build_service_graph(analyses)
    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0


def test_build_service_graph_single_service():
    """Test service graph with single service per issue."""
    analyses = [
        IssueAnalysis(
            id="ticket-1",
            classification=Classification(
                type="bug",
                confidence=0.9,
                services=["auth-service"],
                summary="Test",
            ),
        ),
        IssueAnalysis(
            id="ticket-2",
            classification=Classification(
                type="outage",
                confidence=0.95,
                services=["auth-service"],
                summary="Test",
            ),
        ),
    ]

    graph = build_service_graph(analyses)
    assert len(graph.nodes) == 1
    assert graph.nodes[0].id == "auth-service"
    assert graph.nodes[0].issue_count == 2
    assert len(graph.edges) == 0  # No co-occurrence (single service per issue)


def test_build_service_graph_co_occurrence():
    """Test service co-occurrence edges."""
    analyses = [
        IssueAnalysis(
            id="ticket-1",
            classification=Classification(
                type="bug",
                confidence=0.9,
                services=["auth-service", "user-db"],
                summary="Test",
            ),
        ),
        IssueAnalysis(
            id="ticket-2",
            classification=Classification(
                type="bug",
                confidence=0.9,
                services=["auth-service", "user-db"],
                summary="Test",
            ),
        ),
    ]

    graph = build_service_graph(analyses)
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert {edge.source, edge.target} == {"auth-service", "user-db"}
    assert edge.co_occurrence == 2


def test_build_service_graph_multiple_services():
    """Test issue with multiple services creates multiple edges."""
    analyses = [
        IssueAnalysis(
            id="ticket-1",
            classification=Classification(
                type="bug",
                confidence=0.9,
                services=["auth-service", "payment-api", "user-db"],
                summary="Test",
            ),
        )
    ]

    graph = build_service_graph(analyses)
    assert len(graph.nodes) == 3
    assert len(graph.edges) == 3  # 3 services = 3 pairs
    # All nodes should have issue_count = 1
    for node in graph.nodes:
        assert node.issue_count == 1
