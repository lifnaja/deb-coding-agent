"""Tests for the Greeenery MCP server."""

from __future__ import annotations

import os
from unittest import IsolatedAsyncioTestCase, TestCase, mock

import server
from mcp import Client


class QueryTest(TestCase):
    """Test the query tool without a live PostgreSQL database."""

    @mock.patch("server.psycopg.connect")
    def test_returns_rows_as_dictionaries(
        self,
        connect: mock.MagicMock,
    ) -> None:
        """Use column names as keys and enforce the row limit."""
        connection = connect.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchmany.return_value = [{"name": "Apple", "price": 10.25}]

        result = server.query("select name, price from products")

        self.assertEqual(result, [{"name": "Apple", "price": 10.25}])
        cursor.fetchmany.assert_called_once_with(1_000)


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
        self.assertEqual(result.structured_content, {"result": [{"count": 30}]})
        self.assertTrue(write_result.is_error)
