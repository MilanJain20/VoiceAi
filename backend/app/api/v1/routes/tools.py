"""
Tools REST API — list and inspect available tools.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.services.tools import tool_registry

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("")
async def list_tools():
    """List all registered tools."""
    tools = tool_registry.get_tools()
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters_schema,
            }
            for t in tools
        ],
        "count": len(tools),
    }


@router.get("/{tool_name}")
async def get_tool(tool_name: str):
    """Get details for a specific tool."""
    tool = tool_registry.get(tool_name)
    if tool is None:
        return {"error": f"Tool '{tool_name}' not found"}
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.parameters_schema,
    }
