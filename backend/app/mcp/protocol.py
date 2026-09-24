"""Standard MCP (Model Context Protocol) JSON-RPC schemas and tool specifications."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class MCPToolParameter(BaseModel):
    type: str = "object"
    properties: dict[str, Any]
    required: list[str] = []


class MCPToolDefinition(BaseModel):
    name: str
    description: str
    inputSchema: MCPToolParameter


class MCPRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Optional[str | int] = None
    method: str
    params: Optional[dict[str, Any]] = None


class MCPResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Optional[str | int] = None
    result: Optional[Any] = None
    error: Optional[dict[str, Any]] = None
