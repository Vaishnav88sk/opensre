from __future__ import annotations

from app.agent.prompt import build_system_prompt, format_alert_context


def test_build_system_prompt_non_hermes_uses_generic_category_instruction() -> None:
    prompt = build_system_prompt({"alert_source": "grafana"})

    assert (
        "One of database / infrastructure / code_bug / configuration / network / performance"
        in prompt
    )
    assert "Hermes root cause category taxonomy" not in prompt
    assert "agent_hang" not in prompt


def test_build_system_prompt_hermes_includes_hermes_taxonomy_only() -> None:
    prompt = build_system_prompt({"alert_source": "hermes"})

    assert "Hermes root cause category taxonomy" in prompt
    assert "agent_hang" in prompt
    assert "delivery_hang" in prompt
    assert "ghost_session" in prompt
    assert "connection_exhaustion" not in prompt


def test_alert_context_surfaces_v2_contract_hints_for_tool_selection() -> None:
    context = format_alert_context(
        {
            "alert_name": "RDS latency spike",
            "alert_source": "rds",
            "pipeline_name": "orders",
            "severity": "critical",
            "resolved_integrations": {
                "rds": {"db_instance_identifier": "orders-db", "region": "us-east-1"},
                "postgresql": {"host": "orders-db", "database": "orders", "port": 5432},
            },
        }
    )

    assert "Call these tools first (from: rds" in context
    assert "`describe_rds_instance`" in context
    assert "source_id=aws_rds" in context
    assert "evidence=deployment_metadata" in context
    assert "avoid=Use this tool to inspect SQL query text or Postgres locks." in context


def test_alert_context_includes_cost_tier(monkeypatch) -> None:
    from unittest.mock import MagicMock

    from app.tools.registered_tool import RegisteredTool

    mock_tool = MagicMock(spec=RegisteredTool)
    mock_tool.name = "mock_cheap_tool"
    mock_tool.source = "mock_src"
    mock_tool.description = "A mock tool"
    mock_tool.cost_tier = "cheap"
    mock_tool.is_available.return_value = True

    monkeypatch.setattr(
        "app.tools.registry.get_registered_tools",
        lambda *_args, **_kwargs: [mock_tool],
    )

    context = format_alert_context(
        {
            "alert_source": "mock_src",
            "resolved_integrations": {"mock_src": {"ready": True}},
        }
    )

    assert "cost_tier=cheap" in context
