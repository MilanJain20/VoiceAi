"""
Base tool definition for voice agent function calling.

Every tool must inherit from BaseTool and implement execute().
The tool's schema is auto-generated from its Pydantic input model
and passed to the LLM via LangChain's bind_tools.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


class ToolResult:
    """Wrapper for a tool execution result."""

    def __init__(self, output: str, success: bool = True, data: dict[str, Any] | None = None):
        self.output = output
        self.success = success
        self.data = data or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "output": self.output,
            "success": self.success,
            **self.data,
        }


class BaseTool(abc.ABC):
    """
    Abstract base class for all voice-agent tools.

    Subclasses must define:
      - name: unique tool identifier
      - description: human-readable description for the LLM
      - parameters_schema: JSON-schema dict describing the parameters
      - execute(**kwargs) -> ToolResult
    """

    name: str = ""
    description: str = ""
    parameters_schema: dict[str, Any] = {}

    @abc.abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Run the tool with the given arguments and return a result."""
        ...

    def to_openai_function(self) -> dict[str, Any]:
        """
        Convert this tool to an OpenAI function-calling JSON spec.
        Compatible with LangChain's bind_tools format.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }
