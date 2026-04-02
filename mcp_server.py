"""
MCP Server for IICS dbt Generation
----------------------------------
This file implements the Model Context Protocol (MCP). It acts as a bridge between 
an AI IDE (like Cursor) and our Python fetch logic.

ARCHITECTURE:
- Server Name: 'iics-fetch-server'
- Standard: JSON-RPC over Standard Input/Output (stdio).
- Linkage: Imports `test_iics_fetch_3.py` to perform the actual work.

LLM INSTRUCTION: Register this server in your settings to gain the `get_iics_prompt` tool.
"""
import asyncio
import sys
import os

# Debug logging for paths to see exactly where Cursor is running from
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
print(f"[BOOTSTRAP] MCP Server running from: {SCRIPT_DIR}", file=sys.stderr)
print(f"[BOOTSTRAP] Current Working Directory: {os.getcwd()}", file=sys.stderr)

# Ensure the current directory is in sys.path
if SCRIPT_DIR not in sys.path:
    sys.path.append(SCRIPT_DIR)

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
import test_iics_fetch_3

server = Server("iics-fetch-server")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    Exposes tools to the AI. Cursor reads this to know what 'capabilities' we have.
    """
    return [
        types.Tool(
            name="get_iics_prompt",
            description=(
                "Fetches IICS mapping logic and connection details. "
                "Returns a string containing a complete set of instructions and data "
                "for generating dbt models in Snowflake."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "mapping_name": {"type": "string", "description": "Name of the IICS mapping to fetch"}
                },
                "required": ["mapping_name"],
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls."""
    if name == "get_iics_prompt":
        mapping_name = arguments.get("mapping_name")
        if not mapping_name:
            return [types.TextContent(type="text", text="Error: mapping_name is required.")]
        
        # Run the synchronous fetch logic
        prompt = test_iics_fetch_3.get_iics_mapping_prompt(mapping_name)
        
        return [types.TextContent(type="text", text=prompt)]
    
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="iics-fetch-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
