"""Tests for GitHubSearchIssuesTool."""

from unittest.mock import Mock

import pytest

from app.tools.GitHubSearchIssuesTool import (
    search_github_issues,
)


@pytest.fixture
def mock_github_config():
    config = Mock()
    config.url = "http://localhost:8000"
    config.mode = "streamable-http"
    config.auth_token = "secret"
    config.command = ""
    config.args = []
    config.headers = {}
    config.toolsets = ()
    return config


@pytest.fixture
def mock_resolve_config(monkeypatch, mock_github_config):
    mock = Mock(return_value=mock_github_config)
    monkeypatch.setattr("app.tools.GitHubSearchIssuesTool._resolve_config", mock)
    return mock


@pytest.fixture
def mock_call_github_mcp_tool(monkeypatch):
    mock = Mock()
    monkeypatch.setattr("app.tools.GitHubSearchIssuesTool.call_github_mcp_tool", mock)
    return mock


def test_search_github_issues_success(mock_resolve_config, mock_call_github_mcp_tool):
    """Test successful issue search."""
    mock_call_github_mcp_tool.return_value = {
        "is_error": False,
        "tool": "search_issues",
        "arguments": {"query": "repo:org/repo bug"},
        "text": "Found 1 issue",
        "structured_content": [{"title": "Bug 1", "number": 1}],
        "content": [],
    }

    result = search_github_issues(owner="org", repo="repo", query="bug")

    assert result["available"] is True
    assert result["source"] == "github"
    assert result["query"] == "repo:org/repo bug"
    assert result["matches"] == [{"title": "Bug 1", "number": 1}]

    mock_call_github_mcp_tool.assert_called_once()
    args, kwargs = mock_call_github_mcp_tool.call_args
    assert args[1] == "search_issues"
    assert args[2] == {"query": "repo:org/repo bug"}


def test_search_github_issues_error(mock_resolve_config, mock_call_github_mcp_tool):
    """Test when MCP call fails."""
    mock_call_github_mcp_tool.return_value = {
        "is_error": True,
        "tool": "search_issues",
        "text": "Failed to connect to GitHub",
        "arguments": {"query": "repo:org/repo bug"},
    }

    result = search_github_issues(owner="org", repo="repo", query="bug")

    assert result["available"] is False
    assert result["error"] == "Failed to connect to GitHub"


def test_search_github_issues_not_configured(monkeypatch):
    """Test when GitHub is not configured."""
    mock = Mock(return_value=None)
    monkeypatch.setattr("app.tools.GitHubSearchIssuesTool._resolve_config", mock)

    result = search_github_issues(owner="org", repo="repo", query="bug")

    assert result["available"] is False
    assert result["error"] == "GitHub MCP integration is not configured."
