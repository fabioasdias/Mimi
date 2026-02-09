"""Tests for the CLI and env var resolution."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from gather.cli import _resolve_auth, _resolve_env, main


class TestResolveEnv:
    def test_resolves_env_var(self, monkeypatch):
        monkeypatch.setenv("MY_TOKEN", "secret123")
        assert _resolve_env("${MY_TOKEN}") == "secret123"

    def test_passthrough_no_vars(self):
        assert _resolve_env("plain-string") == "plain-string"

    def test_mixed_content(self, monkeypatch):
        monkeypatch.setenv("HOST", "example.com")
        assert _resolve_env("https://${HOST}/api") == "https://example.com/api"

    def test_missing_var_raises(self):
        # Make sure the var doesn't exist
        os.environ.pop("NONEXISTENT_VAR_XYZ", None)
        with pytest.raises(Exception, match="NONEXISTENT_VAR_XYZ"):
            _resolve_env("${NONEXISTENT_VAR_XYZ}")

    def test_resolve_auth_dict(self, monkeypatch):
        monkeypatch.setenv("TOK", "abc")
        result = _resolve_auth({"token": "${TOK}", "url": "https://fixed.com"})
        assert result == {"token": "abc", "url": "https://fixed.com"}


class TestCLI:
    def test_missing_config_file(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--config", "nonexistent.yaml"])
        assert result.exit_code != 0

    def test_valid_config_runs(self, monkeypatch, tmp_path):
        output_file = tmp_path / "out.json"
        yaml_content = f"""
output: {output_file}

sources:
  test:
    type: github
    auth:
      token: fake-token
    filters:
      repos: []
"""
        config_file = tmp_path / "sources.yaml"
        config_file.write_text(yaml_content)

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["--config", str(config_file)])

        # Should succeed (0 tickets, empty repos list)
        assert result.exit_code == 0
        assert output_file.exists()

    def test_unknown_source_type_warns(self, tmp_path):
        output_file = tmp_path / "out.json"
        yaml_content = f"""
output: {output_file}

sources:
  bad:
    type: nonexistent_service
    auth: {{}}
    filters: {{}}
"""
        config_file = tmp_path / "sources.yaml"
        config_file.write_text(yaml_content)

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["--config", str(config_file)])

        # Should complete but not write output (no valid connectors)
        assert result.exit_code == 0
        assert not output_file.exists()
