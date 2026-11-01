"""
Built-in tools for voice agents.

Provides sample tools that demonstrate the function-calling framework:
- get_current_time: Returns current date/time in a specified timezone
- get_weather: Returns mock weather data for a city
- calculator: Evaluates simple math expressions
"""

from __future__ import annotations

import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.services.tools.base import BaseTool, ToolResult
from app.services.tools.safe_eval import UnsafeExpressionError, safe_eval


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
    """Current weather from Open-Meteo. No API key. Fails closed on timeout."""

    name = "get_weather"
    description = (
        "Get the current weather for a city from Open-Meteo. "
        "Returns temperature, a weather code, and wind speed."
    )
    timeout_s = 8.0
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

    async def execute(self, **kwargs: Any) -> ToolResult:
        city = (kwargs.get("city") or "").strip()
        unit = kwargs.get("unit", "celsius")
        if not city:
            return ToolResult(output="A city name is required.", success=False)
        timeout = httpx.Timeout(getattr(self, "timeout_s", 8.0))
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                geo = await client.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": city, "count": 1},
                )
                geo.raise_for_status()
                results = geo.json().get("results") or []
                if not results:
                    return ToolResult(output=f"No location found for {city}.", success=False)
                loc = results[0]
                forecast = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": loc["latitude"],
                        "longitude": loc["longitude"],
                        "current": "temperature_2m,weather_code,wind_speed_10m",
                    },
                )
                forecast.raise_for_status()
                current = forecast.json().get("current") or {}
        except httpx.TimeoutException:
            return ToolResult(output=f"Weather lookup for {city} timed out.", success=False)
        except httpx.HTTPError as exc:
            return ToolResult(output=f"Weather lookup failed: {exc}", success=False)

        temp_c = current.get("temperature_2m")
        if temp_c is None:
            return ToolResult(
                output=f"Weather service returned no temperature for {city}.", success=False
            )
        if unit == "fahrenheit":
            temp = round(temp_c * 9 / 5 + 32)
            temp_str = f"{temp}°F"
        else:
            temp = temp_c
            temp_str = f"{temp}°C"
        place = loc.get("name", city)
        output = (
            f"Weather in {place}: {temp_str}, "
            f"weather code {current.get('weather_code')}, "
            f"wind {current.get('wind_speed_10m')} km/h. Source: Open-Meteo."
        )
        return ToolResult(
            output=output,
            data={
                "city": place,
                "temperature": temp,
                "unit": unit,
                "weather_code": current.get("weather_code"),
                "wind_kmh": current.get("wind_speed_10m"),
                "source": "open-meteo",
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

    async def execute(self, **kwargs: Any) -> ToolResult:
        expr = kwargs.get("expression", "")
        try:
            result = safe_eval(str(expr))
            if isinstance(result, float) and result == int(result):
                result = int(result)
            elif isinstance(result, float):
                result = round(result, 6)
            return ToolResult(
                output=f"The result of {expr} is {result}.",
                data={"expression": expr, "result": result},
            )
        except ZeroDivisionError:
            return ToolResult(output="Error: Division by zero.", success=False)
        except UnsafeExpressionError as exc:
            return ToolResult(output=f"Error evaluating '{expr}': {exc}", success=False)


def register_builtin_tools() -> None:
    """Register all built-in tools in the global registry."""
    from app.services.tools.registry import tool_registry

    tool_registry.register(GetCurrentTimeTool())
    tool_registry.register(GetWeatherTool())
    tool_registry.register(CalculatorTool())
