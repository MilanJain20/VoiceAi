"""Tool policy, the AST calculator, and executor re-checks."""

import pytest

from app.services.tools.builtin import CalculatorTool
from app.services.tools.policy import ToolPolicy, policy_from_config
from app.services.tools.safe_eval import UnsafeExpressionError, safe_eval


def test_empty_list_allows_nothing() -> None:
    policy = policy_from_config({"enabled_tools": [], "allow_all": False})
    assert policy.allows("calculator") is False
    assert policy.names_or_none == []


def test_allow_all_flag() -> None:
    policy = policy_from_config({"enabled_tools": []}, allow_all_flag=True)
    assert policy.allows("get_weather") is True
    assert policy.names_or_none is None


def test_named_allow_list() -> None:
    policy = ToolPolicy(allow_all=False, enabled=frozenset({"calculator"}))
    assert policy.allows("calculator") is True
    assert policy.allows("get_weather") is False


def test_safe_eval_arithmetic() -> None:
    assert safe_eval("2+2") == 4
    assert safe_eval("sqrt(144)") == 12
    assert safe_eval("3^2") == 9


def test_safe_eval_rejects_calls_and_attributes() -> None:
    with pytest.raises(UnsafeExpressionError):
        safe_eval("__import__('os').system('echo hi')")
    with pytest.raises(UnsafeExpressionError):
        safe_eval("().__class__")


@pytest.mark.asyncio
async def test_calculator_tool_uses_safe_eval() -> None:
    tool = CalculatorTool()
    ok = await tool.execute(expression="2+2")
    assert ok.success is True
    assert "4" in ok.output
    blocked = await tool.execute(expression="__import__('os')")
    assert blocked.success is False
