"""Slack Web API connector."""

import logging
from datetime import datetime, timedelta

import httpx

from gather.config import SourceConfig
from gather.connectors.base import BaseConnector, RawIssue
from gather.models import Message, Person, SourceReference

logger = logging.getLogger(__name__)


class SlackConnector(BaseConnector):
    """Fetches support threads from Slack channels.

    Auth keys: bot_token
    Filter keys: channels (list of channel IDs), oldest_days (int)
    """

    source_type = "slack"

    def __init__(self, name: str, config: SourceConfig):
        super().__init__(name, config)
        self._client = httpx.AsyncClient(
            base_url="https://slack.com/api",
            headers={"Authorization": f"Bearer {self.auth['bot_token']}"},
        )
        self._user_cache: dict[str, dict] = {}

    async def fetch_issues(self) -> list[RawIssue]:
        channels = self.filters.get("channels", [])
        oldest_days = self.filters.get("oldest_days")

        since = None
        if oldest_days:
            since = datetime.now() - timedelta(days=int(oldest_days))

        issues: list[RawIssue] = []

        for channel_id in channels:
            logger.info("Fetching threads from channel %s", channel_id)
            params: dict = {"channel": channel_id, "limit": 200}
            if since:
                params["oldest"] = str(since.timestamp())

            resp = await self._client.get(
                "/conversations.history", params=params
            )
            resp.raise_for_status()
            data = resp.json()

            if not data.get("ok"):
                logger.warning("Slack API error for channel %s: %s", channel_id, data.get("error", "unknown"))
                continue

            for msg in data.get("messages", []):
                # Only treat threaded messages as "issues"
                if "thread_ts" not in msg or msg["ts"] != msg["thread_ts"]:
                    continue

                issue = await self._parse_thread(channel_id, msg)
                issues.append(issue)

        logger.info("Fetched %d Slack threads", len(issues))
        return issues

    async def _parse_thread(self, channel_id: str, parent: dict) -> RawIssue:
        thread_ts = parent["thread_ts"]

        resp = await self._client.get(
            "/conversations.replies",
            params={"channel": channel_id, "ts": thread_ts, "limit": 200},
        )
        resp.raise_for_status()
        thread_data = resp.json()
        thread_messages = thread_data.get("messages", [parent])

        people: list[Person] = []
        messages: list[Message] = []
        raw_parts: list[str] = []
        seen_users: set[str] = set()

        for msg in thread_messages:
            user_id = msg.get("user", "")
            user_info = await self._get_user(user_id)
            text = msg.get("text", "")
            raw_parts.append(text)

            ts = float(msg.get("ts", "0"))
            messages.append(
                Message(
                    source="slack",
                    author=user_info.get("real_name", user_id),
                    author_source_id=user_id,
                    timestamp=datetime.fromtimestamp(ts),
                    content=text,
                )
            )

            if user_id and user_id not in seen_users:
                seen_users.add(user_id)
                role = "reporter" if msg["ts"] == thread_ts else "participant"
                people.append(
                    Person(
                        source="slack",
                        source_id=user_id,
                        name=user_info.get("real_name", user_id),
                        email=user_info.get("profile", {}).get("email"),
                        role=role,
                    )
                )

        title_text = parent.get("text", "")[:120]
        created_ts = float(parent.get("ts", "0"))
        last_msg = thread_messages[-1]
        updated_ts = float(last_msg.get("ts", "0"))

        return RawIssue(
            reference=SourceReference(
                source="slack",
                id=thread_ts,
                meta={"channel": channel_id, "thread_ts": thread_ts},
            ),
            title=title_text,
            status="open",
            created_at=datetime.fromtimestamp(created_ts),
            updated_at=datetime.fromtimestamp(updated_ts),
            people=people,
            conversation=messages,
            raw_text="\n".join(raw_parts),
        )

    async def _get_user(self, user_id: str) -> dict:
        """Fetch and cache Slack user info."""
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        if not user_id:
            return {}

        resp = await self._client.get(
            "/users.info", params={"user": user_id}
        )
        data = resp.json()
        user = data.get("user", {})
        self._user_cache[user_id] = user
        return user
