"""
Built-in tools for voice agents.

Provides sample tools that demonstrate the function-calling framework:
- get_current_time: Returns current date/time in a specified timezone
- get_weather: Returns mock weather data for a city
- calculator: Evaluates simple math expressions
"""

from __future__ import annotations

import datetime
import math
import re
from typing import Any
from zoneinfo import ZoneInfo

from app.services.tools.base import BaseTool, ToolResult


class GetCurrentTimeTool(BaseTool):
    """Returns the current date and time."""

    name = "get_current_time"
    description = (
        "Get the current date and time. Optionally specify a timezone "
        "(e.g. 'America/New_York', 'Europe/London', 'Asia/Tokyo'). "
        "Defaults to UTC."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "IANA timezone name (e.g. 'America/New_York'). Defaults to UTC.",
            }
        },
        "required": [],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        tz_name = kwargs.get("timezone", "UTC")
        try:
            tz = ZoneInfo(tz_name)
        except (KeyError, Exception):
            tz = ZoneInfo("UTC")
            tz_name = "UTC"

        now = datetime.datetime.now(tz)
        formatted = now.strftime("%A, %B %d, %Y at %I:%M %p %Z")
        return ToolResult(
            output=f"The current time in {tz_name} is {formatted}.",
            data={"timezone": tz_name, "iso": now.isoformat()},
        )


class GetWeatherTool(BaseTool):
    """Returns mock weather data for a given city."""

    name = "get_weather"
    description = (
        "Get the current weather for a city. Returns temperature, "
        "conditions, humidity, and wind speed. This is simulated data "
        "for demonstration purposes."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "The city name (e.g. 'San Francisco', 'London', 'Tokyo')",
            },
            "unit": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"],
                "description": "Temperature unit. Defaults to celsius.",
            },
        },
        "required": ["city"],
    }

    # Mock weather data keyed by normalized city name
    _MOCK_DATA: dict[str, dict[str, Any]] = {
        "san francisco": {"temp_c": 16, "condition": "Foggy", "humidity": 78, "wind_kmh": 22},
        "new york": {"temp_c": 22, "condition": "Partly Cloudy", "humidity": 55, "wind_kmh": 15},
        "london": {"temp_c": 14, "condition": "Rainy", "humidity": 85, "wind_kmh": 18},
        "tokyo": {"temp_c": 28, "condition": "Sunny", "humidity": 65, "wind_kmh": 10},
        "paris": {"temp_c": 19, "condition": "Clear", "humidity": 50, "wind_kmh": 12},
        "sydney": {"temp_c": 21, "condition": "Sunny", "humidity": 60, "wind_kmh": 20},
        "berlin": {"temp_c": 17, "condition": "Overcast", "humidity": 70, "wind_kmh": 14},
        "mumbai": {"temp_c": 32, "condition": "Humid", "humidity": 90, "wind_kmh": 8},
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        city = kwargs.get("city", "Unknown")
        unit = kwargs.get("unit", "celsius")

        key = city.lower().strip()
        data = self._MOCK_DATA.get(key)
        if not data:
            # Generate pseudo-random but deterministic weather
            seed = sum(ord(c) for c in key)
            temp_c = 10 + (seed % 25)
            conditions = ["Sunny", "Cloudy", "Rainy", "Partly Cloudy", "Clear", "Windy"]
            data = {
                "temp_c": temp_c,
                "condition": conditions[seed % len(conditions)],
                "humidity": 40 + (seed % 50),
                "wind_kmh": 5 + (seed % 30),
            }

        temp_c = data["temp_c"]
        if unit == "fahrenheit":
            temp = round(temp_c * 9 / 5 + 32)
            temp_str = f"{temp}°F"
        else:
            temp = temp_c
            temp_str = f"{temp}°C"

        output = (
            f"Weather in {city}: {data['condition']}, {temp_str}, "
            f"humidity {data['humidity']}%, wind {data['wind_kmh']} km/h."
        )
        return ToolResult(
            output=output,
            data={
                "city": city,
                "temperature": temp,
                "unit": unit,
                "condition": data["condition"],
                "humidity": data["humidity"],
                "wind_kmh": data["wind_kmh"],
            },
        )


class CalculatorTool(BaseTool):
    """Evaluates simple math expressions safely."""

    name = "calculator"
    description = (
        "Evaluate a mathematical expression. Supports basic arithmetic "
        "(+, -, *, /, **), parentheses, and common math functions "
        "(sqrt, sin, cos, tan, log, abs, round, pi, e). "
        "Examples: '2+2', 'sqrt(144)', '3.14 * 5**2'"
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "The math expression to evaluate (e.g. '2+2', 'sqrt(144)')",
            }
        },
        "required": ["expression"],
    }

    # Whitelist of allowed names in eval
    _SAFE_NAMES: dict[str, Any] = {
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "log2": math.log2,
        "abs": abs,
        "round": round,
        "pow": pow,
        "pi": math.pi,
        "e": math.e,
        "inf": float("inf"),
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        expr = kwargs.get("expression", "")

        # Sanitize: only allow math-safe characters
        if not re.match(r'^[\d\s\+\-\*/\.\(\)\,\^a-zA-Z_]+$', expr):
            return ToolResult(
                output=f"Invalid expression: {expr}",
                success=False,
            )

        # Replace ^ with ** for exponentiation
        expr_clean = expr.replace("^", "**")

        try:
            result = eval(expr_clean, {"__builtins__": {}}, self._SAFE_NAMES)
            # Format nicely
            if isinstance(result, float):
                if result == int(result) and not math.isinf(result):
                    result = int(result)
                else:
                    result = round(result, 6)
            return ToolResult(
                output=f"The result of {expr} is {result}.",
                data={"expression": expr, "result": result},
            )
        except ZeroDivisionError:
            return ToolResult(output="Error: Division by zero.", success=False)
        except Exception as e:
            return ToolResult(output=f"Error evaluating '{expr}': {e}", success=False)


def register_builtin_tools() -> None:
    """Register all built-in tools in the global registry."""
    from app.services.tools.registry import tool_registry

    tool_registry.register(GetCurrentTimeTool())
    tool_registry.register(GetWeatherTool())
    tool_registry.register(CalculatorTool())
