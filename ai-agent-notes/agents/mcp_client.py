"""Minimal MCP client adapter for the OpenAI function-calling format.

Configure servers with the ``MCP_SERVERS`` environment variable. Both the
common ``{"mcpServers": {...}}`` shape and the servers object itself work::

    MCP_SERVERS={"filesystem":{"command":"npx","args":["-y","@modelcontextprotocol/server-filesystem","."]}}

A server may use stdio (``command`` + optional ``args``/``env``) or Streamable
HTTP (``url``). MCP tools are exposed as ``mcp__<server>__<tool>``.
"""

import json
import os
import re
from contextlib import AsyncExitStack


def load_mcp_servers(value=None):
    """Load and validate MCP server definitions from JSON."""
    raw = os.getenv("MCP_SERVERS", "") if value is None else value
    if not raw.strip():
        return {}

    try:
        config = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"MCP_SERVERS is not valid JSON: {error}") from error

    if isinstance(config, dict) and "mcpServers" in config:
        config = config["mcpServers"]
    if not isinstance(config, dict):
        raise ValueError("MCP_SERVERS must be a JSON object")

    for name, server in config.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Every MCP server needs a non-empty name")
        if not isinstance(server, dict):
            raise ValueError(f"MCP server {name!r} must be an object")
        if not server.get("command") and not server.get("url"):
            raise ValueError(f"MCP server {name!r} needs 'command' or 'url'")
    return config


def _safe_name(value):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", value)


class MCPClient:
    """Keep MCP sessions open and translate their tools for Chat Completions."""

    def __init__(self, servers):
        self.servers = servers
        self._stack = AsyncExitStack()
        self._sessions = {}
        self._tool_routes = {}
        self.tools = []
        self.errors = []

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self._stack.aclose()

    async def connect(self):
        """Connect to every configured server and discover its tools."""
        for server_name, config in self.servers.items():
            server_stack = AsyncExitStack()
            try:
                session = await self._open_session(server_stack, config)
                await session.initialize()
                discovered_tools = []
                cursor = None
                while True:
                    response = await session.list_tools(cursor=cursor)
                    discovered_tools.extend(response.tools)
                    cursor = response.nextCursor
                    if not cursor:
                        break
                self._sessions[server_name] = session
                await self._stack.enter_async_context(server_stack)
                for tool in discovered_tools:
                    self._add_tool(server_name, tool)
            except Exception as error:
                await server_stack.aclose()
                self.errors.append(f"{server_name}: {error}")

    async def _open_session(self, stack, config):
        # Imports stay lazy so the agent still runs without the MCP dependency
        # when MCP_SERVERS is not configured.
        from mcp import ClientSession, StdioServerParameters

        if config.get("command"):
            from mcp.client.stdio import stdio_client

            params = StdioServerParameters(
                command=config["command"],
                args=config.get("args", []),
                env=config.get("env"),
            )
            read, write = await stack.enter_async_context(stdio_client(params))
        else:
            from mcp.client.streamable_http import streamable_http_client

            read, write, _ = await stack.enter_async_context(
                streamable_http_client(config["url"])
            )

        return await stack.enter_async_context(ClientSession(read, write))

    def _add_tool(self, server_name, tool):
        base_name = f"mcp__{_safe_name(server_name)}__{_safe_name(tool.name)}"
        public_name = base_name
        suffix = 2
        while public_name in self._tool_routes:
            public_name = f"{base_name}_{suffix}"
            suffix += 1

        self._tool_routes[public_name] = (server_name, tool.name)
        self.tools.append(
            {
                "type": "function",
                "function": {
                    "name": public_name,
                    "description": tool.description or f"MCP tool {tool.name}",
                    "parameters": tool.inputSchema,
                },
            }
        )

    def has_tool(self, name):
        return name in self._tool_routes

    async def call_tool(self, name, arguments):
        """Call a namespaced MCP tool and return a JSON string to the model."""
        if name not in self._tool_routes:
            return _error_result("unknown_mcp_tool", f"Unknown MCP tool: {name}")

        try:
            parsed = json.loads(arguments or "{}")
            if not isinstance(parsed, dict):
                raise ValueError("Tool arguments must be a JSON object")
        except (json.JSONDecodeError, ValueError) as error:
            return _error_result("invalid_arguments", str(error))

        server_name, original_name = self._tool_routes[name]
        try:
            result = await self._sessions[server_name].call_tool(
                original_name, arguments=parsed
            )
            payload = result.model_dump(
                mode="json", by_alias=True, exclude_none=True
            )
            return json.dumps(payload, ensure_ascii=False)
        except Exception as error:
            return _error_result("mcp_call_failed", str(error))


def _error_result(code, message):
    return json.dumps(
        {"ok": False, "error": code, "message": message},
        ensure_ascii=False,
    )
