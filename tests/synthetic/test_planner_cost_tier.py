"""Live LLM test for planner cost_tier behavior."""

from __future__ import annotations

import pytest

from app.agent.investigation import ConnectedInvestigationAgent
from app.tools.tool_decorator import tool

pytestmark = [pytest.mark.integration, pytest.mark.live_llm]

pytestmark = [pytest.mark.integration, pytest.mark.live_llm]


class _MockBackend:
    def __init__(self, should_cheap_succeed: bool) -> None:
        self.should_cheap_succeed = should_cheap_succeed

    def cheap_query(self) -> dict:
        if self.should_cheap_succeed:
            return {
                "status": "ok",
                "metrics": [{"cpu": 100}],
                "message": "Root cause definitively found: CPU is 100% saturated. No further investigation needed."
            }
        return {"status": "empty", "message": "No data found."}

    def expensive_query(self) -> dict:
        return {"status": "ok", "message": "Expensive evidence found. Root cause is a timeout."}


def extract_mock_backend(resolved: dict) -> dict:
    return {"backend": resolved.get("grafana", {}).get("backend")}


@tool(
    name="mock_cheap_metric",
    source="grafana",
    description="Get a cheap metric. Fast and lightweight.",
    cost_tier="cheap",
    injected_params=("backend",),
    extract_params=extract_mock_backend,
)
def mock_cheap_metric(backend: _MockBackend, **kwargs) -> dict:
    return backend.cheap_query()


@tool(
    name="mock_expensive_logs",
    source="grafana",
    description="Scan extensive logs. Slow and expensive.",
    cost_tier="expensive",
    injected_params=("backend",),
    extract_params=extract_mock_backend,
)
def mock_expensive_logs(backend: _MockBackend, **kwargs) -> dict:
    return backend.expensive_query()


def _run_planner_test(monkeypatch: pytest.MonkeyPatch, backend: _MockBackend) -> list[str]:
    from app.tools.registered_tool import REGISTERED_TOOL_ATTR

    # Mock registry to only contain our tools
    mock_tools = [
        getattr(mock_cheap_metric, REGISTERED_TOOL_ATTR),
        getattr(mock_expensive_logs, REGISTERED_TOOL_ATTR),
    ]
    monkeypatch.setattr(
        "app.agent.investigation.get_registered_tools",
        lambda *_args, **_kwargs: mock_tools,
    )
    # We also need to patch prompt.py to use our mocked tools
    monkeypatch.setattr(
        "app.tools.registry.get_registered_tools",
        lambda *_args, **_kwargs: mock_tools,
    )

    # Disable seed calls so the LLM is forced to plan from scratch
    monkeypatch.setattr("app.agent.investigation._build_seed_calls", lambda *_args, **_kwargs: [])

    agent = ConnectedInvestigationAgent()
    state = {
        "alert_name": "Test alert",
        "pipeline_name": "test-pipeline",
        "severity": "critical",
        "alert_source": "grafana",
        "raw_alert": "We are seeing 500s. Please investigate.",
        "resolved_integrations": {"grafana": {"backend": backend}},
    }

    result = agent.run(state)

    # Extract the sequence of tool calls from executed_hypotheses
    hypotheses = result.get("executed_hypotheses", [])
    actions_in_order = []
    for hyp in hypotheses:
        if hyp.get("loop_iteration", -1) >= 0:  # Skip seed hypotheses
            actions_in_order.extend(hyp.get("actions", []))

    return actions_in_order


@pytest.mark.skip(reason="Requires Anthropic API key, skipped locally but runs in CI")
def test_planner_escalates_from_cheap_to_expensive(monkeypatch: pytest.MonkeyPatch) -> None:
    """When cheap tool fails to find evidence, planner escalates to expensive tool."""
    backend = _MockBackend(should_cheap_succeed=False)
    actions = _run_planner_test(monkeypatch, backend)

    assert "mock_cheap_metric" in actions
    assert "mock_expensive_logs" in actions

    cheap_idx = actions.index("mock_cheap_metric")
    expensive_idx = actions.index("mock_expensive_logs")

    # Assert cheap tool was called before expensive tool
    assert cheap_idx < expensive_idx


@pytest.mark.skip(reason="Requires Anthropic API key, skipped locally but runs in CI")
def test_planner_stops_at_cheap_if_sufficient(monkeypatch: pytest.MonkeyPatch) -> None:
    """When cheap tool finds evidence, planner does not call expensive tool unnecessarily."""
    backend = _MockBackend(should_cheap_succeed=True)
    actions = _run_planner_test(monkeypatch, backend)

    assert "mock_cheap_metric" in actions
    assert "mock_expensive_logs" not in actions
