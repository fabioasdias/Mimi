"""Pydantic models defining the analysis output schema."""

from datetime import datetime

from pydantic import BaseModel, Field


class Classification(BaseModel):
    """Issue classification result."""

    type: str  # outage, enhancement, clarification, routing_issue, defect, inquiry
    confidence: float = Field(ge=0.0, le=1.0)
    keywords: list[str] = []
    summary: str


class IssuePerson(BaseModel):
    """A person associated with an issue."""

    source: str
    source_id: str
    name: str
    email: str | None = None
    role: str  # reporter, assignee, commenter


class IssueAnalysis(BaseModel):
    """Analysis result for a single issue."""

    id: str  # matches gather output
    classification: Classification
    people: list[IssuePerson] = []


class Identity(BaseModel):
    """A person's identity in a specific source."""

    source: str
    source_id: str
    email: str | None = None
    display_name: str | None = None


class PersonNode(BaseModel):
    """A person node in the people graph."""

    id: str
    label: str
    identities: list[Identity]


class GraphEdge(BaseModel):
    """An edge in the graph (person↔issue or person↔person)."""

    source: str = Field(alias="from")
    target: str = Field(alias="to")
    role: str | None = None  # reporter, assignee, participant
    relation: str | None = None  # same_identity
    confidence: float | None = None

    model_config = {"populate_by_name": True}


class PeopleGraph(BaseModel):
    """Graph of people and their relationships to issues."""

    nodes: list[PersonNode]
    edges: list[GraphEdge]


class KeywordNode(BaseModel):
    """A keyword/component node."""

    id: str
    issue_count: int = 0


class KeywordEdge(BaseModel):
    """Co-occurrence edge between keywords."""

    source: str = Field(alias="from")
    target: str = Field(alias="to")
    co_occurrence: int = 0

    model_config = {"populate_by_name": True}


class KeywordGraph(BaseModel):
    """Graph of keywords and their co-occurrences."""

    nodes: list[KeywordNode]
    edges: list[KeywordEdge]


class AnalysisMetadata(BaseModel):
    """Metadata about the analysis run."""

    analyzed_at: datetime = Field(default_factory=datetime.now)
    classifier: str = "rule_based_v1"


class AnalyzedData(BaseModel):
    """Top-level output of the analyze module."""

    issues: list[IssueAnalysis]
    people_graph: PeopleGraph
    keyword_graph: KeywordGraph
    metadata: AnalysisMetadata
