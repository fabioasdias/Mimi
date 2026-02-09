"""Tests for the ticket consolidator."""

from datetime import datetime

from gather.connectors.base import RawTicket
from gather.consolidator import consolidate, extract_references
from gather.models import Message, Person, SourceReference


def _make_ticket(
    source: str,
    ticket_id: str,
    raw_text: str = "",
    people: list[Person] | None = None,
    messages: list[Message] | None = None,
) -> RawTicket:
    return RawTicket(
        reference=SourceReference(source=source, id=ticket_id),
        title=f"Ticket {ticket_id}",
        status="open",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 2),
        people=people or [],
        conversation=messages or [],
        raw_text=raw_text,
    )


class TestExtractReferences:
    def test_jira_style(self):
        refs = extract_references("See AUTH-1234 for details")
        assert "AUTH-1234" in refs

    def test_multiple_jira_refs(self):
        refs = extract_references("Linked to AUTH-1234 and PLAT-5678")
        assert refs == {"AUTH-1234", "PLAT-5678"}

    def test_numeric_hash_style(self):
        refs = extract_references("Related to #12345")
        assert "12345" in refs

    def test_no_short_numbers(self):
        refs = extract_references("See #12 and #123")
        assert len(refs) == 0  # Too short to be ticket IDs

    def test_no_refs(self):
        refs = extract_references("This has no ticket references")
        assert len(refs) == 0


class TestConsolidate:
    def test_single_ticket_unchanged(self):
        ticket = _make_ticket("jira", "AUTH-100")
        result = consolidate([ticket])
        assert len(result) == 1
        assert result[0].title == "Ticket AUTH-100"

    def test_cross_referenced_tickets_merge(self):
        jira_ticket = _make_ticket(
            "jira", "AUTH-100", raw_text="Auth is broken"
        )
        slack_ticket = _make_ticket(
            "slack", "thread-1", raw_text="Anyone seeing this? AUTH-100"
        )
        result = consolidate([jira_ticket, slack_ticket])
        assert len(result) == 1
        assert len(result[0].references) == 2

    def test_unrelated_tickets_stay_separate(self):
        t1 = _make_ticket("jira", "AUTH-100", raw_text="Auth issue")
        t2 = _make_ticket("jira", "PLAT-200", raw_text="Platform issue")
        result = consolidate([t1, t2])
        assert len(result) == 2

    def test_transitive_merge(self):
        """A references B, B references C => all three merge."""
        t_a = _make_ticket("jira", "AUTH-1", raw_text="See PLAT-2")
        t_b = _make_ticket("jira", "PLAT-2", raw_text="See BILL-3")
        t_c = _make_ticket("jira", "BILL-3", raw_text="Billing stuff")
        result = consolidate([t_a, t_b, t_c])
        assert len(result) == 1
        assert len(result[0].references) == 3

    def test_people_deduplication(self):
        person = Person(
            source="jira", source_id="u1", name="Alice", email="a@co.com", role="reporter"
        )
        t1 = _make_ticket("jira", "AUTH-1", raw_text="See PLAT-2", people=[person])
        t2 = _make_ticket(
            "slack",
            "PLAT-2",
            raw_text="Related to AUTH-1",
            people=[
                Person(source="jira", source_id="u1", name="Alice", email="a@co.com", role="commenter"),
                Person(source="slack", source_id="s1", name="Alice", role="participant"),
            ],
        )
        result = consolidate([t1, t2])
        assert len(result) == 1
        # jira:u1 should appear only once, slack:s1 once
        source_ids = [(p.source, p.source_id) for p in result[0].people]
        assert source_ids.count(("jira", "u1")) == 1

    def test_conversations_sorted_chronologically(self):
        m1 = Message(
            source="jira", author="A", author_source_id="u1",
            timestamp=datetime(2026, 1, 1, 10, 0), content="First"
        )
        m2 = Message(
            source="slack", author="B", author_source_id="u2",
            timestamp=datetime(2026, 1, 1, 9, 0), content="Actually first"
        )
        t1 = _make_ticket("jira", "AUTH-1", raw_text="See PLAT-2", messages=[m1])
        t2 = _make_ticket("slack", "PLAT-2", raw_text="AUTH-1", messages=[m2])
        result = consolidate([t1, t2])
        assert result[0].conversation[0].content == "Actually first"
        assert result[0].conversation[1].content == "First"
