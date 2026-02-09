"""Tests for the Slack connector with mocked HTTP responses."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from gather.config import SourceConfig
from gather.connectors.slack import SlackConnector


def _mock_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        json=data,
        request=httpx.Request("GET", "https://slack.com/api/test"),
    )


def _make_thread_parent(thread_ts: str, user: str, text: str) -> dict:
    return {"ts": thread_ts, "thread_ts": thread_ts, "user": user, "text": text}


def _make_reply(ts: str, thread_ts: str, user: str, text: str) -> dict:
    return {"ts": ts, "thread_ts": thread_ts, "user": user, "text": text}


@pytest.fixture
def connector():
    config = SourceConfig(
        type="slack",
        auth={"bot_token": "xoxb-fake"},
        filters={"channels": ["C_SUPPORT"]},
    )
    return SlackConnector("test-slack", config)


@pytest.mark.asyncio
async def test_fetch_thread(connector):
    history_resp = {
        "ok": True,
        "messages": [
            _make_thread_parent("1706000001.000100", "U1", "Help! Auth is down"),
            {"ts": "1706000002.000200", "user": "U2", "text": "non-threaded message"},  # no thread_ts
        ],
    }
    replies_resp = {
        "ok": True,
        "messages": [
            _make_thread_parent("1706000001.000100", "U1", "Help! Auth is down"),
            _make_reply("1706000001.000200", "1706000001.000100", "U2", "On it"),
        ],
    }
    user1_resp = {"ok": True, "user": {"real_name": "Alice", "profile": {"email": "alice@co.com"}}}
    user2_resp = {"ok": True, "user": {"real_name": "Bob", "profile": {"email": "bob@co.com"}}}

    with patch.object(connector._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [
            _mock_response(history_resp),   # conversations.history
            _mock_response(replies_resp),   # conversations.replies (inside _parse_thread)
            _mock_response(user1_resp),     # users.info U1
            _mock_response(user2_resp),     # users.info U2
        ]
        tickets = await connector.fetch_tickets()

    assert len(tickets) == 1
    t = tickets[0]
    assert t.reference.source == "slack"
    assert t.reference.meta["channel"] == "C_SUPPORT"
    assert len(t.conversation) == 2
    assert t.conversation[0].content == "Help! Auth is down"
    assert t.conversation[1].content == "On it"
    assert t.people[0].role == "reporter"
    assert t.people[1].role == "participant"


@pytest.mark.asyncio
async def test_api_error_skips_channel(connector):
    error_resp = {"ok": False, "error": "channel_not_found"}

    with patch.object(connector._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(error_resp)
        tickets = await connector.fetch_tickets()

    assert len(tickets) == 0


@pytest.mark.asyncio
async def test_oldest_days_filter():
    config = SourceConfig(
        type="slack",
        auth={"bot_token": "xoxb-fake"},
        filters={"channels": ["C1"], "oldest_days": 7},
    )
    connector = SlackConnector("test-slack", config)

    history_resp = {"ok": True, "messages": []}

    with patch.object(connector._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _mock_response(history_resp)
        await connector.fetch_tickets()

    call_kwargs = mock_get.call_args_list[0]
    params = call_kwargs.kwargs.get("params", {})
    assert "oldest" in params


@pytest.mark.asyncio
async def test_user_cache(connector):
    """Second call for same user should hit cache, not API."""
    history_resp = {
        "ok": True,
        "messages": [_make_thread_parent("100.100", "U1", "msg")],
    }
    replies_resp = {
        "ok": True,
        "messages": [
            _make_thread_parent("100.100", "U1", "msg"),
            _make_reply("100.200", "100.100", "U1", "reply from same user"),
        ],
    }
    user_resp = {"ok": True, "user": {"real_name": "Alice", "profile": {}}}

    with patch.object(connector._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [
            _mock_response(history_resp),
            _mock_response(user_resp),     # first user lookup
            _mock_response(replies_resp),
            # No second user lookup — U1 is cached
        ]
        tickets = await connector.fetch_tickets()

    assert len(tickets) == 1
    # Only 1 person despite 2 messages from U1
    assert len(tickets[0].people) == 1


@pytest.mark.asyncio
async def test_empty_user_id(connector):
    """Messages with no user field should not crash."""
    history_resp = {
        "ok": True,
        "messages": [{"ts": "100.100", "thread_ts": "100.100", "text": "bot msg"}],
    }
    replies_resp = {
        "ok": True,
        "messages": [{"ts": "100.100", "thread_ts": "100.100", "text": "bot msg"}],
    }

    with patch.object(connector._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [
            _mock_response(history_resp),
            _mock_response(replies_resp),
        ]
        tickets = await connector.fetch_tickets()

    assert len(tickets) == 1
    assert len(tickets[0].people) == 0
