"""YAML-based datasource configuration.

Each source gets its own block with auth credentials and
API-specific filter fields that map directly to the service's API.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class SourceConfig(BaseModel):
    """Configuration for a single data source."""

    type: str  # jira, slack, github
    auth: dict[str, str] = {}
    filters: dict[str, Any] = {}


class GatherConfig(BaseModel):
    """Top-level gather configuration."""

    output: str = "data/gathered.json"
    sources: dict[str, SourceConfig] = {}

    @classmethod
    def from_yaml(cls, path: str | Path) -> "GatherConfig":
        path = Path(path)
        raw = yaml.safe_load(path.read_text())
        return cls(**raw)
