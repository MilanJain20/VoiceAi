"""
Tool registry — manages available tools for voice agents.

Tools are registered globally. Agents can opt-in to specific tools
via their AgentConfig.tools list (tool names). An empty list = all tools.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.services.tools.base import BaseTool  # noqa: TC001

logger = get_logger(__name__)


class ToolRegistry:
    """Central registry for all available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool
        logger.info("tool_registered", tool_name=tool.name)

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_tools(self, names: list[str] | None = None) -> list[BaseTool]:
        """
        Get tools by name list.
        If names is None or empty, returns ALL tools.
        """
        if names is None:
            return list(self._tools.values())
        return [t for n in names if (t := self._tools.get(n)) is not None]

    def get_openai_functions(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        """Get OpenAI function-calling specs for a set of tools."""
        return [t.to_openai_function() for t in self.get_tools(names)]

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    @property
    def count(self) -> int:
        return len(self._tools)


# Global singleton
tool_registry = ToolRegistry()
