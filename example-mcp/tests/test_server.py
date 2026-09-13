"""Tests for the Greeenery MCP server."""

from __future__ import annotations

import os
from decimal import Decimal
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase, mock

import server
from mcp import Client


class ExecuteQueryTest(TestCase):
    """Test query execution without a live PostgreSQL database."""

    @mock.patch("server.psycopg.connect")
    def test_normalizes_values_and_truncates_rows(
        self,
        connect: mock.MagicMock,
    ) -> None:
        """Return JSON-compatible values and enforce the row limit."""
        connection = connect.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.description = [SimpleNamespace(name="price")]
        cursor.fetchmany.return_value = [
            (Decimal("10.25"),) for _ in range(server.MAX_ROWS + 1)
        ]

        result = server.execute_query("select price from products")

        self.assertEqual(result["columns"], ["price"])
        self.assertEqual(result["returned_rows"], server.MAX_ROWS)
        self.assertEqual(result["rows"][0], ["10.25"])
        self.assertTrue(result["truncated"])
        cursor.fetchmany.assert_called_once_with(server.MAX_ROWS + 1)

    def test_rejects_empty_sql(self) -> None:
        """Reject an empty statement before opening a connection."""
        with self.assertRaisesRegex(server.ToolError, "SQL must not be empty"):
            server.execute_query("   ")


class ToolRegistrationTest(IsolatedAsyncioTestCase):
    """Test the public MCP surface."""

    async def test_registers_only_query_tool(self) -> None:
        """Expose exactly the requested query tool."""
        tools = await server.mcp.list_tools()

        self.assertEqual([tool.name for tool in tools], ["query"])


class HttpSmokeTest(IsolatedAsyncioTestCase):
    """Exercise the running HTTP server when MCP_URL is supplied."""

    async def test_query_over_streamable_http(self) -> None:
        """List the sole tool and query a known seeded row count."""
        url = os.environ.get("MCP_URL")
        if url is None:
            self.skipTest("MCP_URL is not set")

        async with Client(url) as client:
            tools = await client.list_tools()
            self.assertEqual([tool.name for tool in tools.tools], ["query"])

            result = await client.call_tool(
                "query",
                {"sql": "select count(*)::integer as count from products"},
            )

            write_result = await client.call_tool(
                "query",
                {"sql": "delete from products"},
            )

        self.assertFalse(result.is_error)
        self.assertEqual(
            result.structured_content,
            {
                "columns": ["count"],
                "rows": [[30]],
                "returned_rows": 1,
                "truncated": False,
            },
        )
        self.assertTrue(write_result.is_error)
