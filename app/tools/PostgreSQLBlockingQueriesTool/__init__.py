"""PostgreSQL Blocking Queries Tool."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.integrations.postgresql import (
    get_blocking_queries,
    postgresql_extract_params,
    postgresql_is_available,
    resolve_postgresql_config,
)
from app.tools.tool_decorator import tool
from app.tools.utils.sql_wrapper import call_db_tool_with_default_db_warning


class PostgreSQLBlockingQueriesInput(BaseModel):
    host: str = Field(description="PostgreSQL host or endpoint name.")
    database: str | None = Field(
        default=None,
        description="Target database name. Defaults to integration database when omitted.",
    )
    port: int = Field(default=5432, description="PostgreSQL TCP port.")


class PostgreSQLBlockingQueriesOutput(BaseModel):
    source: str = Field(description="Evidence source label.")
    available: bool = Field(description="Whether blocking queries were retrieved.")
    blocks: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of blocking and blocked query relationships.",
    )
    total_blocks: int = Field(default=0, description="Number of blocking relationships returned.")
    database: str | None = Field(default=None, description="Database queried for stats.")
    default_db_warning: str | None = Field(
        default=None,
        description="Warning emitted when the default database fallback is used.",
    )
    error: str | None = Field(default=None, description="Error details when query fails.")


@tool(
    name="get_postgresql_blocking_queries",
    description=(
        "Retrieve database queries that are currently blocked by other queries, "
        "indicating lock contention or deadlocks."
    ),
    source="postgresql",
    surfaces=("investigation", "chat"),
    use_cases=[
        "Diagnosing database latency spikes caused by row or table lock contention",
        "Finding the root cause of 'lock timeout' or 'deadlock detected' errors",
        "Identifying long-running transactions that are blocking other queries",
    ],
    source_id="postgresql_pg_locks",
    evidence_type="query_stats",
    side_effect_level="read_only",
    examples=[
        "Check for blocking queries to see if a long transaction is halting production traffic.",
    ],
    anti_examples=[
        "Use this tool for pod restart loops or Kubernetes health checks.",
        "Use this tool to get overall database stats like cache hits.",
    ],
    input_model=PostgreSQLBlockingQueriesInput,
    output_model=PostgreSQLBlockingQueriesOutput,
    is_available=postgresql_is_available,
    extract_params=postgresql_extract_params,
)
def get_postgresql_blocking_queries(
    host: str,
    database: str | None = None,
    port: int = 5432,
) -> dict[str, Any]:
    """Fetch blocking query relationships from pg_locks and pg_stat_activity."""
    return call_db_tool_with_default_db_warning(
        database=database,
        default_db_name="postgres",
        config_resolver=resolve_postgresql_config,
        resolver_kwargs={"host": host, "port": port},
        db_caller=lambda config: get_blocking_queries(config),
    )
