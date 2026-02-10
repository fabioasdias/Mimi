"""Pydantic models defining the analysis output schema."""

from datetime import datetime

from pydantic import BaseModel, Field


class Classification(BaseModel):
    """Ticket classification result."""

    type: str  # outage, new_feature, user_error, wrong_team, bug, question
    confidence: float = Field(ge=0.0, le=1.0)
    services: list[str] = []
    summary: str


class IssueAnalysis(BaseModel):
    """Analysis result for a single issue."""

    id: str  # matches gather output
    classification: Classification


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
    """An edge in the graph (person↔ticket or person↔person)."""

    source: str = Field(alias="from")
    target: str = Field(alias="to")
    role: str | None = None  # reporter, assignee, participant
    relation: str | None = None  # same_identity
    confidence: float | None = None

    model_config = {"populate_by_name": True}


class PeopleGraph(BaseModel):
    """Graph of people and their relationships to tickets."""

    nodes: list[PersonNode]
    edges: list[GraphEdge]


class ServiceNode(BaseModel):
    """A service/component node."""

    id: str
    ticket_count: int = 0


class ServiceEdge(BaseModel):
    """Co-occurrence edge between services."""

    source: str = Field(alias="from")
    target: str = Field(alias="to")
    co_occurrence: int = 0

    model_config = {"populate_by_name": True}


class ServiceGraph(BaseModel):
    """Graph of services and their co-occurrences."""

    nodes: list[ServiceNode]
    edges: list[ServiceEdge]


class AnalysisMetadata(BaseModel):
    """Metadata about the analysis run."""

    analyzed_at: datetime = Field(default_factory=datetime.now)
    classifier: str = "rule_based_v1"


class AnalyzedData(BaseModel):
    """Top-level output of the analyze module."""

    issues: list[IssueAnalysis]
    people_graph: PeopleGraph
    service_graph: ServiceGraph
    metadata: AnalysisMetadata
