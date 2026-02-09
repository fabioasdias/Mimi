"""Jira REST API connector."""

import logging
from datetime import datetime

import httpx

from gather.config import SourceConfig
from gather.connectors.base import BaseConnector, RawTicket
from gather.models import Message, Person, SourceReference

logger = logging.getLogger(__name__)


class JiraConnector(BaseConnector):
    """Fetches tickets and conversations from Jira Cloud REST API v3.

    Auth keys: base_url, email, api_token
    Filter keys: jql (string — passed directly to the Jira search API)
    """

    source_type = "jira"

    def __init__(self, name: str, config: SourceConfig):
        super().__init__(name, config)
        base_url = self.auth["base_url"].rstrip("/")
        self._base_url = base_url
        self._client = httpx.AsyncClient(
            base_url=base_url,
            auth=(self.auth["email"], self.auth["api_token"]),
            headers={"Accept": "application/json"},
        )

    async def fetch_tickets(self) -> list[RawTicket]:
        jql = self.filters.get("jql", "ORDER BY updated DESC")
        logger.info("Fetching Jira issues with JQL: %s", jql)

        tickets: list[RawTicket] = []
        start_at = 0
        max_results = 50

        while True:
            resp = await self._client.get(
                "/rest/api/3/search",
                params={
                    "jql": jql,
                    "startAt": start_at,
                    "maxResults": max_results,
                    "fields": "summary,status,created,updated,reporter,assignee,comment",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            logger.debug("Page at offset %d: %d/%d issues", start_at, len(data["issues"]), data["total"])

            for issue in data["issues"]:
                tickets.append(self._parse_issue(issue))

            if start_at + max_results >= data["total"]:
                break
            start_at += max_results

        logger.info("Fetched %d Jira issues", len(tickets))
        return tickets

    def _parse_issue(self, issue: dict) -> RawTicket:
        fields = issue["fields"]
        key = issue["key"]

        people: list[Person] = []
        if fields.get("reporter"):
            people.append(self._parse_person(fields["reporter"], "reporter"))
        if fields.get("assignee"):
            people.append(self._parse_person(fields["assignee"], "assignee"))

        messages: list[Message] = []
        raw_parts = [fields.get("summary", "")]

        comment_data = fields.get("comment", {})
        for comment in comment_data.get("comments", []):
            author = comment.get("author", {})
            body = self._extract_text(comment.get("body", {}))
            raw_parts.append(body)

            messages.append(
                Message(
                    source="jira",
                    author=author.get("displayName", "Unknown"),
                    author_source_id=author.get("accountId", ""),
                    timestamp=datetime.fromisoformat(comment["created"]),
                    content=body,
                )
            )

            author_person = self._parse_person(author, "commenter")
            if author_person.source_id not in {p.source_id for p in people}:
                people.append(author_person)

        return RawTicket(
            reference=SourceReference(
                source="jira",
                id=key,
                url=f"{self._base_url}/browse/{key}",
            ),
            title=fields.get("summary", ""),
            status=fields.get("status", {}).get("name", "unknown"),
            created_at=datetime.fromisoformat(fields["created"]),
            updated_at=datetime.fromisoformat(fields["updated"]),
            people=people,
            conversation=messages,
            raw_text="\n".join(raw_parts),
        )

    @staticmethod
    def _parse_person(data: dict, role: str) -> Person:
        return Person(
            source="jira",
            source_id=data.get("accountId", ""),
            name=data.get("displayName", "Unknown"),
            email=data.get("emailAddress"),
            role=role,
        )

    @staticmethod
    def _extract_text(adf_body: dict) -> str:
        """Extract plain text from Atlassian Document Format."""
        if isinstance(adf_body, str):
            return adf_body

        parts: list[str] = []

        def walk(node: dict | list) -> None:
            if isinstance(node, list):
                for item in node:
                    walk(item)
                return
            if isinstance(node, dict):
                if node.get("type") == "text":
                    parts.append(node.get("text", ""))
                for child in node.get("content", []):
                    walk(child)

        walk(adf_body)
        return " ".join(parts)
