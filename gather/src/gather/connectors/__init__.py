from gather.connectors.base import BaseConnector, RawIssue
from gather.connectors.github import GitHubConnector
from gather.connectors.jira import JiraConnector
from gather.connectors.slack import SlackConnector

# Registry: maps source type string to connector class
CONNECTOR_REGISTRY: dict[str, type[BaseConnector]] = {
    "jira": JiraConnector,
    "slack": SlackConnector,
    "github": GitHubConnector,
}

__all__ = [
    "BaseConnector",
    "RawIssue",
    "CONNECTOR_REGISTRY",
    "JiraConnector",
    "SlackConnector",
    "GitHubConnector",
]
