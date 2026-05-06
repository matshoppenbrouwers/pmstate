"""Schema evolution via upcasters: transform old event shapes to current ones at read time."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Upcaster = Callable[[dict[str, Any]], dict[str, Any]]


class UpcastCycleError(RuntimeError):
    """Raised when upcasting loops through a previously-seen ``type``."""

    def __init__(self, chain: list[str]) -> None:
        super().__init__(f"upcaster cycle detected: {' -> '.join(chain)}")
        self.chain = chain


class UpcasterRegistry:
    """Registry mapping legacy event types to upcaster functions."""

    def __init__(self) -> None:
        self._upcasters: dict[str, Upcaster] = {}

    def register(self, from_type: str, fn: Upcaster) -> None:
        """Register ``fn`` to transform events with ``type == from_type``."""
        if from_type in self._upcasters:
            raise ValueError(f"upcaster already registered for {from_type!r}")
        self._upcasters[from_type] = fn

    def upcast(self, event_dict: dict[str, Any]) -> dict[str, Any]:
        """Apply the chain of upcasters until no more match. Detects cycles."""
        seen: list[str] = []
        current = event_dict
        while True:
            current_type = current.get("type")
            if not isinstance(current_type, str):
                return current
            if current_type in seen:
                seen.append(current_type)
                raise UpcastCycleError(seen)
            fn = self._upcasters.get(current_type)
            if fn is None:
                return current
            seen.append(current_type)
            current = fn(current)


default_registry = UpcasterRegistry()
