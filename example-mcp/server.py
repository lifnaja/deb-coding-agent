"""Expose the seeded Greeenery PostgreSQL database through one MCP tool."""

from __future__ import annotations

import os
from typing import TypeAlias, TypedDict

import psycopg
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

MAX_ROWS = 1_000
STATEMENT_TIMEOUT_MS = 5_000

JsonScalar: TypeAlias = str | int | float | bool | None


class QueryResult(TypedDict):
    """JSON-compatible result returned by the query tool."""

    columns: list[str]
    rows: list[list[JsonScalar]]
    returned_rows: int
    truncated: bool


mcp = MCPServer(
    "greeenery-postgres",
    instructions=(
        "Query the read-only Greeenery PostgreSQL database. "
        "Available tables: addresses, events, order_items, orders, products, "
        "promos, and users."
    ),
)


def _connection_settings() -> dict[str, object]:
    """Read PostgreSQL connection settings from the environment."""
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "5433")),
        "dbname": os.environ.get("DB_NAME", "greeenery"),
        "user": os.environ.get("DB_USER", "greeenery_reader"),
        "password": os.environ.get("DB_PASSWORD", "greeenery_reader"),
        "options": (
            f"-c default_transaction_read_only=on "
            f"-c statement_timeout={STATEMENT_TIMEOUT_MS}"
        ),
    }


def _normalize_value(value: object) -> JsonScalar:
    """Convert an arbitrary PostgreSQL value into a JSON scalar."""
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def execute_query(sql: str) -> QueryResult:
    """Execute one read-only SQL query and cap the returned result size."""
    if not sql.strip():
        raise ToolError("SQL must not be empty.")

    try:
        with psycopg.connect(**_connection_settings()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                if cursor.description is None:
                    raise ToolError("The SQL statement must return rows.")

                columns = [column.name for column in cursor.description]
                fetched_rows = cursor.fetchmany(MAX_ROWS + 1)
    except psycopg.OperationalError as exc:
        raise ToolError("Could not connect to the PostgreSQL database.") from exc
    except psycopg.DatabaseError as exc:
        message = exc.diag.message_primary or "Database query failed."
        sqlstate = f" (SQLSTATE {exc.sqlstate})" if exc.sqlstate else ""
        raise ToolError(f"Query failed{sqlstate}: {message}") from exc

    truncated = len(fetched_rows) > MAX_ROWS
    rows = [
        [_normalize_value(value) for value in row] for row in fetched_rows[:MAX_ROWS]
    ]
    return {
        "columns": columns,
        "rows": rows,
        "returned_rows": len(rows),
        "truncated": truncated,
    }


@mcp.tool(
    annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True),
    structured_output=True,
)
def query(sql: str) -> QueryResult:
    """Run read-only SQL against Greeenery and return at most 1,000 rows."""
    return execute_query(sql)


def main() -> None:
    """Run the MCP server over stateless Streamable HTTP."""
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000,
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
