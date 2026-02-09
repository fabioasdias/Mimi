"""Abstract base class for service connectors."""

from abc import ABC, abstractmethod
from datetime import datetime

from gather.config import SourceConfig
from gather.models import Message, Person, SourceReference


class RawTicket:
    """Intermediate ticket representation from a single source."""

    def __init__(
        self,
        reference: SourceReference,
        title: str,
        status: str,
        created_at: datetime,
        updated_at: datetime,
        people: list[Person],
        conversation: list[Message],
        raw_text: str,
    ):
        self.reference = reference
        self.title = title
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at
        self.people = people
        self.conversation = conversation
        # Full text blob for cross-reference scanning
        self.raw_text = raw_text


class BaseConnector(ABC):
    """Interface that all service connectors must implement.

    Each connector receives a SourceConfig with auth and filters dicts.
    The connector reads whatever keys it needs from those dicts —
    this keeps the config schema flexible per API.
    """

    def __init__(self, name: str, config: SourceConfig):
        self.name = name
        self.config = config
        self.auth = config.auth
        self.filters = config.filters

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Connector type identifier (e.g., 'jira', 'slack', 'github')."""
        ...

    @abstractmethod
    async def fetch_tickets(self) -> list[RawTicket]:
        """Fetch tickets/threads from the service.

        Timing filters (since_days, etc.) are read from self.filters.

        Returns:
            List of raw tickets from this source.
        """
        ...
