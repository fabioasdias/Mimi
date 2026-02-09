"""Tests for the Jira connector with mocked HTTP responses."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from gather.config import SourceConfig
from gather.connectors.jira import JiraConnector


def _make_issue(
    key: str,
    summary: str = "Test issue",
    status: str = "Open",
    reporter: dict | None = None,
    assignee: dict | None = None,
    comments: list[dict] | None = None,
) -> dict:
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "status": {"name": status},
            "created": "2026-01-20T10:00:00+00:00",
            "updated": "2026-01-21T15:00:00+00:00",
            "reporter": reporter or {"accountId": "u1", "displayName": "Alice", "emailAddress": "alice@co.com"},
            "assignee": assignee,
            "comment": {"comments": comments or []},
        },
    }


def _make_comment(account_id: str, display_name: str, body_text: str) -> dict:
    return {
        "author": {"accountId": account_id, "displayName": display_name},
        "created": "2026-01-21T12:00:00+00:00",
        "body": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": body_text}]}]},
    }


def _mock_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        json=data,
        request=httpx.Request("GET", "https://co.atlassian.net/test"),
    )


@pytest.fixture
def connector():
    config = SourceConfig(
        type="jira",
        auth={"base_url": "https://co.atlassian.net", "email": "a@co.com", "api_token": "fake"},
        filters={"jql": "project = AUTH"},
    )
    return JiraConnector("test-jira", config)


@pytest.mark.asyncio
async def test_fetch_basic_issue(connector):
    search_resp = {"issues": [_make_issue("AUTH-1", summary="Login broken")], "total": 1}

    with patch.object(connector._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(search_resp)
        tickets = await connector.fetch_tickets()

    assert len(tickets) == 1
    t = tickets[0]
    assert t.reference.id == "AUTH-1"
    assert t.reference.source == "jira"
    assert t.title == "Login broken"
    assert t.people[0].role == "reporter"
    assert t.people[0].email == "alice@co.com"


@pytest.mark.asyncio
async def test_issue_with_assignee(connector):
    assignee = {"accountId": "u2", "displayName": "Bob", "emailAddress": "bob@co.com"}
    search_resp = {"issues": [_make_issue("AUTH-2", assignee=assignee)], "total": 1}

    with patch.object(connector._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(search_resp)
        tickets = await connector.fetch_tickets()

    assert len(tickets[0].people) == 2
    assert tickets[0].people[1].role == "assignee"
    assert tickets[0].people[1].name == "Bob"


@pytest.mark.asyncio
async def test_issue_with_comments(connector):
    comments = [_make_comment("u3", "Carol", "Looking into this")]
    search_resp = {"issues": [_make_issue("AUTH-3", comments=comments)], "total": 1}

    with patch.object(connector._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(search_resp)
        tickets = await connector.fetch_tickets()

    t = tickets[0]
    assert len(t.conversation) == 1
    assert t.conversation[0].content == "Looking into this"
    assert t.conversation[0].author == "Carol"
    # Carol should be in people as commenter
    commenters = [p for p in t.people if p.role == "commenter"]
    assert len(commenters) == 1


@pytest.mark.asyncio
async def test_comment_author_dedup(connector):
    """Comment by the reporter shouldn't duplicate them in people."""
    comments = [_make_comment("u1", "Alice", "Adding more info")]
    search_resp = {"issues": [_make_issue("AUTH-4", comments=comments)], "total": 1}

    with patch.object(connector._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(search_resp)
        tickets = await connector.fetch_tickets()

    # Only reporter, no duplicate commenter
    assert len(tickets[0].people) == 1


@pytest.mark.asyncio
async def test_pagination(connector):
    page1 = {"issues": [_make_issue(f"AUTH-{i}") for i in range(50)], "total": 75}
    page2 = {"issues": [_make_issue(f"AUTH-{i}") for i in range(50, 75)], "total": 75}

    with patch.object(connector._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [_mock_response(page1), _mock_response(page2)]
        tickets = await connector.fetch_tickets()

    assert len(tickets) == 75


@pytest.mark.asyncio
async def test_no_reporter_no_assignee(connector):
    """Issue with neither reporter nor assignee."""
    issue = {
        "key": "AUTH-5",
        "fields": {
            "summary": "Orphan issue",
            "status": {"name": "Open"},
            "created": "2026-01-20T10:00:00+00:00",
            "updated": "2026-01-21T15:00:00+00:00",
            "reporter": None,
            "assignee": None,
            "comment": {"comments": []},
        },
    }
    search_resp = {"issues": [issue], "total": 1}

    with patch.object(connector._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(search_resp)
        tickets = await connector.fetch_tickets()

    assert len(tickets[0].people) == 0


def test_extract_text_string():
    assert JiraConnector._extract_text("plain text") == "plain text"


def test_extract_text_adf():
    adf = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Hello "}, {"type": "text", "text": "world"}]}
        ],
    }
    assert JiraConnector._extract_text(adf) == "Hello  world"
