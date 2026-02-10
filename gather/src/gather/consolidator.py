"""Cross-reference matching and issue consolidation."""

import logging
import re
from collections import defaultdict

from gather.connectors.base import RawIssue
from gather.models import ConsolidatedIssue, SourceReference

logger = logging.getLogger(__name__)

# Patterns for cross-referencing tickets
ISSUE_PATTERNS = [
    re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b"),  # JIRA-style: PROJ-123
    re.compile(r"#(\d{4,})\b"),  # Numeric: #12345
]


def extract_references(text: str) -> set[str]:
    """Extract issue IDs mentioned in text."""
    refs: set[str] = set()
    for pattern in ISSUE_PATTERNS:
        refs.update(pattern.findall(text))
    return refs


def consolidate(raw_issues: list[RawIssue]) -> list[ConsolidatedIssue]:
    """Group raw issues that reference each other into consolidated records.

    Uses union-find to cluster issues that share cross-references.
    """
    # Index issues by their source IDs
    by_source_id: dict[str, list[int]] = defaultdict(list)
    for i, issue in enumerate(raw_issues):
        by_source_id[issue.reference.id].append(i)

    # Union-find
    parent = list(range(len(raw_issues)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Link issues that reference each other
    for i, issue in enumerate(raw_issues):
        mentioned = extract_references(issue.raw_text)
        if mentioned:
            logger.debug(
                "Issue %s references: %s", issue.reference.id, mentioned
            )
        for ref_id in mentioned:
            if ref_id in by_source_id:
                for j in by_source_id[ref_id]:
                    if i != j:
                        logger.debug(
                            "Linking %s <-> %s via ref %s",
                            issue.reference.id,
                            raw_issues[j].reference.id,
                            ref_id,
                        )
                        union(i, j)

        # Also link by email overlap
        emails = {p.email for p in issue.people if p.email}
        for j, other in enumerate(raw_issues):
            if i == j:
                continue
            other_emails = {p.email for p in other.people if p.email}
            # Don't merge just because the same person appears — only if
            # there's an issue ID cross-reference. Email is used for
            # people dedup within a consolidated issue, not for merging.

    # Group by connected component
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(raw_issues)):
        groups[find(i)].append(i)

    merged_count = sum(1 for g in groups.values() if len(g) > 1)
    logger.info(
        "%d groups (%d merged, %d standalone) from %d raw issues",
        len(groups), merged_count, len(groups) - merged_count, len(raw_issues),
    )

    # Build consolidated issues
    consolidated: list[ConsolidatedIssue] = []
    for indices in groups.values():
        issues = [raw_issues[i] for i in indices]
        consolidated.append(_merge_issues(issues))

    return consolidated


def _merge_issues(issues: list[RawIssue]) -> ConsolidatedIssue:
    """Merge multiple raw issues into one consolidated issue."""
    # Use the earliest issue as the primary
    issues.sort(key=lambda t: t.created_at)
    primary = issues[0]

    # Collect all references
    references: list[SourceReference] = [t.reference for t in issues]

    # Merge people, dedup by (source, source_id)
    seen_people: set[tuple[str, str]] = set()
    people = []
    for t in issues:
        for p in t.people:
            key = (p.source, p.source_id)
            if key not in seen_people:
                seen_people.add(key)
                people.append(p)

    # Merge conversations chronologically
    conversation = []
    for t in issues:
        conversation.extend(t.conversation)
    conversation.sort(key=lambda m: m.timestamp)

    return ConsolidatedIssue(
        references=references,
        title=primary.title,
        status=primary.status,
        created_at=primary.created_at,
        updated_at=max(t.updated_at for t in issues),
        people=people,
        conversation=conversation,
    )
