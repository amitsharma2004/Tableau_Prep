"""Tests for MCP Protocol, JSON-RPC Request Handling, and Tool Executions."""
import json
import pytest

from app.mcp.server import handle_mcp_request, TOOL_DEFINITIONS


def test_mcp_initialize():
    req = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "initialize",
        "params": {},
    }
    resp = handle_mcp_request(req)
    assert resp["id"] == "1"
    assert resp["result"]["serverInfo"]["name"] == "tableau-prep-mcp"


def test_mcp_tools_list():
    req = {
        "jsonrpc": "2.0",
        "id": "2",
        "method": "tools/list",
    }
    resp = handle_mcp_request(req)
    tool_names = [t["name"] for t in resp["result"]["tools"]]
    assert "get_catalog_schema" in tool_names
    assert "inspect_table_profile" in tool_names
    assert "validate_flow_plan" in tool_names
    assert "dry_run_flow" in tool_names
    assert "commit_flow_checkpoint" in tool_names


def test_mcp_validate_flow_plan_with_invalid_plan():
    invalid_plan = {
        "summary": "Invalid DAG test",
        "sources": [{"alias": "orders", "schema_name": "public", "table_name": "orders"}],
        "steps": [
            {
                "type": "filter",
                "target": "missing_alias",  # broken dependency
                "output_alias": "filtered",
                "conditions": [{"column": "status", "operator": "=", "value": "Completed"}],
            }
        ],
        "output_alias": "filtered",
    }
    req = {
        "jsonrpc": "2.0",
        "id": "3",
        "method": "tools/call",
        "params": {
            "name": "validate_flow_plan",
            "arguments": {"plan_data": invalid_plan},
        },
    }
    resp = handle_mcp_request(req)
    assert resp["id"] == "3"
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["is_valid"] is False
    assert "missing_alias" in content["error_message"]
    assert "repair_feedback" in content


def test_mcp_tools_list_includes_get_active_flow_plan():
    req = {
        "jsonrpc": "2.0",
        "id": "4",
        "method": "tools/list",
    }
    resp = handle_mcp_request(req)
    tool_names = [t["name"] for t in resp["result"]["tools"]]
    assert "get_active_flow_plan" in tool_names
