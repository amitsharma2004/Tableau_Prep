"""Model Context Protocol (MCP) Server for Tableau AI Prep.
Runs as a JSON-RPC stdio or SSE server compatible with Cursor IDE, Claude Desktop, and Agentic frameworks.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from app.mcp import tools
from app.mcp.protocol import MCPRequest, MCPResponse, MCPToolDefinition, MCPToolParameter

TOOL_DEFINITIONS = [
    MCPToolDefinition(
        name="get_catalog_schema",
        description="Fetch database schema metadata (tables, columns, SQL types, nullability) with zero data leakage.",
        inputSchema=MCPToolParameter(
            properties={
                "connection_id": {"type": "string", "description": "Optional connection ID. Defaults to active source."}
            },
            required=[],
        ),
    ),
    MCPToolDefinition(
        name="inspect_table_profile",
        description="Inspect column profiles, distinct values, null counts, and sample metrics for a table.",
        inputSchema=MCPToolParameter(
            properties={
                "table_name": {"type": "string", "description": "Target table name"},
                "schema_name": {"type": "string", "description": "Schema name (e.g. public or main)", "default": "public"},
                "connection_id": {"type": "string", "description": "Optional connection ID"},
            },
            required=["table_name"],
        ),
    ),
    MCPToolDefinition(
        name="validate_flow_plan",
        description="Validate a proposed transformation plan against DAG topology, virtual column lineage, and compute AI confidence score.",
        inputSchema=MCPToolParameter(
            properties={
                "plan_data": {"type": "object", "description": "PlanDraft JSON containing sources, steps, output_alias, summary"},
                "connection_id": {"type": "string", "description": "Optional connection ID"},
            },
            required=["plan_data"],
        ),
    ),
    MCPToolDefinition(
        name="dry_run_flow",
        description="In-database pushdown dry-run: compiles plan into CTE SQL and executes limited preview on source DB with zero local CPU load.",
        inputSchema=MCPToolParameter(
            properties={
                "plan_data": {"type": "object", "description": "PlanDraft JSON"},
                "limit": {"type": "integer", "description": "Number of preview rows to fetch", "default": 10},
                "connection_id": {"type": "string", "description": "Optional connection ID"},
            },
            required=["plan_data"],
        ),
    ),
    MCPToolDefinition(
        name="commit_flow_checkpoint",
        description="Persist validated plan as a new immutable checkpoint (PlanVersion) and return direct interactive Studio canvas URL.",
        inputSchema=MCPToolParameter(
            properties={
                "plan_data": {"type": "object", "description": "PlanDraft JSON"},
                "flow_id": {"type": "string", "description": "Optional flow ID to append checkpoint to"},
                "connection_id": {"type": "string", "description": "Optional database connection ID"},
                "change_summary": {"type": "string", "description": "Brief changelog summary for this checkpoint"},
            },
            required=["plan_data"],
        ),
    ),
    MCPToolDefinition(
        name="get_active_flow_plan",
        description="Retrieve the current active transformation plan JSON for an existing flow so you can inspect, follow up, and refine it.",
        inputSchema=MCPToolParameter(
            properties={
                "flow_id": {"type": "string", "description": "Flow ID to retrieve"},
            },
            required=["flow_id"],
        ),
    ),
]


def handle_mcp_request(req_dict: dict[str, Any]) -> dict[str, Any]:
    """Processes an incoming MCP JSON-RPC 2.0 request."""
    req_id = req_dict.get("id")
    method = req_dict.get("method")
    params = req_dict.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "tableau-prep-mcp", "version": "1.0.0"},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [t.model_dump() for t in TOOL_DEFINITIONS],
            },
        }

    if method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments") or {}

        try:
            if tool_name == "get_catalog_schema":
                output = tools.get_catalog_schema(**args)
            elif tool_name == "inspect_table_profile":
                output = tools.inspect_table_profile(**args)
            elif tool_name == "validate_flow_plan":
                output = tools.validate_flow_plan(**args)
            elif tool_name == "dry_run_flow":
                output = tools.dry_run_flow(**args)
            elif tool_name == "commit_flow_checkpoint":
                output = tools.commit_flow_checkpoint(**args)
            elif tool_name == "get_active_flow_plan":
                output = tools.get_active_flow_plan(**args)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method/Tool '{tool_name}' not found"},
                }

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(output, indent=2)}],
                    "isError": False,
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error executing tool {tool_name}: {exc}"}],
                    "isError": True,
                },
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method '{method}'"},
    }


def run_stdio_server():
    """Runs standard input/output JSON-RPC loop for Cursor and Claude Desktop."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req_data = json.loads(line)
            response = handle_mcp_request(req_data)
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except Exception as err:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {err}"},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run_stdio_server()
