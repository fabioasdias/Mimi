"""Pydantic models defining the gathered data schema.

These models are the contract between the gather and analyze modules.
The JSON output of gather is validated against these models.
"""

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class SourceReference(BaseModel):
    """A reference to an issue in a specific source system."""

    source: str
    id: str
    url: str | None = None
    meta: dict = {}  # Source-specific extras (e.g. channel, thread_ts for Slack)


class Person(BaseModel):
    """A person involved in an issue, as seen from a specific source."""

    source: str
    source_id: str
    name: str
    email: str | None = None
    role: str  # reporter, assignee, commenter, participant


class Message(BaseModel):
    """A single message in a conversation."""

    source: str
    author: str
    author_source_id: str
    timestamp: datetime
    content: str


class ConsolidatedIssue(BaseModel):
    """An issue consolidated from multiple sources."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    references: list[SourceReference]
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    people: list[Person]
    conversation: list[Message]


class GatherMetadata(BaseModel):
    """Metadata about the gathering run."""

    gathered_at: datetime = Field(default_factory=datetime.now)
    sources: list[str]


class GatheredData(BaseModel):
    """Top-level output of the gather module."""

    issues: list[ConsolidatedIssue]
    metadata: GatherMetadata
