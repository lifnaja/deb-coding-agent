"""Expose the Greeenery PostgreSQL database through one MCP tool."""

import os
from typing import Any

import psycopg
from mcp.server import MCPServer
from psycopg.rows import dict_row

mcp = MCPServer("greeenery-postgres")


@mcp.tool()
def query(sql: str) -> list[dict[str, Any]]:
    """Run a read-only SQL query and return at most 1,000 rows."""
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5433"),
        dbname=os.getenv("DB_NAME", "greeenery"),
        user=os.getenv("DB_USER", "greeenery_reader"),
        password=os.getenv("DB_PASSWORD", "greeenery_reader"),
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchmany(1_000)


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000,
    )
