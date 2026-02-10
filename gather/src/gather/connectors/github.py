"""GitHub Issues API connector."""

import logging
from datetime import datetime, timedelta

import httpx

from gather.config import SourceConfig
from gather.connectors.base import BaseConnector, RawIssue
from gather.models import Message, Person, SourceReference

logger = logging.getLogger(__name__)


class GitHubConnector(BaseConnector):
    """Fetches issues and their comments from GitHub repositories.

    Auth keys: token (personal access token or GitHub App token)
    Filter keys:
      repos: list of "owner/repo" strings
      labels: list of label names to filter by
      state: "open", "closed", or "all" (default: "all")
    """

    source_type = "github"

    def __init__(self, name: str, config: SourceConfig):
        super().__init__(name, config)
        self._client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {self.auth['token']}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    async def fetch_issues(self) -> list[RawIssue]:
        repos = self.filters.get("repos", [])
        labels = self.filters.get("labels", [])
        state = self.filters.get("state", "all")
        since_days = self.filters.get("since_days")

        since = None
        if since_days:
            since = datetime.now() - timedelta(days=int(since_days))
            logger.debug("Filtering to last %s days (since %s)", since_days, since.isoformat())

        issues: list[RawIssue] = []

        for repo in repos:
            logger.info("Fetching issues from %s (state=%s)", repo, state)
            params: dict = {
                "state": state,
                "per_page": 100,
                "sort": "updated",
                "direction": "desc",
            }
            if since:
                params["since"] = since.isoformat() + "Z"
            if labels:
                params["labels"] = ",".join(labels)

            page = 1
            while True:
                params["page"] = page
                resp = await self._client.get(
                    f"/repos/{repo}/issues", params=params
                )
                resp.raise_for_status()
                page_issues = resp.json()

                if not page_issues:
                    break

                logger.debug("Page %d: %d items from %s", page, len(page_issues), repo)

                for issue_data in page_issues:
                    # Skip pull requests (GitHub includes them in /issues)
                    if "pull_request" in issue_data:
                        continue
                    parsed_issue = await self._parse_issue(repo, issue_data)
                    issues.append(parsed_issue)

                page += 1

            logger.info("Fetched %d issues from %s", len(issues), repo)

        return issues

    async def _parse_issue(self, repo: str, issue: dict) -> RawIssue:
        number = issue["number"]

        people: list[Person] = []
        raw_parts: list[str] = []

        # Reporter
        user = issue.get("user", {})
        if user:
            people.append(self._parse_person(user, "reporter"))

        # Assignees
        for assignee in issue.get("assignees", []):
            people.append(self._parse_person(assignee, "assignee"))

        # Issue body as first message
        messages: list[Message] = []
        body = issue.get("body") or ""
        raw_parts.append(issue.get("title", ""))
        raw_parts.append(body)

        if body:
            messages.append(
                Message(
                    source="github",
                    author=user.get("login", "unknown"),
                    author_source_id=str(user.get("id", "")),
                    timestamp=datetime.fromisoformat(
                        issue["created_at"].replace("Z", "+00:00")
                    ),
                    content=body,
                )
            )

        # Fetch comments
        if issue.get("comments", 0) > 0:
            resp = await self._client.get(
                f"/repos/{repo}/issues/{number}/comments",
                params={"per_page": 100},
            )
            resp.raise_for_status()

            seen_users = {p.source_id for p in people}
            for comment in resp.json():
                author = comment.get("user", {})
                content = comment.get("body", "")
                raw_parts.append(content)

                messages.append(
                    Message(
                        source="github",
                        author=author.get("login", "unknown"),
                        author_source_id=str(author.get("id", "")),
                        timestamp=datetime.fromisoformat(
                            comment["created_at"].replace("Z", "+00:00")
                        ),
                        content=content,
                    )
                )

                author_id = str(author.get("id", ""))
                if author_id and author_id not in seen_users:
                    seen_users.add(author_id)
                    people.append(self._parse_person(author, "commenter"))

        labels = [l.get("name", "") for l in issue.get("labels", [])]
        status = issue.get("state", "open")
        if issue.get("state_reason"):
            status = f"{status} ({issue['state_reason']})"

        return RawIssue(
            reference=SourceReference(
                source="github",
                id=f"{repo}#{number}",
                url=issue["html_url"],
            ),
            title=issue.get("title", ""),
            status=status,
            created_at=datetime.fromisoformat(
                issue["created_at"].replace("Z", "+00:00")
            ),
            updated_at=datetime.fromisoformat(
                issue["updated_at"].replace("Z", "+00:00")
            ),
            people=people,
            conversation=messages,
            raw_text="\n".join(raw_parts),
        )

    @staticmethod
    def _parse_person(data: dict, role: str) -> Person:
        return Person(
            source="github",
            source_id=str(data.get("id", "")),
            name=data.get("login", "unknown"),
            email=None,  # Not available from issues API
            role=role,
        )
