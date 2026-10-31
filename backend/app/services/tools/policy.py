"""Which tools a voice agent is allowed to run.

An empty enabled_tools list allows nothing. Pass allow_all=true to expose
every registered tool. The executor checks this again at call time so a
model cannot invoke a tool that was not bound.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolPolicy:
    allow_all: bool = False
    enabled: frozenset[str] = frozenset()

    def allows(self, name: str) -> bool:
        if self.allow_all:
            return True
        return name in self.enabled

    @property
    def names_or_none(self) -> list[str] | None:
        """None means every tool. An empty list means no tools."""
        if self.allow_all:
            return None
        return sorted(self.enabled)


def policy_from_config(
    tools_config: dict | None = None,
    explicit_names: list[str] | None = None,
    *,
    allow_all_flag: bool = False,
) -> ToolPolicy:
    cfg = tools_config or {}
    if allow_all_flag or cfg.get("allow_all") is True:
        return ToolPolicy(allow_all=True)
    enabled = cfg.get("enabled_tools")
    if enabled is None:
        enabled = explicit_names or []
    return ToolPolicy(allow_all=False, enabled=frozenset(enabled))
