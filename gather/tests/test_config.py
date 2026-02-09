"""Tests for YAML config loading."""

import tempfile
from pathlib import Path

from gather.config import GatherConfig


def test_load_yaml_config():
    yaml_content = """
output: data/out.json

sources:
  my-github:
    type: github
    auth:
      token: fake-token
    filters:
      repos:
        - owner/repo
      state: open
      since_days: 7
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config = GatherConfig.from_yaml(f.name)

    assert config.output == "data/out.json"
    assert "my-github" in config.sources
    src = config.sources["my-github"]
    assert src.type == "github"
    assert src.auth["token"] == "fake-token"
    assert src.filters["repos"] == ["owner/repo"]
    assert src.filters["since_days"] == 7


def test_multiple_sources():
    yaml_content = """
output: data/gathered.json

sources:
  jira-prod:
    type: jira
    auth:
      base_url: https://x.atlassian.net
      email: a@b.com
      api_token: secret
    filters:
      jql: "project = AUTH"
  slack-support:
    type: slack
    auth:
      bot_token: xoxb-123
    filters:
      channels: [C1, C2]
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config = GatherConfig.from_yaml(f.name)

    assert len(config.sources) == 2
    assert config.sources["jira-prod"].type == "jira"
    assert config.sources["slack-support"].filters["channels"] == ["C1", "C2"]
