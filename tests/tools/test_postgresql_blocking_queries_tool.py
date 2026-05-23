"""Tests for PostgreSQLBlockingQueriesTool."""

import pytest

from app.tools.PostgreSQLBlockingQueriesTool import (
    PostgreSQLBlockingQueriesOutput,
    get_postgresql_blocking_queries,
)


from unittest.mock import Mock

@pytest.fixture
def mock_postgresql_config():
    config = Mock()
    config.is_configured = True
    config.host = "test-host"
    config.database = "test-db"
    config.max_results = 50
    return config


@pytest.fixture
def mock_get_blocking_queries(monkeypatch):
    mock = Mock()
    monkeypatch.setattr("app.tools.PostgreSQLBlockingQueriesTool.get_blocking_queries", mock)
    return mock


@pytest.fixture
def mock_resolve_config(monkeypatch, mock_postgresql_config):
    mock = Mock(return_value=mock_postgresql_config)
    monkeypatch.setattr("app.tools.PostgreSQLBlockingQueriesTool.resolve_postgresql_config", mock)
    return mock


def test_postgresql_blocking_queries_tool_success(mock_resolve_config, mock_get_blocking_queries):
    """Test successful retrieval of blocking queries."""
    mock_get_blocking_queries.return_value = {
        "source": "postgresql",
        "available": True,
        "total_blocks": 1,
        "blocks": [
            {
                "blocked_pid": 100,
                "blocked_user": "user1",
                "blocking_pid": 200,
                "blocking_user": "user2",
                "blocked_query_truncated": "SELECT * FROM large_table",
                "blocking_query_truncated": "UPDATE large_table SET status='processing'",
                "blocked_duration_seconds": 45,
            }
        ],
    }

    result = get_postgresql_blocking_queries(host="test-host", database="test-db")
    
    assert result["available"] is True
    assert result["total_blocks"] == 1
    assert result["blocks"][0]["blocked_pid"] == 100
    assert result["blocks"][0]["blocked_user"] == "user1"
    assert result["blocks"][0]["blocking_pid"] == 200
    
    # Verify the output schema matches the result
    output_model = PostgreSQLBlockingQueriesOutput(**result)
    assert output_model.available is True


def test_postgresql_blocking_queries_tool_not_configured(mock_resolve_config, mock_get_blocking_queries):
    """Test when postgresql is not configured."""
    mock_get_blocking_queries.return_value = {
        "source": "postgresql",
        "available": False,
        "error": "Not configured.",
    }

    result = get_postgresql_blocking_queries(host="test-host", database="test-db")
    
    assert result["available"] is False
    assert result["error"] == "Not configured."


def test_postgresql_blocking_queries_tool_error(mock_resolve_config, mock_get_blocking_queries):
    """Test when an error occurs during query execution."""
    mock_get_blocking_queries.return_value = {
        "source": "postgresql",
        "available": False,
        "error": "connection to server failed",
    }

    result = get_postgresql_blocking_queries(host="test-host", database="test-db")
    
    assert result["available"] is False
    assert result["error"] == "connection to server failed"


def test_postgresql_blocking_queries_tool_default_db_fallback(
    mock_resolve_config, mock_get_blocking_queries
):
    """Test that default db warning is propagated when database is missing."""
    mock_get_blocking_queries.return_value = {
        "source": "postgresql",
        "available": True,
        "total_blocks": 0,
        "blocks": [],
    }

    result = get_postgresql_blocking_queries(host="test-host")
    
    assert result["available"] is True
    assert result["default_db_warning"] is not None
    assert "defaulted to 'postgres'" in result["default_db_warning"]
