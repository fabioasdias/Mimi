"""Cross-reference matching and ticket consolidation."""

import logging
import re
from collections import defaultdict

from gather.connectors.base import RawTicket
from gather.models import ConsolidatedTicket, SourceReference

logger = logging.getLogger(__name__)

# Patterns for cross-referencing tickets
TICKET_PATTERNS = [
    re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b"),  # JIRA-style: PROJ-123
    re.compile(r"#(\d{4,})\b"),  # Numeric: #12345
]


def extract_references(text: str) -> set[str]:
    """Extract ticket IDs mentioned in text."""
    refs: set[str] = set()
    for pattern in TICKET_PATTERNS:
        refs.update(pattern.findall(text))
    return refs


def consolidate(raw_tickets: list[RawTicket]) -> list[ConsolidatedTicket]:
    """Group raw tickets that reference each other into consolidated records.

    Uses union-find to cluster tickets that share cross-references.
    """
    # Index tickets by their source IDs
    by_source_id: dict[str, list[int]] = defaultdict(list)
    for i, ticket in enumerate(raw_tickets):
        by_source_id[ticket.reference.id].append(i)

    # Union-find
    parent = list(range(len(raw_tickets)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Link tickets that reference each other
    for i, ticket in enumerate(raw_tickets):
        mentioned = extract_references(ticket.raw_text)
        if mentioned:
            logger.debug(
                "Ticket %s references: %s", ticket.reference.id, mentioned
            )
        for ref_id in mentioned:
            if ref_id in by_source_id:
                for j in by_source_id[ref_id]:
                    if i != j:
                        logger.debug(
                            "Linking %s <-> %s via ref %s",
                            ticket.reference.id,
                            raw_tickets[j].reference.id,
                            ref_id,
                        )
                        union(i, j)

        # Also link by email overlap
        emails = {p.email for p in ticket.people if p.email}
        for j, other in enumerate(raw_tickets):
            if i == j:
                continue
            other_emails = {p.email for p in other.people if p.email}
            # Don't merge just because the same person appears — only if
            # there's a ticket ID cross-reference. Email is used for
            # people dedup within a consolidated ticket, not for merging.

    # Group by connected component
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(raw_tickets)):
        groups[find(i)].append(i)

    merged_count = sum(1 for g in groups.values() if len(g) > 1)
    logger.info(
        "%d groups (%d merged, %d standalone) from %d raw tickets",
        len(groups), merged_count, len(groups) - merged_count, len(raw_tickets),
    )

    # Build consolidated tickets
    consolidated: list[ConsolidatedTicket] = []
    for indices in groups.values():
        tickets = [raw_tickets[i] for i in indices]
        consolidated.append(_merge_tickets(tickets))

    return consolidated


def _merge_tickets(tickets: list[RawTicket]) -> ConsolidatedTicket:
    """Merge multiple raw tickets into one consolidated ticket."""
    # Use the earliest ticket as the primary
    tickets.sort(key=lambda t: t.created_at)
    primary = tickets[0]

    # Collect all references
    references: list[SourceReference] = [t.reference for t in tickets]

    # Merge people, dedup by (source, source_id)
    seen_people: set[tuple[str, str]] = set()
    people = []
    for t in tickets:
        for p in t.people:
            key = (p.source, p.source_id)
            if key not in seen_people:
                seen_people.add(key)
                people.append(p)

    # Merge conversations chronologically
    conversation = []
    for t in tickets:
        conversation.extend(t.conversation)
    conversation.sort(key=lambda m: m.timestamp)

    return ConsolidatedTicket(
        references=references,
        title=primary.title,
        status=primary.status,
        created_at=primary.created_at,
        updated_at=max(t.updated_at for t in tickets),
        people=people,
        conversation=conversation,
    )
