"""Tests for the GitHub connector with mocked HTTP responses."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from gather.config import SourceConfig
from gather.connectors.github import GitHubConnector


def _make_issue(
    number: int,
    title: str = "Test issue",
    body: str = "Issue body",
    state: str = "open",
    comments_count: int = 0,
    labels: list[str] | None = None,
    is_pr: bool = False,
) -> dict:
    issue = {
        "number": number,
        "title": title,
        "body": body,
        "state": state,
        "state_reason": None,
        "html_url": f"https://github.com/owner/repo/issues/{number}",
        "created_at": "2026-01-20T10:00:00Z",
        "updated_at": "2026-01-21T15:00:00Z",
        "user": {"login": "alice", "id": 1001},
        "assignees": [{"login": "bob", "id": 1002}],
        "labels": [{"name": l} for l in (labels or [])],
        "comments": comments_count,
    }
    if is_pr:
        issue["pull_request"] = {"url": "..."}
    return issue


def _make_comment(author: str, author_id: int, body: str) -> dict:
    return {
        "user": {"login": author, "id": author_id},
        "body": body,
        "created_at": "2026-01-21T12:00:00Z",
    }


def _mock_response(data: list | dict, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        json=data,
        request=httpx.Request("GET", "https://api.github.com/test"),
    )


@pytest.fixture
def connector():
    config = SourceConfig(
        type="github",
        auth={"token": "fake-token"},
        filters={
            "repos": ["owner/repo"],
            "labels": [],
            "state": "all",
        },
    )
    return GitHubConnector("test-github", config)


@pytest.mark.asyncio
async def test_fetch_basic_issue(connector):
    """Fetches an issue with no comments."""
    issues = [_make_issue(1, title="Bug report", body="Something broke")]

    with patch.object(connector._client, "get", new_callable=AsyncMock) as mock_get:
        # First call: list issues, second call: empty page
        mock_get.side_effect = [
            _mock_response(issues),
            _mock_response([]),
        ]
        tickets = await connector.fetch_tickets()

    assert len(tickets) == 1
    t = tickets[0]
    assert t.reference.id == "owner/repo#1"
    assert t.title == "Bug report"
    assert t.reference.source == "github"
    assert len(t.people) == 2  # reporter + assignee
    assert t.people[0].role == "reporter"
    assert t.people[1].role == "assignee"


@pytest.mark.asyncio
async def test_fetch_issue_with_comments(connector):
    """Fetches an issue and its comments."""
    issues = [_make_issue(42, title="Help needed", body="How do I?", comments_count=1)]
    comments = [_make_comment("carol", 1003, "Try this...")]

    with patch.object(connector._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [
            _mock_response(issues),     # list issues page 1
            _mock_response(comments),   # comments for issue 42
            _mock_response([]),         # list issues page 2 (empty)
        ]
        tickets = await connector.fetch_tickets()

    assert len(tickets) == 1
    t = tickets[0]
    assert len(t.conversation) == 2  # body + 1 comment
    assert t.conversation[0].content == "How do I?"
    assert t.conversation[1].content == "Try this..."
    assert t.conversation[1].author == "carol"
    # carol should appear in people as commenter
    commenter = [p for p in t.people if p.role == "commenter"]
    assert len(commenter) == 1
    assert commenter[0].name == "carol"


@pytest.mark.asyncio
async def test_pull_requests_are_skipped(connector):
    """PRs returned by the issues endpoint should be ignored."""
    issues = [
        _make_issue(1, title="Real issue"),
        _make_issue(2, title="A pull request", is_pr=True),
    ]

    with patch.object(connector._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [
            _mock_response(issues),
            _mock_response([]),
        ]
        tickets = await connector.fetch_tickets()

    assert len(tickets) == 1
    assert tickets[0].title == "Real issue"


@pytest.mark.asyncio
async def test_since_days_filter(connector):
    """since_days filter should produce a since param in the API call."""
    connector.filters["since_days"] = 7
    issues: list = []

    with patch.object(connector._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(issues)
        await connector.fetch_tickets()

    call_kwargs = mock_get.call_args_list[0]
    params = call_kwargs.kwargs.get("params") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else call_kwargs.kwargs.get("params", {})
    assert "since" in params


@pytest.mark.asyncio
async def test_raw_text_includes_title_and_body(connector):
    """raw_text should contain title and body for cross-reference matching."""
    issues = [_make_issue(1, title="See AUTH-1234", body="Related to PLAT-5678")]

    with patch.object(connector._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [
            _mock_response(issues),
            _mock_response([]),
        ]
        tickets = await connector.fetch_tickets()

    assert "AUTH-1234" in tickets[0].raw_text
    assert "PLAT-5678" in tickets[0].raw_text
